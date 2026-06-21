# DigiWiki – Vollständigkeitstest: Inhalte aus Dokumenten

**Stand:** Juni 2026  
**Zweck:** Wiki-RAG gezielt prüfen (Verträge, Verfahren, Brandvoice, Formulare …) — **nicht** SQL/Marktdaten.

**So testen:**

1. Modus: **🧠 Wiki-Wissen** (nicht Auto/SQL — sonst vermischt sich das Ergebnis)
2. Optional: **Wissensbereich-Filter** wie in Spalte „Bereich“
3. Pro Frage ausfüllen: Antwort OK? | Quelle plausibel? | Lücke?
4. **Export:** Im Chat-Bereich **„📌 Antworten markieren & zusammenfassen“** → markierte Fragen als Markdown in Ordner `Antworten/` speichern

**Legende Komplexität:** 🟢 leicht · 🟡 mittel · 🔴 schwer · ⚡ Grenzfall (Routing/Quellen prüfen)

---

## Auswertung (Kurz)

| Kategorie | Anzahl Fragen | OK | Teilweise | Fehl |
|-----------|---------------|-----|-----------|------|
| Verfahren | 4 | | | |
| Verträge | 4 | | | |
| Brandvoice | 3 | | | |
| Formulare | 2 | | | |
| Aktuell / Notizen | 2 | | | |
| Vollzugriff / Querschnitt | 3 | | | |
| Grenzfälle | 2 | | | |
| **Summe** | **20** | | | |

---

## Die 20 Testfragen

### Verfahren & Abläufe

| # | 🎯 | Bereich | Frage | Was prüfen? | OK / Notiz |
|---|-----|---------|-------|-------------|------------|
| 1 | 🟢 | `verfahren` | Wie läuft unser **Bestellablauf** ab — welche Schritte sind dokumentiert? | Konkrete Schritte aus echtem Leitfaden; **keine** CRM-MD-Quelle (`5000…_Firma.md`) | |
| 2 | 🟡 | `verfahren` | Was ist **MSV** bei DigiBest und welcher **Prozess** ist dafür beschrieben? | Begriff + Ablauf; Quelle aus DigiBest-internem Doc/PDF | |
| 3 | 🔴 | `verfahren` | Im **Vertriebs- oder Akquiseprozess**: Was passiert **nach** der Erstansprache und **wer** ist laut Dokument zuständig? | Mehrstufige Antwort; fehlt evtl. komplett → **Dokument anlegen** | |
| 4 | 🟡 | `verfahren` | Gibt es eine **Checkliste oder Arbeitsanweisung** vor Kundengesprächen oder Vor-Ort-Terminen? | Treffer aus Verfahren/Formular; sonst Lücke dokumentieren | |

---

### Verträge & Rechtliches

| # | 🎯 | Bereich | Frage | Was prüfen? | OK / Notiz |
|---|-----|---------|-------|-------------|------------|
| 5 | 🟢 | `vertraege` | Welche **Laufzeit oder Kündigungsfrist** ist in einem unserer **AV-Verträge** (Auftragsverarbeitung) geregelt? | Konkrete Frist + **PDF/DOCX-Quelle**, nicht SQL | |
| 6 | 🟡 | `vertraege` | Welche **Pflichten** haben wir laut **Datenschutz-/AV-Vertrag** gegenüber dem Auftraggeber? | Aufzählung aus Vertragstext | |
| 7 | 🔴 | `vertraege` | Was steht in **unserem Kundenvertrag** zu **[ konkreter Kunde / Curaden / bekanntes PDF ]** bezüglich Leistungsumfang und Vergütung? | Firmenspezifisch; Quelle muss Vertrags-PDF sein | |
| 8 | 🟡 | `vertraege` | Gibt es **AGB oder Lizenzbedingungen**, die für DigiBest-Leistungen gelten — was ist der Kern? | Rechtstext, nicht Marketing-Website-MD | |

---

### Brandvoice & Kommunikation

| # | 🎯 | Bereich | Frage | Was prüfen? | OK / Notiz |
|---|-----|---------|-------|-------------|------------|
| 9 | 🟢 | `vollzugriff` * | Wie soll **Brandvoice Hans** in Bezug auf **Emotionalität** klingen? | Direkter Brandvoice-Pfad; Quelle `.docx` Brandvoice Hans | |
| 10 | 🟡 | `vollzugriff` * | Worin unterscheidet sich **Brandvoice DigiBest** von **Brandvoice Hans** (Tonalität, Anrede)? | Vergleich aus zwei Brandvoice-Dateien | |
| 11 | 🔴 | `vollzugriff` * | Formuliere laut Brandvoice **Hans** ein kurzes **Erstanschreiben an eine Apotheke** zum Thema Bestelloptimierung — welche Stilregeln gelten dabei? | Antwort + explizite Regeln aus Doc; kein freies Erfinden | |

\* Brandvoice wird intern oft über den **Brandvoice-Wiki-Pfad** geroutet; bei reinem Wiki-Filter ggf. Modus Wiki + Frage mit „Brandvoice“ im Text.

---

### Formulare & Vorlagen

