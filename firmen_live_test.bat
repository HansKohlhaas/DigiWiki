@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo Live-Web Test (Einzel-Firma, Chrome/Playwright)
echo Beispiel: GF bei Hexal (SQL leer -^> Live-Web)
echo.
if not exist ".venv\Scripts\python.exe" (
    echo [FEHLER] .venv fehlt
    pause
    exit /b 1
)
set "FRAGE=Wer ist Geschäftsführer bei Hexal?"
if not "%~1"=="" set "FRAGE=%~1"
.venv\Scripts\python.exe -c "from firmen_live_recherche import firmen_live_recherche, ist_einzel_firma_live_web_frage; f=r'''%FRAGE%'''; print('Live-Web erlaubt:', ist_einzel_firma_live_web_frage(f)); r=firmen_live_recherche(f); print('OK:', r.ok, 'Firma:', r.firmenname, 'URL:', r.url); print('Cache:', r.aus_cache); print('Fehler:', r.fehler or '-'); print('CRM neu/vorhanden/akt:', r.personen_neu, r.personen_vorhanden, r.personen_aktualisiert); [print(' -', p.get('status'), p.get('name'), '-', p.get('funktion')) for p in (r.personen_liste or [])]; print('--- Text ---'); print((r.text or '')[:2000])"
echo.
pause
