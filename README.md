& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command {
    "PSVersion=$($PSVersionTable.PSVersion)"
    "Is64Bit=$([Environment]::Is64BitProcess)"
    foreach ($name in 'Get-Counter','Import-Counter','Export-Counter') {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            "$name=Available"
        } else {
            "$name=Missing"
        }
    }
}
