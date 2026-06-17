# DigiBest Wiki – To-do-Liste

**Stand:** 16.06.2026  
**Priorität:** 🔴 hoch · 🟡 mittel · 🟢 niedrig

---

## 🔴 Sofort / Nächste Session

- [ ] **Uncommittete Änderungen committen und zu GitHub pushen**  
  Enthält: Relationsschicht (`db_*.csv`, `sql_db_meta.py`), UI-Einbindung, Status/TODO-Docs.  
  Branch ist 2 Commits vor `origin/main`; `main` evtl. geschützt → PR falls Push blockiert.

- [ ] **Streamlit neu starten** und SQL-Testfragen durchspielen (siehe `PROJEKT_STATUS.md` §8).

- [ ] **`data_dictionary.csv` bereinigen**  
  - Encoding konsistent (UTF-8)  
  - `abdaartikel` vollständig dokumentieren  
  - `[SUCH]` / `[LEER]`-Tags setzen  
  - Falschen FK korrigieren: `Datei_Index.Anbieter_ID` → `stammdatenindustrie.kundennumm` (nicht `ID`)

---

## 🟡 Kurzfristig (Relationsschicht & SQL)

- [ ] **`sql_frage_katalog.py` mit `db_joins.csv` synchron halten**  
  Manuelle JOIN-Regeln weiter reduzieren; CSV als Single Source of Truth.

- [ ] **Weitere Tabellen/JOINs ergänzen** falls in Access-Schema vorhanden, aber noch nicht in CSVs.

- [ ] **Semantische Aliase erweitern** (`SEMANTISCHE_FELDALIASE` in `sql_frage_katalog.py`)  
  z. B. D2P, Veredelung, Narrativ, Sortiment – nach echten Nutzerfragen.

- [ ] **SQL-Fehlerprotokoll** (optional): fehlgeschlagene Fragen + generiertes SQL loggen für Nachbesserung.

- [ ] **Klassifikator mit `db_tabellen.csv` anreichern**  
  `Typische_Fragentypen` als Hinweis für `klassifiziere_chat_frage()`.

---

## 🟡 Kurzfristig (Wiki & UI)

- [ ] **Wiki-Antwortqualität** mit verschiedenen Wissensbereichen testen.

- [ ] **Performance Chroma/Vektor-Suche** (Roadmap Phase 4) – Batch-Größe, Caching prüfen.

- [ ] **Mikro/Diktat** auf Handy unter Tailscale testen (Browser-Berechtigungen).

---

## 🟡 Infrastruktur & Handy

- [ ] **Tailscale-Stabilität langfristig**  
  - Handy: Akku-Optimierung für Tailscale deaktivieren  
  - Lesezeichen nur IP-URL  
  - `digiwiki_handy.html` / `digiwiki_zugang.txt` aktuell halten

- [ ] **Serve-Health-Check** regelmäßig via `digiwiki_tailscale_fix.ps1` oder `start.bat`.

---

## 🟢 Mittelfristig (Roadmap)

- [ ] **Phase 1 – Vollständige Remote-Steuerung vom Smartphone**  
  Alle Kernfunktionen (Chat, Suche, Agenda, Diktat) stabil per Tailscale.

- [ ] **Phase 2 – FirmaApp / Datenextraktion** weiter stabilisieren.

- [ ] **Phase 4 – Vektor-Suche optimieren** (Embedding-Cache, Index-Wartung).

- [ ] **Render-Deployment** (optional): Ephemeral FS beachten – Chroma/Dateien brauchen persistenten Speicher oder externe DB.

---

## 🟢 Dokumentation & Wartung

- [ ] **`db_schema.txt` mit Live-Access abgleichen** nach Schema-Änderungen.

- [ ] **`PROJEKT_STATUS.md` / `PROJEKT_TODO.md`** nach größeren Meilensteinen aktualisieren.

- [ ] Alte Datei `Status_und_Roadmap_15_06_26.txt` archivieren oder verweisen lassen auf neue MD-Dateien.

---

## Erledigt (Referenz)

- [x] Wiki-RAG in Web-UI (`frage_das_wiki`, Wissensbereich-Dropdown)
- [x] Chat Auto-Routing SQL → Wiki
- [x] `sql_frage_katalog.py` mit 11 SQL-Fragetypen
- [x] Mikro-Buttons neben Feldern + Keyword-Historie
- [x] Mail/WhatsApp/Agenda ohne `st.form`
- [x] Tailscale-Handy-Zugang (IP-first, Firewall, Serve-Fix)
- [x] Relationsschicht angelegt: `db_tabellen.csv`, `db_joins.csv`, `sql_db_meta.py`
- [x] Einbindung Relationsschicht in `uebersetze_frage_in_sql()` (lokal)
- [x] Apotheken-Fokus-Mapping auf `Marktzielgruppe` / `emarktzielgruppe`
- [x] Chroma-Pfad-Fix, Gemini `2.5-flash`, SQL Duplicate-Column-Fix

---

## Empfohlene Reihenfolge für den nächsten Chat

1. Push/Commit abschließen  
2. SQL-Tests mit Relationsschicht  
3. Data Dictionary bereinigen  
4. Weitere JOINs + Aliase nach Testergebnissen
