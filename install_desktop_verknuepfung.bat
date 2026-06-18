@echo off
setlocal
cd /d "%~dp0"

echo [INFO] Erstelle Desktop-Verknuepfung fuer DigiWiki ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0digiwiki_desktop_verknuepfung.ps1"
if errorlevel 1 (
    echo [FEHLER] Verknuepfung konnte nicht erstellt werden.
    pause
    exit /b 1
)
echo.
echo [OK] Fertig. Auf dem Desktop: "DigiWiki starten"
pause
