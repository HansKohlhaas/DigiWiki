# DigiWiki – Bedienung und Nutzung (Anleitung für Nutzer)

**Für wen?** Alle, die DigiWiki **benutzen** wollen – ohne technische Einrichtung am PC.

**Zugang vom Handy:** Siehe zuerst `Anleitung_Nutzer_Handy.md` (Tailscale, Lesezeichen).

---

## 1. Was ist DigiWiki – in einfachen Worten?

DigiWiki ist Ihr **digitaler Assistent** im Browser. Sie können:

- **Fragen stellen** und Antworten bekommen
- **Firmen, Personen, Produkte** aus der Datenbank abfragen
- **Inhalte aus Dokumenten** nachlesen (Verträge, Anleitungen, Notizen …)
- **E-Mails und WhatsApp-Entwürfe** vorbereiten (wenn freigeschaltet)
- **Termine und Aufgaben** aus Outlook sehen (wenn am PC eingerichtet)

Sie schreiben oder sprechen eine Frage – DigiWiki liefert eine Antwort.  
So ähnlich wie ChatGPT, aber **mit den Daten und Dokumenten Ihrer Firma**.

---

## 2. Was muss erfüllt sein? (Voraussetzungen)

| Voraussetzung | Erklärung |
|---------------|-----------|
| **Zugang funktioniert** | Tailscale am Handy **grün**, Lesezeichen öffnet die Seite |
| **PC des Administrators läuft** | DigiWiki lebt auf dem **Büro-PC**, nicht in der Cloud. PC aus = keine Nutzung |
| **Internet** | Am Handy und am PC |
| **Browser** | Chrome, Firefox oder Safari – aktuell halten |
| **Geduld bei der ersten Antwort** | Manchmal dauert die Suche **10–30 Sekunden** – das ist normal |

### Wichtig: Nur ein Gerät gleichzeitig

Wenn Sie DigiWiki **am PC und am Handy** gleichzeitig offen haben, kann eine Meldung erscheinen:

> *„Diese Sitzung wurde auf einem anderen Gerät übernommen …“*

**Lösung:** Seite **neu laden** (F5) oder nur **ein Gerät** nutzen.

---

## 3. Der Bildschirm – Orientierung

Oben sehen Sie:

```
┌──────────────────────────────────────────────┐
│  Logo    DigiWiki Zentrale                   │
├──────────────────────────────────────────────┤
│  📊 System-Status (aufklappbar)              │
│  🎤 Kommando-Feld + 🚀 Ausführen             │
├──────────────────────────────────────────────┤
│  💬 Wiki & Daten | 📬 Mails | 📅 Agenda     │  ← Haupt-Bereiche
├──────────────────────────────────────────────┤
│  … Inhalt des gewählten Bereichs …           │
└──────────────────────────────────────────────┘
```

### System-Status (aufklappbar)

- Zeigt, wie viele **Dokumente** indexiert sind
- Button **„Chat-Verlauf leeren“** – startet das Gespräch von vorn (alte Fragen im Chat werden gelöscht)

### Kommando-Feld (oben)

Für **Schnellbefehle** per Text oder Diktat, z. B.:

- *„Rufe Max Mustermann an“* → zeigt Telefonnummern
- *„Notiere: Morgen Angebot nachfassen“* → speichert Outlook-Notiz (am PC)
- *„Wer ist GF bei Hexal?“* → startet Datenbank-Suche

Tippen → **🚀 Ausführen** drücken.

---

## 4. Die drei Haupt-Bereiche

| Bereich | Wofür? | Am Handy? |
|---------|--------|-----------|
| **💬 Wiki & Daten** | Fragen & Antworten (Hauptfunktion) | ✅ Ja |
| **📬 Mails & Kontakte** | E-Mail schreiben, beantworten, WhatsApp | ⚠️ Teilweise (Entwürfe ja, Versand oft nur am PC) |
| **📅 Agenda & Notizen** | Termine, Aufgaben, Notizen | ⚠️ Anzeige ja; Outlook am PC nötig |

**Für den Einstieg:** Bleiben Sie bei **💬 Wiki & Daten**.

---

## 5. Bereich „Wiki & Daten“ – so bedienen Sie den Chat

### Schritt für Schritt

