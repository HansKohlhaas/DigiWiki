@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo.
echo ============================================================
echo  DigiWiki - Handy-Verbindung reparieren
echo ============================================================
echo.
echo Symptom: Nur Vorschau / Seite reagiert nicht / Connection timeout
echo Fix:      Tailscale + HTTPS-URL + Streamlit neu starten
echo.

echo [INFO] Streamlit neu starten (neue Handy-Einstellungen) ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_cleanup.ps1" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_start_streamlit.ps1" >nul 2>&1
timeout /t 3 >nul

set "TAILSCALE_IP="
set "TAILSCALE_HTTPS="
set "PHONE_ONLINE="
set "PHONE_NAME="
for /f "tokens=1,* delims==" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_tailscale_fix.ps1"') do (
    if /i "%%a"=="TAILSCALE_IP" set "TAILSCALE_IP=%%b"
    if /i "%%a"=="TAILSCALE_HTTPS" set "TAILSCALE_HTTPS=%%b"
    if /i "%%a"=="PHONE_ONLINE" set "PHONE_ONLINE=%%b"
    if /i "%%a"=="PHONE_NAME" set "PHONE_NAME=%%b"
)
if defined TAILSCALE_IP (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_write_zugang.ps1" -TailscaleIp "!TAILSCALE_IP!" -TailscaleHttps "!TAILSCALE_HTTPS!" -Root "%ROOT%" >nul 2>&1
    set "HANDY_URL=http://!TAILSCALE_IP!:8501"
)
echo.

echo --- PC-Status ---
netstat -ano | findstr ":8501.*ABH" >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Streamlit laeuft nicht auf Port 8501 - start.bat ausfuehren
) else (
    echo [OK] Streamlit hoert auf Port 8501
)
if defined TAILSCALE_IP (
    echo [OK] PC Tailscale-IP: !TAILSCALE_IP!
) else (
    echo [FEHLER] Tailscale-IP nicht ermittelt
)
if /i "!PHONE_ONLINE!"=="True" (
    echo [OK] Handy ^(!PHONE_NAME!^) im Tailnet ONLINE
) else if defined PHONE_NAME (
    echo [FEHLER] Handy ^(!PHONE_NAME!^) im Tailnet OFFLINE
    echo          -> Tailscale-App am Handy oeffnen, auf Verbunden ^(gruen^) warten
) else (
    echo [WARNUNG] Kein Handy im Tailnet gefunden
)
echo.

echo --- Handy-Checkliste ---
echo 1. Tailscale-App oeffnen - muss "Verbunden" ^(gruen^) zeigen
echo 2. Privates DNS am Android: AUS ^(nicht Automatisch^)
echo 3. STABILE URL ^(Lesezeichen in Chrome/Safari - KEINE Link-Vorschau^):
if defined TAILSCALE_HTTPS (
    echo    PRIMAER:  http://!TAILSCALE_IP!:8501
    echo    Optional: !TAILSCALE_HTTPS!
) else if defined HANDY_URL (
    echo    !HANDY_URL!
) else if exist "%ROOT%digiwiki_zugang.txt" (
    findstr /i "PRIMAER" "%ROOT%digiwiki_zugang.txt"
)
echo 4. Seite muss vollstaendig laden ^(nicht nur Vorschau^) - dann Frage stellen testen
echo 5. Immer noch Timeout? Flugmodus 5 Sek an/aus, Tailscale neu verbinden
echo.
pause
