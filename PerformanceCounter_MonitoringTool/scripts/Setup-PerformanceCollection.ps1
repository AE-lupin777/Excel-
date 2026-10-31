param(
    [ValidateRange(1, 3600)]
    [int]$SampleInterval = 1
)

$ErrorActionPreference = 'Stop'

if ($env:OS -ne 'Windows_NT') {
    throw 'This script requires Windows.'
}

Import-Module Microsoft.PowerShell.Diagnostics -ErrorAction SilentlyContinue

foreach ($CommandName in 'Get-Counter', 'Export-Counter', 'Import-Counter', 'Start-Process') {
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {

        [PSCustomObject]@{
            Result              = 'NotSupported'
            Reason              = "Required command is not available: $CommandName"
            CollectorHostResult = 'Skipped'
        }

        return
    }
}

$CollectorPowerShellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $CollectorPowerShellPath -PathType Leaf)) {
    throw "Windows PowerShell is not available: $CollectorPowerShellPath"
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConfigDirectory = Join-Path $ProjectRoot 'config'
$OutputDirectory = Join-Path $ProjectRoot 'output'
$LogDirectory = Join-Path $ProjectRoot 'logs'
$SourceCounterFile = Join-Path $ConfigDirectory 'counters.txt'
$EffectiveCounterFile = Join-Path $ConfigDirectory 'counters.effective.txt'
$RoleFile = Join-Path $ConfigDirectory 'role.conf'
if (-not (Test-Path -LiteralPath $RoleFile -PathType Leaf)) { throw "Role file not found: $RoleFile. Run Initialize-PerformanceCollection.cmd sender or receiver first." }
$Role = (Get-Content -LiteralPath $RoleFile -Raw).Trim().ToLowerInvariant()
switch ($Role) {
    'sender'   { $ProcessName = 'ULAgent.Sender' }
    'receiver' { $ProcessName = 'ULAgent.Receiver' }
    default    { throw "Invalid role in role.conf: $Role" }
}

foreach ($Directory in $ConfigDirectory, $OutputDirectory, $LogDirectory) {
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    }
}

if (-not (Test-Path -LiteralPath $SourceCounterFile -PathType Leaf)) {
    throw "Counter file not found: $SourceCounterFile"
}

function ConvertTo-NameMap {
    param([string[]]$CounterTable)

    $Map = @{}
    for ($Index = 0; $Index -lt ($CounterTable.Count - 1); $Index += 2) {
        $Map[$CounterTable[$Index]] = $CounterTable[$Index + 1]
    }
    return $Map
}

