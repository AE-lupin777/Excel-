Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    ForEach-Object {
        [PSCustomObject]@{
            PID = $_.ProcessId
            ParentPID = $_.ParentProcessId
            CommandLine = $_.CommandLine
        }
    } | Format-List
