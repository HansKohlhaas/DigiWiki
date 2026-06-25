@echo off
setlocal EnableDelayedExpansion
set "ROOT=%~dp0"
set "TASK_NAME=DigiWiki Keepalive"
set "PS1=%ROOT%digiwiki_keepalive.ps1"

if not exist "%PS1%" (
    echo [FEHLER] %PS1% nicht gefunden
    pause
    exit /b 1
)

schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Aufgabe existiert - wird aktualisiert ...
    schtasks /delete /tn "%TASK_NAME%" /f >nul
)

echo [INFO] Erstelle Task: beim Login + alle 2 Minuten pruefen/reparieren ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_install_keepalive_task.ps1"

echo.
echo [OK] Keepalive-Task aktiv (Login + alle 2 Min).
echo      Prueft: Watchdog, Tailscale online, Serve/WebSocket, Streamlit Health
echo      Log: digiwiki_keepalive.log
echo      Entfernen: schtasks /delete /tn "%TASK_NAME%" /f
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
echo.
pause
