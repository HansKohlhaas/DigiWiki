# SQL-Regression – typische Firmenfragen (Schritt 1 vor Kaskade)

**Zweck:** Alltagsfragen gegen NL2SQL + Access prüfen. Intern — nicht Nutzer-Doku.

**Ausführen:** `sql_regression_test.bat` oder  
`python sql_regression_test.py`

Ergebnis: `sql_regression_ergebnis.md` (dieser Ordner)

---

## Die 10 Firmen-/Marktfragen (soll → SQL)

| # | Frage | Erwartete Tabellen/Felder | Anmerkung |
|---|-------|---------------------------|-----------|
| 1 | Was ist das Narrativ von Hexal? | `stammdatenindustrie.narrativ` | Hexal AG, kundennumm 50000001 |
| 2 | Marktzielgruppe von Hexal | `Marktzielgruppe` | z. B. „Apotheken IS“ |
| 3 | Top-Produkte von Hexal | `topprodukte` / `top_produkte` | Freitext in DB vorhanden |
| 4 | Wer ist Geschäftsführer bei Hexal? | `crm_personen` + `ref_funktionen` | ebene 1–2, JOIN über funktionid |
| 5 | Firmen in Akquiseklasse 3 mit Apotheken-Fokus | `akquiseklasse`, `Marktzielgruppe` | **nicht** `apotheken_fokus` (leer) |
| 6 | D2P-Score und Begründung von Hexal | `d2p_score`, `d2p_begruendung` | Score kann NULL sein — SQL trotzdem ok |
| 7 | Wie viele ABDA-Artikel hat Hexal? | `abdaartikel` JOIN `anbieternummer` | JOIN: `anbieter_nr` → `anbieternummer` |
| 8 | Adresse und Website von Sanofi-Aventis Deutschland | `stammdatenindustrie` Adresse/URL-Felder | Firma existiert in DB |
| 9 | Wer stellt Hustensaft her? | `abdaartikel` LIKE Husten | Produkt-Suche |
| 10 | Welche Ansprechpartner hat Hexal mit Telefon? | `crm_personen` | Liste mit Telefon |

## 2 Klassifikator-Checks (soll → Wiki, kein SQL)

| # | Frage | Erwartet |
|---|-------|----------|
| W1 | Wie läuft unser Bestellablauf ab? | `wissen` |
| W2 | Brandvoice Hans zu Emotionalität | `wissen` |

---

## Bewertung pro Frage

- **Klassifikation:** Auto-Router → `datenbank` oder `wissen`
- **SQL:** enthält erwartete Tabelle/Felder, läuft ohne Fehler
- **Ergebnis:** mindestens 1 Zeile (wo sinnvoll)

Lücken → `db_spalten.csv`, `db_joins.csv`, `SEMANTISCHE_FELDALIASE` in `sql_frage_katalog.py`
