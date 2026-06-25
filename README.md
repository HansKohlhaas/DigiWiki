# DigiWiki

Persönliches Wissens- und CRM-System für DigiBest: semantische Dokumentensuche (ChromaDB + Gemini), Streamlit-Web-UI, Access-CRM-Anbindung und Tailscale-Zugriff vom Smartphone.

## Schnellstart (Windows)

1. Python-venv anlegen und Abhängigkeiten installieren
2. `.env` mit API-Keys anlegen (siehe `.env.example` falls vorhanden)
3. `start.bat` ausführen → UI unter `http://localhost:8501`  
   (Desktop-Verknüpfung: einmalig `install_desktop_verknuepfung.bat` ausführen)
4. Handy (Tailscale): MagicDNS-URL aus dem Startfenster

## Wichtige Dateien

| Datei | Rolle |
|-------|--------|
| `15_wiki_web_ui.py` | Streamlit-Haupt-UI |
| `9_wiki_waechter.py` | Hintergrund-Indizierung |
| `11_wiki_api.py` | FastAPI für externes CRM |
| `ask_wiki.py` | RAG / Wiki-Abfragen |
| `antworten_export.py` | Markierte Antworten zusammenfassen → Ordner `Antworten/` |
| `datenbank_pflege.py` | KI-Datenbankpflege (Live-Web → crm_personen) |
| `firmen_live_recherche.py` / `firmen_live_personen.py` | Live-Web-Impressum, Personen-Extraktion |
| `crm_funktion_mapping.py` | Synonym-Zuordnung `crm_funktion_synonyme` (CLI) |
| `Antworten/` | Exportierte Antwort-Sammlungen (Markdown) |
| `config.py` | Pfade und Einstellungen |
| `start.bat` | Start inkl. Tailscale & Helfer |

## Anleitungen (Dokumentation)

Vollständige Übersicht: **[Projektdokumente/DOKUMENTE.md](Projektdokumente/DOKUMENTE.md)**

| Datei | Zielgruppe |
|-------|------------|
| [Anleitung_Nutzer_Handy.md](Projektdokumente/Anleitung_Nutzer_Handy.md) | Nutzer: Zugang vom Handy (Tailscale) |
| [Anleitung_Nutzer_Bedienung.md](Projektdokumente/Anleitung_Nutzer_Bedienung.md) | Nutzer: Bedienung, Fragen, Ergebnisse |
| [Anleitung_Nutzer_Kurzreferenz.md](Projektdokumente/Anleitung_Nutzer_Kurzreferenz.md) | Nutzer: **1-Seiten-Spickzettel** |
| [Anleitung_Nutzer_Kurzreferenz.html](Projektdokumente/Anleitung_Nutzer_Kurzreferenz.html) | Nutzer: Kurzreferenz **drucken / als PDF** (Strg+P) |
| [Anleitung_PC_und_Handy_Einrichtung_Admin.md](Projektdokumente/Anleitung_PC_und_Handy_Einrichtung_Admin.md) | Administrator: PC, Tailscale, Start |
| [Roadmap_Wissens_Kaskade.md](Projektdokumente/Roadmap_Wissens_Kaskade.md) | Planung (Entwicklung): SQL → Web → MD → KI |

## Hinweise

- `Chroma_DB/` und Laufzeit-JSON (`wiki_stand.json` etc.) sind lokal und nicht im Repo
- Access-Datenbank-Pfad über `DIGIWIKI_ACCESS_DB` in `.env` oder `config.py`
- Outlook-Integration benötigt laufendes Outlook am PC
