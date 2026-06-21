param(
    [Parameter(Mandatory = $true)][string]$TailscaleIp,
    [string]$TailscaleHttps = '',
    [string]$LanIp = '',
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$ipUrl = "http://${TailscaleIp}:8501"
$primaryUrl = $ipUrl
$zugangPath = Join-Path $Root 'digiwiki_zugang.txt'
$htmlPath = Join-Path $Root 'digiwiki_handy.html'
$stand = Get-Date -Format 'dd.MM.yyyy HH:mm'

$lines = @(
    'DigiWiki - Zugang',
    "Stand: $stand",
    '',
    'PC (lokal):         http://localhost:8501'
)
if ($LanIp) {
    $lines += "PC (WLAN/Netzwerk): http://${LanIp}:8501  (nur gleiches WLAN)"
}
$lines += @(
    '',
    'HANDY (Lesezeichen - Tailscale muss verbunden sein):',
    "  PRIMAER:  $primaryUrl",
    '  (IP-Adresse - funktioniert OHNE DNS, deshalb stabil auf Android.)'
)
if ($TailscaleHttps) {
    $lines += "  Optional: $TailscaleHttps  (nur wenn Tailscale-DNS am Handy aktiv ist)"
}
$lines += @(
    '',
    'Wenn Browser meldet "Adresse nicht gefunden":',
    '  -> PRIMAER-URL oben nutzen (http://100.x.x.x:8501), NICHT die https://...ts.net URL',
    '  -> Android: Einstellungen -> Netzwerk -> Privates DNS -> AUS',
    '',
    'WICHTIG am Handy:',
    '  - In Chrome/Safari oeffnen (keine Link-Vorschau aus WhatsApp).',
    '  - Tailscale-App ZUERST auf Verbunden (gruen).',
    '',
    'Checkliste Handy:',
    '  1. Tailscale-App = Verbunden (gruen), VOR dem Browser',
    '  2. Android: Privates DNS AUS, Akku Tailscale uneingeschraenkt',
    '  3. Bei Timeout: Flugmodus kurz an/aus, Tailscale neu verbinden'
)

Set-Content -Path $zugangPath -Value ($lines -join "`r`n") -Encoding UTF8

$httpsNote = if ($TailscaleHttps) {
    "<p style=`"color:#666;font-size:0.9em`">Optional (nur mit Tailscale-DNS): <a href=`"$TailscaleHttps`">$TailscaleHttps</a></p>"
} else { '' }

$html = @"
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DigiWiki</title>
<meta http-equiv="refresh" content="0;url=$primaryUrl">
</head>
<body style="font-family:sans-serif;text-align:center;margin-top:3em;padding:1em">
<h2>DigiWiki</h2>
<p><a href="$primaryUrl" style="font-size:1.4em">App oeffnen</a></p>
<p style="color:#666">Tailscale am Handy muss verbunden sein.<br>
URL beginnt mit <b>http://100.</b> und endet mit <b>:8501</b></p>
$httpsNote
</body></html>
"@
Set-Content -Path $htmlPath -Value $html -Encoding UTF8

Write-Host "HANDY_URL=$primaryUrl"