function ConvertTo-LocalizedCounterPath {
    param(
        [string]$Path,
        [hashtable]$EnglishNameToIndex,
        [hashtable]$LocalizedIndexToName
    )

    if (-not $Path.StartsWith('\')) {
        return $Path
    }

    $SeparatorIndex = $Path.IndexOf('\', 1)
    if ($SeparatorIndex -lt 0) {
        return $Path
    }

    $ObjectWithInstance = $Path.Substring(1, $SeparatorIndex - 1)
    $CounterName = $Path.Substring($SeparatorIndex + 1)
    $OpenParenthesis = $ObjectWithInstance.IndexOf('(')

    if ($OpenParenthesis -ge 0) {
        $ObjectName = $ObjectWithInstance.Substring(0, $OpenParenthesis)
        $InstanceName = $ObjectWithInstance.Substring($OpenParenthesis)
    }
    else {
        $ObjectName = $ObjectWithInstance
        $InstanceName = ''
    }

    if ($ObjectName -eq 'Network Interface' -and $InstanceName) {
        $InstanceName = '(*)'
    }

    $LocalizedObject = $ObjectName
    $LocalizedCounter = $CounterName

    if ($EnglishNameToIndex.ContainsKey($ObjectName)) {
        $NameIndex = $EnglishNameToIndex[$ObjectName]
        if ($LocalizedIndexToName.ContainsKey($NameIndex)) {
            $LocalizedObject = $LocalizedIndexToName[$NameIndex]
        }
    }

    if ($EnglishNameToIndex.ContainsKey($CounterName)) {
        $NameIndex = $EnglishNameToIndex[$CounterName]
        if ($LocalizedIndexToName.ContainsKey($NameIndex)) {
            $LocalizedCounter = $LocalizedIndexToName[$NameIndex]
        }
    }

    return "\$LocalizedObject$InstanceName\$LocalizedCounter"
}

$EnglishNameToIndex = @{}
$LocalizedIndexToName = @{}
$CounterNameMode = 'LocalizedRegistryMap'

try {
    $PerflibRoot = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Perflib'
    $EnglishIndexToName = ConvertTo-NameMap -CounterTable (Get-ItemPropertyValue -Path (Join-Path $PerflibRoot '009') -Name Counter)
    $LocalizedIndexToName = ConvertTo-NameMap -CounterTable (Get-ItemPropertyValue -Path (Join-Path $PerflibRoot 'CurrentLanguage') -Name Counter)
    foreach ($Entry in $EnglishIndexToName.GetEnumerator()) {
        $EnglishNameToIndex[$Entry.Value] = $Entry.Key
    }
}
catch {
    $CounterNameMode = 'OriginalNames'
}

$ConfiguredCounters = @(
    Get-Content -LiteralPath $SourceCounterFile |
        ForEach-Object { $_.Trim().Replace('{PROCESS_NAME}', $ProcessName) } |
        Where-Object { $_ -and -not $_.StartsWith('#') }
)

if ($ConfiguredCounters.Count -eq 0) {
    throw "No performance counters are defined: $SourceCounterFile"
}

$EffectiveCounters = New-Object System.Collections.Generic.List[string]
$SkippedCounters = New-Object System.Collections.Generic.List[string]

foreach ($ConfiguredCounter in $ConfiguredCounters) {
    $Candidate = ConvertTo-LocalizedCounterPath -Path $ConfiguredCounter -EnglishNameToIndex $EnglishNameToIndex -LocalizedIndexToName $LocalizedIndexToName
    try {
        $Samples = @(Get-Counter -Counter $Candidate -MaxSamples 1 -ErrorAction Stop).CounterSamples
        foreach ($Sample in $Samples) {
            $PortablePath = $Sample.Path -replace '^\\\\[^\\]+\\', '\'
            if (-not $EffectiveCounters.Contains($PortablePath)) {
                $EffectiveCounters.Add($PortablePath)
            }
        }
    }
    catch {
        $SkippedCounters.Add($ConfiguredCounter)
        Write-Warning "Unavailable counter skipped: $ConfiguredCounter"
    }
}

if ($EffectiveCounters.Count -eq 0) {
    throw 'None of the configured performance counters are available on this PC.'
}

$EffectiveCounters | Set-Content -LiteralPath $EffectiveCounterFile -Encoding UTF8

$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = New-Object Security.Principal.WindowsPrincipal($Identity)
$HostStarter = Join-Path $PSScriptRoot 'Start-CollectorHost.ps1'
if (-not (Test-Path -LiteralPath $HostStarter -PathType Leaf)) {
    throw "Collector host starter not found: $HostStarter"
}
$HostResult = & $HostStarter

[PSCustomObject]@{
    Result               = 'Ready'
        Role                 = $Role
        ProcessName          = $ProcessName
    PowerShellVersion    = $PSVersionTable.PSVersion.ToString()
    CollectorPowerShell  = $CollectorPowerShellPath
    CounterNameMode      = $CounterNameMode
    IsAdministrator      = $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    SampleInterval       = $SampleInterval
    ConfiguredCount      = $ConfiguredCounters.Count
    EffectiveCount       = $EffectiveCounters.Count
    SkippedCount         = $SkippedCounters.Count
    EffectiveCounterFile = $EffectiveCounterFile
    OutputDirectory      = $OutputDirectory
    LogDirectory         = $LogDirectory
    CollectorHostResult = $HostResult.Result
    CollectorHostPid    = $HostResult.ProcessId
}
