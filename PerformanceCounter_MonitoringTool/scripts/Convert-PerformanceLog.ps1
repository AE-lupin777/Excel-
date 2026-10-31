param(
    [Parameter(Mandatory = $true)]
    [string]$BlgPath
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -Path $BlgPath -PathType Leaf)) {
    throw "BLG file not found: $BlgPath"
}

$CsvPath = [System.IO.Path]::ChangeExtension($BlgPath, '.csv')

if (Test-Path -Path $CsvPath) {
    throw "CSV file already exists: $CsvPath"
}

try {
    Import-Counter -Path $BlgPath |
        Export-Counter -Path $CsvPath -FileFormat CSV
}
catch {
    throw "BLG to CSV conversion failed: $($_.Exception.Message)"
}

$CsvData = @(Import-Csv -LiteralPath $CsvPath)

if ($CsvData.Count -eq 0) {
    throw "Converted CSV contains no data rows: $CsvPath"
}

try {
    foreach ($Row in $CsvData) {
        $TimestampProperty = $Row.PSObject.Properties | Select-Object -First 1

        if ($null -eq $TimestampProperty) {
            throw "Timestamp column was not found."
        }

        $TimestampText = $TimestampProperty.Value

        if ([string]::IsNullOrWhiteSpace($TimestampText)) {
            throw "Timestamp value is empty."
        }

        $LocalTimestamp = Get-Date -Date $TimestampText
        $UtcTimestamp = $LocalTimestamp.ToUniversalTime()

        $TimestampProperty.Value = $UtcTimestamp.ToString(
            "yyyy-MM-dd'T'HH:mm:ss.fff'+00:00'"
        )
    }
}
catch {
    throw "Timestamp conversion failed: $($_.Exception.Message)"
}

try {
    $CsvData |
        Export-Csv -LiteralPath $CsvPath -NoTypeInformation -Encoding Default
}
catch {
    throw "Failed to rewrite CSV with UTC timestamps: $($_.Exception.Message)"
}

$ConvertedCsvData = @(Import-Csv -LiteralPath $CsvPath)

if ($ConvertedCsvData.Count -eq 0) {
    throw "Converted CSV contains no data rows after timestamp conversion: $CsvPath"
}

$ColumnCount = @($ConvertedCsvData[0].PSObject.Properties).Count

[PSCustomObject]@{
    Result      = 'Converted'
    BlgPath     = $BlgPath
    CsvPath     = $CsvPath
    DataRows    = $ConvertedCsvData.Count
    ColumnCount = $ColumnCount
}
