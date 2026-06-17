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

REM --- Bereits aktiv? (ueberspringen mit set DIGIWIKI_FORCE=1) ---
if not defined DIGIWIKI_FORCE (
    tasklist /v /FI "WINDOWTITLE eq DigiWiki-Streamlit*" 2>nul | find /I "cmd.exe" >nul
    if not errorlevel 1 (
        echo.
        echo [HINWEIS] DigiWiki-Streamlit laeuft bereits.
        echo          Browser: http://localhost:8501
        echo          Neu starten: altes Fenster schliessen ODER set DIGIWIKI_FORCE=1
        pause
        exit /b 1
    )
)

REM --- Alte Prozesse beenden ---
echo [INFO] Bereinige alte DigiWiki-Prozesse ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_cleanup.ps1" >nul 2>&1
taskkill /FI "WINDOWTITLE eq DigiWiki-Streamlit*" /F >nul 2>&1
REM Alte (haengende) Haupt-Fenster frueherer Starts schliessen (eigenes Fenster ist noch nicht umbenannt)
taskkill /FI "WINDOWTITLE eq DigiWiki-Haupt*" /F >nul 2>&1

set "INSTANCE_ID=%RANDOM%%RANDOM%"
title DigiWiki-Haupt-!INSTANCE_ID!

REM --- Tailscale ---
echo.
echo [INFO] Tailscale vorbereiten ...
set "TAILSCALE_IP="
set "TAILSCALE_DNS="
set "TAILSCALE_HTTPS="
set "TAILSCALE_ONLINE=False"
for /f "tokens=1,* delims==" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_tailscale_fix.ps1"') do (
    if /i "%%a"=="TAILSCALE_IP" set "TAILSCALE_IP=%%b"
    if /i "%%a"=="TAILSCALE_DNS" set "TAILSCALE_DNS=%%b"
    if /i "%%a"=="TAILSCALE_HTTPS" set "TAILSCALE_HTTPS=%%b"
    if /i "%%a"=="TAILSCALE_ONLINE" set "TAILSCALE_ONLINE=%%b"
)

if not defined TAILSCALE_IP set "TAILSCALE_IP=100.116.74.108"

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

REM --- Helfer (SleepGuard + Tailscale-Keepalive) ---
start "DigiWiki-Helpers" /MIN powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%digiwiki_helpers.ps1" -WatchPid 0

REM --- Streamlit in eigenem, sichtbarem Fenster ---
echo.
echo [INFO] Starte Streamlit-Web-UI (15_wiki_web_ui.py) ...
start "DigiWiki-Streamlit" /MIN /D "%ROOT%" cmd /k call "%ROOT%digiwiki_run_streamlit.bat"

ping 127.0.0.1 -n 6 >nul
start "" "http://localhost:8501"

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
echo  HANDY (von zuhause - NUR DIESE URL IM BROWSER^):
echo     http://!TAILSCALE_IP!:8501
echo.
echo  NICHT die https://desktop-velbert... URL nutzen!
echo  ERR_NAME_NOT_RESOLVED = falscher Hostname / MagicDNS kaputt
echo.
echo  Vor dem Oeffnen: Tailscale-App = Verbunden (gruen)
echo  Android: Privates DNS AUS, Akku-Optimierung Tailscale AUS
echo.
echo  Hinweis: Das minimierte Fenster "DigiWiki-Streamlit" haelt den Server.
echo  Diese Zugangsdaten stehen auch in: digiwiki_zugang.txt
echo ============================================================
echo.

REM --- Zugangsdaten in Datei sichern (bleibt verfuegbar, auch nachdem dieses Fenster schliesst) ---
(
    echo DigiWiki - Zugang
    echo Stand: %date% %time%
    echo.
    echo PC ^(lokal^):         http://localhost:8501
    if defined LAN_IP echo PC ^(WLAN/Netzwerk^): http://!LAN_IP!:8501  ^(IP: !LAN_IP!^)
    echo HANDY - NUR DIESE URL ^(Lesezeichen^):
    echo   http://!TAILSCALE_IP!:8501
    echo.
    echo NICHT https://desktop-velbert... ^(MagicDNS, bricht alle 10 Min ab^)
    echo ERR_NAME_NOT_RESOLVED = Hostname-URL benutzt, nicht IP!
    echo.
    echo Vorher: Tailscale-App verbunden. Privates DNS AUS.
    if defined LAN_IP echo PC ^(WLAN^): http://!LAN_IP!:8501  ^(nur gleiches WLAN^)
) > "%ROOT%digiwiki_zugang.txt"

REM --- Einfache HTML-Weiterleitung fuer Handy-Lesezeichen (ohne DNS) ---
(
    echo ^<!DOCTYPE html^>
    echo ^<html^>^<head^>^<meta charset="utf-8"^>^<title^>DigiWiki^</title^>^</head^>
    echo ^<body style="font-family:sans-serif;text-align:center;margin-top:3em"^>
    echo ^<h2^>DigiWiki^</h2^>
    echo ^<p^>^<a href="http://!TAILSCALE_IP!:8501" style="font-size:1.4em"^>App oeffnen^</a^>^</p^>
    echo ^<p style="color:#666"^>Tailscale am Handy muss verbunden sein.^</p^>
    echo ^</body^>^</html^>
) > "%ROOT%digiwiki_handy.html"

echo [INFO] Dieses Fenster schliesst sich in 15 Sekunden automatisch ...
timeout /t 15 /nobreak >nul
exit
