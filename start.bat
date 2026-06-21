@echo off
setlocal EnableDelayedExpansion

REM ===== DigiWiki Start: Streamlit 15_wiki_web_ui.py + Tailscale =====

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PYTHON=%ROOT%.venv\Scripts\python.exe"
set "APP=%ROOT%15_wiki_web_ui.py"

if not exist "%APP%" (
    echo.
    echo [FEHLER] Datei fehlt: %APP%
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    echo.
    echo [FEHLER] Python fehlt: %PYTHON%
    pause
    exit /b 1
)

if not exist "%ROOT%digiwiki_run_streamlit.bat" (
    echo.
    echo [FEHLER] Datei fehlt: %ROOT%digiwiki_run_streamlit.bat
    pause
    exit /b 1
)

REM --- Aus PowerShell-Terminal: eigenes CMD-Fenster oeffnen (nicht hinter PS verstecken) ---
if not defined DIGIWIKI_DETACHED (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_relaunch_if_ps.ps1" -BatPath "%~f0" -Root "%ROOT%"
    if not errorlevel 1 exit /b 0
)

REM --- Parallelen Start verhindern (Doppel-/Dreifach-Klick, Task + manuell) ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_start_lock.ps1" >nul 2>&1
if errorlevel 2 (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_port_frei.ps1" >nul 2>&1
    if not errorlevel 1 (
        echo.
        echo [HINWEIS] DigiWiki laeuft bereits - pruefe/repariere Verbindung ...
        powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_keepalive.ps1" -Quiet
        powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_start_helper.ps1" >nul 2>&1
        timeout /t 3 /nobreak >nul
        start "" "http://localhost:8501"
        exit /b 0
    )
    echo [INFO] Alte Start-Sperre ohne laufenden Server – starte neu ...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_start_lock.ps1" -Action Release >nul 2>&1
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_start_lock.ps1" >nul 2>&1
)

REM --- Alte Prozesse beenden (immer zuerst, auch bei Neustart) ---
echo [INFO] Bereinige alte DigiWiki-Prozesse ...
for /f "tokens=2 delims==" %%n in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_cleanup.ps1" 2^>nul ^| findstr /B "STOPPED="') do set "CLEANUP_COUNT=%%n"
if defined CLEANUP_COUNT (
    if !CLEANUP_COUNT! GTR 0 (
        echo [OK] !CLEANUP_COUNT! alte Prozess(e^) beendet.
    ) else (
        echo [OK] Keine alten Prozesse gefunden.
    )
)
ping 127.0.0.1 -n 3 >nul

REM Port 8501 muss frei sein – sonst zweite Instanz / Connection-Fehler
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_port_frei.ps1" >nul 2>&1
if errorlevel 1 (
    echo [WARNUNG] Port 8501 noch belegt – zweiter Bereinigungslauf ...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_cleanup.ps1" >nul 2>&1
    ping 127.0.0.1 -n 3 >nul
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_port_frei.ps1"
    if errorlevel 1 (
        echo [FEHLER] Port 8501 blockiert. Task-Manager: python.exe beenden, dann erneut starten.
        powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_start_lock.ps1" -Action Release >nul 2>&1
        pause
        exit /b 1
    )
)

set "INSTANCE_ID=%RANDOM%%RANDOM%"
title DigiWiki-Haupt-!INSTANCE_ID!

REM --- Tailscale ---
echo.
echo [INFO] Tailscale vorbereiten ...
set "TAILSCALE_IP="
set "TAILSCALE_DNS="
set "TAILSCALE_HTTPS="
set "TAILSCALE_HANDY_URL="
set "TAILSCALE_ONLINE=False"
for /f "tokens=1,* delims==" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_tailscale_fix.ps1"') do (
    if /i "%%a"=="TAILSCALE_IP" set "TAILSCALE_IP=%%b"
    if /i "%%a"=="TAILSCALE_DNS" set "TAILSCALE_DNS=%%b"
    if /i "%%a"=="TAILSCALE_HTTPS" set "TAILSCALE_HTTPS=%%b"
    if /i "%%a"=="TAILSCALE_HANDY_URL" set "TAILSCALE_HANDY_URL=%%b"
    if /i "%%a"=="TAILSCALE_ONLINE" set "TAILSCALE_ONLINE=%%b"
)

if not defined TAILSCALE_IP (
    echo [WARNUNG] Tailscale-IP nicht ermittelt – Handy-Zugriff evtl. nicht moeglich.
) else if not defined TAILSCALE_HANDY_URL (
    if defined TAILSCALE_HTTPS (
        set "TAILSCALE_HANDY_URL=!TAILSCALE_HTTPS!"
    ) else (
        set "TAILSCALE_HANDY_URL=http://!TAILSCALE_IP!:8501"
    )
)

