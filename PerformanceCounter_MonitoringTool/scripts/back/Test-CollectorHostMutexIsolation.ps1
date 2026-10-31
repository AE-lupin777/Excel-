param(
    [Parameter(Mandatory=$true)]
    [string]$CollectorHostPath
)
$ErrorActionPreference = 'Stop'
$HostScript = (Resolve-Path -LiteralPath $CollectorHostPath).Path
$WindowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$TestDir = Join-Path $env:TEMP ("ZZ_HostMutexTest_" + [Guid]::NewGuid().ToString('N'))
$FirstId = [Guid]::NewGuid().ToString('N')
$SecondId = [Guid]::NewGuid().ToString('N')
$FirstProcess = $null
$SecondProcess = $null
$Success = $false
New-Item -ItemType Directory -Path $TestDir -Force | Out-Null
try {
    $FirstArgs = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -ControlDirectory "{1}" -HostId {2}' -f $HostScript,$TestDir,$FirstId
    $FirstProcess = Start-Process -FilePath $WindowsPowerShell -ArgumentList $FirstArgs -PassThru -WindowStyle Hidden
    $ReadyPath = Join-Path $TestDir 'collector-host.ready'
    $StatePath = Join-Path $TestDir 'collector-host.json'
    $Deadline = (Get-Date).AddSeconds(15)
    $InitialReady = $null
    while ((Get-Date) -lt $Deadline) {
        $FirstProcess.Refresh()
        if ($FirstProcess.HasExited) { throw "First Host exited: $($FirstProcess.ExitCode)" }
        if ((Test-Path -LiteralPath $ReadyPath) -and (Test-Path -LiteralPath $StatePath)) {
            try {
                $Ready = Get-Content -LiteralPath $ReadyPath -Raw | ConvertFrom-Json
                if ([string]$Ready.HostId -eq $FirstId) { $InitialReady = $Ready; break }
            } catch { }
        }
        Start-Sleep -Milliseconds 100
    }
    if ($null -eq $InitialReady) { throw 'First Host did not become Ready.' }

    $SecondArgs = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -ControlDirectory "{1}" -HostId {2}' -f $HostScript,$TestDir,$SecondId
    $SecondProcess = Start-Process -FilePath $WindowsPowerShell -ArgumentList $SecondArgs -PassThru -WindowStyle Hidden
    if (-not $SecondProcess.WaitForExit(10000)) { throw 'Second Host did not exit within 10 seconds.' }
    $SecondProcess.Refresh()
    if ($SecondProcess.ExitCode -ne 12) { throw "Second Host exit code was $($SecondProcess.ExitCode), expected 12." }
    $FirstProcess.Refresh()
    if ($FirstProcess.HasExited) { throw 'First Host terminated unexpectedly.' }
    if (-not (Test-Path -LiteralPath $ReadyPath)) { throw 'First Host Ready file was deleted.' }
    $ReadyAfter = Get-Content -LiteralPath $ReadyPath -Raw | ConvertFrom-Json
    if ([string]$ReadyAfter.HostId -ne $FirstId) { throw 'Ready file belongs to wrong Host.' }
    if (-not (Test-Path -LiteralPath $StatePath)) { throw 'Host state was removed.' }
    $StateAfter = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    if ([string]$StateAfter.HostId -ne $FirstId) { throw 'Host state was replaced.' }
    Write-Output 'Result=Passed'
    Write-Output 'Check=MutexRejectedHostDoesNotDeleteReady'
    Write-Output "FirstHostPid=$($FirstProcess.Id)"
    Write-Output "SecondHostExitCode=$($SecondProcess.ExitCode)"
    $Success = $true
}
finally {
    if ($null -ne $FirstProcess) {
        $FirstProcess.Refresh()
        if (-not $FirstProcess.HasExited) {
            # Clean shutdown through the Host's own request protocol; never force-kill.
            $ShutdownPath = Join-Path $TestDir 'collector-host.shutdown'
            @{ HostId = $FirstId } | ConvertTo-Json | Set-Content -LiteralPath $ShutdownPath -Encoding UTF8
            [void]$FirstProcess.WaitForExit(10000)
            $FirstProcess.Refresh()
        }
    }
    if ($null -ne $FirstProcess -and -not $FirstProcess.HasExited) {
        Write-Warning "Temporary Host is still running (PID=$($FirstProcess.Id)). Test directory preserved: $TestDir"
    }
    else {
        Remove-Item -LiteralPath $TestDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
