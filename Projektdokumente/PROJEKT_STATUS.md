# DigiBest Wiki – Projektstatus

**Stand:** 16.06.2026  
**Branch:** `main` (lokal 2 Commits vor `origin/main`, plus uncommittete Änderungen)  
**Zweck:** Kontext-Handover für die nächste Chat-Session

---

## 1. Kurzfassung

Das Projekt ist eine **Streamlit-Web-UI** (`15_wiki_web_ui.py`) für CRM-Kontakte, Wiki-RAG und **natürlichsprachliche SQL-Abfragen** gegen eine Access-Datenbank. In den letzten Sessions wurden Wiki-Intelligenz, SQL-Auto-Routing, Mikro-Buttons, Keyword-Historie, Tailscale-Handy-Zugang und der **Beginn einer Relationsschicht** (Tabellen + JOINs) umgesetzt.

---

## 2. Was funktioniert (umgesetzt)

### Wiki & Chat (RAG + SQL)

| Feature | Status | Dateien |
|--------|--------|---------|
| Wiki-RAG via ChromaDB + Gemini | ✅ | `ask_wiki.py`, `config.py` |
| Chat-Modi: Auto (SQL→Wiki), Wiki, SQL | ✅ | `15_wiki_web_ui.py` |
| Frage-Klassifikation (11 SQL-Typen) | ✅ | `sql_frage_katalog.py` |
| Semantische Feld-Aliase (z. B. Apotheken-Fokus → `Marktzielgruppe`) | ✅ | `sql_frage_katalog.py` |
| NL→SQL mit GPT-4o-mini | ✅ | `uebersetze_frage_in_sql()` |
| Duplicate-Column-Fix bei JOINs | ✅ | `_eindeutige_spaltennamen()` |
| Relationsschicht (Tabellen + JOIN-Graph) | ✅ neu, **noch nicht gepusht** | `db_tabellen.csv`, `db_joins.csv`, `sql_db_meta.py` |
| Einbindung Relationsschicht in SQL-Prompt | ✅ lokal | `15_wiki_web_ui.py` |

### UI & Bedienung

| Feature | Status |
|--------|--------|
| Mikro-Button (🎤) direkt neben Feldern | ✅ |
| Keyword-Historie für Anschlussfragen | ✅ |
| Mail-/WhatsApp-Suche ohne `st.form` (Feld+Mikro+Button) | ✅ |
| Agenda-Notiz/Aufgabe ohne Form | ✅ |
| Wissensbereich-Dropdown für Wiki | ✅ |

### Infrastruktur & Remote (Handy)

| Feature | Status | Hinweis |
|--------|--------|---------|
| Tailscale Serve + Firewall-Fix | ✅ | `digiwiki_tailscale_fix.ps1` |
| Netzwerk-Diagnose | ✅ | `digiwiki_netz_diag.ps1` |
| Serve-Repair in Helpers | ✅ | `digiwiki_helpers.ps1` |
| Start-Skript mit IP-first für Handy | ✅ | `start.bat` |
| Chroma-Pfad mit Umlaut-Fix | ✅ | `config.chroma_db_path_str()` |
| Gemini-Modell aktualisiert | ✅ | `gemini-2.5-flash` |

### Git (lokal)

| Commit | Inhalt |
|--------|--------|
| `32ee75e` | Wiki-Intelligenz (RAG) in Web-UI |
| `f9e3a70` | SQL-Auto-Routing, Mikro/Historie, Tailscale, `sql_frage_katalog.py`, Data-Dictionary-Updates |

**Noch nicht auf GitHub:** diese 2 Commits + aktuelle uncommittete Änderungen (siehe Abschnitt 4).

---

## 3. Architektur (aktuell)

