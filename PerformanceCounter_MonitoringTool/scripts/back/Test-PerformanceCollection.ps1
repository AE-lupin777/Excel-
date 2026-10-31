param([ValidateRange(3,60)][int]$DurationSeconds=4,[ValidateRange(1,5)][int]$Cycles=2,[switch]$KeepArtifacts,[switch]$ShutdownHost)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$Start=Join-Path $PSScriptRoot 'Start-PerformanceCollection.ps1'
$Stop=Join-Path $PSScriptRoot 'Stop-PerformanceCollection.ps1'
$StopHost=Join-Path $PSScriptRoot 'Stop-CollectorHost.ps1'
$StateFile=Join-Path $Root 'logs\collection-state.json'
$Results=@()
$Active=$false
try {
    for($i=1;$i -le $Cycles;$i++){
        $StartResult=& $Start -TestId ("SELFTEST_HOST_{0}_{1}" -f $i,(Get-Date).ToString('yyyyMMdd_HHmmssfff'))
        $Active=$true
        Start-Sleep -Seconds $DurationSeconds
        $StopResult=& $Stop
        $Active=$false
        if($StopResult.SampleCount -lt 2){throw 'Too few samples.'}
        if($StopResult.CounterCount -ne $StartResult.CounterCount){throw 'Counter count mismatch.'}
        if($StopResult.DataRows -ne $StopResult.SampleCount){throw 'CSV row mismatch.'}
        if($StopResult.ColumnCount -ne ($StopResult.CounterCount+1)){throw 'CSV column mismatch.'}
        $Results += [pscustomobject]@{Cycle=$i;StartTotalSeconds=$StartResult.StartTotalSeconds;SampleCount=$StopResult.SampleCount;CounterCount=$StopResult.CounterCount;DataRows=$StopResult.DataRows;ColumnCount=$StopResult.ColumnCount;BlgPath=$StopResult.BlgPath;CsvPath=$StopResult.CsvPath;LogPath=$StopResult.LogPath}
    }
    [pscustomobject]@{Result='Passed';Cycles=$Cycles;Measurements=$Results}
}
finally {
    if($Active -and (Test-Path -LiteralPath $StateFile)){try{& $Stop|Out-Null}catch{Write-Warning $_.Exception.Message}}
    if(-not $KeepArtifacts){foreach($r in $Results){Remove-Item -LiteralPath $r.BlgPath,$r.CsvPath,$r.LogPath -Force -ErrorAction SilentlyContinue}}
    if($ShutdownHost){try{& $StopHost|Out-Null}catch{Write-Warning $_.Exception.Message}}
}
