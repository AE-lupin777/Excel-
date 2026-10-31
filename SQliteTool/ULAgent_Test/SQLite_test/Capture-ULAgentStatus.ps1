[CmdletBinding()]
param(
    [string]$TestID = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$IniPath = Join-Path $ScriptDir "ULAgent_StatusCapture.ini"

function Read-SimpleIni {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "INI file not found: $Path"
    }

    $values = @{}

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $text = $line.Trim()

        if ($text -eq "" -or $text.StartsWith("#") -or $text.StartsWith(";")) {
            continue
        }

        if ($text -match '^([^=]+)=(.*)$') {
            $values[$Matches[1].Trim()] = $Matches[2].Trim()
        }
    }

    return $values
}

function Save-Json {
    param($Value, [string]$Path)

    $Value |
        ConvertTo-Json -Depth 20 |
        Set-Content -LiteralPath $Path -Encoding UTF8
}

try {
    $config = Read-SimpleIni -Path $IniPath

    foreach ($key in @("Target", "BaseUrl", "RecordsPath", "Limit", "OutputDirectory")) {
        if (-not $config.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($config[$key])) {
            throw "Required INI setting is missing: $key"
        }
    }

    $target = $config["Target"]
    $baseUrl = $config["BaseUrl"].TrimEnd("/")
    $recordsPath = "/" + $config["RecordsPath"].Trim("/")
    $limit = [int]$config["Limit"]
    $outputSetting = $config["OutputDirectory"]

    if ($limit -lt 1 -or $limit -gt 500) {
        throw "Limit must be between 1 and 500."
    }

    if ([System.IO.Path]::IsPathRooted($outputSetting)) {
        $outputRoot = $outputSetting
    }
    else {
        $outputRoot = Join-Path $ScriptDir $outputSetting
    }

    $startedAt = [DateTimeOffset]::Now
    $timestamp = $startedAt.ToString("yyyyMMdd_HHmmss")
    $safeTarget = $target -replace '[\\/:*?"<>|]', '_'
    $safeComputer = $env:COMPUTERNAME -replace '[\\/:*?"<>|]', '_'
    
    $folderName = if ([string]::IsNullOrWhiteSpace($TestID)) {
    "{0}_{1}_{2}" -f $timestamp, $safeComputer, $safeTarget
	}
	else {
    	"{0}_{1}_{2}_{3}" -f $TestID, $timestamp, $safeComputer, $safeTarget
	}

	$outputDir = Join-Path $outputRoot $folderName

    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

    Write-Host "Target : $target"
    Write-Host "URL    : $baseUrl"
    Write-Host "Output : $outputDir"
    Write-Host ""

    $health = Invoke-RestMethod -Method Get -Uri "$baseUrl/health" -TimeoutSec 10
    $status = Invoke-RestMethod -Method Get -Uri "$baseUrl/api/status" -TimeoutSec 10
    $records = Invoke-RestMethod -Method Get -Uri "$baseUrl$recordsPath`?limit=$limit" -TimeoutSec 10
    $recordList = @($records)
    $completedAt = [DateTimeOffset]::Now

    $info = [pscustomobject]@{
        captureStartedAt = $startedAt.ToString("o")
        captureCompletedAt = $completedAt.ToString("o")
        computerName = $env:COMPUTERNAME
        target = $target
        baseUrl = $baseUrl
        recordsPath = $recordsPath
        requestedLimit = $limit
        returnedRecordCount = $recordList.Count
    }

    $allResults = [ordered]@{
        executionInfo = $info
        health = $health
        status = $status
        records = $recordList
    }

    Save-Json -Value $allResults -Path (Join-Path $outputDir "all_results.json")
    Save-Json -Value $recordList -Path (Join-Path $outputDir "records.json")

    $info |
        Export-Csv -LiteralPath (Join-Path $outputDir "execution_info.csv") -NoTypeInformation -Encoding UTF8

    $status |
        Export-Csv -LiteralPath (Join-Path $outputDir "status.csv") -NoTypeInformation -Encoding UTF8

    if ($recordList.Count -gt 0) {
        $recordList |
            Export-Csv -LiteralPath (Join-Path $outputDir "records.csv") -NoTypeInformation -Encoding UTF8
    }
    else {
        "No records were returned." |
            Set-Content -LiteralPath (Join-Path $outputDir "records.csv") -Encoding UTF8
    }

    Write-Host "Capture completed successfully."
    Write-Host "Records: $($recordList.Count)"
    exit 0
}
catch {
    $errorRoot = Join-Path $ScriptDir "Evidence"
    New-Item -ItemType Directory -Path $errorRoot -Force | Out-Null
    $errorFile = Join-Path $errorRoot ("ERROR_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

    @(
        "Capture failed."
        "Time: $([DateTimeOffset]::Now.ToString('o'))"
        "Computer: $env:COMPUTERNAME"
        "Message: $($_.Exception.Message)"
    ) | Set-Content -LiteralPath $errorFile -Encoding UTF8

    Write-Host "Capture failed." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Error file: $errorFile"
    exit 1
}
