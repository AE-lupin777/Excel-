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
