# SQL-Regression – Ergebnis

**Stand:** 2026-06-19 12:05
**DB:** `C:\CodexProjekte\FirmenApp\Digibest_Master.accdb`
**Ergebnis:** 12/12 bestanden


| # | Frage | Klassifikation | SQL ok | Zeilen | Status |
|---|-------|----------------|--------|--------|--------|
| 1 | Was ist das Narrativ von Hexal? | datenbank✓ | ✓ | 1 | ✅ OK |

### #1 Was ist das Narrativ von Hexal?

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- **SQL:** `SELECT TOP 200 nama, nameb, narrativ FROM stammdatenindustrie WHERE nama LIKE '%Hexal%'`
- **Ergebnis (1 Zeilen):**
```
    nama nameb                                 narrativ
Hexal AG       Hexal AG ist einer der führenden Anbi...
```

| 2 | Marktzielgruppe von Hexal | datenbank✓ | ✓ | 1 | ✅ OK |

### #2 Marktzielgruppe von Hexal

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- **SQL:** `SELECT TOP 200 Marktzielgruppe, emarktzielgruppe FROM stammdatenindustrie WHERE nama LIKE '%Hexal%'`
- **Ergebnis (1 Zeilen):**
```
Marktzielgruppe         emarktzielgruppe
   Apotheken IS B2B, Apotheken, Kliniken
```

| 3 | Top-Produkte von Hexal | datenbank✓ | ✓ | 200 | ✅ OK |

### #3 Top-Produkte von Hexal

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- **SQL:** `SELECT TOP 200 s.nama, s.nameb, s.gl_produkt1, s.gl_produkt2, s.gl_produkt3, s.topprodukte, s.top_produkte FROM stammdatenindustrie AS s INNER JOIN abdaartikel AS a ON a.anbieter_nr = s.anbieternummer WHERE s.nama LIKE '%Hexal%'`
- **Ergebnis (200 Zeilen):**
```
    nama nameb gl_produkt1 gl_produkt2 gl_produkt3                              topprodukte                             top_produkte
Hexal AG              None        None        None Generika, Arzneimittel, Gesundheitspr... Generika, Arzneimittel, Gesundheitspr...
Hexal AG              None        None        None Generika, Arzneimittel, Gesundheitspr... Generika, Arzneimittel, Gesundheitspr...
Hexal AG              None        None        None Generika, Arzneimittel, Gesundheitspr... Generika, Arzneimittel, Gesundheitspr...
```

| 4 | Wer ist Geschäftsführer bei Hexal? | datenbank✓ | ✓ | 0 | ✅ OK |

### #4 Wer ist Geschäftsführer bei Hexal?

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- *Hinweis:* 0 Zeilen ok wenn GF nicht gepflegt — SQL-Struktur zählt
- **SQL:** `SELECT TOP 200 p.vorname, p.nachname, rf.funktionsbezeichnung, rf.ebene, s.nama FROM (crm_personen AS p INNER JOIN stammdatenindustrie AS s ON p.kundennumm = s.kundennumm) LEFT JOIN ref_funktionen AS rf ON p.funktionid = rf.funktionid WHERE s.nama LIKE '%Hexal%' AND rf.ebene IN ('1', '2')`
- **Ergebnis (0 Zeilen):**
```
*(keine Zeilen)*
```

| 5 | Firmen in Akquiseklasse 3 mit Apotheken-Fokus | datenbank✓ | ✓ | 200 | ✅ OK |

### #5 Firmen in Akquiseklasse 3 mit Apotheken-Fokus

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- *Hinweis:* Filter Marktzielgruppe LIKE Apothek erwartet
- **SQL:** `SELECT TOP 200 akquiseklasse, Marktzielgruppe, emarktzielgruppe, nama, nameb, ort, plz FROM stammdatenindustrie WHERE akquiseklasse = 3 AND (Marktzielgruppe LIKE '%Apothek%' OR emarktzielgruppe LIKE '%Apothek%')`
- **Ergebnis (200 Zeilen):**
```
 akquiseklasse Marktzielgruppe               emarktzielgruppe                 nama             nameb        ort   plz
             3       Apotheken B2B, Apotheken, Endverbraucher        Harras Pharma Arzneimittel GmbH    München 81369
             3       Apotheken                            B2B       Heinrich Klenk     GmbH & Co. KG Schwebheim 97525
             3       Apotheken B2B, Apotheken, Endverbraucher NESTMANN Pharma GmbH                   Zapfendorf 96199
```

