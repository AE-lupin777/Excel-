<#
.SYNOPSIS
  Rebuilds CTC test data under a dedicated output folder.

.DESCRIPTION
  Generates EVENT, SAMPLING, and PROCESS files every 10 minutes.
  Folder and file names follow the supplied Excel naming rules.
  The output folder is removed and recreated at the start of each run.

  ASCII only (comments/messages) for Windows PowerShell 5.1 compatibility.

.PARAMETER Date
  File date in yyyyMMdd format. Default is today.

.PARAMETER Count
  Number of 10-minute slots. Default 145 (00:00 through 24:00).

.PARAMETER OutputRoot
  Dedicated output folder. The existing folder is deleted before generation.
  The legacy parameter name Root is accepted as an alias.

.EXAMPLE
  .\Make-CtcTestDataEx2-Complete.ps1

.EXAMPLE
  .\Make-CtcTestDataEx2-Complete.ps1 -Date 20261031 -Count 145
#>
[CmdletBinding()]
param(
    [ValidatePattern('^\d{8}$')]
    [string] $Date = (Get-Date -Format 'yyyyMMdd'),

    [ValidateRange(1, 100000)]
    [int] $Count = 145,

    [Alias('Root')]
    [string] $OutputRoot = (Join-Path $PSScriptRoot 'output'),

    [ValidateSet('EVENT', 'SAMPLING', 'PROCESS')]
    [string[]] $Kinds = @('EVENT', 'SAMPLING', 'PROCESS'),

    [string] $EventConnection = 'PMC',
    [string] $SamplingChamber = 'Chamber_24h',
    # [string] $TargetSize = ''
    [string] $SamplingSize = '',
    [string] $EventSize = '',
    [string] $ProcessSize = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$invariant = [System.Globalization.CultureInfo]::InvariantCulture
$dateStyles = [System.Globalization.DateTimeStyles]::None
$baseDate = [datetime]::MinValue

if (-not [datetime]::TryParseExact($Date, 'yyyyMMdd', $invariant, $dateStyles, [ref] $baseDate)) {
    throw "Invalid Date: '$Date'. Use a real date in yyyyMMdd format."
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    throw 'OutputRoot must not be empty.'
}

$outputFullPath = [System.IO.Path]::GetFullPath($OutputRoot)
$outputTrimmed = $outputFullPath.TrimEnd([char[]] @('\', '/'))
$volumeRoot = [System.IO.Path]::GetPathRoot($outputFullPath).TrimEnd([char[]] @('\', '/'))
$scriptRootFullPath = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd([char[]] @('\', '/'))

if (($outputTrimmed -eq $volumeRoot) -or ($outputTrimmed -eq $scriptRootFullPath)) {
    throw "Unsafe OutputRoot: '$outputFullPath'. Specify a dedicated output subfolder."
}

function Get-TargetBytes {
    param([string] $Size)

    if ([string]::IsNullOrWhiteSpace($Size)) {
        return [long] 0
    }

    if ($Size -match '^\s*(\d+(?:\.\d+)?)\s*(K|M|G|KB|MB|GB)\s*$') {
        $value = [double]::Parse($matches[1], $invariant)

        switch ($matches[2].ToUpperInvariant()) {
            'K'  { return [long] ($value * 1KB) }
            'KB' { return [long] ($value * 1KB) }
            'M'  { return [long] ($value * 1MB) }
            'MB' { return [long] ($value * 1MB) }
            'G'  { return [long] ($value * 1GB) }
            'GB' { return [long] ($value * 1GB) }
        }
    }

    throw "Invalid TargetSize: '$Size'. Examples: 500KB, 10MB, 1GB."
}

function Format-ProcessTs {
    param([datetime] $Time)

    $offset = [System.TimeZoneInfo]::Local.GetUtcOffset($Time)
    $dto = New-Object System.DateTimeOffset($Time, $offset)
    $datePart = $dto.ToString('yyyy/MM/dd HH:mm:ss.fff')
    $zonePart = $dto.ToString('zzz').Replace(':', '')
    return "$datePart$zonePart"
}

function Write-Utf8File {
    param(
        [string] $Path,
        [string] $Content
    )

    $directory = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function New-EventContent {
    param(
        [datetime] $SlotTime,
        [int] $SlotIndex,
        [string] $RunToken,
        [long] $TargetBytes
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $currentBytes = [long] 0
    $row = 0

    do {
        $severity = if (($row % 2) -eq 0) { 'Info' } else { 'Warn' }
        $message = if (($row % 2) -eq 0) { 'Test start' } else { 'Running' }

        $event = [ordered] @{
            Time = $SlotTime.AddSeconds($row).ToString('yyyy-MM-dd HH:mm:ss.ffff')
            Source = $EventConnection
            LogType = 'Log'
            Severity = $severity
            Message = $message
            MetaData = [ordered] @{
                WaferID = ('WF-{0}-{1:D4}-{2:D7}' -f $RunToken, $SlotIndex, ($row + 1))
            }
        }

        $line = $event | ConvertTo-Json -Compress -Depth 5
        $lines.Add($line)
        $currentBytes += $utf8NoBom.GetByteCount($line + "`r`n")
        $row++
    } while (($row -lt 2) -or (($TargetBytes -gt 0) -and ($currentBytes -lt $TargetBytes)))

    return (($lines -join "`r`n") + "`r`n")
}

function New-SamplingContent {
    param(
        [datetime] $SlotTime,
        [int] $SlotIndex,
        [long] $TargetBytes
    )

    $columnCount = 8
    $names = 1..$columnCount | ForEach-Object { 'Data{0:D2}' -f $_ }
    $units = 1..$columnCount | ForEach-Object {
        if (($_ % 3) -eq 0) { 'Pa' }
        elseif (($_ % 3) -eq 1) { 'degC' }
        else { 'V' }
    }

    $builder = New-Object System.Text.StringBuilder
    [void] $builder.Append("Date,Time," + ($names -join ',') + "`r`n")
    [void] $builder.Append(",," + ($units -join ',') + "`r`n")
    $currentBytes = [long] $utf8NoBom.GetByteCount($builder.ToString())
    $row = 0

    do {
        $time = $SlotTime.AddMilliseconds($row * 100)
        $values = for ($column = 1; $column -le $columnCount; $column++) {
            $value = 100.0 + ($SlotIndex * 0.1) + ($column * 0.25) + ($row / 1000.0)
            $value.ToString('F3', $invariant)
        }

        $line = '{0},{1},{2}' -f $time.ToString('yyyy/MM/dd'), $time.ToString('HH:mm:ss.fff'), ($values -join ',')
        [void] $builder.Append($line + "`r`n")
        $currentBytes += $utf8NoBom.GetByteCount($line + "`r`n")
        $row++
    } while (($row -lt 20) -or (($TargetBytes -gt 0) -and ($currentBytes -lt $TargetBytes)))

    return $builder.ToString()
}

function New-ProcessContent {
    param(
        [datetime] $SlotTime,
        [int] $SlotIndex,
        [string] $RunToken,
        [long] $TargetBytes
    )

    $wafers = New-Object System.Collections.Generic.List[object]
    $waferIndex = 1
    $json = ''

    do {
        $dataRows = New-Object System.Collections.Generic.List[object]

        for ($row = 0; $row -lt 10; $row++) {
            $dataTime = $SlotTime.AddMinutes($waferIndex).AddMilliseconds($row * 100)
            $dataRows.Add([ordered] @{
                Time = Format-ProcessTs $dataTime
                Name = 'Pressure'
                Value = [double] ((10.0 * $waferIndex) + ($SlotIndex / 10.0) + ($row / 10.0))
                Unit = 'Pa'
            })
        }

        $waferStart = $SlotTime.AddMinutes($waferIndex)
        $chamberStart = $waferStart.AddMinutes(1)
        $stepStart = $chamberStart.AddMinutes(1)

        $wafers.Add([ordered] @{
            LocalID = ('{0}-{1:D4}-{2:D4}' -f $RunToken, $SlotIndex, $waferIndex)
            WaferID = ('WF-{0}-{1:D4}-{2:D3}' -f $RunToken, $SlotIndex, $waferIndex)
            ProcessJobID = ('PJ-TEST-{0}-{1:D4}-{2:D3}' -f $RunToken, $SlotIndex, $waferIndex)
            TransferRoute = @('A')
            StartTime = Format-ProcessTs $waferStart
            EndTime = Format-ProcessTs $waferStart.AddMinutes(8)
            ChamberDatas = @(
                [ordered] @{
                    Chamber = 'A'
                    RecipeName = ('TEST_RECIPE_{0:D3}' -f $waferIndex)
                    StartTime = Format-ProcessTs $chamberStart
                    EndTime = Format-ProcessTs $chamberStart.AddMinutes(7)
                    Steps = @(
                        [ordered] @{
                            StepNo = $waferIndex.ToString($invariant)
                            OriginalStepNo = $waferIndex.ToString($invariant)
                            RepeatStepCount = '0'
                            StartTime = Format-ProcessTs $stepStart
                            EndTime = Format-ProcessTs $stepStart.AddMinutes(6)
                            Datas = $dataRows.ToArray()
                        }
                    )
                }
            )
        })

        $process = [ordered] @{
            ControlJobID = ('CJ-{0}-{1:D4}' -f $RunToken, $SlotIndex)
            CarrierID = ('CARRIER-TEST-{0}-{1:D4}' -f $RunToken, $SlotIndex)
            LotID = ('LOT-TEST-{0}-{1:D4}' -f $RunToken, $SlotIndex)
            FlowRecipe = 'TEST_RECIPE'
            StartTime = Format-ProcessTs $SlotTime
            EndTime = Format-ProcessTs $SlotTime.AddMinutes(10 + $waferIndex)
            Wafers = $wafers.ToArray()
        }

        $json = $process | ConvertTo-Json -Depth 12
        $waferIndex++
    } while (($TargetBytes -gt 0) -and ($utf8NoBom.GetByteCount($json) -lt $TargetBytes))

    return ($json + "`r`n")
}

# $targetBytes = Get-TargetBytes $TargetSize
$samplingBytes = Get-TargetBytes $SamplingSize
$eventBytes    = Get-TargetBytes $EventSize
$processBytes  = Get-TargetBytes $ProcessSize
$runToken = (Get-Date).ToString('yyyyMMddHHmmssfff')

if (Test-Path -LiteralPath $outputFullPath) {
    Remove-Item -LiteralPath $outputFullPath -Recurse -Force
}
New-Item -ItemType Directory -Path $outputFullPath -Force | Out-Null

for ($index = 0; $index -lt $Count; $index++) {
    $totalMinutes = $index * 10
    $ruleHour = [int] [math]::Floor($totalMinutes / 60)
    $ruleMinute = [int] ($totalMinutes % 60)
    $tenMinuteIndex = [int] ($ruleMinute / 10)
    $slotTime = $baseDate.AddMinutes($totalMinutes)
    $slotFolder = 'n{0:D2}-{1}' -f $ruleHour, $tenMinuteIndex
    $slotRoot = Join-Path $outputFullPath $slotFolder

    if ($Kinds -contains 'SAMPLING') {
        $samplingName = '{0}_{1:D2}{2:D2}.csv' -f $Date, $ruleHour, $ruleMinute
        $samplingPath = Join-Path $slotRoot (Join-Path 'SamplingLog' (Join-Path $SamplingChamber $samplingName))
        $samplingContent = New-SamplingContent -SlotTime $slotTime -SlotIndex $index -TargetBytes $samplingBytes
        Write-Utf8File -Path $samplingPath -Content $samplingContent
    }

    if ($Kinds -contains 'EVENT') {
        $eventFolder = '{0}_{1:D2}' -f $EventConnection, $ruleHour
        $eventName = '{0}_{1:D2}.evt' -f $Date, $tenMinuteIndex
        $eventPath = Join-Path $slotRoot (Join-Path 'EventLog' (Join-Path $eventFolder $eventName))
        $eventContent = New-EventContent -SlotTime $slotTime -SlotIndex $index -RunToken $runToken -TargetBytes $eventBytes
        Write-Utf8File -Path $eventPath -Content $eventContent
    }

    if ($Kinds -contains 'PROCESS') {
        $processName = '{0}_{1:D2}{2:D2}00.log' -f $Date, $ruleHour, $ruleMinute
        $processPath = Join-Path $slotRoot (Join-Path 'ProcessLog' $processName)
        $processContent = New-ProcessContent -SlotTime $slotTime -SlotIndex $index -RunToken $runToken -TargetBytes $processBytes
        Write-Utf8File -Path $processPath -Content $processContent
    }
}

$kindSummary = ($Kinds -join ', ')
Write-Host "Done. Rebuilt: $outputFullPath"
Write-Host "Date: $Date  Count: $Count  Kinds: $kindSummary"
