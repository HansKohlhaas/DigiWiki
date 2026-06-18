# DigiWiki auf dem Handy nutzen – Anleitung für Nutzer

**Für wen ist diese Anleitung?**  
Für alle, die DigiWiki **nur benutzen** wollen – **ohne** etwas am PC einzurichten. Den PC kümmert sich der Administrator (technische Betreuung).

**Was ist DigiWiki?**  
Eine Web-Seite im Browser, mit der Sie Fragen stellen, Informationen nachschlagen und (je nach Freigabe) Mails vorbereiten können. Sie öffnen sie wie eine normale Internet-Seite – nur dass der Zugang über ein sicheres Zusatz-Netzwerk (**Tailscale**) läuft.

---

## Was Sie brauchen

| Nr. | Was | Hinweis |
|-----|-----|--------|
| 1 | **Smartphone** (Android oder iPhone) | Aktuelles Betriebssystem hilft |
| 2 | **Internet** | Mobilfunk (LTE/5G) oder WLAN |
| 3 | **App „Tailscale“** | Kostenlos im App Store / Play Store |
| 4 | **Zugang von Ihrem Administrator** | E-Mail-Einladung zu Tailscale **und** die **Adresse** für DigiWiki |
| 5 | **Browser** | Chrome, Firefox oder Safari |

**Wichtig:** Ohne Einladung in Tailscale funktioniert der Zugang **nicht** – auch wenn Sie die Adresse kennen. Bitten Sie den Administrator, Sie freizuschalten.

---

## Teil 1: Einmal einrichten (dauert etwa 10 Minuten)

### Schritt 1: App Tailscale installieren

**Android (Samsung, etc.):**  
Play Store öffnen → nach **„Tailscale“** suchen → installieren  
Direktlink: https://play.google.com/store/apps/details?id=com.tailscale.ipn

**iPhone:**  
App Store → **„Tailscale“** → installieren  
Direktlink: https://apps.apple.com/app/tailscale/id1470499037

---

### Schritt 2: In Tailscale anmelden

1. App **Tailscale** öffnen  
2. **Anmelden** tippen  
3. So anmelden, wie es Ihr Administrator sagt – meist mit **derselben E-Mail / demselben Konto**, zu dem Sie eingeladen wurden  
4. Warten, bis die App **„Verbunden“** anzeigt (oft mit grünem Hinweis)

**Falls Sie eine Einladungs-E-Mail von Tailscale bekommen haben:**  
Link in der E-Mail antippen und den Anweisungen folgen.

**Falls etwas unklar ist:** Administrator fragen – **nicht** selbst am PC herumprobieren.

---

### Schritt 3: Android – zwei Einstellungen (sehr wichtig)

Diese Schritte **einmal** machen. Ohne sie gibt es oft **„Zeitüberschreitung“** oder **„Seite nicht gefunden“**.

#### A) Privates DNS ausschalten

1. **Einstellungen** am Handy öffnen  
2. **Netzwerk & Internet** (Bezeichnung kann leicht anders heißen)  
3. **Privates DNS** antippen  
4. **Aus** wählen (**nicht** „Automatisch“)

#### B) Akku für Tailscale freigeben

1. **Einstellungen** → **Apps** → **Tailscale**  
2. **Akku** / **Akkuverbrauch**  
3. **Uneingeschränkt** oder **Nicht optimieren** wählen  

So wird Tailscale im Hintergrund nicht „abgemurxt“.

**iPhone:** Einstellungen → Tailscale → **Hintergrundaktualisierung** erlauben.

---

### Schritt 4: Adresse von DigiWiki speichern

Ihr Administrator schickt Ihnen **eine oder zwei Adressen** (Links). Typischerweise:

- **Haupt-Adresse (empfohlen):** beginnt mit `https://` und endet oft mit `.ts.net`  
  Beispiel: `https://desktop-velbert.tail094343.ts.net`  
- **Ersatz-Adresse:** beginnt mit `http://100.` und hat am Ende `:8501`  
  Beispiel: `http://100.116.74.108:8501`

**Ihre echten Adressen können anders aussehen** – nutzen Sie **genau** die, die Sie vom Administrator bekommen.

**Lesezeichen anlegen (empfohlen):**

1. Browser öffnen  
2. **Haupt-Adresse** eintippen oder einfügen  
3. Seite laden lassen  
4. Im Browser **Lesezeichen / Favorit** setzen, Name z. B. **„DigiWiki“**

---

## Teil 2: So nutzen Sie DigiWiki (jedes Mal)

Merken Sie sich die **Reihenfolge** – die ist entscheidend:

```
1. Tailscale-App öffnen
2. Warten, bis „Verbunden“ (grün) steht
3. Erst dann Browser öffnen
4. Lesezeichen „DigiWiki“ antippen
```

**Nicht** zuerst den Browser öffnen und **danach** Tailscale starten – das führt oft zu Fehlern.

---

### Kurz in Bildern (Ablauf)

```
┌─────────────────┐
│  Tailscale-App  │  →  muss „Verbunden“ zeigen
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Browser     │  →  Lesezeichen „DigiWiki“
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DigiWiki-Seite │  →  Chat / Suche nutzen
└─────────────────┘
```

---

## Was Sie **nicht** tun sollten