| 6 | D2P-Score und Begründung von Hexal | datenbank✓ | ✓ | 1 | ✅ OK |

### #6 D2P-Score und Begründung von Hexal

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- **SQL:** `SELECT TOP 200 d2p_score, d2p_begruendung FROM stammdatenindustrie WHERE nama LIKE '%Hexal%'`
- **Ergebnis (1 Zeilen):**
```
d2p_score                          d2p_begruendung
     None Hexal AG ist ein bedeutender Akteur i...
```

| 7 | Wie viele ABDA-Artikel hat Hexal? | datenbank✓ | ✓ | 1 | ✅ OK |

### #7 Wie viele ABDA-Artikel hat Hexal?

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- *Hinweis:* JOIN anbieternummer/anbieter_nr
- **SQL:** `SELECT COUNT(*) AS Anzahl_ABDA_Artikel FROM abdaartikel AS a INNER JOIN stammdatenindustrie AS s ON a.anbieter_nr = s.anbieternummer WHERE s.nama LIKE '%Hexal%'`
- **Ergebnis (1 Zeilen):**
```
 Anzahl_ABDA_Artikel
                3719
```

| 8 | Adresse und Website von Sanofi-Aventis Deutsc | datenbank✓ | ✓ | 4 | ✅ OK |

### #8 Adresse und Website von Sanofi-Aventis Deutschland

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- **SQL:** `SELECT TOP 200 nama, nameb, strasse, hausnr, plz, ort, internetadresse FROM stammdatenindustrie WHERE nama LIKE '%Sanofi-Aventis%'`
- **Ergebnis (4 Zeilen):**
```
                           nama                              nameb                              strasse hausnr   plz               ort       internetadresse
Sanofi-Aventis Deutschland GmbH GB Selbstmedikation /Consumer-Care Industriepark Hoechst / Gebäude K607        65926         Frankfurt http://www.sanofi.de/
                 Sanofi-Aventis            GB Seltene Erkrankungen  Industriepark Höchst / Gebäude K607        65926 Frankfurt am Main https://www.sanofi.de
                 Sanofi-Aventis                               GmbH  Industriepark Höchst / Gebäude K607        65926 Frankfurt am Main https://www.sanofi.de
```

| 9 | Wer stellt Hustensaft her? | datenbank✓ | ✓ | 59 | ✅ OK |

### #9 Wer stellt Hustensaft her?

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- **SQL:** `SELECT TOP 200 s.nama, s.nameb, a.artikelname, a.pzn FROM abdaartikel AS a INNER JOIN stammdatenindustrie AS s ON a.anbieter_nr = s.anbieternummer WHERE a.artikelname LIKE '%Hustensaft%'`
- **Ergebnis (59 Zeilen):**
```
                           nama    nameb                           artikelname      pzn
                AbZ-Pharma GmbH             AMBROXOL AbZ Hustensaft 15 mg/5 ml 02058541
                AbZ-Pharma GmbH             AMBROXOL AbZ Hustensaft 15 mg/5 ml 02058535
Pharma Aldenhoven GmbH & Co. KG & Co. KG DOC MORRIS Spitzwegerich Hustensaft V 13567346
```

| 10 | Welche Ansprechpartner hat Hexal mit Telefon? | datenbank✓ | ✓ | 2 | ✅ OK |

### #10 Welche Ansprechpartner hat Hexal mit Telefon?

- **Erwartet:** `datenbank` | **Ist:** `datenbank`
- **SQL:** `SELECT TOP 200 p.vorname, p.nachname, p.telefon, s.nama FROM (crm_personen AS p INNER JOIN stammdatenindustrie AS s ON p.kundennumm = s.kundennumm) WHERE s.nama LIKE '%Hexal%'`
- **Ergebnis (2 Zeilen):**
```
vorname nachname     telefon     nama
 Ulrike    Störk 08024 908-0 Hexal AG
Martina   Bracke   080249080 Hexal AG
```

| W1 | Wie läuft unser Bestellablauf ab? | wissen✓ | ✓ | - | ✅ OK |

### #W1 Wie läuft unser Bestellablauf ab?

- **Erwartet:** `wissen` | **Ist:** `wissen`

| W2 | Brandvoice Hans zu Emotionalität | wissen✓ | ✓ | - | ✅ OK |

### #W2 Brandvoice Hans zu Emotionalität

- **Erwartet:** `wissen` | **Ist:** `wissen`
