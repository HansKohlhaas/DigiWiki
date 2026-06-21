@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo [INFO] Erstelle Desktop-Verknuepfung fuer DigiWiki ...
set "LINK="
set "DESKTOP="
for /f "tokens=1,* delims==" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0digiwiki_desktop_verknuepfung.ps1"') do (
    if /i "%%a"=="VERKNUEPFUNG" set "LINK=%%b"
    if /i "%%a"=="DESKTOP" set "DESKTOP=%%b"
)
if errorlevel 1 (
    echo [FEHLER] Verknuepfung konnte nicht erstellt werden.
    pause
    exit /b 1
)
echo.
echo [OK] Verknuepfung erstellt:
echo      !LINK!
echo.
echo Name auf dem Desktop:  DigiWiki starten
echo.
echo Falls nicht sichtbar:
echo   - Rechtsklick auf Desktop - Ansicht - Desktop-Symbole anzeigen
echo   - F5 druecken oder Desktop neu laden
echo.
choice /C JN /M "Desktop-Ordner jetzt oeffnen und Verknuepfung markieren"
if errorlevel 2 goto ende
if defined LINK explorer /select,"!LINK!"
:ende
pause
