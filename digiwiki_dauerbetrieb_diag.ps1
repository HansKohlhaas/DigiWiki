# Diagnose: Dauerbetrieb, Hintergrundprozesse, Erreichbarkeit (lokal + Tailscale).
param(
    [switch]$Save
)

$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $root 'digiwiki_erreichbarkeit.ps1')

$out = New-Object System.Collections.Generic.List[string]
function Add-Line { param([string]$Text) $out.Add($Text); Write-Host $Text }

Add-Line "============================================================"
Add-Line "DigiWiki Dauerbetrieb-Diagnose  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Add-Line "============================================================"
Add-Line ""

Add-Line "=== Geplante Tasks (DigiWiki) ==="
$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskName -like 'DigiWiki*' }
if ($tasks) {
    foreach ($t in $tasks) {
        $info = Get-ScheduledTaskInfo -TaskName $t.TaskName -ErrorAction SilentlyContinue
        $last = if ($info.LastRunTime) { $info.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss') } else { '-' }
        $res = if ($info.LastTaskResult -ne $null) { $info.LastTaskResult } else { '-' }
        Add-Line ("  {0,-28} State={1,-10} LastRun={2} Result={3}" -f $t.TaskName, $t.State, $last, $res)
    }
} else {
    Add-Line "  (keine Tasks gefunden)"
}

$needKeepalive = -not ($tasks | Where-Object { $_.TaskName -eq 'DigiWiki Keepalive' -and $_.State -eq 'Ready' })
$needAutostart = -not ($tasks | Where-Object { $_.TaskName -eq 'DigiWiki Streamlit' -and $_.State -eq 'Ready' })
if ($needKeepalive -or $needAutostart) {
    Add-Line ""
    Add-Line "  *** HINWEIS: Dauerbetrieb unvollstaendig! ***"
    if ($needKeepalive) { Add-Line "      Fehlt/inaktiv: DigiWiki Keepalive (alle 2 Min Reparatur)" }
    if ($needAutostart) { Add-Line "      Fehlt/inaktiv: DigiWiki Streamlit (Autostart beim Login)" }
    Add-Line "      -> install_dauerbetrieb.bat als Administrator ausfuehren"
}

Add-Line ""
Add-Line "=== Port 8501 / Streamlit ==="
$portPid = Get-DigiWikiStreamlitPortPid
$pidFile = Join-Path $env:TEMP 'digiwiki_streamlit.pid'
$filePid = ''
if (Test-Path $pidFile) { $filePid = (Get-Content $pidFile -Raw).Trim() }
Add-Line "  Port-PID:      $portPid"
Add-Line "  PID-Datei:     $filePid"
if ($portPid -gt 0 -and $filePid -and ([string]$portPid -ne $filePid)) {
    Add-Line "  *** WARNUNG: PID-Datei passt nicht zum Port (veraltet) ***"
}
if ($portPid -gt 0) {
    $proc = Get-Process -Id $portPid -ErrorAction SilentlyContinue
    if ($proc) {
        Add-Line ("  Prozess:       {0} seit {1}" -f $proc.ProcessName, $proc.StartTime)
    }
    $wmi = Get-CimInstance Win32_Process -Filter "ProcessId=$portPid" -ErrorAction SilentlyContinue
    if ($wmi -and $wmi.CommandLine) {
        $cmd = [string]$wmi.CommandLine
        if ($cmd.Length -gt 120) { $cmd = $cmd.Substring(0, 117) + '...' }
        Add-Line "  Kommando:      $cmd"
    }
} else {
    Add-Line "  Kein Listener auf Port 8501"
}

Add-Line ""
Add-Line "=== Watchdog (digiwiki_helpers.ps1) ==="
$helperPidFile = Join-Path $env:TEMP 'digiwiki_helper.pid'
$helperOk = $false
if (Test-Path $helperPidFile) {
    $hpid = (Get-Content $helperPidFile -Raw).Trim()
    Add-Line "  PID-Datei:     $hpid"
    if ($hpid -match '^\d+$') {
        $hproc = Get-Process -Id ([int]$hpid) -ErrorAction SilentlyContinue
        if ($hproc -and $hproc.ProcessName -match '^powershell') {
            $helperOk = $true
            Add-Line ("  Laeuft:        ja (seit {0})" -f $hproc.StartTime)
        }
    }
}
if (-not $helperOk) {
    $alive = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'digiwiki_helpers\.ps1' } |
        Select-Object -First 1
    if ($alive) {
        Add-Line ("  Laeuft:        ja (PID {0}, ohne PID-Datei)" -f $alive.ProcessId)
        $helperOk = $true
    } else {
        Add-Line "  Laeuft:        NEIN ***"
        Add-Line "      -> Kein Watchdog: Tailscale/Streamlit werden nicht laufend repariert"
    }
}

