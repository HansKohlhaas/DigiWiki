# DigiWiki – Änderungsprotokoll

**Zweck:** Funktionale **Programm-Änderungen** erfassen; Übernahme ins Bedienungshandbuch erst nach **`OK`** (GROSSBUCHSTABEN).

**Workflow:** [DOKUMENTATIONS_WORKFLOW.md](DOKUMENTATIONS_WORKFLOW.md)

**Hinweis:** Interne Tests und Analysen (z. B. `md_personen_abgleich.py`, Lückenanalyse, Testfragen) gehören **nicht** ins Nutzer-Handbuch und **nicht** in die Streamlit-UI / SQL-Katalog.

---

## Ausstehend (wartet auf OK)

| Datum | Änderung | Betroffene Docs | Status |
|-------|----------|-----------------|--------|
| — | *(keine)* | — | — |

---

## Bestätigt (OK erhalten → Docs aktualisiert)

| OK-Datum | Änderung | Aktualisierte Docs |
|----------|----------|-------------------|
| 2026-06-18 | **Antworten exportieren** | Bedienung §8, Kurzreferenz, README, PROJEKT_STATUS |
| 2026-06-18 | **Antwort ausblenden** | Bedienung §8, Kurzreferenz |

---

## Intern / Test (keine Nutzer-Doku)

| Artefakt | Zweck | Im Programm? |
|----------|-------|--------------|
| `md_personen_abgleich.py` / `.bat` | Einmal-Analyse MD vs. CRM → Access-Tabelle | ❌ nur Kommandozeile |
| `Wiki_Lueckenanalyse.md` | Entwickler-Analyse Wiki vs. SQL | ❌ |
| `Testfragen_Wiki_Dokumente.md` | Vollständigkeitstest Wiki | ❌ |

Diese Dateien bleiben im Repo zur internen Arbeit; sie werden nicht in README, Bedienung oder SQL-Routing eingebunden.
