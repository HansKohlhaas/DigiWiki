# DigiWiki – Bedienungsanleitung (Komplett)

**Stand:** Juni 2026  
**Für wen:** Alle Nutzer — PC und Handy  
**Kurzversion:** [Anleitung_Nutzer_Kurzreferenz.md](Anleitung_Nutzer_Kurzreferenz.md)

---

## 1. Was ist DigiWiki?

DigiWiki ist Ihr **Firmen-Assistent im Browser**. Sie stellen Fragen in normaler Sprache und erhalten Antworten aus:

- der **CRM-Datenbank** (Firmen, Personen, Produkte, Marktdaten)
- **Dokumenten** (Verträge, Anleitungen, Brandvoice)
- bei Bedarf der **Live-Website** einer Firma
- als **KI-Briefing** zusammengefasst

**Wichtig:** DigiWiki läuft auf dem **Büro-PC**. PC aus = keine Nutzung (auch nicht vom Handy).

---

## 2. Zugang

| Von | URL |
|-----|-----|
| **PC** | `http://localhost:8501` |
| **Handy** | `http://100.x.x.x:8501` (Tailscale grün, IP aus `digiwiki_zugang.txt`) |

Details: [Anleitung_Nutzer_Handy.md](Anleitung_Nutzer_Handy.md) · [DigiWiki_Verbindung_Einrichtung_Schulung.md](DigiWiki_Verbindung_Einrichtung_Schulung.md)

**Handy:** URL in **Chrome** eintippen — keine Link-Vorschau aus WhatsApp.

---

## 3. Oberfläche

```
┌──────────────────────────────────────────────┐
│  DigiWiki Zentrale                           │
├──────────────────────────────────────────────┤
│  🎤 Kommando-Feld + Ausführen                │
├──────────────────────────────────────────────┤
│  💬 Wiki & Daten | 📬 Mails | 📅 Agenda       │
├──────────────────────────────────────────────┤
│  Chat-Verlauf + Eingabefeld unten            │
└──────────────────────────────────────────────┘
```

**Einstieg:** Bereich **💬 Wiki & Daten**.

---

## 4. Modi im Chat

| Modus | Bedeutung | Wann? |
|-------|-----------|-------|
| **🎯 Auto (SQL → Web → MD → KI)** | Intelligent: Datenbank → Website → Archiv → Briefing | **Standard — empfohlen** |
| **🧠 Wiki-Wissen** | Nur Dokumente (Verträge, Anleitungen, Brandvoice) | Verfahren, Verträge |
| **🗄️ Datenbank (SQL)** | Nur Tabellen | Listen, Zahlen, Adressen |

### Was passiert im Auto-Modus?

1. **Datenbank** — Firmen, Personen, Produkte aus Access
2. **Live-Website** — wenn DB leer (Einzel-Firma)
3. **MD-Archiv** — Offline-Snapshot der Firmen-Website
4. **KI-Briefing** — lesbare Zusammenfassung (besonders bei Produktfragen)

Bei **Verfahrensfragen** („Wie richte ich DigiBest ein?“) → automatisch **Wiki**, nicht SQL.

---

## 5. Fragen stellen — Beispiele

### Firmen & Markt (Auto)

| Frage | Quelle |
|-------|--------|
| *Was ist das Narrativ von Hexal?* | SQL (Stammfelder) |
| *Wer ist GF bei Klosterfrau?* | SQL (Personen + ref_funktionen) |
| *Welche Produkte hat Ratiopharm?* | SQL (ArtikelDB) + KI-Briefing |
| *Top-Produkte von Sanofi* | SQL (Freitext-Felder topprodukte) |
| *Briefing zu Hexal* | SQL + ggf. Live-Web + KI-Briefing |

### Folgefragen

Nach einer Firmenantwort können Sie kurz nachfragen:

- *„Und die Top-Produkte?“*
- *„Welche Produkte haben die denn?“*
- *„Was ist deren Marktzielgruppe?“*

DigiWiki erkennt die **gleiche Firma** (kundennumm) und filtert korrekt.

### Wiki / Dokumente

| Frage | Modus |
|-------|-------|
| *Wie wird DigiBest für die Industrie eingerichtet?* | Auto → Wiki (Verfahren) |
| *Brandvoice: wie emotional?* | Wiki, Bereich Brandvoice |
| *Was steht im Vertrag zu …?* | Wiki |

### Wissensbereich (Dropdown)

Filtert nur die **Dokument-Suche**: Verfahren, Verträge, Brandvoice, Formulare …

---

## 6. Antworten verstehen

| Anzeige | Bedeutung |
|---------|-----------|
| 🗄️ Stufe 1: CRM-Datenbank | Tabellen-Ergebnis |
| ✨ Stufe 4: KI-Synthese | Lesbares Briefing |
| 🌐 Stufe 2: Live-Website | Aktuelle Firmen-Website |
| 📄 Stufe 3: MD-Archiv | Offline-Website-Snapshot |
| 🧠 Wiki-Dokumente | Aus indexierten Dateien |
| 📚 Quellen | Dateinamen / URLs |

Bei SQL-Antworten: **Briefing oben**, Rohdaten im aufklappbaren Bereich.

---

## 7. Export & Chat

- **📌 Export markieren** — Antwort für Markdown-Export vormerken
- **👁️ Ausblenden** — aus Chat ausblenden (Export bleibt)
- **Chat-Verlauf leeren** — neues Gespräch (System-Status)

Exportierte Paare landen in `Antworten/` (am PC).

---

## 8. Spracheingabe (Mikro 🎤)

- Neben Eingabefeldern: **Diktat** (Google-Spracherkennung)
- Am **PC** zuverlässiger als am Handy
- Internet erforderlich

---

## 9. Mails & Agenda (Kurz)

| Bereich | Funktion | Handy |
|---------|----------|-------|
| **📬 Mails** | Entwürfe, Kontaktsuche | Entwurf ja, Versand oft nur PC |
| **📅 Agenda** | Outlook-Termine, Notizen | Anzeige ja, Outlook am PC nötig |

---

## 10. Typische Probleme

| Problem | Lösung |
|---------|--------|
| Keine Antwort / Timeout Handy | Tailscale grün? PC an? `start.bat` am PC |
| „Adresse nicht gefunden“ | IP-URL `http://100.x.x.x:8501`, nicht `.ts.net` |
| Nur Vorschau, kein Tippen | In Chrome öffnen, nicht WhatsApp-Vorschau |
| Falsche Firma bei Folgefrage | Chat leeren, Firma explizit nennen |
| Wiki findet Anleitung nicht | Datei unter `Einrichtung + Schulung`? Wächter-Lauf abwarten |

---

## 11. Weitere Anleitungen

| Dokument | Inhalt |
|----------|--------|
| [Anleitung_Nutzer_Handy.md](Anleitung_Nutzer_Handy.md) | Handy Schritt für Schritt |
| [Anleitung_Nutzer_Bedienung.md](Anleitung_Nutzer_Bedienung.md) | Ausführliche Bedienung (Legacy, detailliert) |
| [Anleitung_Nutzer_Kurzreferenz.md](Anleitung_Nutzer_Kurzreferenz.md) | Einseitiger Spickzettel |
| [DigiWiki_Technische_Zusammenhaenge.md](DigiWiki_Technische_Zusammenhaenge.md) | Technik für Admins |
