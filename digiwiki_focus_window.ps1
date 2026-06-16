param(
    [string]$WindowTitlePattern = 'DigiWiki-Streamlit',
    [switch]$MinimizeCaller
)

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class DigiwikiWin32 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
}
'@

function Focus-Window([string]$pattern) {
    $proc = Get-Process |
        Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero -and $_.MainWindowTitle -like "*$pattern*" } |
        Select-Object -First 1
    if (-not $proc) { return $false }
    [DigiwikiWin32]::ShowWindow($proc.MainWindowHandle, 9) | Out-Null
    [DigiwikiWin32]::BringWindowToTop($proc.MainWindowHandle) | Out-Null
    [DigiwikiWin32]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
    return $true
}

if ($MinimizeCaller) {
    $caller = Get-Process -Id $PID -ErrorAction SilentlyContinue
    if ($caller -and $caller.MainWindowHandle -ne [IntPtr]::Zero) {
        [DigiwikiWin32]::ShowWindow($caller.MainWindowHandle, 6) | Out-Null
    }
}

for ($i = 0; $i -lt 12; $i++) {
    if (Focus-Window $WindowTitlePattern) { exit 0 }
    Start-Sleep -Milliseconds 500
}

exit 1
