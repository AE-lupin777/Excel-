param([ValidateRange(3,30)][int]$DurationSeconds=3)
$ErrorActionPreference='Stop'
$Start=Join-Path $PSScriptRoot 'Start-PerformanceCollection.ps1'
$Stop=Join-Path $PSScriptRoot 'Stop-PerformanceCollection.ps1'
$StopHost=Join-Path $PSScriptRoot 'Stop-CollectorHost.ps1'
$HostStateFile=Join-Path (Split-Path -Parent $PSScriptRoot) 'logs\collector-host.json'
$Checks=New-Object System.Collections.Generic.List[object]
$Active=$false
$StopResult=$null
try {
    try { & $Start -TestId 'INVALID/ID' | Out-Null; throw 'Invalid TestId was accepted.' }
    catch { if($_.Exception.Message -eq 'Invalid TestId was accepted.'){throw}; $Checks.Add([pscustomobject]@{Check='InvalidTestId';Result='Passed';Message=$_.Exception.Message}) }

    $First = & $Start -TestId ("ERRORPATH_{0}" -f (Get-Date).ToString('yyyyMMdd_HHmmssfff'))
    $Active=$true
    try { & $Start -TestId 'SECOND_START' | Out-Null; throw 'Second Start was accepted.' }
    catch { if($_.Exception.Message -eq 'Second Start was accepted.'){throw}; $Checks.Add([pscustomobject]@{Check='DoubleStart';Result='Passed';Message=$_.Exception.Message}) }

    Start-Sleep -Seconds $DurationSeconds
    $StopResult = & $Stop
    $Active=$false
    $Checks.Add([pscustomobject]@{Check='FirstStop';Result='Passed';Message="Samples=$($StopResult.SampleCount)"})

    try { & $Stop | Out-Null; throw 'Second Stop was accepted.' }
    catch { if($_.Exception.Message -eq 'Second Stop was accepted.'){throw}; $Checks.Add([pscustomobject]@{Check='SecondStop';Result='Passed';Message=$_.Exception.Message}) }

    [pscustomobject]@{Result='Passed';Checks=$Checks;Artifact=$StopResult.LogPath}
}
finally {
    if($Active){try{& $Stop|Out-Null}catch{Write-Warning $_.Exception.Message}}
    if(Test-Path -LiteralPath $HostStateFile -PathType Leaf){try{& $StopHost|Out-Null}catch{Write-Warning $_.Exception.Message}}
}