1. Bereich **💬 Wiki & Daten** wählen (falls nicht schon aktiv)
2. **Modus** wählen (siehe unten) – Anfänger: **🎯 Auto**
3. Frage **tippen** oder **🎤 diktieren**
4. **Enter** oder Button **„Fragen“** drücken
5. Warten, bis die Antwort da ist
6. Antwort lesen – bei Wiki-Antworten auch **Quellen** beachten
7. Optional: **📌 Export markieren** / **👁️ Ausblenden** (unter der Antwort)

### Wo tippe ich die Frage?

- **Unten:** großes Chat-Feld (*„Frage ans Wiki oder die Datenbank …“*)
- **Darüber:** kleines Feld mit Mikrofon + Button **„Fragen“**
- **Oben:** Kommando-Feld für Sprachbefehle

---

## 6. Die drei Modi – was sie bedeuten

| Modus | Bedeutung | Wann nutzen? |
|-------|-----------|--------------|
| **🎯 Auto (SQL → Wiki)** | DigiWiki entscheidet selbst: erst **Datenbank**, bei leerem Ergebnis **Dokumente** | **Empfohlen** für fast alles |
| **🧠 Wiki-Wissen** | Sucht nur in **Dokumenten** (PDF, Word, Notizen …) | Verträge, Anleitungen, Brandvoice, Prozesse |
| **🗄️ Datenbank (SQL)** | Sucht nur in **Tabellen** (Firmen, Personen, Produkte …) | Adressen, Listen, Zahlen, Kontakte |

### Wissensbereich (bei Auto und Wiki)

Dropdown **„Wissensbereich“** – filtert die Dokument-Suche:

| Bereich | Sucht vor allem in … |
|---------|----------------------|
| **vollzugriff** | Allen Dokumenten |
| **verfahren** | Abläufen, Leitfäden, Checklisten |
| **formulare** | Vorlagen, Mustern |
| **vertraege** | Verträgen, Vereinbarungen |
| **datenbank** | DB-Dokumentation, Exporten |
| **aktuell** | Reports, Protokollen, aktuellen Ständen |

**Tipp:** Erst **vollzugriff** lassen. Nur einschränken, wenn zu viele irrelevante Treffer kommen.

---

## 7. Wie kommen die Antworten? – Zwei Antwort-Typen

### Typ A: 🧠 Antwort aus Wiki-Wissensbasis

**Wann?** Frage betrifft **Dokumente** (Texte, Verträge, Anleitungen …)

**So sieht es aus:**

- Fließtext-Antwort auf Deutsch
- Unten klein: **📚 Quellen:** Dateiname.docx, …
- Manchmal: *„Dazu liegen mir keine Informationen vor“*

**Was bedeutet das?**

- Die KI hat in den **indexierten Dateien** gesucht
- **Quellen** = aus welchen Dateien die Antwort stammt
- Keine Quellen + „keine Informationen“ = im Dokumentenbestand nichts Passendes gefunden

**Beispiel-Fragen:**

- *„Was steht im Vertrag mit Firma X zur Laufzeit?“*
- *„Wie ist das Verfahren für … beschrieben?“*
- *„Was sagt die Brandvoice Hans zum Thema Emotionalität?“*
- *„Was steht in der Anleitung zu …?“*

---

### Typ B: 🗄️ Antwort aus Datenbank (SQL)

**Wann?** Frage betrifft **strukturierte Daten** (Tabellen)

**So sieht es aus:**

- Meldung: *„X Datensätze gefunden“*
- **Tabelle** mit Spalten (Name, Ort, Telefon …)
- Tabelle kann **seitlich scrollen** (viele Spalten)

**Was bedeutet das?**

- DigiWiki hat Ihre Frage in eine **Datenbank-Abfrage** übersetzt
- Ergebnis = **Zeilen aus der CRM-/Firmen-Datenbank**
- *„Keine Treffer“* = nichts Passendes in der DB (bei **Auto** wird dann oft noch im Wiki nachgeschaut)

**Beispiel-Fragen:**

- *„Wer ist Ansprechpartner bei Hexal?“*
- *„Telefonnummer von Müller bei Bayer“*
- *„Adresse von Klosterfrau“*
- *„Alle Firmen in Köln“*
- *„Firmen in Akquiseklasse 3 mit Apotheken-Fokus“*
- *„Wer ist GF bei Bayer?“*
- *„Wer stellt in Deutschland Hustensaft her?“*
- *„Apotheken in München mit mehr als 10 Mitarbeitern“*

