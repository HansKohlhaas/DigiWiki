param(
    [Parameter(Mandatory = $false)]
    [int]$WatchPid = 0
)

$pidFile = Join-Path $env:TEMP 'digiwiki_helper.pid'
$PID | Out-File -FilePath $pidFile -Encoding ascii -Force

$m = '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
Add-Type -MemberDefinition $m -Name K -Namespace W

$lastTailscale = [datetime]::MinValue

try {
    while ($true) {
        if ($WatchPid -gt 0) {
            if (-not (Get-Process -Id $WatchPid -ErrorAction SilentlyContinue)) {
                exit 0
            }
        }

        [W.K]::SetThreadExecutionState(0x80000003) | Out-Null

        if (((Get-Date) - $lastTailscale).TotalSeconds -ge 90) {
            try {
                # Offline erkennen und neu verbinden -> Handy bleibt ueber Internet erreichbar.
                $status = (tailscale status --json 2>$null | ConvertFrom-Json)
                if (-not ($status -and $status.Self.Online)) {
                    tailscale up --accept-dns=true 2>$null | Out-Null
                }
                $prefs = (tailscale debug prefs 2>$null | ConvertFrom-Json)
                if ($prefs.RouteAll -and -not $prefs.ExitNodeID) {
                    tailscale up --reset --exit-node="" --accept-routes=false 2>$null | Out-Null
                }
            } catch {}
            $lastTailscale = Get-Date
        }

        Start-Sleep -Seconds 45
    }
}
finally {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}
