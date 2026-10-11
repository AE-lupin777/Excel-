@echo off
setlocal
set "D=%~dp0"
set "P=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if /i "%~1"=="setup" goto setup
if /i "%~1"=="start" goto start
if /i "%~1"=="stop" goto stop
if /i "%~1"=="test" goto test
if /i "%~1"=="shutdown" goto shutdown
echo Usage: PerformanceCollection.cmd setup ^| start TEST_ID ^| stop ^| test ^| shutdown
exit /b 2

:setup
"%P%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%D%Setup-PerformanceCollection.ps1"
exit /b %errorlevel%

:start
if "%~2"=="" (
    echo TEST_ID is required.
    exit /b 2
)
"%P%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%D%Start-PerformanceCollection.ps1" -TestId "%~2"
exit /b %errorlevel%

:stop
"%P%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%D%Stop-PerformanceCollection.ps1"
exit /b %errorlevel%

:test
"%P%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%D%Test-PerformanceCollection.ps1" -KeepArtifacts
exit /b %errorlevel%

:shutdown
"%P%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%D%Stop-CollectorHost.ps1"
exit /b %errorlevel%
param(
    [ValidateRange(1, 3600)]
    [int]$SampleInterval = 1
)

$ErrorActionPreference = 'Stop'

if ($env:OS -ne 'Windows_NT') {
    throw 'This script requires Windows.'
}

Import-Module Microsoft.PowerShell.Diagnostics -ErrorAction Stop

foreach ($CommandName in 'Get-Counter', 'Export-Counter', 'Import-Counter', 'Start-Process') {
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "Required command is not available: $CommandName"
    }
}

$CollectorPowerShellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $CollectorPowerShellPath -PathType Leaf)) {
    throw "Windows PowerShell is not available: $CollectorPowerShellPath"
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConfigDirectory = Join-Path $ProjectRoot 'config'
$OutputDirectory = Join-Path $ProjectRoot 'output'
$LogDirectory = Join-Path $ProjectRoot 'logs'
$SourceCounterFile = Join-Path $ConfigDirectory 'counters.txt'
$EffectiveCounterFile = Join-Path $ConfigDirectory 'counters.effective.txt'
$RoleFile = Join-Path $ConfigDirectory 'role.conf'
if (-not (Test-Path -LiteralPath $RoleFile -PathType Leaf)) { throw "Role file not found: $RoleFile. Run Initialize-PerformanceCollection.cmd sender or receiver first." }
$Role = (Get-Content -LiteralPath $RoleFile -Raw).Trim().ToLowerInvariant()
switch ($Role) {
    'sender'   { $ProcessName = 'ULAgent.Sender' }
    'receiver' { $ProcessName = 'ULAgent.Receiver' }
    default    { throw "Invalid role in role.conf: $Role" }
}

foreach ($Directory in $ConfigDirectory, $OutputDirectory, $LogDirectory) {
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    }
}
