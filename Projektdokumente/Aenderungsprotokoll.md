# DigiWiki – Änderungsprotokoll

**Zweck:** Funktionale **Programm-Änderungen** erfassen; Übernahme ins Bedienungshandbuch erst nach **`OK`** (GROSSBUCHSTABEN).

**Workflow:** [DOKUMENTATIONS_WORKFLOW.md](DOKUMENTATIONS_WORKFLOW.md)

**Hinweis:** Interne Tests und Analysen (z. B. `md_personen_abgleich.py`, Lückenanalyse, Testfragen) gehören **nicht** ins Nutzer-Handbuch und **nicht** in die Streamlit-UI / SQL-Katalog.

---

## Ausstehend (wartet auf OK)

| Datum | Änderung | Betroffene Docs | Status |
|-------|----------|-----------------|--------|
| 2026-06-24 | **Dauerbetrieb:** Diagnose-Skript, End-to-End-Erreichbarkeit (HTTPS+WS), PID-Sync, Keepalive repariert lokal+extern | `Anleitung_PC_und_Handy_Einrichtung_Admin.md`, `PROJEKT_STATUS.md` | Ausstehend |
| 2026-06-22 | **Dauerbetrieb:** Keepalive 2 Min + Login-Trigger, Watchdog-Pruefung, schnellere Helfer-Intervalle, `install_dauerbetrieb.bat`, Sleep-Guard am Netzstrom | `Anleitung_PC_und_Handy_Einrichtung_Admin.md`, `DigiWiki_Verbindung_Einrichtung_Schulung.md` | Ausstehend |
| 2026-06-22 | **Handy-Erreichbarkeit:** Keepalive prüft Tailscale Serve/WebSocket + Handy-Offline-Log; `digiwiki_write_zugang.ps1` HTTPS als Primaer-URL | `Anleitung_Nutzer_Handy.md`, `DigiWiki_Verbindung_Einrichtung_Schulung.md` | Ausstehend |
| 2026-06-24 | **Handy-Zugang:** IP-URL (`http://100.x:8501`) als einziges Primaer-Lesezeichen statt HTTPS/.ts.net | `Anleitung_Nutzer_Handy.md`, `digiwiki_zugang.txt` | Ausstehend |
| 2026-06-24 | **Dauerbetrieb:** Keepalive beendet venv-Launcher nicht mehr faelschlich; PID-Datei = Port-Prozess; Watchdog-Erkennung robuster | `Anleitung_PC_und_Handy_Einrichtung_Admin.md`, `PROJEKT_STATUS.md` | Ausstehend |

---

## Bestätigt (OK erhalten → Docs aktualisiert)

| OK-Datum | Änderung | Aktualisierte Docs |
|----------|----------|-------------------|
| 2026-06-24 | **Datenbankpflege:** Hauptreiter, Auto-Pflege (Akquiseklasse, Dauerbetrieb/Intervalle, Datensatz-Bereich), Live-Web → crm_personen + Stammdaten | `Anleitung_Nutzer_Bedienung.md`, `PROJEKT_STATUS.md` |
| 2026-06-24 | **Datenbankpflege:** URL-Gueltigkeit vor Live-Web; persistenter Playwright-Chrome-Profilordner | `Anleitung_Nutzer_Bedienung.md`, `PROJEKT_STATUS.md` |
| 2026-06-24 | **Datenbankpflege:** KI-Plausibilitaet setzt Anrede, funktionid, funktionsbezeichnung | `Anleitung_Nutzer_Bedienung.md`, `PROJEKT_STATUS.md` |
| 2026-06-24 | **Funktionszuordnung:** Live-Suche nutzt `crm_funktion_synonyme` (exakt, Teilstring, TF-IDF) vor ref_funktionen | `PROJEKT_STATUS.md` |
| 2026-06-22 | **Wiki-Waechter:** Schicht-Zaehler korrekt (Basis vor Lauf), Fehler-Dateien mit Pfad und Grund in E-Mail | `PROJEKT_STATUS.md`, `Anleitung_PC_und_Handy_Einrichtung_Admin.md` |
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
