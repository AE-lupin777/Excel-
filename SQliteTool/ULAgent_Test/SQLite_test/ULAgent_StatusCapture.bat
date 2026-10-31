@echo off
setlocal

set "TESTID=%~1"

if "%TESTID%"=="" (
    echo.
    set /p TESTID=Enter Test ID (e.g. 1-1-1)
)

if "%TESTID%"=="" (
    echo.
    echo [ERROR] Test ID is required.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass ^
    -File "%~dp0Capture-ULAgentStatus.ps1" ^
    -TestID "%TESTID%"

pause