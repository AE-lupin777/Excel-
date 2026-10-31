<#
.SYNOPSIS
  Place one EVENT / SAMPLING / PROCESS test file into the CTC(Sender) watch folders.
  For per-log-type registration checks in the integration/soak test.

.DESCRIPTION
  Generates files matching ULAgent.Sender default input profiles:
    - EVENT   : EventLog\<connection>\yyyyMMdd_HHmmss.evt   (JSON Lines)
    - SAMPLING: SamplingLog\<chamber>\yyyyMMdd_HHmmss.csv   (Date,Time,Data01..NN)
    - PROCESS : ProcessLog\yyyyMMdd_HHmmss.log             (Lot/Wafer/Chamber/Step JSON)
  In-file timestamps are derived from the run time to avoid duplicates.

  ASCII only (comments/messages) to avoid Windows PowerShell 5.1 encoding issues.

.PARAMETER Root
  Sender ULAgent data root. Default C:\CTC-Main\ULAgent

.PARAMETER Kinds
  Which kinds to generate. Default all (EVENT,SAMPLING,PROCESS).

.EXAMPLE
  .\Make-CtcTestData.ps1
  .\Make-CtcTestData.ps1 -Kinds SAMPLING,PROCESS
  .\Make-CtcTestData.ps1 -Root "C:\CTC-Main\ULAgent" -Kinds EVENT
