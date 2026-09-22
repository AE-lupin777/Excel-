@echo off
cd /d "%~dp0"

echo [1/3] Unblocking PowerShell scripts...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-ChildItem -Path '%~dp0' -Recurse -Filter *.ps1 | Unblock-File"

if errorlevel 1 goto error

echo [2/3] Running setup...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Setup-PerformanceCollection.ps1"

if errorlevel 1 goto error

echo [3/3] Running self-test...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Test-PerformanceCollection.ps1" -KeepArtifacts

if errorlevel 1 goto error

echo.
echo ========================================
echo Setup and self-test completed.
echo ========================================
pause
exit /b 0

:error
echo.
echo ========================================
echo ERROR: Setup or self-test failed.
echo ========================================
pause
exit /b 1