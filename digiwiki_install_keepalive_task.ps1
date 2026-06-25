# Geplanten Task fuer digiwiki_keepalive.ps1 anlegen (Pfad-sicher).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $root 'digiwiki_keepalive.ps1'
$taskName = 'DigiWiki Keepalive'

if (-not (Test-Path $script)) {
    Write-Host "FEHLER: $script nicht gefunden"
    exit 1
}

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    try {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
    } catch {
        Write-Host "HINWEIS: Task-Update braucht Admin-Rechte. Bitte install_dauerbetrieb.bat als Administrator ausfuehren."
        Write-Host "       Bestehender Task bleibt aktiv (ggf. noch alle 5 Min)."
        exit 0
    }
}

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" -Quiet"

$triggerLogon = New-ScheduledTaskTrigger -AtLogOn
$triggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 2) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger @($triggerLogon, $triggerRepeat) `
    -Settings $settings `
    -Description 'DigiWiki: Watchdog + Tailscale + Streamlit alle 2 Min, sofort beim Login' `
    -RunLevel Limited | Out-Null

Write-Host "OK: Task '$taskName' beim Login + alle 2 Minuten aktiv"
Write-Host "Log: $(Join-Path $root 'digiwiki_keepalive.log')"
