# DigiWiki – Schulungs-Handbuch (Übersicht)

**Stand:** Juni 2026  
**Zweck:** Einstieg für Schulung, Einrichtung und Weiterentwicklung

---

## Für Nutzer

| Dokument | Wann lesen? |
|----------|-------------|
| [DigiWiki_Bedienungsanleitung_Komplett.md](DigiWiki_Bedienungsanleitung_Komplett.md) | **Hauptanleitung** — Chat, Modi, Beispielfragen |
| [Anleitung_Nutzer_Handy.md](Anleitung_Nutzer_Handy.md) | Erstes Mal vom Smartphone |
| [Anleitung_Nutzer_Kurzreferenz.md](Anleitung_Nutzer_Kurzreferenz.md) | Spickzettel zum Ausdrucken |

---

## Für Administrator / IT

| Dokument | Wann lesen? |
|----------|-------------|
| [DigiWiki_Verbindung_Einrichtung_Schulung.md](DigiWiki_Verbindung_Einrichtung_Schulung.md) | PC starten, Tailscale, Keepalive-Task |
| [Anleitung_PC_und_Handy_Einrichtung_Admin.md](Anleitung_PC_und_Handy_Einrichtung_Admin.md) | Detaillierte Admin-Einrichtung |
| [DigiWiki_Technische_Zusammenhaenge.md](DigiWiki_Technische_Zusammenhaenge.md) | **Technikbericht** — Module, Datenfluss, Konfiguration |

---

## Für Entwicklung & Planung

| Dokument | Wann lesen? |
|----------|-------------|
| [Roadmap_Wissens_Kaskade.md](Roadmap_Wissens_Kaskade.md) | **Roadmap** — erledigt vs. offen |
| [PROJEKT_STATUS.md](PROJEKT_STATUS.md) | Aktueller Softwarestand |
| [PROJEKT_TODO.md](PROJEKT_TODO.md) | Offene Aufgaben |
| [Wiki_Lueckenanalyse.md](Wiki_Lueckenanalyse.md) | Hintergrund: Wiki vs. SQL |

---

## Empfohlene Schulungs-Reihenfolge

1. **Zugang** — Handy/PC öffnen, Tailscale prüfen  
2. **Bedienung** — Auto-Modus, Beispielfragen, Folgefragen  
3. **Ergebnisse** — Stufen 1–4, Quellen, Export  
4. **Optional Admin** — `start.bat`, Keepalive, Wächter  

---

## Schnellstart-Befehle (PC)

| Aktion | Datei |
|--------|-------|
| DigiWiki starten | `start.bat` |
| Handy-Verbindung prüfen | `digiwiki_handy_reparieren.bat` |
| SQL-Regression | `sql_regression_test.bat` |
| Live-Web testen | `firmen_live_test.bat` |
| Autostart einrichten | `install_autostart.bat` |
| Keepalive-Task | `install_keepalive_task.bat` |
