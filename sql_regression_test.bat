@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo SQL-Regression (10 Firmenfragen + 2 Wiki-Checks)
echo OpenAI + Access noetig. Dauer ca. 1-2 Minuten.
echo.
.venv\Scripts\python.exe sql_regression_test.py
echo.
pause
