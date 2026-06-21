# DigiBest Wiki – To-do-Liste

**Stand:** 17.06.2026  
**Priorität:** 🔴 hoch · 🟡 mittel · 🟢 niedrig

---

## 🔴 Sofort / Nächste Session

- [ ] **`web_cache` in Access** statt `live_web_cache.json` (Roadmap Phase B)
- [ ] **KI-Synthese erweitern** — alle Firmen-Fragetypen, nicht nur Produkte/Briefing
- [ ] **Wiki-Wächter vollständig laufen lassen** — CRM-MD aus Chroma entfernen (~4200 Einträge)
- [ ] **`data_dictionary.csv` bereinigen** — UTF-8, `abdaartikel` vollständig, FK korrigieren

---

## 🟡 Kurzfristig

- [ ] Phase D: Personen aus Web/MD → CRM-Vorschlag + UI „In CRM übernehmen“
- [ ] Regressionstest-Matrix (20 Kaskaden- + 20 Wiki-Fragen)
- [ ] `sql_frage_katalog.py` mit `db_joins.csv` synchron halten
- [ ] Tailscale Akku-Optimierung am Handy dauerhaft deaktivieren

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

- [x] Wissens-Kaskade: `wissens_kaskade.py`, Stufen 1–4
- [x] Live-Web: `firmen_live_recherche.py` + Cache JSON
- [x] MD-Fallback: `firmen_md_fallback.py` gezielt per kundennumm
- [x] KI-Synthese: `orakel_synthese.py`
- [x] Folgefragen: `frage_kontext.py`
- [x] Produkte via `abdaartikel` JOIN `anbieternummer`
- [x] CRM-MD aus Chroma (`CHROMA_EXCLUDE_CRM_MD`, Wächter)
- [x] Verfahren-Wiki: `verfahren_wiki.py`
- [x] Handy-Keepalive-Task + Single-Session parallel
- [x] Schulungsdoku: Technik, Bedienung, Roadmap
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