---

### Auto-Modus: Fallback

Im Modus **🎯 Auto** passiert Folgendes:

```
Ihre Frage
    ↓
Datenbank-Suche
    ↓
Treffer?  → Ja → Tabelle anzeigen
    ↓ Nein
Wiki-Suche
    ↓
Text-Antwort + Quellen
```

Das erklärt manchmal: Erst kurz „Durchsuche Datenbank …“, dann „wechsle zur Wiki-Wissensbasis“.

---

## 8. Antworten markieren, ausblenden und exportieren

Nach jeder **erfolgreichen** Antwort (Wiki-Text oder SQL-Tabelle) erscheinen **unter der Antwort** zwei Checkboxen nebeneinander:

| Checkbox | Wirkung |
|----------|---------|
| **📌 Für Export markieren** | Antwort wird in die **Export-Datei** aufgenommen (Standard: angehakt) |
| **👁️ Antwort ausblenden** | Antwort **im Chat unsichtbar** — bleibt aber **vollständig in der Export-Datei**, solange exportiert markiert |

### Antwort ausblenden

- Der Chat bleibt übersichtlich, z. B. bei vielen Einzelfragen oder vorübergehend unbrauchbaren Antworten.
- Statt des Textes sehen Sie: *„Antwort ausgeblendet — bleibt in der Export-Datei erhalten.“*
- Checkboxen bleiben sichtbar — **Ausblenden** wieder abwählen zum Einblenden.

### Antworten exportieren

1. Nach unten scrollen zum Bereich **„📌 Antworten exportieren (X/Y markiert)“** (unter dem Chat-Eingabefeld).
2. Optional: **Alle markieren** / **Alle abwählen**.
3. Optional: **Dokumenttitel** eingeben (sonst schlägt die KI einen Titel vor).
4. **„📝 Markierte zusammenfassen & speichern“** klicken.
5. DigiWiki erstellt eine **Markdown-Datei** mit:
   - **Gesamtzusammenfassung** (KI)
   - **allen markierten Einzelantworten** inkl. Quellen (auch ausgeblendete!)

**Speicherort:** Ordner `Antworten` im DigiWiki-Projekt (Pfad steht im Export-Bereich).

**Dateiname:** sprechend, z. B. `2026-06-18_wiki-test-vertraege-5-fragen.md`

**Hinweis:** Nur Antworten mit Inhalt (Wiki/SQL-Treffer) können markiert werden. Bei *„Keine Treffer“* ohne Wiki-Fallback gibt es nichts zu exportieren.

**Nach Neustart:** DigiWiki einmal mit `start.bat` neu starten, damit neue Funktionen aktiv sind.

---

## 9. Was kann ich fragen? – Übersicht nach Thema

### Personen & Kontakte

| Beispiel-Frage |
|----------------|
| Wer ist Ansprechpartner bei [Firma]? |
| Telefonnummer von [Name] bei [Firma] |
| Wer ist Geschäftsführer bei [Firma]? |
| E-Mail von [Person] |

### Firmen & Adressen

| Beispiel-Frage |
|----------------|
| Adresse von [Firma] |
| Alle Firmen in [Stadt] |
| Hersteller in Deutschland |
| LinkedIn-URL von [Firma] |

### Markt & Segment

| Beispiel-Frage |
|----------------|
| Firmen in Akquiseklasse 3 |
| Welche Marktzielgruppe hat [Firma]? |
| Firmen mit Apotheken-Fokus |
| Was ist das Narrativ / die Strategie von [Firma]? |

### Produkte & Artikel

| Beispiel-Frage |
|----------------|
| Wer stellt [Produkt] her? |
| Top-Produkte von [Firma] |
| Wie viele Artikel hat [Firma]? |
| Rx-Artikel von [Hersteller] |

### Apotheken

| Beispiel-Frage |
|----------------|
| Apotheken in [Stadt] |
| Apothekengruppe von [Apotheke] |

### Dokumente & Wissen (Wiki)

| Beispiel-Frage |
|----------------|
| Was steht im Vertrag über …? |
| Wie läuft das Verfahren … ab? |
| Was sagt die Brandvoice … zu …? |
| Zusammenfassung des Dokuments … |

