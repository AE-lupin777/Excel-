@echo off
setlocal

set "TESTID=%~1"

if "%TESTID%"=="" (
    set /p TESTID=Enter Test ID:
)

echo TestID=%TESTID%

pause