@echo off
setlocal EnableDelayedExpansion

REM DigiWiki Streamlit - Startskript (LAN + Tailscale vom Handy)

REM ============================================================================
REM DAUERBETRIEB-CHECKLISTE (Handy via Tailscale IN)
REM ----------------------------------------------------------------------------
REM Android: Tailscale-App NICHT beenden; Hintergrund + Batterie-Optimierung
REM   fuer Tailscale ausschalten. Bookmark: MagicDNS-URL (IP nicht mischen).
REM PC: Tailscale-Dienst auf Automatisch; dieses Fenster offen lassen.
REM PC-Schlaf: SleepGuard laeuft - Energieoptionen trotzdem auf "Nie" pruefen.
REM Tailscale-Key: Auth-Key-Ablauf in Admin-Console; vor Ablauf erneuern.
REM Leerlauf: Tab neu laden ist NORMAL (WebSocket-Sleep), kein Fehler.
REM RouteAll ohne Exit-Node: HINWEIS unten oder set DIGIWIKI_AUTO_ROUTEALL_OFF=1
REM Autostart beim Login: einmalig install_autostart.bat ausfuehren
REM Hintergrund-Helfer: max. 1 PowerShell (SleepGuard + Tailscale-Keepalive).
REM   Beim Schliessen dieses Fensters beendet sich der Helfer automatisch.
REM ============================================================================

cd /d "%~dp0"

call .venv\Scripts\activate
if errorlevel 1 (
    echo [FEHLER] Virtuelle Umgebung .venv nicht gefunden.
    pause
    exit /b 1
)

REM --- Alte Hintergrund-Helfer beenden (verhindert PowerShell-Ansammlung) ---
call :kill_digiwiki_helpers

REM --- Einzelinstanz: nur ein start.bat gleichzeitig ---
set "LOCK_FILE=%TEMP%\DigiWiki_streamlit.lock"
if exist "%LOCK_FILE%" (
    set /p OLD_PID=<"%LOCK_FILE%"
    tasklist /FI "PID eq !OLD_PID!" 2>nul | find /I "cmd.exe" >nul
    if not errorlevel 1 (
        echo [FEHLER] DigiWiki laeuft bereits ^(PID !OLD_PID!^).
        echo          Bestehendes Fenster nutzen oder dort beenden.
        pause
        exit /b 1
    )
    del "%LOCK_FILE%" >nul 2>&1
)

set "INSTANCE_ID=%RANDOM%%RANDOM%"
title DigiWiki-Streamlit-!INSTANCE_ID!

