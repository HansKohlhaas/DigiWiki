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

Write-Host "TAILSCALE_IP=$ip"
Write-Host "TAILSCALE_DNS=$dns"
Write-Host "TAILSCALE_ONLINE=$online"
Write-Host "TAILSCALE_ROUTEALL=$routeAll"

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
