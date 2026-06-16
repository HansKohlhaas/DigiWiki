@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
set "APP=%~dp0\15_wiki_web_ui.py"

if not exist "%PYTHON%" (
    echo [FEHLER] Python nicht gefunden: %PYTHON%
    pause
    exit /b 1
)

if not exist "%APP%" (
    echo [FEHLER] App nicht gefunden: %APP%
    pause
    exit /b 1
)

title DigiWiki-Streamlit

:restart
echo.
echo [%date% %time%] Starte 15_wiki_web_ui.py ...
"%PYTHON%" -m streamlit run "%APP%" --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false --server.enableWebsocketCompression false --server.websocketPingInterval 30 --server.disconnectedSessionTTL 3600 --browser.serverAddress localhost
echo [%date% %time%] Streamlit beendet. Neustart in 5 Sekunden ...
ping 127.0.0.1 -n 6 >nul
goto restart