```
Nutzer (Browser / Handy)
        │
        ▼
15_wiki_web_ui.py (Streamlit, Port 8501)
        │
        ├── Chat Auto ──► klassifiziere_chat_frage()
        │                      │
        │                      ├─ SQL ──► uebersetze_frage_in_sql()
        │                      │              ├── db_schema.txt
        │                      │              ├── data_dictionary.csv
        │                      │              ├── sql_db_meta (Tabellen + JOINs)  ← NEU
        │                      │              ├── sql_frage_katalog (Typen + Aliase)
        │                      │              └── GPT-4o-mini → Access via pyodbc
        │                      │
        │                      └─ Wiki ──► ask_wiki.py → ChromaDB + Gemini
        │
        ├── Kontaktsuche, Agenda, Diktat, Mikro
        └── Access .accdb (CRM, Stammdaten, ABDA, LinkedIn, …)
```

**Hub-Tabelle:** `stammdatenindustrie` (PK: `kundennumm`)  
**Wichtige JOINs:** Person→Firma (`kundennumm`), Artikel→Hersteller (`anbieter_nr` = `anbieternummer`)

---

## 4. Uncommittete Änderungen (Stand jetzt)

| Datei | Art |
|-------|-----|
| `db_tabellen.csv` | neu – 12 Tabellen mit Rollen |
| `db_joins.csv` | neu – 15 JOINs mit SQL-Beispielen |
| `sql_db_meta.py` | neu – Loader + Leitfäden für NL2SQL |
| `15_wiki_web_ui.py` | geändert – `baue_db_meta_leitfaden()` im SQL-Prompt |
| `sql_frage_katalog.py` | geändert – JOIN-Regeln → Verweis auf CSVs |
| `digiwiki_helpers.ps1` | geändert – Serve-Repair |
| `start.bat` | geändert – Handy-URL IP-first |

---

## 5. Bekannte Einschränkungen & Fixes

| Problem | Lösung / Workaround |
|---------|---------------------|
| Handy: `ERR_NAME_NOT_RESOLVED` | Android **Privates DNS → AUS**; URL nur per IP: `http://100.116.74.108:8501` |
| `apotheken_fokus` liefert 0 Treffer | Feld leer → nutze `Marktzielgruppe` / `emarktzielgruppe LIKE '%Apothek%'` |
| Chroma mit Pfad `Makroübungen` | `chroma_db_path_str()` in `config.py` |
| Duplicate columns bei SQL-JOINs | Cursor + `_eindeutige_spaltennamen()` |
| `main` auf GitHub ggf. geschützt | Push kann Freigabe/PR erfordern |

---

## 6. Zugangsdaten (lokal)

| Was | Wert |
|-----|------|
| Tailscale-IP PC | `100.116.74.108` |
| MagicDNS | `desktop-velbert.tail094343.ts.net` |
| **Empfohlene Handy-URL** | `http://100.116.74.108:8501` |
| Streamlit-Port | `8501` |

---

## 7. Wichtige Dateien

| Rolle | Pfad |
|-------|------|
| Haupt-UI | `15_wiki_web_ui.py` |
| Wiki-RAG | `ask_wiki.py` |
| SQL-Fragekatalog | `sql_frage_katalog.py` |
| DB-Relationen | `db_tabellen.csv`, `db_joins.csv`, `sql_db_meta.py` |
| Data Dictionary | `Projektdokumente/data_dictionary.csv` |
| DB-Schema | `db_schema.txt` |
| Config | `config.py` |
| Tailscale | `start.bat`, `digiwiki_tailscale_fix.ps1`, `digiwiki_helpers.ps1` |
| Wächter/Indizierung | `9_wiki_waechter0.py` |

---

## 8. Testfragen (SQL-Qualität prüfen)

1. *Firmen in Akquiseklasse 3 mit Apotheken-Fokus*
2. *Wer stellt Hustensaft her?*
3. *Wer ist GF bei [Firmenname]?*
4. *Topprodukte von [Firma]*
5. *Apotheken in PLZ [xxxx]*

Nach Code-Änderungen: **Streamlit neu starten** (Cache/`__pycache__`).

---

*Dieses Dokument ersetzt/ergänzt `Status_und_Roadmap_15_06_26.txt` als aktuellen Handover-Stand.*
