@echo off
chcp 65001 >nul
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    echo Fordere Administrator-Rechte an ...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Beende Streamlit auf Port 8501 (Administrator) ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0digiwiki_stop_streamlit.ps1"
echo.
pause
