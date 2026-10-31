$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'HostCommon.ps1')

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDirectory = Join-Path $ProjectRoot 'logs'
$HostScript = Join-Path $PSScriptRoot 'CollectorHost.ps1'
$HostStateFile = Join-Path $LogDirectory 'collector-host.json'
$HostReadyFile = Join-Path $LogDirectory 'collector-host.ready'
$HostErrorFile = Join-Path $LogDirectory 'collector-host.error.log'
$HostStdout = Join-Path $LogDirectory 'collector-host.stdout.log'
$HostStderr = Join-Path $LogDirectory 'collector-host.stderr.log'
$WindowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Read-HostState {
    if (-not (Test-Path -LiteralPath $HostStateFile -PathType Leaf)) { return $null }
    try { return (Get-Content -LiteralPath $HostStateFile -Raw | ConvertFrom-Json) }
    catch { throw "Collector host state is unreadable. No new host was started: $($_.Exception.Message)" }
}

function Wait-ForMatchingReady {
    param([object]$HostState, [int]$Seconds)
    $Deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $Deadline) {
        if (Test-CollectorHostReadyIdentity -ReadyFile $HostReadyFile -HostState $HostState) { return $true }
        $Identity = Get-CollectorHostIdentityResult -HostState $HostState -ExpectedExecutablePath $WindowsPowerShell
        if (-not $Identity.IsValid) { return $false }
        Start-Sleep -Milliseconds 100
    }
    return $false
}

New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$ExistingState = Read-HostState
if ($null -ne $ExistingState) {
    $Identity = Get-CollectorHostIdentityResult -HostState $ExistingState -ExpectedExecutablePath $WindowsPowerShell
    if ($Identity.IsValid) {
        if (-not (Wait-ForMatchingReady -HostState $ExistingState -Seconds 3)) {
            throw "CollectorHost is alive and identity-matched, but Ready was not restored. Duplicate host was not started. HostId: $($ExistingState.HostId)"
        }
        [PSCustomObject]@{
            Result='AlreadyRunning'; ProcessId=[int]$ExistingState.ProcessId; HostId=[string]$ExistingState.HostId
            ProcessStartTimeUtcTicks=[Int64]$ExistingState.ProcessStartTimeUtcTicks; StateFile=$HostStateFile
        }
        return
    }

    if (Test-CollectorHostMutexHeld -ControlDirectory $LogDirectory) {
        throw "CollectorHost mutex is held while its state is inconsistent. Duplicate host was not started. Reason: $($Identity.Reason)"
    }

    $StalePath = Join-Path $LogDirectory ("collector-host-stale-{0}-{1}.json" -f (Get-Date).ToString('yyyyMMdd_HHmmssfff'), [Guid]::NewGuid().ToString('N').Substring(0,8))
    Move-Item -LiteralPath $HostStateFile -Destination $StalePath
    Remove-Item -LiteralPath $HostReadyFile -Force -ErrorAction SilentlyContinue
}
elseif (Test-CollectorHostMutexHeld -ControlDirectory $LogDirectory) {
    throw 'CollectorHost mutex is held but the host state file is missing. Duplicate host was not started.'
}

Remove-Item -LiteralPath $HostReadyFile, $HostErrorFile, $HostStdout, $HostStderr -Force -ErrorAction SilentlyContinue
$NewHostId = [Guid]::NewGuid().ToString('N')
$Arguments = @(
    '-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
    '-File', ('"{0}"' -f $HostScript),
    '-ControlDirectory', ('"{0}"' -f $LogDirectory),
    '-HostId', $NewHostId
) -join ' '
$LaunchedProcess = Start-Process -FilePath $WindowsPowerShell -ArgumentList $Arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $HostStdout -RedirectStandardError $HostStderr
$Deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $Deadline) {
    $LaunchedProcess.Refresh()
    if ($LaunchedProcess.HasExited) {
        $Detail = if (Test-Path -LiteralPath $HostErrorFile) { Get-Content -LiteralPath $HostErrorFile -Raw } elseif (Test-Path -LiteralPath $HostStderr) { Get-Content -LiteralPath $HostStderr -Raw } else { '' }
        throw "CollectorHost exited during startup. ExitCode: $($LaunchedProcess.ExitCode). $Detail"
    }

    $StartedState = Read-HostState
    if ($null -ne $StartedState -and [string]$StartedState.HostId -eq $NewHostId -and [int]$StartedState.ProcessId -eq $LaunchedProcess.Id) {
        $Identity = Get-CollectorHostIdentityResult -HostState $StartedState -ExpectedExecutablePath $WindowsPowerShell
        if ($Identity.IsValid -and (Test-CollectorHostReadyIdentity -ReadyFile $HostReadyFile -HostState $StartedState)) {
            [PSCustomObject]@{
                Result='Started'; ProcessId=$LaunchedProcess.Id; HostId=$NewHostId
                ProcessStartTimeUtcTicks=[Int64]$StartedState.ProcessStartTimeUtcTicks; StateFile=$HostStateFile
            }
            return
        }
    }
    Start-Sleep -Milliseconds 100
}

throw "Timed out while starting CollectorHost. The process was not forcibly terminated; HostId $NewHostId and diagnostic files were preserved."