Add-Line ""
Add-Line "=== Weitere DigiWiki-Hintergrundprozesse ==="
$bg = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^(python|pythonw|powershell|cmd)\.exe$' -and
        [string]$_.CommandLine -match 'digiwiki_|15_wiki_web_ui|streamlit run|9_wiki_waechter'
    }
if ($bg) {
    foreach ($p in $bg) {
        $cmd = [string]$p.CommandLine
        if ($cmd.Length -gt 100) { $cmd = $cmd.Substring(0, 97) + '...' }
        Add-Line ("  PID {0,-6} {1}" -f $p.ProcessId, $cmd)
    }
    $stCount = @($bg | Where-Object { [string]$_.CommandLine -match 'streamlit\s+run' }).Count
    $stRoots = @(Get-DigiWikiStreamlitRootPids)
    if ($stRoots.Count -gt 1) {
        Add-Line ""
        Add-Line "  *** WARNUNG: $($stRoots.Count) Streamlit-Instanzen parallel (Konflikt!) ***"
        Add-Line "      -> start.bat oder digiwiki_keepalive.ps1 ausfuehren"
    } elseif ($stCount -gt 1 -and $stRoots.Count -le 1) {
        Add-Line ""
        Add-Line "  Hinweis: $stCount Streamlit-Prozesse = 1 Instanz (venv-Launcher + Server, normal)"
    }
} else {
    Add-Line "  (keine weiteren gefunden)"
}

Add-Line ""
Add-Line "=== Erreichbarkeit ==="
$status = Get-DigiWikiErreichbarkeit
Add-Line ("  Lokal Health:        {0}" -f $(if ($status.LokalHealth) { 'OK' } else { 'FEHLER' }))
Add-Line ("  Tailscale DNS:       {0}" -f $(if ($status.TailscaleDns) { $status.TailscaleDns } else { '(offline)' }))
Add-Line ("  Remote Health HTTPS: {0}" -f $(if ($status.RemoteHealth) { 'OK' } else { 'FEHLER' }))
Add-Line ("  Remote WebSocket:    {0}" -f $(if ($status.RemoteWebSocket) { 'OK' } else { 'FEHLER' }))
if ($status.LokalHealth -and -not $status.ExternOk) {
    Add-Line ""
    Add-Line "  *** Typisches Problem: lokal OK, von aussen nicht erreichbar ***"
    Add-Line "      (Tailscale Serve haengt oder Streamlit-Zombie - Neustart/reparieren noetig)"
}
Write-DigiWikiErreichbarkeitStatus -Status $status -Root $root

Add-Line ""
Add-Line "=== Tailscale ==="
try {
    $ts = tailscale status 2>$null
    if ($ts) { $ts | ForEach-Object { Add-Line "  $_" } }
} catch {
    Add-Line "  tailscale status nicht verfuegbar"
}
try {
    $serve = tailscale serve status 2>$null
    if ($serve) { $serve | ForEach-Object { Add-Line "  $_" } }
} catch {}

Add-Line ""
Add-Line "=== Energie / Sleep (Netzstrom) ==="
try {
    $ac = powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 2>$null | Select-String 'Aktuelle Wechselstrom'
    $dc = powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 2>$null | Select-String 'Aktuelle Gleichstrom'
    if ($ac) { Add-Line "  $ac" }
    if ($dc) { Add-Line "  $dc" }
} catch {}

Add-Line ""
Add-Line "=== Letzte Keepalive-Logzeilen ==="
$logFile = Join-Path $root 'digiwiki_keepalive.log'
if (Test-Path $logFile) {
    Get-Content $logFile -Tail 15 -Encoding UTF8 | ForEach-Object { Add-Line "  $_" }
} else {
    Add-Line "  (keine digiwiki_keepalive.log - Keepalive-Task vermutlich nie gelaufen)"
}

Add-Line ""
Add-Line "=== Empfohlene Sofortmassnahme ==="
if ($needKeepalive -or $needAutostart -or -not $helperOk) {
    Add-Line "  1. install_dauerbetrieb.bat als Administrator"
}
if (-not $status.GesamtOk) {
    Add-Line "  2. digiwiki_keepalive.ps1 ausfuehren (oder start.bat)"
}
Add-Line "============================================================"

if ($Save) {
    $ziel = Join-Path $root 'digiwiki_dauerbetrieb_diag.txt'
    $out -join "`r`n" | Set-Content -Path $ziel -Encoding UTF8
    Add-Line "Gespeichert: $ziel"
}
