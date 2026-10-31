$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'HostCommon.ps1')

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDirectory = Join-Path $ProjectRoot 'logs'
$StateFile = Join-Path $LogDirectory 'collection-state.json'
$HostStateFile = Join-Path $LogDirectory 'collector-host.json'
$ConvertScript = Join-Path $PSScriptRoot 'Convert-PerformanceLog.ps1'
$WindowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $StateFile -PathType Leaf)) { throw "Collection state file not found: $StateFile" }

$State = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
if ($State.Scheme -ne 'PersistentCollectorRunV2') { throw 'Invalid collection state. No process or Host was changed.' }
if (-not (Test-Path -LiteralPath $HostStateFile -PathType Leaf)) {
    $State.Status='HostStateMissingDuringStop';$State.LastError='CollectorHost state file is missing.';$State.LastTransitionTime=(Get-Date).ToString('o')
    Write-JsonAtomic -Value $State -Path $StateFile; Write-TerminalRunState -State $State -LogDirectory $LogDirectory | Out-Null
    throw 'CollectorHost state is missing. Run state and artifacts were preserved.'
}

$HostState = Get-Content -LiteralPath $HostStateFile -Raw | ConvertFrom-Json
$HostIdentity = Get-CollectorHostIdentityResult -HostState $HostState -ExpectedExecutablePath $WindowsPowerShell
$HostMatchesRun = (
    $HostIdentity.IsValid -and
    [string]$HostState.HostId -eq [string]$State.HostId -and
    [int]$HostState.ProcessId -eq [int]$State.WorkerProcessId -and
    [Int64]$HostState.ProcessStartTimeUtcTicks -eq [Int64]$State.HostProcessStartTimeUtcTicks
)
if (-not $HostMatchesRun) {
    $State.Status='HostIdentityMismatchDuringStop';$State.LastError="Host identity mismatch: $($HostIdentity.Reason)";$State.LastTransitionTime=(Get-Date).ToString('o')
    Write-JsonAtomic -Value $State -Path $StateFile; Write-TerminalRunState -State $State -LogDirectory $LogDirectory | Out-Null
    throw 'CollectorHost identity does not match the active run. No process was stopped; state and artifacts were preserved.'
}

$State.Status='StopRequested';$State.LastTransitionTime=(Get-Date).ToString('o')
Write-JsonAtomic -Value $State -Path $StateFile
Write-JsonAtomic -Value ([PSCustomObject]@{Scheme='CollectorRunStopV2';HostId=$State.HostId;RunId=$State.RunId;Reason='UserStop';Time=(Get-Date).ToString('o')}) -Path $State.StopFile

$Deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $Deadline -and -not (Test-Path -LiteralPath $State.CompletedFile -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath $HostStateFile -PathType Leaf)) {
        $State.Status='HostExitedDuringStop';$State.LastError='Host state disappeared while stopping.';$State.LastTransitionTime=(Get-Date).ToString('o')
        Write-JsonAtomic -Value $State -Path $StateFile; Write-TerminalRunState -State $State -LogDirectory $LogDirectory | Out-Null
        throw 'CollectorHost exited while stopping. State and artifacts were preserved.'
    }
    $CurrentHostState = Get-Content -LiteralPath $HostStateFile -Raw | ConvertFrom-Json
    $CurrentIdentity = Get-CollectorHostIdentityResult -HostState $CurrentHostState -ExpectedExecutablePath $WindowsPowerShell
    if (-not $CurrentIdentity.IsValid -or [string]$CurrentHostState.HostId -ne [string]$State.HostId) {
        $State.Status='HostIdentityLostDuringStop';$State.LastError="Host identity was lost: $($CurrentIdentity.Reason)";$State.LastTransitionTime=(Get-Date).ToString('o')
        Write-JsonAtomic -Value $State -Path $StateFile; Write-TerminalRunState -State $State -LogDirectory $LogDirectory | Out-Null
        throw 'CollectorHost identity was lost while stopping. State and artifacts were preserved.'
    }
    Start-Sleep -Milliseconds 100
}
if (-not (Test-Path -LiteralPath $State.CompletedFile -PathType Leaf)) {
    $State.Status='StopTimeout';$State.LastError='Timed out waiting for Host completion.';$State.LastTransitionTime=(Get-Date).ToString('o')
    Write-JsonAtomic -Value $State -Path $StateFile; Write-TerminalRunState -State $State -LogDirectory $LogDirectory | Out-Null
    throw 'Timed out while stopping collection. State and artifacts were preserved.'
}

