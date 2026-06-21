@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo Wiki-Waechter (Chroma-Index aktualisieren)
echo.
if not exist ".venv\Scripts\python.exe" (
    echo [FEHLER] Virtuelle Umgebung fehlt. Zuerst venv anlegen.
    pause
    exit /b 1
)
python 9_wiki_waechter.py
echo.
pause
