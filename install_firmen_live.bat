@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo Playwright + BeautifulSoup4 fuer Live-Web (Einzel-Firma)
echo.
if not exist ".venv\Scripts\python.exe" (
    echo [FEHLER] .venv fehlt
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m pip install playwright beautifulsoup4
.venv\Scripts\python.exe -m playwright install chrome
echo.
echo Fertig. Test: firmen_live_test.bat
pause
