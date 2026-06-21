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
$lastStreamlitCheck = [datetime]::MinValue
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$streamlitStarter = Join-Path $scriptDir 'digiwiki_start_streamlit.ps1'
$zugangWriter = Join-Path $scriptDir 'digiwiki_write_zugang.ps1'

function Test-ServeWebSocket {
    param([string]$DnsName)
    if (-not $DnsName) { return $false }
    try {
        $out = & curl.exe --max-time 10 -sS -D - -o NUL `
            -H 'Connection: Upgrade' -H 'Upgrade: websocket' `
            -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' `
            "https://$DnsName/_stcore/stream" 2>&1
        return ($out -match '101 Switching Protocols')
    } catch {
        return $false
    }
}

function Ensure-StreamlitRunning {
    if (-not (Test-Path $streamlitStarter)) { return }
    $portOpen = [bool](Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)
    $healthy = $false
    if ($portOpen) {
        try {
            $code = (& curl.exe -sS -o NUL -w '%{http_code}' --max-time 8 'http://127.0.0.1:8501/_stcore/health' 2>$null)
            $healthy = ($code -eq '200')
        } catch {}
    }
    if ($portOpen -and $healthy) { return }
    if ($portOpen -and -not $healthy) {
        Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $streamlitStarter | Out-Null
}

function Update-ZugangDatei {
    try {
        $status = (tailscale status --json 2>$null | ConvertFrom-Json)
        if (-not ($status -and $status.Self.Online)) { return }
        $ip = ($status.Self.TailscaleIPs | Where-Object { $_ -match '^100\.' } | Select-Object -First 1)
        if (-not $ip) { return }
        $dns = ($status.Self.DNSName -replace '\.$', '')
        $https = if ($dns) { "https://$dns" } else { '' }
        if (Test-Path $zugangWriter) {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $zugangWriter `
                -TailscaleIp $ip -TailscaleHttps $https -Root $scriptDir | Out-Null
        }
    } catch {}
}

function Repair-TailscaleServe {
    param([string]$DnsName)
    if (-not $DnsName) { return }
    $httpOk = $false
    try {
        $null = Invoke-WebRequest -Uri "https://$DnsName" -UseBasicParsing -TimeoutSec 12 -MaximumRedirection 0
        $httpOk = $true
    } catch {}
    $wsOk = Test-ServeWebSocket -DnsName $DnsName
    if (-not $httpOk -or -not $wsOk) {
        tailscale serve reset 2>$null | Out-Null
        tailscale serve --bg 8501 2>$null | Out-Null
    }
}

try {
    Update-ZugangDatei
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
                if (((Get-Date) - $lastServeCheck).TotalSeconds -ge 180) {
                    $dns = ($status.Self.DNSName -replace '\.$', '')
                    Repair-TailscaleServe -DnsName $dns
                    $lastServeCheck = Get-Date
                }
            } catch {}
            $lastTailscale = Get-Date
        }

        if (((Get-Date) - $lastStreamlitCheck).TotalSeconds -ge 120) {
            Ensure-StreamlitRunning
            $lastStreamlitCheck = Get-Date
        }

        Start-Sleep -Seconds 45
    }
}
finally {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}
