$helpers = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -match 'digiwiki_helpers|SetThreadExecutionState|tailscale status \| Out-Null' }

Write-Host "DigiWiki PS helpers: $($helpers.Count)"
Write-Host "Total PowerShell:   $((Get-Process powershell -ErrorAction SilentlyContinue).Count)"

if ($helpers.Count -gt 0) {
    Write-Host "--- Helper details ---"
    $helpers | ForEach-Object { Write-Host "  PID $($_.ProcessId): $($_.CommandLine.Substring(0, [Math]::Min(100, $_.CommandLine.Length)))..." }
}