| ❌ Nicht | Warum |
|--------|--------|
| Adresse mit `192.168.` … nutzen (vom Administrator als „nur WLAN“ markiert) | Funktioniert **nur** im Büro-WLAN, **nicht** von zuhause oder unterwegs |
| `localhost` eingeben | Das ist **nur** der Administrator-PC, nicht Ihr Handy |
| Tailscale „Als VPN nutzen“ / Exit-Node einschalten | Kann die Verbindung kaputt machen – **aus** lassen, außer der Administrator sagt es ausdrücklich |
| App Tailscale dauerhaft beenden / deinstallieren | Ohne Tailscale kein Zugang von außen |

---

## Wenn es nicht klappt – Fehler und Lösungen

### „Verbindung fehlgeschlagen“ / „Zeitüberschreitung“ / „Connection timed out“

**Meistens:** Tailscale am Handy ist **nicht** wirklich verbunden.

1. Tailscale-App öffnen  
2. Steht dort **Verbunden**?  
   - **Nein** → Verbindung antippen / warten / ggf. Handy neu starten  
   - **Ja** → weiter mit Schritt 3  
3. **Flugmodus** 5 Sekunden **an**, dann wieder **aus**  
4. Tailscale wieder öffnen, bis **Verbunden**  
5. Browser **komplett schließen** (auch aus den letzten Apps wischen)  
6. Browser neu öffnen → Lesezeichen **DigiWiki**

---

### „Adresse nicht gefunden“ / „ERR_NAME_NOT_RESOLVED“

**Meistens:** **Privates DNS** am Android noch auf „Automatisch“.

→ Siehe **Teil 1, Schritt 3 A)** → **Privates DNS auf Aus**

Alternativ die **Ersatz-Adresse** mit `http://100.` … `:8501` probieren (vom Administrator).

---

### Seite lädt ewig / bleibt weiß

1. Tailscale prüfen (grün?)  
2. Anderen Browser probieren (Chrome statt Firefox oder umgekehrt)  
3. Handy einmal neu starten  
4. Administrator fragen, ob der **PC eingeschaltet** ist und DigiWiki läuft  

DigiWiki läuft auf dem **PC des Administrators**. Ist der PC aus oder DigiWiki nicht gestartet, kommen Sie nicht rein – das ist normal.

---

### „Nicht sicher“ / Zertifikat-Hinweis im Browser

Bei der **Haupt-Adresse** (`https://…ts.net`) kann der Browser kurz warnen.  
Wenn die Adresse **vom Administrator** stammt und Tailscale **verbunden** ist, können Sie fortfahren (je nach Browser: „Erweitert“ → „Trotzdem fortfahren“).  
Bei Unsicherheit: **Administrator fragen**, nicht raten.

---

## Checkliste zum Abhaken (Einmal-Setup)

- [ ] App Tailscale installiert  
- [ ] Angemeldet (Einladung vom Administrator)  
- [ ] Android: Privates DNS **Aus**  
- [ ] Android: Akku Tailscale **Uneingeschränkt**  
- [ ] Lesezeichen mit **Haupt-Adresse** angelegt  
- [ ] Test: Tailscale grün → Lesezeichen → DigiWiki-Startseite sichtbar  

---

## Checkliste vor jeder Nutzung (30 Sekunden)

- [ ] Tailscale-App: **Verbunden**  
- [ ] Browser: Lesezeichen **DigiWiki**  
- [ ] Bei Problemen: Flugmodus kurz an/aus, dann nochmal  

---

## An wen wenden bei Problemen?

| Problem | Wen fragen |
|---------|------------|
| Keine Tailscale-Einladung / Anmeldung klappt nicht | **Administrator** |
| Adresse / Link unklar oder verloren | **Administrator** |
| Alles am Handy OK, Seite geht trotzdem nicht | **Administrator** (PC / DigiWiki läuft vermutlich nicht) |
| Passwort, Inhalte, Berechtigungen in DigiWiki | **Administrator** |

**Bitte angeben, wenn Sie Hilfe brauchen:**

- Was genau steht auf dem Bildschirm? (Foto schicken hilft)  
- Welche Adresse haben Sie eingegeben?  
- War Tailscale **grün**?  
- Android oder iPhone?  

---

## Häufige Fragen (kurz)

**Muss ich etwas am PC installieren?**  
Nein. Nur der Administrator richtet den PC ein.

**Kostet Tailscale etwas?**  
Für private/kleine Nutzung meist **kostenlos**. Der Administrator klärt das.

**Geht das auch mit dem iPad?**  
Ja – gleiche Schritte wie am iPhone: Tailscale installieren, verbinden, Browser, Lesezeichen.

**Kann ich DigiWiki ohne Tailscale nutzen?**  
Nur wenn Sie im **selben WLAN wie der PC** sind **und** der Administrator Ihnen eine **WLAN-Adresse** (`192.168.…`) gegeben hat. Von zuhause oder unterwegs: **immer Tailscale zuerst**.

**Warum zwei verschiedene Adressen?**  
Die **https-Adresse** ist meist am stabilsten. Die **100.x-Adresse** ist ein Ersatz, falls die erste hakt.

---

## Zusammenfassung in einem Satz

**Tailscale grün → Browser → Lesezeichen DigiWiki** – in **dieser** Reihenfolge, jedes Mal.

---

*Stand: Juni 2026 · Technische Einrichtung am PC: siehe separate Administrator-Anleitung.*
