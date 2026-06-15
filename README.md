# DigiWiki

Persönliches Wissens- und CRM-System für DigiBest: semantische Dokumentensuche (ChromaDB + Gemini), Streamlit-Web-UI, Access-CRM-Anbindung und Tailscale-Zugriff vom Smartphone.

## Schnellstart (Windows)

1. Python-venv anlegen und Abhängigkeiten installieren
2. `.env` mit API-Keys anlegen (siehe `.env.example` falls vorhanden)
3. `start.bat` ausführen → UI unter `http://localhost:8501`
4. Handy (Tailscale): MagicDNS-URL aus dem Startfenster

## Wichtige Dateien

| Datei | Rolle |
|-------|--------|
| `15_wiki_web_ui.py` | Streamlit-Haupt-UI |
| `9_wiki_waechter.py` | Hintergrund-Indizierung |
| `11_wiki_api.py` | FastAPI für externes CRM |
| `ask_wiki.py` | RAG / Wiki-Abfragen |
| `config.py` | Pfade und Einstellungen |
| `start.bat` | Start inkl. Tailscale & Helfer |

## Hinweise

- `Chroma_DB/` und Laufzeit-JSON (`wiki_stand.json` etc.) sind lokal und nicht im Repo
- Access-Datenbank-Pfad über `DIGIWIKI_ACCESS_DB` in `.env` oder `config.py`
- Outlook-Integration benötigt laufendes Outlook am PC
