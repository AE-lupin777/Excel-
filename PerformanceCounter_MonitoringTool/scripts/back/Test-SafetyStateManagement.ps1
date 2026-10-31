$ErrorActionPreference = 'Stop'

$Cases = @(
    'Test-HostReadyLoss.ps1'
    'Test-HostStateMismatch.ps1'
    'Test-StartFailureRecovery.ps1'
)
$Results = New-Object System.Collections.Generic.List[object]

foreach ($Case in $Cases) {
    $CasePath = Join-Path $PSScriptRoot $Case
    $Output = @(& $CasePath)
    $Result = $Output | Where-Object { $_.PSObject.Properties['Result'] } | Select-Object -Last 1
    if ($null -eq $Result -or [string]$Result.Result -ne 'Passed') {
        throw "Safety test did not report success: $Case"
    }
    $Results.Add($Result)
}

[PSCustomObject]@{
    Result = 'Passed'
    Cases = $Results
}
