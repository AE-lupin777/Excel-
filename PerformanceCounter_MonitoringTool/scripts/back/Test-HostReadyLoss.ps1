$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $Root 'logs'
$HostStateFile = Join-Path $Logs 'collector-host.json'
$HostReadyFile = Join-Path $Logs 'collector-host.ready'
$CollectionStateFile = Join-Path $Logs 'collection-state.json'
$Starter = Join-Path $PSScriptRoot 'Start-CollectorHost.ps1'
$Stopper = Join-Path $PSScriptRoot 'Stop-CollectorHost.ps1'

if (Test-Path -LiteralPath $CollectionStateFile) { throw 'Collection state exists before Ready-loss test.' }
if (Test-Path -LiteralPath $HostStateFile) { & $Stopper | Out-Null }

try {
    $First = & $Starter
    if (-not (Test-Path -LiteralPath $HostReadyFile -PathType Leaf)) { throw 'Initial Host Ready was not created.' }
    Remove-Item -LiteralPath $HostReadyFile -Force
    $Second = & $Starter
    if ([int]$First.ProcessId -ne [int]$Second.ProcessId) { throw 'Ready loss caused a different Host PID.' }
    if ([string]$First.HostId -ne [string]$Second.HostId) { throw 'Ready loss caused a different HostId.' }
    [PSCustomObject]@{Result='Passed';Check='ReadyFileMissing';ProcessId=$Second.ProcessId;HostId=$Second.HostId;SecondStartResult=$Second.Result}
}
finally {
    if (Test-Path -LiteralPath $HostStateFile -PathType Leaf) { & $Stopper | Out-Null }
}
