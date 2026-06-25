# Verhindert PC-Ruhezustand am Netzstrom (DigiWiki-Server).
# Der laufende Watchdog (digiwiki_helpers.ps1) haelt zusaetzlich per API wach.
$ErrorActionPreference = 'SilentlyContinue'

function Set-AcTimeout {
    param([string]$Setting, [int]$Minutes)
    powercfg /change $Setting $Minutes 2>$null | Out-Null
}

# 0 = nie (nur am Netzstrom)
Set-AcTimeout 'standby-timeout-ac' 0
Set-AcTimeout 'monitor-timeout-ac' 0
Set-AcTimeout 'hibernate-timeout-ac' 0

Write-Host 'SLEEP_GUARD_AC=OK'
Write-Host 'Hinweis: Bildschirm/Standby am Netzstrom aus. Watchdog verhindert zusaetzlich System-Sleep.'