---

## 10. Tipps für **gute** Fragen

| ✅ Besser | ❌ Schlechter |
|----------|-------------|
| *„Wer ist GF bei Hexal?“* | *„Hexal“* |
| *„Adresse von Klosterfrau in Deutschland“* | *„Gib mir alles“* |
| *„Firmen in Akquiseklasse 3 mit Apotheken-Fokus“* | *„Liste“* |
| Firmennamen **so schreiben wie in der DB** (z. B. „Bayer“, „Hexal“) | Sehr allgemeine Fragen ohne Kontext |

**Nachfragen gehen:** DigiWiki merkt sich den **Chat-Verlauf**. Sie können fragen:

- *„Und die Telefonnummer?“* (Bezug auf vorherige Antwort)
- *„Zeig mir mehr Details zu Zeile 2“* (manuell in der Tabelle nachschauen)

**Verlauf löschen:** System-Status → **Chat-Verlauf leeren** (wenn das Thema wechselt).

---

## 11. Mit den Ergebnissen arbeiten

### Bei Tabellen (Datenbank)

| Aktion | So geht's |
|--------|-----------|
| **Scrollen** | Tabelle horizontal/vertikal wischen (Handy) oder Scrollbalken (PC) |
| **Kopieren** | Text markieren (am PC einfacher) |
| **Export sammeln** | Mehrere Antworten markieren → **Zusammenfassen & speichern** (Abschnitt 8) |
| **Anrufen** | Nummer aus Tabelle abtippen – oder Kommando *„Rufe [Name] an“* oben |

DigiWiki speichert Tabellen **nicht automatisch** als Datei. Was Sie brauchen, kopieren Sie selbst.

### Bei Wiki-Antworten

| Aktion | So geht's |
|--------|-----------|
| **Quellen prüfen** | Unten **📚 Quellen** – dort steht die Original-Datei |
| **Original öffnen** | Datei auf dem Firmen-PC/Netzlaufwerk (Administrator fragen) |
| **Vertrauen** | Antworten basieren **nur** auf indexierten Dokumenten – bei Unsicherheit Quelle nachlesen |

### Ergebnis unbrauchbar?

1. Frage **präziser** formulieren
2. Anderen **Modus** wählen (Wiki statt Auto, oder umgekehrt)
3. **Chat-Verlauf leeren** und neu fragen
4. Administrator fragen, ob die **Daten/Dateien** überhaupt in DigiWiki liegen

---

## 12. Bereich „Mails & Kontakte“

### Neue E-Mail

1. Aufklappen: **✉️ Neue E-Mail verfassen**
2. **Empfänger suchen** (Name oder Firma)
3. Optional: **Brandvoice** wählen (Schreibstil „Hans“, „DigiBest“ oder „Ohne“)
4. Kurz beschreiben, **worum es geht**
5. **✨ KI-Entwurf** → Text prüfen und anpassen
6. **Senden** (braucht **Outlook am PC** des Administrators)

### E-Mail beantworten

- Liste der **Whitelist-Mails** (nur freigegebene Kontakte)
- Original lesen → Anweisung eingeben → **Entwurf generieren** → senden

### WhatsApp

1. **📱 Manuelle WhatsApp senden**
2. Kontakt suchen
3. Kurz beschreiben, was die Nachricht enthalten soll
4. **✨ KI-Entwurf** → **WhatsApp öffnen** (Link) → Nachricht einfügen/senden

**Brandvoice:** Drei Optionen – **BV Hans** (persönlich), **BV Digi** (Unternehmen), **Ohne** (neutral).

> **Am Handy:** Entwürfe erstellen geht gut. **E-Mail-Versand** über Outlook funktioniert nur, wenn der **PC mit Outlook** läuft und erreichbar ist.

---

## 13. Bereich „Agenda & Notizen“

| Funktion | Beschreibung |
|----------|--------------|
| **Terminkalender** | Termine der Woche aus Outlook |
| **Neue Notiz** | Text diktieren/tippen → in Outlook speichern |
| **Neue Aufgabe** | To-do mit Fälligkeitsdatum |
| **Aufgaben erledigen/löschen** | Buttons ✔️ / 🗑️ |

