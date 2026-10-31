@echo off
setlocal

cd /d "%~dp0"

if /i "%~1"=="sender" (
    set "ROLE=sender"
    goto role_ok
)

if /i "%~1"=="receiver" (
    set "ROLE=receiver"
    goto role_ok
)

echo Usage: Initialize-PerformanceCollection.cmd sender ^| receiver
exit /b 2

:role_ok

>"%~dp0config\role.conf" echo %ROLE%

set "P=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

"%P%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass ^
  -File "%~dp0scripts\Setup-PerformanceCollection.ps1"

if errorlevel 1 (
    echo [ERROR] Setup-PerformanceCollection.ps1 failed.
    exit /b 1
)

echo [INFO] CollectorHost initialization completed. Role=%ROLE%

exit /b 0