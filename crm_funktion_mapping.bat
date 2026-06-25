@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [FEHLER] .venv fehlt
    pause
    exit /b 1
)
echo Synonym-Mapping: leere funktionid in crm_funktion_synonyme
echo.
echo   crm_funktion_mapping.bat           = SCHREIBEN in Access + CSV
echo   crm_funktion_mapping.bat --dry     = nur Vorschau + CSV, keine DB
echo   crm_funktion_mapping.bat --schwelle 0.35
echo.
.venv\Scripts\python.exe -m pip install scikit-learn -q
.venv\Scripts\python.exe crm_funktion_mapping.py %*
pause