**Voraussetzung:** Outlook am **PC** des Administrators muss laufen und eingeloggt sein.

---

## 14. Spracheingabe (Diktat)

| Wo | Mikrofon-Symbol 🎤 |
|----|---------------------|
| Chat-Bereich | Neben dem Frage-Feld |
| Kommando oben | Im Bereich „Diktat aufnehmen“ |
| Mails / Agenda | Neben Textfeldern |

**Ablauf:** Mikrofon → sprechen → Text erscheint → **prüfen** → absenden.

**Hinweis:** Diktat braucht **Internet** (Google-Spracherkennung). Am **Desktop-PC** oft zuverlässiger als am Handy.

---

## 15. Was DigiWiki **nicht** kann

| Erwartung | Realität |
|-----------|----------|
| „Kennt alles im Internet“ | Nur **Firma-Datenbank** + **indexierte Dokumente** |
| „Immer 100 % richtig“ | KI kann irren – **wichtige Fakten prüfen** |
| „Funktioniert ohne PC“ | Der **Administrator-PC** muss laufen |
| „Alle E-Mails senden“ | Nur **Whitelist-Kontakte** |
| „Live-Internet-Recherche“ | Nein – nur hinterlegtes Wissen |
| „Excel-Datei exportieren“ | Tabellen manuell kopieren |

---

## 16. Häufige Meldungen – kurz erklärt

| Meldung | Bedeutung |
|---------|-----------|
| *Dazu liegen mir keine Informationen vor* | Weder DB noch Wiki hatten einen Treffer |
| *Keine Treffer in der Datenbank* | SQL leer; bei Auto folgt ggf. Wiki |
| *X Datensätze gefunden* | Erfolgreiche DB-Abfrage – Tabelle ansehen |
| *📚 Quellen: …* | Herkunft der Wiki-Antwort |
| *Diese Sitzung wurde übernommen* | Anderes Gerät aktiv – Seite neu laden |
| *Durchsuche die Wissensbasis …* | Bitte warten |
| *Connection error / Timeout* | Verbindung – siehe Handy-Anleitung (Tailscale) |

---

## 17. Kurz-Checkliste für den Alltag

**Vor der Nutzung:**

- [ ] Tailscale **grün** (Handy)
- [ ] Lesezeichen **DigiWiki** öffnen
- [ ] Bereich **💬 Wiki & Daten**, Modus **🎯 Auto**

**Bei jeder Frage:**

- [ ] Konkret formulieren (Firma, Name, Thema)
- [ ] Auf Antwort-Typ achten (Tabelle **oder** Text)
- [ ] Quellen bei Wiki-Antworten lesen
- [ ] Test-/Sammelfragen: markieren → **Antworten exportieren** (Abschnitt 8)

**Danach:**

- [ ] Brauchbare Infos kopieren / notieren
- [ ] Bei wichtigen Entscheidungen: **Originalquelle** prüfen

---

## 18. Hilfe holen

| Problem | An wen? |
|---------|---------|
| Seite lädt nicht | Administrator (Tailscale / PC an?) |
| Antwort ist falsch/unvollständig | Administrator (fehlen Daten/Dokumente?) |
| Kein Zugriff / Einladung | Administrator |
| Outlook/Mail geht nicht | Administrator (Outlook am PC?) |

**Mitgeben:** Ihre **exakte Frage**, **Modus**, Screenshot der Antwort.

---

## 19. Alles auf einer Seite – Merkkarte

```
ZUGANG:     Tailscale grün → Lesezeichen öffnen
HAUPT:      💬 Wiki & Daten
MODUS:      🎯 Auto (Standard)
FRAGE:      Konkret tippen oder 🎤 diktieren
ANTWORT:    Tabelle = Datenbank  |  Text + Quellen = Wiki
NACHFRAGEN: Im gleichen Chat möglich
EXPORT:     📌 markieren → Zusammenfassen & speichern → Ordner Antworten
AUSBLENDEN: 👁️ nur Anzeige — Export bleibt vollständig
RESET:      Chat-Verlauf leeren
GRENZEN:    Nur Firmenwissen, PC muss laufen, KI prüfen!
```

---

*Stand: Juni 2026 · Technische Einrichtung: `Anleitung_Nutzer_Handy.md` · PC-Administration: separate Administrator-Anleitung.*
