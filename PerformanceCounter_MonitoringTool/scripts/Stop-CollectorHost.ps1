$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'HostCommon.ps1')

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDirectory = Join-Path $ProjectRoot 'logs'
$CollectionState = Join-Path $LogDirectory 'collection-state.json'
$HostStateFile = Join-Path $LogDirectory 'collector-host.json'
$HostReadyFile = Join-Path $LogDirectory 'collector-host.ready'
$ShutdownFile = Join-Path $LogDirectory 'collector-host.shutdown'
$WindowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

if (Test-Path -LiteralPath $CollectionState -PathType Leaf) { throw 'A collection state exists. Stop or investigate it before shutting down the Host.' }
if (-not (Test-Path -LiteralPath $HostStateFile -PathType Leaf)) {
    if (Test-CollectorHostMutexHeld -ControlDirectory $LogDirectory) { throw 'CollectorHost mutex is held but its state file is missing. No shutdown signal was sent.' }
    [PSCustomObject]@{Result='NotRunning'}
    return
}

$HostState = Get-Content -LiteralPath $HostStateFile -Raw | ConvertFrom-Json
$Identity = Get-CollectorHostIdentityResult -HostState $HostState -ExpectedExecutablePath $WindowsPowerShell
if (-not $Identity.IsValid) {
    if (Test-CollectorHostMutexHeld -ControlDirectory $LogDirectory) {
        throw "CollectorHost state is inconsistent while its mutex is held. No shutdown signal was sent. $($Identity.Reason)"
    }
    $StalePath = Join-Path $LogDirectory ("collector-host-stale-{0}-{1}.json" -f (Get-Date).ToString('yyyyMMdd_HHmmssfff'), [Guid]::NewGuid().ToString('N').Substring(0,8))
    Move-Item -LiteralPath $HostStateFile -Destination $StalePath
    Remove-Item -LiteralPath $HostReadyFile -Force -ErrorAction SilentlyContinue
    [PSCustomObject]@{Result='ArchivedStaleState';Reason=$Identity.Reason;StaleStateFile=$StalePath}
    return
}

Write-JsonAtomic -Value ([PSCustomObject]@{
    Scheme='CollectorHostShutdownV2'; HostId=[string]$HostState.HostId
    ProcessId=[int]$HostState.ProcessId; ProcessStartTimeUtcTicks=[Int64]$HostState.ProcessStartTimeUtcTicks
    RequestTime=(Get-Date).ToString('o')
}) -Path $ShutdownFile

$Process = $Identity.Process
Wait-Process -Id $Process.Id -Timeout 10 -ErrorAction SilentlyContinue
if (-not $Process.HasExited) {
    $Process.Refresh()
    if (-not $Process.HasExited) { throw "CollectorHost did not stop within 10 seconds. It was not forcibly terminated. HostId: $($HostState.HostId)" }
}

[PSCustomObject]@{
    Result='Stopped'; ProcessId=$Process.Id; HostId=[string]$HostState.HostId
    ProcessStartTimeUtcTicks=[Int64]$HostState.ProcessStartTimeUtcTicks
}
