$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'HostCommon.ps1')
$Root = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $Root 'logs'
$HostStateFile = Join-Path $Logs 'collector-host.json'
$CollectionStateFile = Join-Path $Logs 'collection-state.json'
$Starter = Join-Path $PSScriptRoot 'Start-CollectorHost.ps1'
$Stopper = Join-Path $PSScriptRoot 'Stop-CollectorHost.ps1'
$WindowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

if (Test-Path -LiteralPath $CollectionStateFile) { throw 'Collection state exists before mismatch test.' }
if (Test-Path -LiteralPath $HostStateFile) { & $Stopper | Out-Null }
$ThisProcess = Get-Process -Id $PID
$FakeHostId = [Guid]::NewGuid().ToString('N')
$FakeState = [PSCustomObject]@{
    Scheme='PersistentCollectorHostV2'; HostId=$FakeHostId; ProcessId=$PID
    ProcessStartTimeUtcTicks=($ThisProcess.StartTime.ToUniversalTime().Ticks + 1)
    HostExecutablePath=$WindowsPowerShell; ControlDirectory=$Logs; StartTime=(Get-Date).ToString('o')
    Status='Ready'; ActiveRunId=$null; LastTransitionTime=(Get-Date).ToString('o'); LastError=$null
}
Write-JsonAtomic -Value $FakeState -Path $HostStateFile

try {
    $Replacement = & $Starter
    if (-not (Get-Process -Id $PID -ErrorAction SilentlyContinue)) { throw 'Unrelated test process was terminated.' }
    if ([int]$Replacement.ProcessId -eq $PID) { throw 'Inconsistent Host state was accepted.' }
    $Stale = @(Get-ChildItem -LiteralPath $Logs -Filter 'collector-host-stale-*.json' -File | Where-Object { (Get-Content -LiteralPath $_.FullName -Raw) -match $FakeHostId })
    if ($Stale.Count -lt 1) { throw 'Inconsistent Host state was not archived.' }
    [PSCustomObject]@{Result='Passed';Check='HostStateMismatch';UnrelatedProcessId=$PID;ReplacementProcessId=$Replacement.ProcessId;ReplacementHostId=$Replacement.HostId;StaleState=$Stale[-1].FullName}
}
finally {
    if (Test-Path -LiteralPath $HostStateFile -PathType Leaf) { & $Stopper | Out-Null }
}
