Set-StrictMode -Version 2.0

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)][object]$Value,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $Directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    }

    $TemporaryPath = Join-Path $Directory ('.{0}.{1}.{2}.tmp' -f [IO.Path]::GetFileName($Path), $PID, [Guid]::NewGuid().ToString('N'))
    $BackupPath = Join-Path $Directory ('.{0}.{1}.{2}.bak' -f [IO.Path]::GetFileName($Path), $PID, [Guid]::NewGuid().ToString('N'))
    try {
        $Value | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $TemporaryPath -Encoding UTF8
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            [IO.File]::Replace($TemporaryPath, $Path, $BackupPath)
            Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
        }
        else {
            [IO.File]::Move($TemporaryPath, $Path)
        }
    }
    finally {
        Remove-Item -LiteralPath $TemporaryPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
    }
}

function Get-CollectorHostMutexName {
    param([Parameter(Mandatory = $true)][string]$ControlDirectory)

    $FullPath = [IO.Path]::GetFullPath($ControlDirectory).ToLowerInvariant()
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try {
        $Hash = $Hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($FullPath))
    }
    finally {
        $Hasher.Dispose()
    }
    $Token = ([BitConverter]::ToString($Hash)).Replace('-', '').Substring(0, 24)
    return "Local\ZZPerformanceCollectorHost_$Token"
}

function Test-CollectorHostMutexHeld {
    param([Parameter(Mandatory = $true)][string]$ControlDirectory)

    $Mutex = New-Object Threading.Mutex($false, (Get-CollectorHostMutexName -ControlDirectory $ControlDirectory))
    $Acquired = $false
    try {
        try { $Acquired = $Mutex.WaitOne(0, $false) }
        catch [Threading.AbandonedMutexException] { $Acquired = $true }
        if ($Acquired) { $Mutex.ReleaseMutex() }
        return (-not $Acquired)
    }
    finally {
        $Mutex.Dispose()
    }
}

function Get-CollectorHostIdentityResult {
    param(
        [Parameter(Mandatory = $true)][object]$HostState,
        [Parameter(Mandatory = $true)][string]$ExpectedExecutablePath
    )

    $Failure = $null
    $Process = $null
    $HostGuid = [Guid]::Empty

    if ($null -eq $HostState -or $HostState.Scheme -ne 'PersistentCollectorHostV2') {
        $Failure = 'Host state scheme is invalid.'
    }
    elseif (-not [Guid]::TryParse([string]$HostState.HostId, [ref]$HostGuid)) {
        $Failure = 'HostId is invalid.'
    }
    elseif (-not $HostState.ProcessId -or -not $HostState.ProcessStartTimeUtcTicks) {
        $Failure = 'Host process identity is incomplete.'
    }
    else {
        $Process = Get-Process -Id ([int]$HostState.ProcessId) -ErrorAction SilentlyContinue
        if ($null -eq $Process) {
            $Failure = 'Host process is not running.'
        }
        else {
            try {
                $ActualTicks = $Process.StartTime.ToUniversalTime().Ticks
                if ($ActualTicks -ne [Int64]$HostState.ProcessStartTimeUtcTicks) {
                    $Failure = 'PID exists but process start time does not match.'
                }
                $ActualPath = $Process.Path
                if (-not $Failure -and -not [string]::Equals($ActualPath, $ExpectedExecutablePath, [StringComparison]::OrdinalIgnoreCase)) {
                    $Failure = 'PID exists but executable path does not match Windows PowerShell 5.1.'
                }
                if (-not $Failure -and -not [string]::Equals([string]$HostState.HostExecutablePath, $ExpectedExecutablePath, [StringComparison]::OrdinalIgnoreCase)) {
                    $Failure = 'Host state executable identity does not match.'
                }
            }
            catch {
                $Failure = "Host process identity could not be read: $($_.Exception.Message)"
            }
        }
    }

    [PSCustomObject]@{
        IsValid = [string]::IsNullOrEmpty($Failure)
        Reason  = $Failure
        Process = $Process
        HostId  = if ($HostGuid -eq [Guid]::Empty) { $null } else { $HostGuid.ToString('N') }
    }
}

function Test-CollectorHostReadyIdentity {
    param(
        [Parameter(Mandatory = $true)][string]$ReadyFile,
        [Parameter(Mandatory = $true)][object]$HostState
    )

    if (-not (Test-Path -LiteralPath $ReadyFile -PathType Leaf)) { return $false }
    try {
        $Ready = Get-Content -LiteralPath $ReadyFile -Raw | ConvertFrom-Json
        return (
            $Ready.Scheme -eq 'PersistentCollectorHostReadyV2' -and
            [string]$Ready.HostId -eq [string]$HostState.HostId -and
            [int]$Ready.ProcessId -eq [int]$HostState.ProcessId -and
            [Int64]$Ready.ProcessStartTimeUtcTicks -eq [Int64]$HostState.ProcessStartTimeUtcTicks
        )
    }
    catch { return $false }
}

function Write-TerminalRunState {
    param(
        [Parameter(Mandatory = $true)][object]$State,
        [Parameter(Mandatory = $true)][string]$LogDirectory
    )
    $Path = Join-Path $LogDirectory ("collector-run-{0}.final.json" -f $State.RunId)
    Write-JsonAtomic -Value $State -Path $Path
    return $Path
}
