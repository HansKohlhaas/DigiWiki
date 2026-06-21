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
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" -Quiet"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description 'DigiWiki: Tailscale + Streamlit alle 5 Min pruefen/reparieren' `
    -RunLevel Limited | Out-Null

Write-Host "OK: Task '$taskName' alle 5 Minuten aktiv"
Write-Host "Log: $(Join-Path $root 'digiwiki_keepalive.log')"
