param(
    [int]$MaxAttempts = 3
)

$ErrorActionPreference = 'SilentlyContinue'

function Get-TailscaleJson {
    try {
        return (tailscale status --json 2>$null | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Get-TailscalePrefs {
    try {
        return (tailscale debug prefs 2>$null | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Repair-RouteAllStuck {
    $prefs = Get-TailscalePrefs
    if (-not $prefs) { return }
    if ($prefs.RouteAll -and -not $prefs.ExitNodeID) {
        Write-Host '[INFO] RouteAll ohne Exit-Node reparieren (Handy->PC Verbindung) ...'
        tailscale up --reset --exit-node="" --accept-routes=false 2>$null | Out-Null
        Start-Sleep -Seconds 2
    }
}

function Ensure-TailscaleServe {
    # HTTPS-Proxy im Tailnet: stabiler Remote-Zugriff vom Handy (WebSocket/Mobilfunk).
    param([string]$DnsName)

    $needsReset = $false
    $serveStatus = tailscale serve status 2>&1
    if ($LASTEXITCODE -ne 0 -or -not ($serveStatus -match 'localhost:8501|127\.0\.0\.1:8501')) {
        $needsReset = $true
    } elseif ($DnsName) {
        # Serve haengt manchmal -> HTTPS-Timeout obwohl http://100.x:8501 geht.
        try {
            $null = Invoke-WebRequest -Uri "https://$DnsName" -UseBasicParsing -TimeoutSec 12 -MaximumRedirection 0
        } catch {
            $needsReset = $true
            Write-Host '[INFO] Tailscale Serve antwortet nicht – neu einrichten ...'
        }
    }

    if ($needsReset) {
        Write-Host '[INFO] Tailscale Serve fuer Port 8501 einrichten (HTTPS Remote) ...'
        tailscale serve reset 2>$null | Out-Null
        tailscale serve --bg --https=443 http://127.0.0.1:8501 2>$null | Out-Null
        Start-Sleep -Seconds 2
    }
}

function Ensure-FirewallTailscale {
    # Eingehende Regeln fuer Port 8501 (alle Profile inkl. Public).
    $ruleName = 'DigiWiki Streamlit 8501 Tailscale'
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Host '[INFO] Firewall-Regel fuer Tailscale-Zugriff (Port 8501) anlegen ...'
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort 8501 -Profile Any -Enabled True `
            -ErrorAction SilentlyContinue | Out-Null
    }

    # Tailscale-Adapter als "Privat" (nicht Oeffentlich) – sonst blockiert Windows eingehend.
    $tsProfile = Get-NetConnectionProfile -InterfaceAlias 'Tailscale' -ErrorAction SilentlyContinue
    if ($tsProfile -and $tsProfile.NetworkCategory -eq 'Public') {
        Write-Host '[INFO] Tailscale-Netzwerk auf Privat setzen (Firewall) ...'
        Set-NetConnectionProfile -InterfaceAlias 'Tailscale' -NetworkCategory Private -ErrorAction SilentlyContinue
    }

    # Tailscale-In-Regeln oft nur Domain+Private – Ergaenzung fuer Public falls noetig.
    $tsIn = Get-NetFirewallRule -DisplayName 'Tailscale-In' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($tsIn -and ($tsIn.Profile -notmatch 'Public')) {
        $extraName = 'Tailscale-In-Public-DigiWiki'
        if (-not (Get-NetFirewallRule -DisplayName $extraName -ErrorAction SilentlyContinue)) {
            Write-Host '[INFO] Zusaetzliche Tailscale-Inbound-Regel (Public-Profil) ...'
            New-NetFirewallRule -DisplayName $extraName -Direction Inbound -Action Allow `
                -Program "$env:ProgramFiles\Tailscale\tailscale.exe" -Profile Public `
                -Enabled True -ErrorAction SilentlyContinue | Out-Null
        }
    }
}

$service = Get-Service -Name 'Tailscale' -ErrorAction SilentlyContinue
if ($service) {
    # Dienst dauerhaft auf "Automatisch" -> nach Neustart sofort wieder ueber Internet erreichbar.
    if ($service.StartType -ne 'Automatic') {
        Write-Host '[INFO] Tailscale-Dienst auf Autostart (Automatisch) setzen ...'
        Set-Service -Name 'Tailscale' -StartupType Automatic -ErrorAction SilentlyContinue
    }
    if ($service.Status -ne 'Running') {
        Write-Host '[INFO] Tailscale-Dienst starten ...'
        Start-Service -Name 'Tailscale' -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
    }
}

Repair-RouteAllStuck

for ($i = 1; $i -le $MaxAttempts; $i++) {
    tailscale up --accept-dns=true 2>$null | Out-Null
    Start-Sleep -Seconds 2
    Repair-RouteAllStuck
    $status = Get-TailscaleJson
    if ($status -and $status.Self.Online -and ($status.Self.TailscaleIPs | Where-Object { $_ -match '^100\.' })) {
        break
    }
    Write-Host "[INFO] Tailscale-Verbindung Versuch $i/$MaxAttempts ..."
    Start-Sleep -Seconds 2
}

$status = Get-TailscaleJson
if (-not $status) {
    Write-Host '[WARNUNG] Tailscale-Status nicht lesbar.'
    exit 1
}

$ip = ($status.Self.TailscaleIPs | Where-Object { $_ -match '^100\.' } | Select-Object -First 1)
$dns = ($status.Self.DNSName -replace '\.$', '')
$online = [string]$status.Self.Online
$prefs = Get-TailscalePrefs
$routeAll = if ($prefs) { [string]$prefs.RouteAll } else { 'unknown' }

if ($ip -and ($online -eq 'True')) {
    Ensure-FirewallTailscale
    Ensure-TailscaleServe -DnsName $dns
}

Write-Host "TAILSCALE_IP=$ip"
Write-Host "TAILSCALE_DNS=$dns"
Write-Host "TAILSCALE_ONLINE=$online"
Write-Host "TAILSCALE_ROUTEALL=$routeAll"
if ($dns) {
    Write-Host "TAILSCALE_HTTPS=https://$dns"
}

if ($ip -and ($online -eq 'True')) {
    if ($routeAll -eq 'True') {
        Write-Host '[WARNUNG] RouteAll noch aktiv - Handy-Verbindung kann instabil sein.'
        Write-Host '           In Tailscale-App: Exit-Node / VPN vollstaendig AUS.'
        exit 2
    }
    Write-Host '[OK] Tailscale bereit.'
    exit 0
}

Write-Host '[WARNUNG] Tailscale nicht vollstaendig bereit.'
exit 2
