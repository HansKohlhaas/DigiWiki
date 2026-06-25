# DigiBest Wiki – Projektstatus

**Stand:** 24.06.2026  
**Branch:** `main`  
**Zweck:** Technischer Softwarestand und Handover

---

## 1. Kurzfassung

DigiWiki ist eine **Streamlit-Web-UI** (`15_wiki_web_ui.py`) für CRM-Abfragen, **Vier-Stufen-Wissens-Kaskade** (SQL → Live-Web → MD → KI-Synthese), Wiki-RAG und Remote-Zugang per Tailscale.

**Neu in dieser Session:** Wissens-Kaskade (Phasen A–C), Produktsuche über `abdaartikel`, KI-Briefing, CRM-MD aus Chroma, Verfahren-Wiki, **Datenbankpflege (KI-Live-Web)**, Funktionszuordnung über `crm_funktion_synonyme`.

---

## 2. Was funktioniert

### Wissens-Kaskade (Auto-Modus)

| Stufe | Modul | Status |
|-------|-------|--------|
| 1 SQL | `sql_frage_katalog.py`, `15_wiki_web_ui.py` | ✅ |
| 2 Live-Web | `firmen_live_recherche.py` | ✅ (Cache: JSON) |
| 3 MD-Fallback | `firmen_md_fallback.py` | ✅ |
| 4 KI-Synthese | `orakel_synthese.py` | ✅ (Produkte, Briefings) |
| Router | `wissens_kaskade.py` | ✅ |
| Folgefragen | `frage_kontext.py` | ✅ |

### Wiki & SQL

| Feature | Status |
|---------|--------|
| Wiki-RAG Chroma + Gemini | ✅ |
| CRM-MD aus Standard-Index (`CHROMA_EXCLUDE_CRM_MD`) | ✅ |
| Verfahren-Direktpfad (`verfahren_wiki.py`) | ✅ |
| Produkte via `abdaartikel.anbieter_nr` | ✅ |
| Relationsschicht (`db_*.csv`, `sql_db_meta.py`) | ✅ |
| NL2SQL + 11 Fragetypen | ✅ |

### Datenbankpflege (KI-Live-Web)

| Feature | Modul | Status |
|---------|-------|--------|
| Hauptreiter **Datenbankpflege** in UI | `15_wiki_web_ui.py` | ✅ |
| Kandidaten ohne `crm_personen` (Akquiseklasse 1–4) | `datenbank_pflege.py` | ✅ |
| Live-Web Impressum → Personen | `firmen_live_recherche.py`, `firmen_live_personen.py` | ✅ |
| URL-Prüfung vor Live-Abruf | `pruefe_url_fuer_live_web()` | ✅ |
| Persistenter Chrome-Profilordner (Cookie-Wände) | `config.py`, Playwright | ✅ |
| KI-Plausibilität (Anrede, Funktion) | `firmen_live_personen.py` | ✅ |
| Funktionszuordnung über Synonym-Tabelle | `crm_funktion_mapping.py` → `crm_funktion_synonyme` | ✅ |
| Auto-Pflege: Dauerbetrieb / Intervalle, Datensatz-Bereich | UI + `datenbank_pflege.py` | ✅ |
| CRM-Schreiben (`crm_personen`, Stammdaten) | `firmen_live_personen.py` | ✅ |
| Synonym-Mapping (Batch, TF-IDF) | `crm_funktion_mapping.py` / `.bat` | ✅ (CLI) |

### Infrastruktur

| Feature | Status |
|---------|--------|
| Tailscale Handy (IP-first) | ✅ |
| Keepalive-Task (`digiwiki_keepalive.ps1`) | ✅ |
| Single-Session parallel PC+Handy (`DIGIWIKI_SINGLE_SESSION=false`) | ✅ |
| Wiki-Wächter CRM-Bereinigung | ✅ |
| Wiki-Wächter E-Mail-Bericht (Schicht-Zähler, Fehlerdetails) | ✅ |
| Autostart / Desktop-Verknüpfung | ✅ |

---

## 3. Architektur (aktuell)

Siehe ausführlich: [DigiWiki_Technische_Zusammenhaenge.md](DigiWiki_Technische_Zusammenhaenge.md)

```
Nutzer → 15_wiki_web_ui.py
           ├── Auto → wissens_kaskade.py → SQL / Web / MD / orakel_synthese
           ├── Wiki → ask_wiki.py (+ verfahren_wiki, brandvoice)
           └── SQL  → uebersetze_frage_in_sql() → Access
```

---

## 4. Dokumentation

| Dokument | Rolle |
|----------|-------|
| [DigiWiki_Schulungs_Handbuch.md](DigiWiki_Schulungs_Handbuch.md) | Einstieg Schulung |
| [DigiWiki_Technische_Zusammenhaenge.md](DigiWiki_Technische_Zusammenhaenge.md) | Technikbericht |
| [DigiWiki_Bedienungsanleitung_Komplett.md](DigiWiki_Bedienungsanleitung_Komplett.md) | Nutzer-Bedienung |
| [Roadmap_Wissens_Kaskade.md](Roadmap_Wissens_Kaskade.md) | Roadmap erledigt/offen |
| [DigiWiki_Verbindung_Einrichtung_Schulung.md](DigiWiki_Verbindung_Einrichtung_Schulung.md) | PC/Handy-Einrichtung |

---

## 5. Offen (Priorität)

Siehe [PROJEKT_TODO.md](PROJEKT_TODO.md) und [Roadmap_Wissens_Kaskade.md](Roadmap_Wissens_Kaskade.md) §10:

- `web_cache` in Access statt JSON
- Phase D: MD/Web → CRM-Import
- KI-Synthese für alle Firmen-Fragetypen
- `data_dictionary.csv` bereinigen
- Vollständiger Wächter-Lauf (CRM-MD aus Index entfernen)

---

## 6. Test-Befehle

| Test | Befehl |
|------|--------|
| SQL-Regression | `sql_regression_test.bat` |
| Live-Web | `firmen_live_test.bat` |
| Funktion-Synonyme mappen | `crm_funktion_mapping.bat` |
| Wiki-Wächter | `python 9_wiki_waechter.py` |

### Wiki-Wächter (`9_wiki_waechter.py`)

Nächtlicher Lauf (Task Scheduler, typisch 22:35 via `install_wiki_waechter_nacht.bat`): scannt `WATCH_ROOTS`, aktualisiert Chroma-Index und `wiki_stand.json`.

**E-Mail-Bericht** (wenn `EMAIL_*` und `SMTP_*` in `.env` gesetzt):

| Feld | Bedeutung |
|------|-----------|
| Vorheriger / Neuer Stand | Anzahl Dateien in `wiki_stand.json` |
| Neu seit Schichtbeginn | Dateien seit 22:30 Uhr (Basis wird **vor** dem Lauf in `wiki_schicht_snapshot.json` gesetzt) |
| Jetzt im Durchlauf gelernt | In diesem Durchlauf neu indexiert |
| Fehlerhaft | Anzahl; darunter **Pfad und Grund** je Datei |
| Neue Quarantäne | Dateien über Größenlimit (`wiki_quarantaene.json`) |

Lokale Kopie: `wiki_waechter_bericht.txt` im Projektordner.
