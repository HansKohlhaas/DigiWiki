# DigiWiki Orakel – To-do für morgen (18.06.2026)

**Ziel:** Vom heutigen Stand (SQL + Live-Web + Gesprächskontext) zum **vollständigen Orakel** — eine Antwort aus allen Quellen, aktuell, nachvollziehbar, ohne CRM-MD-Rauschen.

**Heute erledigt:** Produktschwerpunkt + Region im Folgefragen-Kontext (`frage_kontext.py`); Live-Web für Einzelfirmen; CRM-Sync Personen aus Impressum.

---

## 🔴 Morgen früh – Verifizieren & festziehen

- [ ] **Streamlit neu starten** und Kontext-UX testen:
  - Frage 1: „Briefing Hexal“ → Caption zeigt Firma, Schwerpunkt, Region
  - Frage 2: „Und die Top-Produkte?“ / „Wer sitzt in der Region?“ → Folgefrage nutzt Schwerpunkt + PLZ/Ort
- [ ] **3–5 Folgefragen-Matrix** dokumentieren (Hexal, Stada, ein regionaler Hersteller)
- [ ] **`sql_regression_test.bat`** laufen lassen; Ergebnis mit Kontext-Tests abgleichen
- [ ] **Live-Web Personen-Review:** `validation_status=auto_web` in Access prüfen — Duplikate, falsche Funktionen?

---

## 🟡 Stufe 3 – MD-Fallback (fehlt noch komplett)

Roadmap: MD **nur** per `kundennumm`, nicht über Chroma.

- [ ] Modul `firmen_md_fallback.py` (oder Erweiterung `wissens_kaskade.py`):
  - Pfad `C:\Eigene Projekte\MD\{kundennumm}_*.md`
  - Max. ~1,5 MB lesen, relevante Abschnitte (GF, Sortiment, Impressum)
  - Nur wenn SQL **und** Live-Web die Frage nicht beantworten
- [ ] In `15_wiki_web_ui.py`: Kaskade SQL → Web → **MD** → (später KI) verdrahten
- [ ] UI-Caption: „📄 Stufe 3: MD-Archiv (Fallback)“

---

## 🟡 Stufe 4 – KI-Synthese (das eigentliche „Orakel“)

Heute: getrennte Ausgaben (Tabelle, Impressum-Text, Wiki-Chunk). **Soll:** ein Briefing.

- [ ] Prompt-Modul `orakel_synthese.py`:
  - Input: Frage + SQL-JSON + Web-Text + optional MD-Ausschnitt + Gesprächskontext
  - Output: strukturiertes C-Level-Briefing mit **Quellenblöcken** (SQL / Web / MD)
- [ ] Gemini 2.5 Flash (bestehend) als Standard; Token-Limits für Web-Text kürzen
- [ ] Streamlit: Toggle „Rohdaten anzeigen“ vs. „Orakel-Antwort“

---

## 🟡 Index-Hygiene (Phase C – Chroma entlasten)

- [ ] CRM-MD-Ordner aus Standard-Chroma **ausschließen** (`DIGIWIKI_CHROMA_EXCLUDE_MD`) — **implementiert**, Wächter-Lauf bereinigt Altbestand
- [ ] Wiki-Wächter (`9_wiki_waechter.py`): MD-Watch optional abschaltbar — CRM-MD wird übersprungen, nicht mehr indexiert
- [x] Metadaten `bereich=crm_archiv` für alte Scrapes — nicht in Firmensuche
- [ ] Nach Bereinigung: Chroma-Größe + 5 Wiki-Testfragen (Brandvoice, Verträge)

---

## 🟡 Cache & Infrastruktur

- [ ] **`web_cache` in Access** statt `live_web_cache.json` (ephemeral auf Render; lokal auch robuster)
  - Felder: `kundennumm`, `url`, `text`, `cache_typ` (basis/fuehrung), `abgerufen_am`
- [ ] TTL + Invalidierung bei manuellem „Neu scrapen“
- [ ] Config-Flags: `DIGIWIKI_KASKADE_WEB`, `DIGIWIKI_KASKADE_MD`, `DIGIWIKI_KASKADE_KI`

