@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

REM Einmalig: DigiWiki dauerhaft erreichbar halten (Autostart + Watchdog + Keepalive + kein Sleep am Netzstrom).
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo.
echo ============================================================
echo  DigiWiki - Dauerbetrieb einrichten
echo ============================================================
echo.
echo  1. Autostart beim Windows-Login (start.bat)
echo  2. Keepalive-Task alle 2 Min + sofort beim Login
echo  3. Watchdog (Tailscale, Streamlit, Serve, Sleep-Guard)
echo  4. Kein Standby/Ruhezustand am Netzstrom
echo.

if not exist "%ROOT%start.bat" (
    echo [FEHLER] start.bat nicht gefunden
    pause
    exit /b 1
)

set "TASK_STREAMLIT=DigiWiki Streamlit"
set "START_BAT=%ROOT%start.bat"

echo [1/4] Autostart-Task ...
schtasks /query /tn "%TASK_STREAMLIT%" >nul 2>&1
if not errorlevel 1 schtasks /delete /tn "%TASK_STREAMLIT%" /f >nul
schtasks /create /tn "%TASK_STREAMLIT%" /tr "\"%START_BAT%\"" /sc onlogon /rl limited /f
if errorlevel 1 (
    echo [WARNUNG] Autostart fehlgeschlagen - ggf. als Administrator erneut versuchen.
) else (
    echo [OK] Autostart beim Login aktiv.
)

echo.
echo [2/4] Keepalive-Task (2 Min, Login) ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_install_keepalive_task.ps1"
if errorlevel 1 (
    echo [WARNUNG] Keepalive-Task fehlgeschlagen.
) else (
    echo [OK] Keepalive-Task aktiv.
)

echo.
echo [3/4] Watchdog + Dienste ...
echo [HINWEIS] Streamlit nicht als Administrator starten.
echo           Nach diesem Setup einmal normal start.bat ausfuehren (Doppelklick, ohne Admin).
echo           Sonst blockiert Port 8501 bei normalem Neustart.
REM Kein Keepalive hier: laeuft als Admin und wuerde Streamlit mit Admin-Rechten starten.

echo.
echo [4/4] Ruhezustand am Netzstrom deaktivieren ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%digiwiki_sleep_guard.ps1"

echo.
echo [5/5] Pruefe Tasks ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = Get-ScheduledTask -TaskName 'DigiWiki Keepalive','DigiWiki Streamlit' -EA 0; ^
   if (-not $t) { Write-Host '[FEHLER] Keepalive/Autostart-Tasks fehlen - als Admin erneut ausfuehren!'; exit 1 }; ^
   $t | ForEach-Object { Write-Host ('[OK] Task: ' + $_.TaskName + ' = ' + $_.State) }"
if errorlevel 1 (
    echo [WARNUNG] Dauerbetrieb-Tasks unvollstaendig.
) else (
    echo [OK] Alle Dauerbetrieb-Tasks registriert.
)

echo.
echo ============================================================
echo  FERTIG - Dauerbetrieb aktiv
echo.
echo  - Nach Neustart: start.bat laeuft automatisch beim Login
echo  - Alle 2 Min: Keepalive prueft Watchdog, Tailscale, Streamlit
echo  - Watchdog: alle 30-90 Sek. Reparatur + verhindert PC-Sleep
echo  - Log: digiwiki_keepalive.log
echo  - Diagnose: digiwiki_dauerbetrieb_diag.bat
echo.
echo  Handy: Tailscale-App muss am Handy selbst verbunden sein.
echo ============================================================
echo.
pause
