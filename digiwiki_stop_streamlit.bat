@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Beende Streamlit auf Port 8501 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0digiwiki_stop_streamlit.ps1"
pause
