# Einmaliger Health-Check + Reparatur (Streamlit, Tailscale, Helfer).
# Wird alle 5 Min per Task Scheduler aufgerufen und bei start.bat "laeuft bereits".
param(
    [switch]$Quiet
)

$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
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
    try {
        $code = (& curl.exe -sS -o NUL -w '%{http_code}' --max-time 8 'http://127.0.0.1:8501/_stcore/health' 2>$null)
        return ($code -eq '200')
    } catch {
        return $false
    }
}

function Stop-StreamlitOnPort {
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

function Ensure-TailscaleOnline {
    $svc = Get-Service -Name 'Tailscale' -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne 'Running') {
        Write-Log 'Tailscale-Dienst gestoppt -> starte neu'
        Start-Service -Name 'Tailscale' -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
    }
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
    }
}

function Ensure-StreamlitHealthy {
    $portOpen = [bool](Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)
    if ($portOpen -and (Test-StreamlitHealthy)) {
        return
    }
    if ($portOpen) {
        Write-Log 'Port 8501 offen, aber Health-Check fehlgeschlagen -> Streamlit neu starten'
    } else {
        Write-Log 'Port 8501 geschlossen -> Streamlit starten'
    }
    Stop-StreamlitOnPort
    if (Test-Path $streamlitStarter) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $streamlitStarter | Out-Null
        Start-Sleep -Seconds 3
        if (Test-StreamlitHealthy) {
            Write-Log 'Streamlit nach Neustart OK'
        } else {
            Write-Log 'WARNUNG: Streamlit startet nicht sauber'
        }
    }
}

function Ensure-HelperRunning {
    if (Test-Path $helperStarter) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $helperStarter | Out-Null
    }
}

Write-Log '--- Keepalive-Lauf ---'
Ensure-TailscaleOnline
Ensure-StreamlitHealthy
Ensure-HelperRunning
Write-Log 'Keepalive fertig'
