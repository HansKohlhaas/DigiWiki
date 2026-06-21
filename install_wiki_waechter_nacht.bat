@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

REM Einmalig: naechtlicher Wiki-Waechter (Task Scheduler, 22:35 — ohne .bat im Lauf)
REM Entfernen: schtasks /delete /tn "DigiWiki Wiki-Waechter Nacht" /f

set "TASK_NAME=DigiWiki Wiki-Waechter Nacht"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
set "SCRIPT=%~dp09_wiki_waechter.py"
set "WORKDIR=%~dp0"

if not exist "%PYTHON%" (
    echo [FEHLER] .venv fehlt: %PYTHON%
    pause
    exit /b 1
)
if not exist "%SCRIPT%" (
    echo [FEHLER] Skript fehlt: %SCRIPT%
    pause
    exit /b 1
)

schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Aufgabe "%TASK_NAME%" existiert — wird aktualisiert ...
    schtasks /delete /tn "%TASK_NAME%" /f >nul
)

echo [INFO] Erstelle geplante Aufgabe "%TASK_NAME%" ...
echo        Taeglich 22:35, Python: %PYTHON%
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON%\" \"%SCRIPT%\"" /sc daily /st 22:35 /rl limited /f

if errorlevel 1 (
    echo [FEHLER] schtasks fehlgeschlagen. Als Administrator erneut versuchen.
    pause
    exit /b 1
)

echo.
echo [OK] Wiki-Waechter laeuft ab jetzt jede Nacht um 22:35.
echo      Task: %TASK_NAME%
echo      Manuell testen: "%PYTHON%" "%SCRIPT%"
echo      Oder: python 9_wiki_waechter.py  ^(leitet automatisch auf .venv um^)
echo      Entfernen: schtasks /delete /tn "%TASK_NAME%" /f
echo.
pause