| # | 🎯 | Bereich | Frage | Was prüfen? | OK / Notiz |
|---|-----|---------|-------|-------------|------------|
| 12 | 🟢 | `formulare` | Gibt es eine **Mustervorlage oder Vorlage** für **Angebote** oder **Anschreiben**? | Dateiname + Kurzbeschreibung | |
| 13 | 🟡 | `formulare` | Welche **Pflichtfelder** oder **Abschnitte** muss laut Vorlage ein **[ Angebot / Antrag / Formular aus Ihrem Bestand ]** enthalten? | Strukturierte Liste aus Template-Doc | |

---

### Aktuell, Notizen, Reports

| # | 🎯 | Bereich | Frage | Was prüfen? | OK / Notiz |
|---|-----|---------|-------|-------------|------------|
| 14 | 🟡 | `aktuell` | Was ist der **aktuelle Stand** laut **Projektprotokoll oder Statusbericht** zum DigiWiki / zur Wissensbasis? | Treffer aus Report/Protokoll; Datum nennen wenn möglich | |
| 15 | 🔴 | `aktuell` | Welche **offenen Punkte oder To-dos** stehen in **Projektnotizen** zur Wiki-Indizierung oder SQL-Anbindung? | Aus PROJEKT_TODO-ähnlichem Doc im Index — sonst Index-Lücke | |

---

### Vollzugriff & Querschnitt (mehrere Dokumenttypen)

| # | 🎯 | Bereich | Frage | Was prüfen? | OK / Notiz |
|---|-----|---------|-------|-------------|------------|
| 16 | 🟡 | `vollzugriff` | Welche **Leistungen und USPs** beschreibt DigiBest in **internen Unterlagen** (nicht Firmen-CRM)? | DigiBest-Marketing/PDF; **nicht** `5000…_Hexal.md` | |
| 17 | 🔴 | `vollzugriff` | Was empfehlen unsere **Marketing- oder Social-Media-Unterlagen** für die **Ansprache von Apotheken**? | Inhalt aus echtem Strategie-Doc; Quellen nennen | |
| 18 | 🔴 | `vollzugriff` | Nenne **drei konkrete Aussagen** aus DigiBest-Dokumenten zu **Bestelloptimierung** und gib die **Quelldateien** an. | 3 Fakten + 3 Quellen; prüft Quellenqualität | |

---

### Grenzfälle (Routing & Fehlquellen)

| # | 🎯 | Bereich | Frage | Was prüfen? | OK / Notiz |
|---|-----|---------|-------|-------------|------------|
| 19 | ⚡ | `vertraege` | *„Was ist die Adresse von Hexal?“* — **bewusst falsch** im Wiki-Modus: sollte **keine** sinnvolle Vertragsantwort liefern (Adresse = SQL). | Wiki antwortet ehrlich „keine Info“ **oder** verweist nicht auf CRM-MD-Müll als Vertrag | |
| 20 | ⚡ | `vollzugriff` | *„Erkläre mir den Unterschied zwischen Wiki-Wissen und Datenbank-Modus anhand unserer Anleitung.“* | Meta-Frage: Treffer aus **Bedienungs-/Admin-Anleitung** falls indexiert unter `C:\Verwaltung` / Projekt | |

---

## Bewertungsskala (pro Frage)

| Symbol | Bedeutung |
|--------|-----------|
| ✅ | Antwort inhaltlich korrekt, Quelle passend (PDF/DOCX/echtes MD, kein CRM-Scrape) |
| 🟡 | Teilweise richtig, falsche/zu vage Quelle, oder „keine Info“ obwohl Doc existiert |
| ❌ | Falsch, CRM-MD-Rauschen als Quelle, oder kompletter Ausfall |
| ➖ | Doc fehlt im Index — **Nacharbeit: Dokument anlegen oder indexieren** |

---

## Typische Fehlermuster (beim Nacharbeiten)

| Muster | Maßnahme |
|--------|----------|
| Quelle = `5000…_Firma.md` | CRM-MD aus RAG ausschließen (Roadmap Phase C) |
| „Keine Informationen“, Doc existiert | Pfad prüfen: unter `WATCH_ROOTS`? Endung `.pdf`/`.docx`? Wächter-Lauf |
| Brandvoice leer | `docx2txt` in venv; Brandvoice-Ordner prüfen |
| Vertrag nicht gefunden | PDF in Watch-Ordner legen; Bereich `vertraege` testen |
| Antwort erfunden | Prompt/RAG ok; ggf. `k` (Trefferzahl) erhöhen |

---

## Nach dem Test

1. Alle ❌ und 🟡 in `PROJEKT_TODO.md` oder Lückenliste übernehmen  
2. Fehlende Docs gemäß [Wiki_Lueckenanalyse.md](Wiki_Lueckenanalyse.md) §6 anlegen  
3. Erneut testen — nur die fehlgeschlagenen Nummern  

**Siehe auch:** [Roadmap_Wissens_Kaskade.md](Roadmap_Wissens_Kaskade.md) — langfristig CRM-MDs aus Standard-Wiki raus, Dokumenten-Wissen bleibt.

---

## Platzhalter anpassen

Bei Frage **7** und **13** konkrete Kunden-/Formularnamen einsetzen, die Sie wirklich im Index haben (z. B. aus `C:\Verwaltung` oder `C:\Eigene Projekte\DIGIBEST\`).
