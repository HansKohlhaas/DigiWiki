@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo DigiWiki Dauerbetrieb-Diagnose ...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0digiwiki_dauerbetrieb_diag.ps1" -Save
echo.
pause
