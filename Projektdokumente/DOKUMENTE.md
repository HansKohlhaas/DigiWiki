# DigiWiki – Projektdokumente

Übersicht — **Nutzer-Dokumentation** vs. **interne Entwicklung**.

---

## Nutzer & Administrator

| Dokument | Inhalt |
|----------|--------|
| [DigiWiki_Schulungs_Handbuch.md](DigiWiki_Schulungs_Handbuch.md) | **Einstieg Schulung** — Übersicht aller Anleitungen |
| [DigiWiki_Bedienungsanleitung_Komplett.md](DigiWiki_Bedienungsanleitung_Komplett.md) | **Bedienungsanleitung** (aktuell, Kaskade, Folgefragen) |
| [Anleitung_Nutzer_Handy.md](Anleitung_Nutzer_Handy.md) | Zugang vom Smartphone (Tailscale) |
| [Anleitung_Nutzer_Bedienung.md](Anleitung_Nutzer_Bedienung.md) | Ausführliche Bedienung (Legacy) |
| [Anleitung_Nutzer_Kurzreferenz.md](Anleitung_Nutzer_Kurzreferenz.md) | Einseitiger Spickzettel |
| [Anleitung_Nutzer_Kurzreferenz.html](Anleitung_Nutzer_Kurzreferenz.html) | Kurzreferenz drucken / PDF |
| [Anleitung_PC_und_Handy_Einrichtung_Admin.md](Anleitung_PC_und_Handy_Einrichtung_Admin.md) | Admin: PC, Tailscale, Start |
| [DigiWiki_Verbindung_Einrichtung_Schulung.md](DigiWiki_Verbindung_Einrichtung_Schulung.md) | Verbindung, URLs, Helferprogramme, Tasks |

---

## Entwicklung & Planung (nicht für Endnutzer)

| Dokument | Inhalt |
|----------|--------|
| [DigiWiki_Technische_Zusammenhaenge.md](DigiWiki_Technische_Zusammenhaenge.md) | **Technikbericht** — Module, Datenfluss |
| [Roadmap_Wissens_Kaskade.md](Roadmap_Wissens_Kaskade.md) | Roadmap SQL → Web → MD → KI (Stand erledigt/offen) |
| [PROJEKT_STATUS.md](PROJEKT_STATUS.md) | Technischer Softwarestand |
| [PROJEKT_TODO.md](PROJEKT_TODO.md) | Offene Aufgaben |
| [DOKUMENTATIONS_WORKFLOW.md](DOKUMENTATIONS_WORKFLOW.md) | OK-Workflow für Doc-Updates |
| [Aenderungsprotokoll.md](Aenderungsprotokoll.md) | Bestätigte Programm-Änderungen |

---

## Intern / Test (nicht im Programm, keine Nutzer-Doku)

Nur für Entwicklung und Qualitätssicherung — **erscheinen nicht in DigiWiki (UI/SQL)**:

| Datei | Zweck |
|-------|--------|
| [Wiki_Lueckenanalyse.md](Wiki_Lueckenanalyse.md) | Analyse Wiki vs. SQL (Arbeitsnotiz) |
| [Testfragen_Wiki_Dokumente.md](Testfragen_Wiki_Dokumente.md) | 20 Testfragen Wiki-Dokumente |
| `md_personen_abgleich.py` / `.bat` | CLI: MD-Personen vs. CRM (Access-Tabelle) |

---

## Daten & SQL (Programm)

| Datei | Inhalt |
|-------|--------|
| [data_dictionary.csv](data_dictionary.csv) | Spalten-Lexikon |
| Projektroot: `db_tabellen.csv`, `db_joins.csv`, `db_spalten.csv`, `db_schema.txt` | NL2SQL-Metadaten |

---

## Empfohlene Lesereihenfolge

**Nutzer:** Bedienung → Kurzreferenz  
**Entwicklung:** PROJEKT_STATUS → Roadmap → PROJEKT_TODO