set "MAIN_PID="
REM Primaer: Parent-PID des kurz gestarteten PowerShell-Helfers (= dieses cmd-Fenster)
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "try{$pp=(Get-CimInstance Win32_Process -Filter ('ProcessId=' + $PID)).ParentProcessId;if($pp -gt 0){$pp}else{''}}catch{''}" 2^>nul`) do (
    if not defined MAIN_PID set "MAIN_PID=%%p"
)
REM Fallback: Fenstertitel (tasklist zeigt oft "Nicht zutreffend" ohne echtes Konsolenfenster)
if not defined MAIN_PID (
    for /f "tokens=2 delims=," %%p in ('tasklist /fi "imagename eq cmd.exe" /fo csv /v /nh 2^>nul ^| findstr /C:"DigiWiki-Streamlit-!INSTANCE_ID!"') do (
        if not defined MAIN_PID set "MAIN_PID=%%~p"
    )
)

set "HELPER_WATCH_PID=!MAIN_PID!"
if not defined MAIN_PID (
    echo [WARNUNG] Eigene Prozess-ID nicht ermittelt - Helfer ohne Fenster-Wacht.
    set "HELPER_WATCH_PID=0"
) else (
    echo !MAIN_PID!>"%LOCK_FILE%"
)

REM --- Tailscale: Tunnel fuer eingehende Handy-Verbindung pruefen/verbinden ---
set "TAILSCALE_IP="
set "TAILSCALE_DNS="
set "TAILSCALE_OK=0"
set "TAILSCALE_ONLINE=False"

sc query Tailscale 2>nul | find "RUNNING" >nul
if errorlevel 1 (
    echo [INFO] Tailscale-Dienst starten ...
    sc start Tailscale >nul 2>&1
    timeout /t 3 /nobreak >nul
)

call :ts_read_ip
if not defined TAILSCALE_IP (
    echo [INFO] Keine Tailscale-IP - versuche tailscale up ...
    tailscale up >nul 2>&1
    timeout /t 4 /nobreak >nul
    call :ts_read_ip
)

if not defined TAILSCALE_IP (
    if defined DIGIWIKI_TAILSCALE_IP (
        set "TAILSCALE_IP=!DIGIWIKI_TAILSCALE_IP!"
    ) else (
        set "TAILSCALE_IP=100.116.74.108"
    )
    echo [WARN] Tailscale-IP nicht live ermittelt - Fallback: !TAILSCALE_IP!
    echo        Optional: set DIGIWIKI_TAILSCALE_IP=100.x.x.x
) else (
    echo [OK] Tailscale-IP: !TAILSCALE_IP!
)

for /f "usebackq delims=" %%h in (`powershell -NoProfile -Command "try{(tailscale status --json|ConvertFrom-Json).Self.DNSName.TrimEnd('.')}catch{''}" 2^>nul`) do set "TAILSCALE_DNS=%%h"
for /f "usebackq delims=" %%o in (`powershell -NoProfile -Command "try{[string](tailscale status --json|ConvertFrom-Json).Self.Online}catch{'False'}" 2^>nul`) do set "TAILSCALE_ONLINE=%%o"

echo !TAILSCALE_IP!| findstr /r "^100\." >nul 2>&1
if not errorlevel 1 if /i "!TAILSCALE_ONLINE!"=="True" set "TAILSCALE_OK=1"

if "!TAILSCALE_OK!"=="0" (
    echo.
    echo ============================================================
    echo  [WARNUNG] Eingehende Handy-Verbindung ueber Tailscale UNKLAR
    echo ============================================================
    echo !TAILSCALE_IP!| findstr /r "^100\." >nul 2>&1
    if errorlevel 1 (
        echo  - PC hat keine gueltige Tailscale-IP ^(100.x.x.x^).
        echo    Dienst: Win+R services.msc -^> Tailscale auf Automatisch
    )
    if /i not "!TAILSCALE_ONLINE!"=="True" (
        echo  - PC ist im Tailnet als OFFLINE gemeldet.
        echo    Tailscale oeffnen oder: tailscale up
    )
    echo  - Kein Internetzugriff am Tailscale-Adapter ist NORMAL
    echo    ^(nur Tailnet, kein oeffentliches Internet - kein Fehler^).
    echo  - Am Handy: Tailscale-App aktiv lassen ^(nicht beenden^).
    echo  - Bei Wackeln: MagicDNS statt IP nutzen ^(siehe URL unten^).
    echo ============================================================
    echo.
) else (
    echo [OK] Tailscale bereit fuer eingehende Verbindungen.
    if defined TAILSCALE_DNS echo [OK] MagicDNS ^(empfohlen^): !TAILSCALE_DNS!
)

for /f "usebackq delims=" %%r in (`powershell -NoProfile -Command "try{$p=(tailscale debug prefs|ConvertFrom-Json);if($p.RouteAll -and -not $p.ExitNodeID){'1'}else{''}}catch{''}" 2^>nul`) do (
    if "%%r"=="1" (
        if "!DIGIWIKI_AUTO_ROUTEALL_OFF!"=="1" (
            echo [INFO] RouteAll ohne Exit-Node - deaktiviere ^(DIGIWIKI_AUTO_ROUTEALL_OFF^) ...
            tailscale set --route-all=false >nul 2>&1
        ) else (
            echo [HINWEIS] Tailscale RouteAll aktiv, aber kein Exit-Node - ggf. instabil.
            echo         Optional: tailscale set --route-all=false
            echo         Oder dauerhaft: set DIGIWIKI_AUTO_ROUTEALL_OFF=1 vor start.bat
        )
    )
)

netsh advfirewall firewall show rule name="DigiWiki Streamlit 8501" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall show rule name="Streamlit Tailscale Open" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Erstelle Firewall-Regel fuer Port 8501 ...
        netsh advfirewall firewall add rule name="DigiWiki Streamlit 8501" dir=in action=allow protocol=TCP localport=8501 profile=any >nul
    )
)

start "DigiWiki-Helpers" /MIN powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0digiwiki_helpers.ps1" -WatchPid !HELPER_WATCH_PID!

echo.
echo ============================================================
echo  Am PC (lokal):         http://localhost:8501
if defined TAILSCALE_DNS (
    echo  Vom Handy ^(EMPFOHLEN^):  http://!TAILSCALE_DNS!^:8501
    echo  Alternative ^(IP^):       http://!TAILSCALE_IP!^:8501
    echo  Immer dieselbe URL nutzen ^(MagicDNS^) - IP/DNS nicht mischen.
) else (
    echo  Vom Handy ^(Tailscale^): http://!TAILSCALE_IP!^:8501
)
if "!TAILSCALE_OK!"=="0" echo  *** Handy-Zugriff evtl. instabil - Tailscale-Warnung oben ***
echo  DAUERBETRIEB: MagicDNS bookmarken ^| Tailscale-App am Handy offen
echo  Android: Batterie-Optimierung fuer Tailscale ausschalten
echo  Nach Leerlauf: Tab neu laden ^(normal^). PC-Schlaf: Energieoptionen pruefen
echo  Tailscale-Key-Ablauf beachten. Fenster offen ^| Auto-Neustart nach 5 s
echo  Zum Beenden: Fenster schliessen ^(Helfer-Prozesse werden beendet^)
echo ============================================================
echo.

:restart
echo [%date% %time%] Starte Streamlit ...
python -m streamlit run 15_wiki_web_ui.py --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false --server.enableWebsocketCompression false --server.websocketPingInterval 30 --server.disconnectedSessionTTL 3600 --browser.serverAddress localhost
echo [%date% %time%] Streamlit beendet. Neustart in 5 Sekunden ...
timeout /t 5 /nobreak >nul
goto restart

:kill_digiwiki_helpers
if exist "%TEMP%\digiwiki_helper.pid" (
    set /p HELPER_PID=<"%TEMP%\digiwiki_helper.pid"
    if defined HELPER_PID taskkill /PID !HELPER_PID! /F >nul 2>&1
    del "%TEMP%\digiwiki_helper.pid" >nul 2>&1
)
taskkill /FI "WINDOWTITLE eq DigiWiki-Helpers*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq DigiWiki-SleepGuard*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq DigiWiki-TailscaleKeepalive*" /F >nul 2>&1
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -match 'digiwiki_helpers\.ps1|SetThreadExecutionState|tailscale status \| Out-Null' } | ForEach-Object { $_.ProcessId }" 2^>nul`) do (
    taskkill /PID %%p /F >nul 2>&1
)
exit /b 0

:ts_read_ip
set "TAILSCALE_IP="
for /f "usebackq delims=" %%i in (`tailscale ip -4 2^>nul`) do (
    echo %%i| findstr /r "^100\." >nul 2>&1 && set "TAILSCALE_IP=%%i"
)
exit /b 0

