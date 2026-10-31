param(
    [Parameter(Mandatory = $true)][string]$ControlDirectory,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{32}$')][string]$HostId
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'HostCommon.ps1')

$HostStateFile = Join-Path $ControlDirectory 'collector-host.json'
$HostReadyFile = Join-Path $ControlDirectory 'collector-host.ready'
$HostErrorFile = Join-Path $ControlDirectory 'collector-host.error.log'
$RequestFile = Join-Path $ControlDirectory 'collector-request.json'
$ShutdownFile = Join-Path $ControlDirectory 'collector-host.shutdown'
$HostExecutablePath = [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
$ProcessStartTicks = [Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime().Ticks
$Mutex = New-Object Threading.Mutex($false, (Get-CollectorHostMutexName -ControlDirectory $ControlDirectory))
$MutexAcquired = $false
$NormalShutdown = $false
$HostState = $null

function Save-HostState {
    $script:HostState.LastTransitionTime = (Get-Date).ToString('o')
    Write-JsonAtomic -Value $script:HostState -Path $HostStateFile
}

function Publish-HostReady {
    Write-JsonAtomic -Value ([PSCustomObject]@{
        Scheme='PersistentCollectorHostReadyV2'; HostId=$HostId; ProcessId=$PID
        ProcessStartTimeUtcTicks=$ProcessStartTicks; Status=$HostState.Status
        Time=(Get-Date).ToString('o')
    }) -Path $HostReadyFile
}

New-Item -ItemType Directory -Path $ControlDirectory -Force | Out-Null
try {
    try { $MutexAcquired = $Mutex.WaitOne(0, $false) }
    catch [Threading.AbandonedMutexException] { $MutexAcquired = $true }
    if (-not $MutexAcquired) {
        Set-Content -LiteralPath $HostErrorFile -Value 'Another CollectorHost owns the control-directory mutex. Duplicate host was not started.' -Encoding UTF8
        exit 12
    }

    Remove-Item -LiteralPath $HostReadyFile, $HostErrorFile, $ShutdownFile -Force -ErrorAction SilentlyContinue
    $HostState = [PSCustomObject]@{
        Scheme='PersistentCollectorHostV2'; HostId=$HostId; ProcessId=$PID
        ProcessStartTimeUtcTicks=$ProcessStartTicks; HostExecutablePath=$HostExecutablePath
        ControlDirectory=[IO.Path]::GetFullPath($ControlDirectory); StartTime=(Get-Date).ToString('o')
        Status='Ready'; ActiveRunId=$null; LastTransitionTime=(Get-Date).ToString('o'); LastError=$null
    }
    Save-HostState
    Publish-HostReady

    while ($true) {
        if (Test-Path -LiteralPath $ShutdownFile -PathType Leaf) {
            $Shutdown = Get-Content -LiteralPath $ShutdownFile -Raw | ConvertFrom-Json
            if ([string]$Shutdown.HostId -ne $HostId) { throw 'Shutdown HostId does not match this CollectorHost.' }
            $NormalShutdown = $true
            break
        }

        if (-not (Test-CollectorHostReadyIdentity -ReadyFile $HostReadyFile -HostState $HostState)) { Publish-HostReady }
        if (-not (Test-Path -LiteralPath $RequestFile -PathType Leaf)) {
            Start-Sleep -Milliseconds 100
            continue
        }

        $Request = $null
        $CollectorPowerShell = $null
        $AsyncResult = $null
        $StopWasRequested = $false
        $RunStatus = 'Failed'
        $RunError = $null
        $RunStartTime = Get-Date

        try {
            $Request = Get-Content -LiteralPath $RequestFile -Raw | ConvertFrom-Json
            if ([string]$Request.HostId -ne $HostId) { throw 'Request HostId does not match this CollectorHost.' }
            if ([string]::IsNullOrWhiteSpace([string]$Request.RunId)) { throw 'Request RunId is missing.' }
            Remove-Item -LiteralPath $RequestFile -Force
            foreach ($RequiredProperty in 'CounterFile','BlgPath','ReadyFile','StopFile','CompletedFile','ErrorFile','SampleInterval') {
                if (-not $Request.PSObject.Properties[$RequiredProperty]) { throw "Request property is missing: $RequiredProperty" }
            }

            $HostState.Status = 'Collecting'
            $HostState.ActiveRunId = [string]$Request.RunId
            $HostState.LastError = $null
            Save-HostState
            Publish-HostReady

            $Counters = @(Get-Content -LiteralPath $Request.CounterFile | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') })
            if ($Counters.Count -eq 0) { throw 'No usable counters were found.' }
            # RunId固有のStop要求は、Start側の早期失敗で既に作成されている可能性があるため削除しない。
            Remove-Item -LiteralPath $Request.ReadyFile, $Request.CompletedFile, $Request.ErrorFile -Force -ErrorAction SilentlyContinue

            $CollectorScript = @'
param([string[]]$Counters,[string]$BlgPath,[string]$ReadyFile,[int]$SampleInterval,[string]$RunId)
$ErrorActionPreference='Stop'
$ReadySent=$false
Get-Counter -Counter $Counters -SampleInterval $SampleInterval -Continuous -ErrorAction Stop |
    ForEach-Object {
        if(-not $ReadySent){
            $Ready=[pscustomobject]@{Scheme='CollectorRunReadyV2';RunId=$RunId;Time=(Get-Date).ToString('o')}
            $Temp="$ReadyFile.tmp-$PID"
            $Ready|ConvertTo-Json|Set-Content -LiteralPath $Temp -Encoding UTF8
            if(Test-Path -LiteralPath $ReadyFile){[IO.File]::Replace($Temp,$ReadyFile,$null)}else{[IO.File]::Move($Temp,$ReadyFile)}
            $ReadySent=$true
        }
        $_
    } |
    Export-Counter -Path $BlgPath -FileFormat BLG -Force -ErrorAction Stop
'@
            $CollectorPowerShell = [PowerShell]::Create()
            [void]$CollectorPowerShell.AddScript($CollectorScript).
                AddArgument([string[]]$Counters).
                AddArgument([string]$Request.BlgPath).
                AddArgument([string]$Request.ReadyFile).
                AddArgument([int]$Request.SampleInterval).
                AddArgument([string]$Request.RunId)
            $AsyncResult = $CollectorPowerShell.BeginInvoke()

            while ($true) {
                if ($AsyncResult.IsCompleted) {
                    [void]$CollectorPowerShell.EndInvoke($AsyncResult)
                    throw 'Collector pipeline stopped unexpectedly.'
                }
                if (Test-Path -LiteralPath $Request.StopFile -PathType Leaf) {
                    $StopRequest = Get-Content -LiteralPath $Request.StopFile -Raw | ConvertFrom-Json
                    if ([string]$StopRequest.RunId -ne [string]$Request.RunId) { throw 'Stop request RunId does not match the active run.' }
                    $StopWasRequested = $true
                    $RunStatus = 'Stopped'
                    break
                }
                Start-Sleep -Milliseconds 100
            }
        }
        catch {
            $RunError = $_.Exception.ToString()
            if ($null -ne $Request -and $Request.PSObject.Properties['ErrorFile']) {
                Set-Content -LiteralPath $Request.ErrorFile -Value $RunError -Encoding UTF8
            }
            else {
                Set-Content -LiteralPath $HostErrorFile -Value $RunError -Encoding UTF8
            }
        }
        finally {
            if ($null -ne $CollectorPowerShell) {
                if ($null -ne $AsyncResult -and -not $AsyncResult.IsCompleted) { $CollectorPowerShell.Stop() }
                if ($null -ne $AsyncResult) {
                    try { [void]$CollectorPowerShell.EndInvoke($AsyncResult) }
                    catch [Management.Automation.PipelineStoppedException] { if (-not $StopWasRequested) { $RunError = $_.Exception.ToString(); $RunStatus='Failed' } }
                    catch { $RunError = $_.Exception.ToString(); $RunStatus='Failed' }
                }
                $CollectorPowerShell.Dispose()
            }
        }

        if ($null -ne $Request -and $Request.PSObject.Properties['CompletedFile']) {
            if ($RunError) { Set-Content -LiteralPath $Request.ErrorFile -Value $RunError -Encoding UTF8 }
            Write-JsonAtomic -Value ([PSCustomObject]@{
                Scheme='CollectorRunCompletionV2'; RunId=[string]$Request.RunId; HostId=$HostId
                Status=$RunStatus; StartTime=$RunStartTime.ToString('o'); EndTime=(Get-Date).ToString('o'); Error=$RunError
            }) -Path $Request.CompletedFile
        }

        $HostState.Status = 'Ready'
        $HostState.ActiveRunId = $null
        $HostState.LastError = $RunError
        Save-HostState
        Publish-HostReady
    }
}
catch {
    $Failure = $_.Exception.ToString()
    Set-Content -LiteralPath $HostErrorFile -Value $Failure -Encoding UTF8
    if ($null -ne $HostState) {
        $HostState.Status = 'Faulted'
        $HostState.LastError = $Failure
        Save-HostState
    }
}
finally {
    if ($MutexAcquired) {
        Remove-Item -LiteralPath $HostReadyFile, $ShutdownFile -Force -ErrorAction SilentlyContinue
    }
    if ($NormalShutdown -and $null -ne $HostState) {
        $HostState.Status = 'Stopped'
        $HostState.ActiveRunId = $null
        Save-HostState
        Write-JsonAtomic -Value $HostState -Path (Join-Path $ControlDirectory ("collector-host-{0}.final.json" -f $HostId))
        Remove-Item -LiteralPath $HostStateFile -Force -ErrorAction SilentlyContinue
    }
    if ($MutexAcquired) { $Mutex.ReleaseMutex() }
    $Mutex.Dispose()
}
