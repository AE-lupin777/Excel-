$root = "C:\Users\s-katsuhiro.ando\Desktop\アルバック様\Tools\テストデータ作成拡張版Tool\output"

# 生成時に指定した値に合わせる
$date = "20261031"
$count = 145
$samplingSize = 2141KB
$eventSize = 552KB
$processSize = 28.1KB

$errors = [System.Collections.Generic.List[string]]::new()
$allFiles = Get-ChildItem -LiteralPath $root -File -Recurse
$folders = Get-ChildItem -LiteralPath $root -Directory

# フォルダ数・ファイル数
if ($folders.Count -ne $count) {
    $errors.Add("フォルダ数異常: $($folders.Count) / $count")
}
if ($allFiles.Count -ne ($count * 3)) {
    $errors.Add("ファイル数異常: $($allFiles.Count) / $($count * 3)")
}

$expectedPaths = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)

for ($i = 0; $i -lt $count; $i++) {

    $hour = [int][math]::Floor($i / 6)
    $minuteIndex = $i % 6
    $minute = $minuteIndex * 10

    $folder = "n{0:D2}-{1}" -f $hour, $minuteIndex
    $hh = "{0:D2}" -f $hour
    $mm = "{0:D2}" -f $minute
    $mi = "{0:D2}" -f $minuteIndex

    $items = @(
        @{
            Path = "$folder\SamplingLog\Chamber_24h\${date}_${hh}${mm}.csv"
            Size = $samplingSize
        },
        @{
            Path = "$folder\EventLog\PMC_$hh\${date}_${mi}.evt"
            Size = $eventSize
        },
        @{
            Path = "$folder\ProcessLog\${date}_${hh}${mm}00.log"
            Size = $processSize
        }
    )

    foreach ($item in $items) {
        $relative = $item.Path
        [void]$expectedPaths.Add($relative)

        $path = Join-Path $root $relative

        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $errors.Add("ファイルなし: $relative")
            continue
        }

        $file = Get-Item -LiteralPath $path
        if ($file.Length -lt $item.Size) {
            $errors.Add("サイズ不足: $relative ($($file.Length) bytes)")
        }
    }
}

# 予期しないファイル
foreach ($file in $allFiles) {
    $relative = [System.IO.Path]::GetRelativePath($root, $file.FullName)
    if (-not $expectedPaths.Contains($relative)) {
        $errors.Add("想定外ファイル: $relative")
    }
}

# フォルダ構成の確認
for ($i = 0; $i -lt $count; $i++) {
    $folder = "n{0:D2}-{1}" -f [int][math]::Floor($i / 6), ($i % 6)
    if (-not (Test-Path -LiteralPath (Join-Path $root $folder) -PathType Container)) {
        $errors.Add("フォルダなし: $folder")
    }
}

# 内容の完全一致チェック（SHA256）
$duplicates = $allFiles |
    Get-FileHash -Algorithm SHA256 |
    Group-Object Hash |
    Where-Object Count -gt 1

foreach ($group in $duplicates) {
    $errors.Add("同一内容ファイル: $($group.Count)個 / $($group.Group.Path -join ', ')")
}

Write-Host ""
Write-Host "========== 検証結果 =========="
Write-Host "フォルダ数 : $($folders.Count)"
Write-Host "ファイル数 : $($allFiles.Count)"
Write-Host "エラー数   : $($errors.Count)"

if ($errors.Count -eq 0) {
    Write-Host "検証結果   : PASS" -ForegroundColor Green
} else {
    Write-Host "検証結果   : FAIL" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
}