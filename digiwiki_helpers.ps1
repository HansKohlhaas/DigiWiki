param(
    [Parameter(Mandatory = $false)]
    [int]$WatchPid = 0
)

$pidFile = Join-Path $env:TEMP 'digiwiki_helper.pid'
$PID | Out-File -FilePath $pidFile -Encoding ascii -Force

$m = '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
Add-Type -MemberDefinition $m -Name K -Namespace W

$lastTailscale = [datetime]::MinValue
$lastServeCheck = [datetime]::MinValue
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Repair-TailscaleServe {
    param([string]$DnsName)
    if (-not $DnsName) { return }
    $ok = $false
    try {
        $null = Invoke-WebRequest -Uri "https://$DnsName" -UseBasicParsing -TimeoutSec 12 -MaximumRedirection 0
        $ok = $true
    } catch {}
    if (-not $ok) {
        tailscale serve reset 2>$null | Out-Null
        tailscale serve --bg --https=443 http://127.0.0.1:8501 2>$null | Out-Null
    }
}

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
                $status = (tailscale status --json 2>$null | ConvertFrom-Json)
                if (-not ($status -and $status.Self.Online)) {
                    tailscale up --accept-dns=true 2>$null | Out-Null
                }
                $prefs = (tailscale debug prefs 2>$null | ConvertFrom-Json)
                if ($prefs.RouteAll -and -not $prefs.ExitNodeID) {
                    tailscale up --reset --exit-node="" --accept-routes=false 2>$null | Out-Null
                }
                if (((Get-Date) - $lastServeCheck).TotalSeconds -ge 600) {
                    $dns = ($status.Self.DNSName -replace '\.$', '')
                    Repair-TailscaleServe -DnsName $dns
                    $lastServeCheck = Get-Date
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
