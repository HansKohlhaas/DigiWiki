param(
    [switch]$Fix
)

$ErrorActionPreference = 'Continue'
Write-Host "=== DigiWiki Netzwerk-Diagnose ===" -ForegroundColor Cyan
Write-Host ""

function Show-Section($title) {
    Write-Host "--- $title ---" -ForegroundColor Yellow
}

Show-Section "1) Streamlit laeuft?"
$port = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1 LocalAddress, OwningProcess
if ($port) {
    $proc = Get-Process -Id $port.OwningProcess -ErrorAction SilentlyContinue
    Write-Host "[OK] Port 8501 LISTEN auf $($port.LocalAddress) (PID $($port.OwningProcess), $($proc.ProcessName))"
} else {
    Write-Host "[FEHLER] Kein Prozess hoert auf Port 8501. start.bat ausfuehren."
}

Show-Section "2) Tailscale-Dienst"
$svc = Get-Service -Name 'Tailscale' -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host "Dienst: $($svc.Status), Starttyp: $($svc.StartType)"
} else {
    Write-Host "[FEHLER] Tailscale-Dienst nicht gefunden."
}

Show-Section "3) Tailscale-Status"
$status = $null
try { $status = tailscale status --json 2>$null | ConvertFrom-Json } catch {}
if (-not $status) {
    Write-Host "[FEHLER] tailscale status nicht lesbar."
} else {
    $ip = ($status.Self.TailscaleIPs | Where-Object { $_ -match '^100\.' } | Select-Object -First 1)
    $dns = ($status.Self.DNSName -replace '\.$', '')
    Write-Host "Online:     $($status.Self.Online)"
    Write-Host "Tailscale-IP: $ip"
    Write-Host "MagicDNS:   $dns"
    Write-Host ""
    Write-Host "Geraete im Tailnet:"
    tailscale status 2>$null
}

Show-Section "4) Tailscale-Prefs (haeufige Handy-Probleme)"
$prefs = $null
try { $prefs = tailscale debug prefs 2>$null | ConvertFrom-Json } catch {}
if ($prefs) {
    Write-Host "RouteAll (VPN voll): $($prefs.RouteAll)  <- muss False sein ohne Exit-Node"
    Write-Host "ExitNode:            $($prefs.ExitNodeID)"
    Write-Host "CorpDNS:             $($prefs.CorpDNS)"
    if ($prefs.RouteAll -and -not $prefs.ExitNodeID) {
        Write-Host "[WARNUNG] RouteAll aktiv ohne Exit-Node blockiert oft Handy->PC."
        if ($Fix) {
            tailscale up --reset --exit-node="" --accept-routes=false 2>$null | Out-Null
            Write-Host "[FIX] RouteAll zurueckgesetzt."
        }
    }
}

Show-Section "5) Tailscale Serve (empfohlene Remote-URL)"
$serve = tailscale serve status 2>&1
if ($LASTEXITCODE -eq 0 -and $serve) {
    Write-Host $serve
    if ($status -and $status.Self.DNSName) {
        $httpsUrl = "https://$($status.Self.DNSName -replace '\.$','')"
        Write-Host ""
        Write-Host "[OK] Remote-Zugriff Handy (von ueberall):" -ForegroundColor Green
        Write-Host "     $httpsUrl"
        Write-Host "     (HTTPS ueber Tailscale, kein :8501 noetig)"
    }
} else {
    Write-Host "[WARNUNG] Tailscale Serve nicht aktiv."
    Write-Host "          Ohne Serve: http://TAILSCALE-IP:8501 (anfaellig bei Mobilfunk/WebSocket)"
    if ($Fix -and $status -and $status.Self.Online) {
        tailscale serve --bg --https=443 http://127.0.0.1:8501 2>$null | Out-Null
        Write-Host "[FIX] tailscale serve eingerichtet."
        tailscale serve status 2>&1
    }
}

Show-Section "6) LAN-IP (nur gleiches WLAN!)"
$lan = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike '127.*' -and
        $_.IPAddress -notlike '169.254.*' -and
        $_.IPAddress -notlike '100.*'
    } | Sort-Object InterfaceMetric | Select-Object -First 1).IPAddress
if ($lan) {
    Write-Host "LAN: $lan  -> http://${lan}:8501"
    Write-Host "[HINWEIS] LAN-URL funktioniert NUR im gleichen Buero/WLAN, NICHT von zuhause!"
}

Show-Section "7) Firewall Port 8501"
$rules = Get-NetFirewallRule -ErrorAction SilentlyContinue |
    Where-Object { $_.Enabled -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' } |
    Get-NetFirewallPortFilter -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -eq 8501 }
if ($rules) {
    Write-Host "[OK] Firewall-Regel(n) fuer Port 8501 vorhanden."
} else {
    Write-Host "[WARNUNG] Keine Firewall-Regel fuer Port 8501."
    if ($Fix) {
        New-NetFirewallRule -DisplayName "DigiWiki Streamlit 8501" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8501 -Profile Any -ErrorAction SilentlyContinue | Out-Null
        Write-Host "[FIX] Firewall-Regel angelegt."
    }
}

Show-Section "8) Verbindungstest zum Handy"
$phone = $null
if ($status) {
    $phone = $status.Peer.PSObject.Properties.Value |
        Where-Object { $_.OS -match 'android|ios' -and $_.Online } |
        Select-Object -First 1
}
if ($phone -and $phone.TailscaleIPs) {
    $phoneIp = ($phone.TailscaleIPs | Where-Object { $_ -match '^100\.' } | Select-Object -First 1)
    Write-Host "Ping zu $($phone.HostName) ($phoneIp) ..."
    tailscale ping $phoneIp 2>&1 | Select-Object -First 3
} else {
    Write-Host "Kein online Android/iOS-Geraet im Tailnet gefunden."
    Write-Host "Handy-App oeffnen und pruefen: Tailscale = Verbunden (gruen)."
}

Show-Section "9) Netcheck (NAT/DERP)"
tailscale netcheck 2>&1 | Select-String -Pattern 'UDP:|IPv4:|Nearest DERP:|MappingVaries|PortMapping' | ForEach-Object { $_.Line }

Write-Host ""
Write-Host "=== Checkliste Handy (von zuhause) ===" -ForegroundColor Cyan
Write-Host "1. Tailscale-App: Status 'Verbunden' (gruen) – VOR dem Browser oeffnen"
Write-Host "2. Exit-Node / 'Use as VPN' AUS"
Write-Host "3. Android: Einstellungen -> Netzwerk -> Privates DNS -> AUS (nicht Automatisch!)"
Write-Host "   (Privates DNS 'Automatisch' blockiert MagicDNS -> 'Adresse nicht gefunden')"
Write-Host "4. URL primaer:  https://desktop-velbert....ts.net"
Write-Host "   URL Fallback: http://TAILSCALE-IP:8501  (wenn DNS nicht geht)"
if ($ip) {
    Write-Host "                 http://${ip}:8501  <- diese IP jetzt testen" -ForegroundColor Green
}
Write-Host "5. Akku-Optimierung fuer Tailscale: Uneingeschraenkt"
Write-Host "6. Bei Timeout: Flugmodus kurz an/aus, Tailscale neu verbinden"
Write-Host ""
Write-Host "Diagnose mit Auto-Fix:  powershell -File digiwiki_netz_diag.ps1 -Fix"
Write-Host ""
