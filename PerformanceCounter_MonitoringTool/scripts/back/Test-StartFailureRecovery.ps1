$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'HostCommon.ps1')
$Root = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $Root 'logs'
$CounterFile = Join-Path $Root 'config\counters.effective.txt'
$HostStateFile = Join-Path $Logs 'collector-host.json'
$CollectionStateFile = Join-Path $Logs 'collection-state.json'
$Starter = Join-Path $PSScriptRoot 'Start-CollectorHost.ps1'
$Stopper = Join-Path $PSScriptRoot 'Stop-CollectorHost.ps1'
$CollectionStarter = Join-Path $PSScriptRoot 'Start-PerformanceCollection.ps1'
$WindowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$Backup = Join-Path (Split-Path $CounterFile) ('.counters.effective.{0}.test-backup' -f [Guid]::NewGuid().ToString('N'))
$BackupCreated = $false

if (Test-Path -LiteralPath $CollectionStateFile) { throw 'Collection state exists before Start-failure test.' }
if (Test-Path -LiteralPath $HostStateFile) { & $Stopper | Out-Null }

try {
    $HostResult = & $Starter
    Copy-Item -LiteralPath $CounterFile -Destination $Backup
    $BackupCreated = $true
    Set-Content -LiteralPath $CounterFile -Value '\DefinitelyMissingObject\DefinitelyMissingCounter' -Encoding UTF8
    $Before = @(Get-ChildItem -LiteralPath $Logs -Filter 'collector-run-*.final.json' -File).FullName
    $Failed = $false
    try { & $CollectionStarter -TestId ("STARTFAIL_{0}" -f (Get-Date).ToString('yyyyMMdd_HHmmssfff')) | Out-Null }
    catch { $Failed=$true; $FailureMessage=$_.Exception.Message }
    if (-not $Failed) { throw 'Invalid-counter Start unexpectedly succeeded.' }
    if (Test-Path -LiteralPath $CollectionStateFile) { throw 'Active state remained after confirmed Start failure cleanup.' }
    $NewFinals = @(Get-ChildItem -LiteralPath $Logs -Filter 'collector-run-*.final.json' -File | Where-Object { $Before -notcontains $_.FullName })
    $FailedFinal = $NewFinals | Where-Object { (Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json).Status -eq 'StartFailedCleaned' } | Select-Object -Last 1
    if ($null -eq $FailedFinal) { throw 'StartFailedCleaned terminal state was not created.' }
    $CurrentHost = Get-Content -LiteralPath $HostStateFile -Raw | ConvertFrom-Json
    $Identity = Get-CollectorHostIdentityResult -HostState $CurrentHost -ExpectedExecutablePath $WindowsPowerShell
    if (-not $Identity.IsValid -or [int]$CurrentHost.ProcessId -ne [int]$HostResult.ProcessId) { throw 'Host was not reusable after Start failure cleanup.' }
    [PSCustomObject]@{Result='Passed';Check='StartFailureCleanup';ProcessId=$CurrentHost.ProcessId;HostId=$CurrentHost.HostId;TerminalState=$FailedFinal.FullName;Failure=$FailureMessage}
}
finally {
    if ($BackupCreated -and (Test-Path -LiteralPath $Backup)) { Move-Item -LiteralPath $Backup -Destination $CounterFile -Force }
    if (-not (Test-Path -LiteralPath $CollectionStateFile) -and (Test-Path -LiteralPath $HostStateFile)) { & $Stopper | Out-Null }
}