$Completion = Get-Content -LiteralPath $State.CompletedFile -Raw | ConvertFrom-Json
if ($Completion.Scheme -ne 'CollectorRunCompletionV2' -or [string]$Completion.RunId -ne [string]$State.RunId -or [string]$Completion.HostId -ne [string]$State.HostId) {
    $State.Status='CompletionIdentityMismatch';$State.LastError='Completion identity did not match the active run.';$State.LastTransitionTime=(Get-Date).ToString('o')
    Write-JsonAtomic -Value $State -Path $StateFile; Write-TerminalRunState -State $State -LogDirectory $LogDirectory | Out-Null
    throw 'Host completion identity mismatch. State and artifacts were preserved.'
}
if ($Completion.Status -ne 'Stopped') {
    $State.Status='CollectorFailed';$State.LastError=[string]$Completion.Error;$State.HostCompletionStatus=[string]$Completion.Status;$State.LastTransitionTime=(Get-Date).ToString('o')
    Write-JsonAtomic -Value $State -Path $StateFile; Write-TerminalRunState -State $State -LogDirectory $LogDirectory | Out-Null
    throw 'Collector reported abnormal completion. State, error, BLG, and logs were preserved.'
}

try {
    if (-not (Test-Path -LiteralPath $State.BlgPath -PathType Leaf)) { throw "BLG file was not created: $($State.BlgPath)" }
    $EscapedBlg = ([string]$State.BlgPath).Replace("'", "''")
    $EscapedConverter = $ConvertScript.Replace("'", "''")
    $Command = @"
`$ErrorActionPreference='Stop'
`$ProgressPreference='SilentlyContinue'
`$Blg='$EscapedBlg'
`$Summary=Import-Counter -Path `$Blg -Summary
`$Count=@((Import-Counter -Path `$Blg -MaxSamples 1).CounterSamples).Count
`$Csv=[IO.Path]::ChangeExtension(`$Blg,'.csv')
if(Test-Path -LiteralPath `$Csv){`$Data=@(Import-Csv -LiteralPath `$Csv);if(`$Data.Count -eq 0){throw 'Existing CSV is empty.'};`$Conv=[pscustomobject]@{CsvPath=`$Csv;DataRows=`$Data.Count;ColumnCount=@(`$Data[0].PSObject.Properties).Count}}
else{`$Conv=& '$EscapedConverter' -BlgPath `$Blg}
[pscustomobject]@{SampleCount=`$Summary.SampleCount;CounterCount=`$Count;CsvPath=`$Conv.CsvPath;DataRows=`$Conv.DataRows;ColumnCount=`$Conv.ColumnCount}|ConvertTo-Json -Compress
"@
    $Encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
    $Json = & $WindowsPowerShell -NoLogo -NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand $Encoded
    if ($LASTEXITCODE -ne 0) { throw "BLG validation or CSV conversion failed with exit code $LASTEXITCODE." }
    $Result = ($Json | Out-String).Trim() | ConvertFrom-Json
    if ([int]$Result.CounterCount -ne [int]$State.CounterCount) { throw "Counter count mismatch. Expected $($State.CounterCount), actual $($Result.CounterCount)." }
    if ([int]$Result.DataRows -ne [int]$Result.SampleCount) { throw 'CSV row count does not match BLG sample count.' }
    if ([int]$Result.ColumnCount -ne ([int]$Result.CounterCount + 1)) { throw 'CSV column count does not match counter count plus timestamp.' }
}
catch {
    $State.Status='OutputValidationFailed';$State.LastError=$_.Exception.ToString();$State.LastTransitionTime=(Get-Date).ToString('o')
    Write-JsonAtomic -Value $State -Path $StateFile; Write-TerminalRunState -State $State -LogDirectory $LogDirectory | Out-Null
    throw
}

$StopTime = Get-Date
$State.Status='CompletedValidated';$State.LastError=$null;$State.HostCompletionStatus='Stopped';$State.StopTime=$StopTime.ToString('o')
$State.SampleCount=[int]$Result.SampleCount;$State.DataRows=[int]$Result.DataRows;$State.ColumnCount=[int]$Result.ColumnCount;$State.CsvPath=[string]$Result.CsvPath
$State.LastTransitionTime=(Get-Date).ToString('o')
Write-JsonAtomic -Value $State -Path $StateFile
Write-TerminalRunState -State $State -LogDirectory $LogDirectory | Out-Null
Add-Content -LiteralPath $State.LogPath -Encoding UTF8 -Value @(
    "StopTime=$($State.StopTime)"
    "Result=Stopped"
    "LifecycleStatus=CompletedValidated"
    "SampleCount=$($Result.SampleCount)"
    "CounterCount=$($Result.CounterCount)"
    "CsvPath=$($Result.CsvPath)"
)
Remove-Item -LiteralPath $State.ReadyFile, $State.StopFile, $State.CompletedFile, $State.ErrorFile, $StateFile -Force -ErrorAction SilentlyContinue
[PSCustomObject]@{Result='Stopped';LifecycleStatus='CompletedValidated';TestId=$State.TestId;RunId=$State.RunId;HostId=$State.HostId;StartTime=$State.StartTime;StopTime=$State.StopTime;SampleCount=[int]$Result.SampleCount;CounterCount=[int]$Result.CounterCount;BlgPath=$State.BlgPath;CsvPath=[string]$Result.CsvPath;DataRows=[int]$Result.DataRows;ColumnCount=[int]$Result.ColumnCount;LogPath=$State.LogPath;TerminalStateFile=$State.TerminalStateFile}