echo [OK] Tailscale-IP: !TAILSCALE_IP!
if defined TAILSCALE_DNS echo [OK] MagicDNS: !TAILSCALE_DNS!

REM --- Firewall Port 8501 ---
netsh advfirewall firewall show rule name="DigiWiki Streamlit 8501" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Firewall-Regel Port 8501 anlegen ...
    netsh advfirewall firewall add rule name="DigiWiki Streamlit 8501" dir=in action=allow protocol=TCP localport=8501 profile=any >nul
)

REM --- Lokale WLAN/Netzwerk-IP ermitteln (fuer PC-Zugriff im eigenen Netz) ---
set "LAN_IP="
for /f "delims=" %%i in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -notlike '100.*' } | Sort-Object InterfaceMetric | Select-Object -First 1).IPAddress"') do set "LAN_IP=%%i"

REM --- Helfer (SleepGuard + Tailscale/Streamlit-Watchdog, max. 1 Instanz) ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_start_helper.ps1" >nul 2>&1

REM --- Streamlit: EINE Instanz im Hintergrund (kein zweites CMD-Fenster) ---
echo.
echo [INFO] Starte Streamlit-Web-UI (15_wiki_web_ui.py) ...
for /f "tokens=1,2 delims==" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_start_streamlit.ps1" 2^>^&1') do (
    if /i "%%a"=="STARTED" set "STREAMLIT_PID=%%b"
    if /i "%%a"=="ERROR" set "STREAMLIT_ERR=%%b"
)
if defined STREAMLIT_ERR (
    if "!STREAMLIT_ERR!"=="PORT_BELEGT" (
        echo [HINWEIS] Streamlit laeuft bereits auf Port 8501.
    ) else if "!STREAMLIT_ERR!"=="BEREITS_LAUFEND" (
        echo [HINWEIS] Streamlit-Prozess laeuft bereits.
    ) else (
        echo [FEHLER] Streamlit konnte nicht starten: !STREAMLIT_ERR!
        echo          Siehe digiwiki_run_streamlit.bat fuer manuellen Start.
    )
) else if defined STREAMLIT_PID (
    echo [OK] Streamlit gestartet ^(PID !STREAMLIT_PID!^)
)

echo [INFO] Warte auf Streamlit (Port 8501) ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_warte_port.ps1" -Sekunden 45
if errorlevel 1 (
    echo [WARNUNG] Streamlit antwortet noch nicht. Log pruefen oder digiwiki_run_streamlit.bat manuell.
) else (
    start "" "http://localhost:8501"
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_start_lock.ps1" -Action Release >nul 2>&1

echo.
echo ============================================================
echo  FERTIG - DigiWiki Web-UI
echo.
echo  PC (lokal):
echo     IP:  127.0.0.1
echo     URL: http://localhost:8501
if defined LAN_IP (
    echo  PC (WLAN/Netzwerk^):
    echo     IP:  !LAN_IP!
    echo     URL: http://!LAN_IP!:8501
)
echo.
echo  HANDY (von zuhause - Tailscale verbunden^):
if defined TAILSCALE_HTTPS (
    echo     PRIMAER:  !TAILSCALE_HTTPS!
    echo     Fallback: http://!TAILSCALE_IP!:8501
) else (
    echo     PRIMAER:  !TAILSCALE_HANDY_URL!
)
echo     ^(In Chrome oeffnen – keine Link-Vorschau/WhatsApp-Vorschau^)
echo.
echo  WICHTIG: Zuerst Tailscale-App oeffnen = Verbunden ^(gruen^)!
echo  Diese IP-URL als Lesezeichen speichern ^(digiwiki_zugang.txt^).
echo  Android: Privates DNS AUS, Akku-Optimierung Tailscale AUS
echo.
echo  Hinweis: Streamlit laeuft im Hintergrund (kein zweites Fenster).
echo  Debug mit sichtbarem Fenster: digiwiki_run_streamlit.bat
echo  Keepalive-Task (empfohlen): install_keepalive_task.bat
echo ============================================================
echo.

REM --- Zugangsdaten fuer Handy-Lesezeichen ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_write_zugang.ps1" -TailscaleIp "!TAILSCALE_IP!" -TailscaleHttps "!TAILSCALE_HTTPS!" -LanIp "!LAN_IP!" -Root "%ROOT%" >nul 2>&1

echo  Diese Zugangsdaten stehen auch in: digiwiki_zugang.txt
echo  Handy-Lesezeichen-Datei: digiwiki_handy.html

echo [INFO] Dieses Fenster schliesst sich in 15 Sekunden automatisch ...
ping 127.0.0.1 -n 16 >nul
exit
