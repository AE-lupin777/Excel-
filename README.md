$pidTarget = 5176

1..6 | ForEach-Object {
    $p = Get-Process -Id $pidTarget -ErrorAction SilentlyContinue

    if ($null -eq $p) {
        Write-Host "Process finished"
        return
    }

    [PSCustomObject]@{
        Time       = Get-Date -Format "HH:mm:ss"
        PID        = $p.Id
        CPUSeconds = [math]::Round($p.CPU, 2)
        MemoryMB   = [math]::Round($p.WorkingSet64 / 1MB, 2)
        Threads    = $p.Threads.Count
    }

    Start-Sleep -Seconds 10
}
