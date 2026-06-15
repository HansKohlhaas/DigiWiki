@echo off
setlocal EnableDelayedExpansion

REM Einmalig ausfuehren: DigiWiki start.bat beim Windows-Login automatisch starten.
REM start.bat beendet verwaiste Hintergrund-Helfer beim Start und erlaubt nur
REM eine Instanz – mehrfaches Login/Neustart erzeugt keine PowerShell-Ansammlung.
REM Entfernen: schtasks /delete /tn "DigiWiki Streamlit" /f

set "TASK_NAME=DigiWiki Streamlit"
set "START_BAT=%~dp0start.bat"

if not exist "%START_BAT%" (
    echo [FEHLER] start.bat nicht gefunden: %START_BAT%
    pause
    exit /b 1
)

REM Verwaiste Helfer von frueheren Laeufen bereinigen (einmalig bei Installation)
powershell -NoProfile -Command "if (Test-Path (Join-Path $env:TEMP 'digiwiki_helper.pid')) { Get-Content (Join-Path $env:TEMP 'digiwiki_helper.pid') | ForEach-Object { Stop-Process -Id $_ -Force -EA 0 }; Remove-Item (Join-Path $env:TEMP 'digiwiki_helper.pid') -Force -EA 0 }; Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -match 'digiwiki_helpers\.ps1|SetThreadExecutionState|tailscale status \| Out-Null' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA 0 }; Remove-Item (Join-Path $env:TEMP 'DigiWiki_streamlit.lock') -Force -EA 0" >nul 2>&1

schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Aufgabe "%TASK_NAME%" existiert bereits – wird aktualisiert ...
    schtasks /delete /tn "%TASK_NAME%" /f >nul
)

echo [INFO] Erstelle geplante Aufgabe "%TASK_NAME%" ...
schtasks /create /tn "%TASK_NAME%" /tr "\"%START_BAT%\"" /sc onlogon /rl limited /f

if errorlevel 1 (
    echo [FEHLER] schtasks fehlgeschlagen. Als Administrator erneut versuchen.
    pause
    exit /b 1
)

echo.
echo [OK] DigiWiki startet ab jetzt automatisch beim Login.
echo      Task: %TASK_NAME%
echo      Skript: %START_BAT%
echo      Entfernen: schtasks /delete /tn "%TASK_NAME%" /f
echo      Erwartete PowerShell-Helfer: 0 wenn gestoppt, max. 1 wenn start.bat laeuft
echo.
pause