#>
[CmdletBinding()]
param(
    [string] $Root = (Join-Path $PSScriptRoot "output"),
    [ValidateSet("EVENT", "SAMPLING", "PROCESS")]
    [string[]] $Kinds = @("EVENT", "SAMPLING", "PROCESS"),
    [string] $EventConnection = "PMC",
    [string] $SamplingChamber = "Chamber-Z4",
    [string] $TargetSize = ""
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$now = Get-Date

# Filename formats are validated by the Sender per log type:
#   EVENT   : yyyyMMdd_HH.evt   (hour resolution)
#   SAMPLING: yyyyMMdd_HHmm.csv (minute resolution)
#   PROCESS : any base name .log
# To reduce same-name collisions across runs, use offset times per kind.
$eventStamp    = $now.AddHours(-2).ToString("yyyyMMdd_HH")     # e.g. 20260914_07
$samplingStamp = $now.AddMinutes(-2).ToString("yyyyMMdd_HHmm") # e.g. 20260914_0920
$processStamp  = $now.ToString("yyyyMMdd_HHmmss")              # .log allows seconds

function Get-TargetBytes {

    param([string]$Size)

    if ([string]::IsNullOrWhiteSpace($Size)) {
        return 0
    }

    if ($Size -match '^\s*(\d+(?:\.\d+)?)\s*(K|M|G|KB|MB|GB)\s*$'){

        $value = [double]$matches[1]

        switch ($matches[2].ToUpper()) {

		    "K"  { return [long]($value * 1KB) }
		    "KB" { return [long]($value * 1KB) }
		    "M"  { return [long]($value * 1MB) }
		    "MB" { return [long]($value * 1MB) }
		    "G"  { return [long]($value * 1GB) }
		    "GB" { return [long]($value * 1GB) }        
		}
    }

    throw "Invalid TargetSize: $Size"
}

function Format-ProcessTs {
    param([datetime]$t)
    $off = [System.TimeZoneInfo]::Local.GetUtcOffset($t)
    $dt = [System.DateTimeOffset]::new($t, $off).ToString("yyyy/MM/dd HH:mm:ss.fff")
    $z = [System.DateTimeOffset]::new($t, $off).ToString("zzz").Replace(":", "")
    return "$dt$z"
}

function Write-File {
    param([string]$Path, [string]$Content)
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force $dir | Out-Null
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
    Write-Host "  -> $Path"
}

# ---- EVENT (.evt / JSON Lines) ----
if ($Kinds -contains "EVENT") {
    Write-Host "[EVENT]"
    $path = Join-Path $Root "EventLog\$EventConnection\$eventStamp.evt"

	$lines = New-Object System.Collections.Generic.List[string]

	$currentSize = 0
	$targetBytes = Get-TargetBytes $TargetSize
	
	$r = 0

	while ($true) {

	    $sev =
	        if (($r % 2) -eq 0) {
	            "Info"
	        } else {
	            "Warn"
	        }

	    $msg =
	        if (($r % 2) -eq 0) {
	            "Test start"
	        } else {
	            "Running"
	        }

	    $line =
	        ('{{"Time":"{0}","Source":"{1}","LogType":"Log","Severity":"{2}","Message":"{3}","MetaData":{{"WaferID":"WF-{4:D7}"}}}}' -f
	            $now.AddSeconds($r).ToString("yyyy-MM-dd HH:mm:ss.ffff"),
	            $EventConnection,
	            $sev,
	            $msg,
	            ($r + 1)
	        )

	    $lines.Add($line)

	    $currentSize +=
	        [System.Text.Encoding]::UTF8.GetByteCount(
	            $line + "`r`n"
	        )

	    $r++

	    if ($targetBytes -gt 0) {

	        if ($currentSize -ge $targetBytes) {
	            break
	        }

	    } else {

	        if ($r -ge 2) {
	            break
	        }
	    }
	}

    Write-File -Path $path -Content (($lines -join "`r`n") + "`r`n")
}

# ---- SAMPLING (.csv / Date,Time,Data01..08) ----
if ($Kinds -contains "SAMPLING") {

    Write-Host "[SAMPLING]"

    $path = Join-Path $Root "SamplingLog\$SamplingChamber\$samplingStamp.csv"

    $cols = 8

    $names = 1..$cols | ForEach-Object {
        "Data{0:D2}" -f $_
    }

    $units = 1..$cols | ForEach-Object {
        if ($_ % 3 -eq 0) {
            "Pa"
        }
        elseif ($_ % 3 -eq 1) {
            "degC"
        }
        else {
            "V"
        }
    }

    $sb = New-Object System.Text.StringBuilder

    [void]$sb.AppendLine("Date,Time," + ($names -join ","))
    [void]$sb.AppendLine(",," + ($units -join ","))

    $currentSize =
        [System.Text.Encoding]::UTF8.GetByteCount(
            $sb.ToString()
        )


    $targetBytes = Get-TargetBytes $TargetSize


    $r = 0

    while ($true) {

        $t = $now.AddMilliseconds($r * 100)

        $vals = for ($c = 1; $c -le $cols; $c++) {
            (
                100.0 +
                $c * 0.25 +
                $r / 1000.0
            ).ToString(
                "F3",
                [System.Globalization.CultureInfo]::InvariantCulture
            )
        }

        $line =
            "{0},{1},{2}" -f
            $t.ToString("yyyy/MM/dd"),
            $t.ToString("HH:mm:ss.fff"),
            ($vals -join ",")

        [void]$sb.AppendLine($line)

        $currentSize +=
            [System.Text.Encoding]::UTF8.GetByteCount(
                $line + "`r`n"
            )
            
        $r++

        if ($targetBytes -gt 0) {

            if ($currentSize -ge $targetBytes) {
                break
            }

        } else {

            if ($r -ge 20) {
                break
            }
        }
    }

    Write-File -Path $path -Content $sb.ToString()

    Write-Host ("  Rows      : {0:N0}" -f $r)
    Write-Host ("  File Size : {0:N2} MB" -f ($currentSize / 1MB))
}

# ---- PROCESS (.log / ProcessJob JSON) ----
if ($Kinds -contains "PROCESS") {
    Write-Host "[PROCESS]"
    $path = Join-Path $Root "ProcessLog\$processStamp.log"

	$targetBytes = Get-TargetBytes $TargetSize
	$idx = 1
	$currentSize = 0
	$waferBlocks = @()
	$runId = $now.ToString("yyyyMMddHHmmss")

    
    while ($true) {
	    $datas = @()
	    for ($r = 0; $r -lt 10; $r++) {
	        $datas += (
	            '{{"Time":"{0}","Name":"Pressure","Value":{1},"Unit":"Pa"}}' -f
	            (Format-ProcessTs $now.AddMinutes($idx).AddMilliseconds($r * 100)),
	            (10.0 * $idx + ($r / 10.0)).ToString(
	                "F1",
	                [System.Globalization.CultureInfo]::InvariantCulture
	            )
	        )
    	}
    
	    $lotStart     = $now.AddMinutes($idx)
	    $waferStart   = $now.AddMinutes($idx + 1)
	    $chamberStart = $now.AddMinutes($idx + 2)
	    $stepStart    = $now.AddMinutes($idx + 3)

	    $waferJson = @"
	    {
	      "LocalID": "$runId-$($idx.ToString("D4"))",
	      "WaferID": "WF-$runId-$($idx.ToString("D3"))",
	      "ProcessJobID": "PJ-TEST-$runId-$($idx.ToString("D3"))",
	      "TransferRoute": ["A"],
	      "StartTime": "$(Format-ProcessTs $waferStart)",
	      "EndTime": "$(Format-ProcessTs $waferStart.AddMinutes(8))",
	      "ChamberDatas": [
	        {
	          "Chamber": "A",
	          "RecipeName": "TEST_RECIPE_$($idx.ToString("D3"))",
	          "StartTime": "$(Format-ProcessTs $chamberStart)",
	          "EndTime": "$(Format-ProcessTs $chamberStart.AddMinutes(7))",
	          "Steps": [
	            {
	              "StepNo": "$idx",
	              "OriginalStepNo": "$idx",
	              "RepeatStepCount": "0",
	              "StartTime": "$(Format-ProcessTs $stepStart)",
	              "EndTime": "$(Format-ProcessTs $stepStart.AddMinutes(6))", "Datas": [$($datas -join ",`r`n")]
	            }
	          ]
	        }
	      ]
	    }
	}
"@

    $waferBlocks += $waferJson

    $currentSize +=
        [System.Text.Encoding]::UTF8.GetByteCount(
            $waferJson
        )

    if ($targetBytes -gt 0) {

        if ($currentSize -ge $targetBytes) {
            break
        }

    } else {

        if ($idx -ge 1) {
            break
        }
    }

    $idx++
}

$lotStart = $now

$json = @"
{
  "ControlJobID": "CJ-$runId-001",
  "CarrierID": "CARRIER-TEST-$runId",
  "LotID": "LOT-TEST-$runId",
  "FlowRecipe": "TEST_RECIPE",
  "StartTime": "$(Format-ProcessTs $lotStart)",
  "EndTime": "$(Format-ProcessTs $now.AddMinutes(10))",
  "Wafers": [
$($waferBlocks -join ",`r`n")
  ]
}
"@

Write-File -Path $path -Content $json
}


Write-Host ""
Write-Host "Done. Sender picks up files on its scan interval (default 60s)."
Write-Host "Check Sender: Invoke-RestMethod 'http://127.0.0.1:5080/api/transfers?limit=10' | ConvertTo-Json -Depth 5"
