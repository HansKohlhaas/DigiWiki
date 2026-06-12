@echo off
title DigiWiki Startsequenz

:: 1. Wechsel in das Projektverzeichnis
cd /d "C:\Digibest_Wiki_Projekt"

:: 2. Virtuelle Umgebung (venv) aktivieren
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo --- venv erfolgreich aktiviert ---
) else (
    echo FEHLER: venv-Ordner nicht gefunden.
    pause
    exit
)

:: 3. DigiWiki UI via Streamlit starten (Tailscale Freigabe)
echo --- Starte DigiWiki UI ---
streamlit run 15_wiki_web_ui.py --server.address 0.0.0.0 --server.enableCORS false --server.enableXsrfProtection false

:: 4. Fehlerbehandlung
if %errorlevel% neq 0 (
    echo.
    echo FEHLER: Streamlit konnte 15_wiki_web_ui.py nicht starten.
    pause
)