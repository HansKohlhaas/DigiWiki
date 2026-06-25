# Einmaliger Health-Check + Reparatur (Streamlit, Tailscale, Helfer).
# Wird alle 5 Min per Task Scheduler aufgerufen und bei start.bat "laeuft bereits".
param(
    [switch]$Quiet
)

$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $root 'digiwiki_erreichbarkeit.ps1')
$logFile = Join-Path $root 'digiwiki_keepalive.log'
$streamlitStarter = Join-Path $root 'digiwiki_start_streamlit.ps1'
$tailscaleFix = Join-Path $root 'digiwiki_tailscale_fix.ps1'
$helperStarter = Join-Path $root 'digiwiki_start_helper.ps1'

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    if (-not $Quiet) { Write-Host $line }
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    try {
        if ((Get-Item $logFile).Length -gt 512000) {
            $tail = Get-Content $logFile -Tail 200 -Encoding UTF8
            Set-Content -Path $logFile -Value $tail -Encoding UTF8
        }
    } catch {}
}

function Test-StreamlitHealthy {
    return Test-DigiWikiStreamlitLocal
}

function Stop-StreamlitOnPort {
    $portPid = Get-DigiWikiStreamlitPortPid
    if ($portPid -gt 0) {
        Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
    }
    Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    $pidFile = Join-Path $env:TEMP 'digiwiki_streamlit.pid'
    if (Test-Path $pidFile) {
        $spid = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($spid -match '^\d+$') {
            Stop-Process -Id ([int]$spid) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

function Test-ServeWebSocket {
    param([string]$DnsName)
    return Test-DigiWikiServeWebSocket -DnsName $DnsName
}

function Ensure-TailscaleOnline {
    $svc = Get-Service -Name 'Tailscale' -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne 'Running') {
        Write-Log 'Tailscale-Dienst gestoppt -> starte neu'
        Start-Service -Name 'Tailscale' -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
    }
    $status = $null
    $online = $false
    try {
        $status = (tailscale status --json 2>$null | ConvertFrom-Json)
        $online = [bool]($status -and $status.Self.Online)
    } catch {}
    if (-not $online) {
        Write-Log 'Tailscale offline -> tailscale up + Fix-Skript'
        tailscale up --accept-dns=true 2>$null | Out-Null
        if (Test-Path $tailscaleFix) {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $tailscaleFix | Out-Null
        }
        return
    }
    $dns = ($status.Self.DNSName -replace '\.$', '')
    if ($dns -and -not (Test-ServeWebSocket -DnsName $dns)) {
        Write-Log 'Tailscale Serve/WebSocket defekt -> neu einrichten'
        tailscale serve reset 2>$null | Out-Null
        tailscale serve --bg 8501 2>$null | Out-Null
        Start-Sleep -Seconds 2
    }
    $phone = $status.Peer.PSObject.Properties.Value |
        Where-Object { $_.OS -match 'android|ios' } |
        Select-Object -First 1
    if ($phone -and [string]$phone.Online -ne 'True') {
        Write-Log "Handy offline ($($phone.HostName)) - Tailscale-App am Handy oeffnen"
    }
}

function Ensure-StreamlitHealthy {
    $pidFile = Join-Path $env:TEMP 'digiwiki_streamlit.pid'
    $doppelt = Stop-DoppelteStreamlitInstanzen
    if ($doppelt -gt 0) {
        Write-Log "Doppelte Streamlit-Instanzen beendet: $doppelt"
        Start-Sleep -Seconds 2
    }

    $portPid = Get-DigiWikiStreamlitPortPid
    if ($portPid -gt 0) {
        $filePid = ''
        if (Test-Path $pidFile) { $filePid = (Get-Content $pidFile -Raw).Trim() }
        if ($filePid -and ([string]$portPid -ne $filePid)) {
            Write-Log "PID-Datei veraltet ($filePid vs Port $portPid) -> korrigiere"
            Sync-DigiWikiStreamlitPidFile -PidFile $pidFile | Out-Null
        }
    }

    $reach = Get-DigiWikiErreichbarkeit
    Write-DigiWikiErreichbarkeitStatus -Status $reach -Root $root

    $portOpen = $portPid -gt 0
    $localOk = $reach.LokalHealth
    $externOk = $reach.ExternOk

    if ($portOpen -and $localOk -and $externOk) {
        return
    }

    if ($portOpen -and $localOk -and -not $externOk -and $reach.TailscaleDns) {
        Write-Log 'Lokal OK, extern nicht erreichbar -> Tailscale Serve reparieren'
        Repair-DigiWikiTailscaleServe -DnsName $reach.TailscaleDns
        $reach = Get-DigiWikiErreichbarkeit
        if ($reach.ExternOk) {
            Write-Log 'Extern nach Serve-Reparatur OK'
            Write-DigiWikiErreichbarkeitStatus -Status $reach -Root $root
            return
        }
        Write-Log 'Extern weiterhin defekt -> Streamlit neu starten'
    }

    if ($portOpen -and -not $localOk) {
        Write-Log 'Port 8501 offen, aber Health-Check fehlgeschlagen -> Streamlit neu starten'
    } elseif (-not $portOpen) {
        Write-Log 'Port 8501 geschlossen -> Streamlit starten'
    } elseif ($portOpen -and $localOk -and -not $externOk) {
        Write-Log 'Streamlit-Neustart nach fehlgeschlagener Serve-Reparatur'
    }

    Stop-StreamlitOnPort
    if (Test-Path $streamlitStarter) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $streamlitStarter | Out-Null
        Start-Sleep -Seconds 4
        if ($reach.TailscaleDns) {
            Repair-DigiWikiTailscaleServe -DnsName $reach.TailscaleDns
        }
        $reach = Get-DigiWikiErreichbarkeit
        Write-DigiWikiErreichbarkeitStatus -Status $reach -Root $root
        if ($reach.LokalHealth) {
            if ($reach.ExternOk) {
                Write-Log 'Streamlit + externe Erreichbarkeit OK'
            } else {
                Write-Log 'WARNUNG: Streamlit lokal OK, extern weiterhin defekt'
            }
        } else {
            Write-Log 'WARNUNG: Streamlit startet nicht sauber'
        }
    }
}

function Test-HelperRunning {
    $pidFile = Join-Path $env:TEMP 'digiwiki_helper.pid'
    if (Test-Path $pidFile) {
        $hpid = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($hpid -match '^\d+$') {
            $proc = Get-Process -Id ([int]$hpid) -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -match '^powershell') {
                return $true
            }
        }
    }
    $alive = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'digiwiki_helpers\.ps1' } |
        Select-Object -First 1
    return [bool]$alive
}

function Ensure-HelperRunning {
    if (Test-HelperRunning) { return }
    Write-Log 'Watchdog fehlt -> starte digiwiki_helpers.ps1'
    if (Test-Path $helperStarter) {
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $helperStarter 2>&1
        foreach ($line in @($out)) {
            if ($line) { Write-Log "  helper: $line" }
        }
        Start-Sleep -Seconds 2
        if (Test-HelperRunning) {
            Write-Log 'Watchdog gestartet'
        } else {
            Write-Log 'WARNUNG: Watchdog startet nicht'
        }
    }
}

Write-Log '--- Keepalive-Lauf ---'
Ensure-HelperRunning
Ensure-TailscaleOnline
Ensure-StreamlitHealthy
Ensure-HelperRunning
Write-Log 'Keepalive fertig'