---

## 🟡 Wiki-Stabilisierung (Verfahren / Einrichtung + Schulung)

- [x] **Bereichs-Tagging:** Pfade unter `Einrichtung + Schulung` / `Anleitungen` → `verfahren` (`config.py`)
- [x] **Auto-Router:** Einrichtungs-/Anleitungsfragen → Wiki (`ist_verfahren_wiki_frage`)
- [x] **Chroma-Filter:** Bereich `verfahren` inkl. Pfad-Fallback für bereits indexierte Dateien
- [x] **CRM-MD aus Standard-Wiki-Suche ausschließen** (`DIGIWIKI_CHROMA_EXCLUDE_MD`, Wächter bereinigt Index)
- [x] **Verfahren-Direktpfad** `verfahren_wiki.py` (wie Brandvoice, Einrichtung + Schulung)
- [ ] **Konvention:** Anleitungen künftig unter `DIGIBEST\Einrichtung + Schulung\` ablegen

---

- [ ] **Regionaler Bezug bei Listen-Abfragen:** gemeinsame PLZ/Ort-Bündelung (Bayern, NRW) in SQL-Prompt
- [ ] **Produktschwerpunkt bei Marktfragen:** „Wer stellt Hustensaft her?“ → Kontext aus erster Zeile der Liste
- [ ] Folgefragen-Erkennung: „in der Nähe“, „Konkurrenz“, „vergleichbare Firmen“
- [ ] `baue_wiki_kontext_block()` in Wiki-Pfad einbinden (noch ungenutzt?)

---

## 🟡 Veredelung CRM (Phase D – Anfang)

- [ ] UI: „Live-Web-Personen prüfen“ — Liste `auto_web` mit Übernehmen/Löschen
- [ ] `md_personen_abgleich` → optionaler Import-Workflow
- [ ] Audit: `quelle`, `geprueft_am` bei manueller Freigabe

---

## 🟢 Qualität & Regression (laufend)

- [ ] Testfragen-Matrix aus `Wiki_Lueckenanalyse.md` §8 auf **20 Fragen** erweitern
- [ ] Automatisierter Test: SQL + (mock) Web + Kontext-Anreicherung
- [ ] Fehlerprotokoll: fehlgeschlagene Fragen + generiertes SQL loggen

---

## 🟢 Nice-to-have (wenn Zeit bleibt)

- [ ] Async Spinner während Live-Web (bessere UX bei 10–15 s)
- [ ] `firmen_live_test.bat` um Impressum + Kontext-Folgefrage erweitern
- [ ] Tailscale-Handy: Mikro + Folgefragen im Chat testen

---

## Definition „vollkommenes Orakel“ (Done-Kriterien)

| Kriterium | Status |
|-----------|--------|
| SQL liefert strukturierte Basis inkl. Profil/Region | ✅ weitgehend |
| Live-Web für Einzelfirmen (Impressum, GF) | ✅ |
| Personen zurück ins CRM | ✅ (Review offen) |
| Gesprächskontext inkl. Schwerpunkt + Region | ✅ (heute) |
| MD gezielt per kundennumm | ❌ |
| Eine KI-Synthese mit Quellen | ❌ |
| Kein CRM-MD-Rauschen in Wiki-Suche | ❌ |
| Persistenter Web-Cache in Access | ❌ |
| Regression + Review-Workflow | 🟡 teilweise |

---

## Empfohlene Reihenfolge morgen

1. Verifizierung Kontext (30 Min)
2. MD-Fallback Stufe 3 (2–3 h)
3. KI-Synthese Stufe 4 – MVP (2–3 h)
4. Chroma-Ausschluss CRM-MD (1 h)
5. Rest: Cache Access, Review-UI

---

*Bezug: [Roadmap_Wissens_Kaskade.md](Roadmap_Wissens_Kaskade.md), [PROJEKT_TODO.md](PROJEKT_TODO.md)*
