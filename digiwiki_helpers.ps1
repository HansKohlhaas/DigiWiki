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
. (Join-Path $scriptDir 'digiwiki_erreichbarkeit.ps1')
$streamlitStarter = Join-Path $scriptDir 'digiwiki_start_streamlit.ps1'
$zugangWriter = Join-Path $scriptDir 'digiwiki_write_zugang.ps1'
$pidFileStreamlit = Join-Path $env:TEMP 'digiwiki_streamlit.pid'

function Test-ServeWebSocket {
    param([string]$DnsName)
    return Test-DigiWikiServeWebSocket -DnsName $DnsName
}

function Ensure-StreamlitRunning {
    if (-not (Test-Path $streamlitStarter)) { return }
    $portPid = Get-DigiWikiStreamlitPortPid
    if ($portPid -gt 0) {
        Sync-DigiWikiStreamlitPidFile -PidFile $pidFileStreamlit | Out-Null
    }
    $reach = Get-DigiWikiErreichbarkeit
    if ($reach.LokalHealth -and $reach.ExternOk) { return }

    if ($reach.LokalHealth -and -not $reach.ExternOk -and $reach.TailscaleDns) {
        Repair-DigiWikiTailscaleServe -DnsName $reach.TailscaleDns
        $reach = Get-DigiWikiErreichbarkeit
        if ($reach.ExternOk) { return }
    }

    if ($portPid -gt 0) {
        Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
        Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $streamlitStarter | Out-Null
    Start-Sleep -Seconds 3
    $dns = Get-DigiWikiTailscaleDns
    if ($dns) { Repair-DigiWikiTailscaleServe -DnsName $dns }
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
    $httpOk = Test-DigiWikiServeHttp -DnsName $DnsName
    $wsOk = Test-DigiWikiServeWebSocket -DnsName $DnsName
    if (-not $httpOk -or -not $wsOk) {
        Repair-DigiWikiTailscaleServe -DnsName $DnsName
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
                if (((Get-Date) - $lastServeCheck).TotalSeconds -ge 90) {
                    $dns = if ($status) { ($status.Self.DNSName -replace '\.$', '') } else { '' }
                    Repair-TailscaleServe -DnsName $dns
                    $lastServeCheck = Get-Date
                }
            } catch {}
            $lastTailscale = Get-Date
        }

        if (((Get-Date) - $lastStreamlitCheck).TotalSeconds -ge 60) {
            Ensure-StreamlitRunning
            Write-DigiWikiErreichbarkeitStatus -Status (Get-DigiWikiErreichbarkeit) -Root $scriptDir
            $lastStreamlitCheck = Get-Date
        }

        Start-Sleep -Seconds 30
    }
}
finally {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}
