@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Zweite Instanz verhindern (Port bereits belegt)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0digiwiki_port_frei.ps1" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [HINWEIS] Port 8501 belegt – DigiWiki laeuft bereits.
    timeout /t 5
    exit /b 0
)

set "PYTHON=.venv\Scripts\python.exe"
set "APP=15_wiki_web_ui.py"

if not exist "%PYTHON%" (
    echo [FEHLER] Python nicht gefunden: %PYTHON%
    pause
    exit /b 1
)

title DigiWiki-Streamlit

:restart
echo.
echo [%date% %time%] Starte 15_wiki_web_ui.py ...
"%PYTHON%" -m streamlit run "%APP%" --server.address 0.0.0.0 --server.headless true --server.enableCORS true --server.enableXsrfProtection false --server.enableWebsocketCompression false --server.websocketPingInterval 30 --server.disconnectedSessionTTL 3600
echo [%date% %time%] Streamlit beendet. Neustart in 5 Sekunden ...
ping 127.0.0.1 -n 6 >nul
goto restart
