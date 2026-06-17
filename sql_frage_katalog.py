"""Frage-Routing und Feld-Mapping fuer NL2SQL, abgeleitet aus data_dictionary.csv.

Die meisten Nutzerfragen lassen sich ueber strukturierte Tabellen beantworten.
Wiki-RAG ist nur fuer echtes Dokumentenwissen (Vertraege, Verfahren, Formulare) gedacht.
"""

from __future__ import annotations

__all__ = [
    "baue_semantik_leitfaden",
    "baue_klassifikator_leitfaden",
    "baue_sql_feld_leitfaden",
    "ist_offensichtliche_wiki_frage",
    "SEMANTISCHE_FELDALIASE",
    "SQL_FRAGETYPEN",
    "WIKI_FRAGETYPEN",
]

# Nutzer-Begriffe → echte DB-Spalten (data_dictionary + Live-DB abgeglichen).
# WICHTIG: Spalte "marktorientierung" existiert NICHT – Nutzer meinen Marktzielgruppe/emarktzielgruppe.
SEMANTISCHE_FELDALIASE = [
    {
        "nutzer_begriffe": [
            "marktorientierung", "markt orientierung", "apotheken-fokus", "apotheken fokus",
            "apothekenfokus", "fokus apotheken", "zielgruppe apotheken", "segment apotheken",
        ],
        "db_tabelle": "stammdatenindustrie",
        "db_felder": ["Marktzielgruppe", "emarktzielgruppe"],
        "filter_beispiel": (
            "(Marktzielgruppe LIKE '%Apothek%' OR emarktzielgruppe LIKE '%Apothek%')"
        ),
        "hinweis": (
            "NICHT stammdatenindustrie.apotheken_fokus filtern – dieses Feld ist in der DB leer. "
            "Apotheken-Segment steht in Marktzielgruppe (Hauptwert z.B. 'Apotheken') "
            "und emarktzielgruppe (Detail, z.B. 'B2B, Apotheken, Endverbraucher')."
        ),
    },
    {
        "nutzer_begriffe": [
            "akquiseklasse", "akquise klasse", "akquise-klasse", "ak 1", "ak 2", "ak 3",
        ],
        "db_tabelle": "stammdatenindustrie",
        "db_felder": ["akquiseklasse"],
        "filter_beispiel": "akquiseklasse = 3",
        "hinweis": "akquiseklasse ist int – exakter Zahlenvergleich, kein LIKE.",
    },
    {
        "nutzer_begriffe": [
            "marktfunktion", "markt funktion", "funktion am markt", "rolle am markt",
        ],
        "db_tabelle": "stammdatenindustrie",
        "db_felder": ["funktion", "efunktion"],
        "filter_beispiel": "funktion LIKE '%...%'",
        "hinweis": "funktion = Kurzbezeichnung, efunktion = Detail.",
    },
    {
        "nutzer_begriffe": [
            "angebotskategorie", "kategorie", "segment kategorie",
        ],
        "db_tabelle": "stammdatenindustrie",
        "db_felder": ["Kategorie", "ekategorie"],
        "filter_beispiel": "Kategorie LIKE '%...%'",
        "hinweis": "Kategorie = Kurz, ekategorie = Detail.",
    },
    {
        "nutzer_begriffe": ["hersteller", "anbieter", "produzent", "stellt her", "produziert"],
        "db_tabelle": "stammdatenindustrie / abdaartikel",
        "db_felder": ["nama", "nameb", "anbietername", "artikelname"],
        "filter_beispiel": "JOIN abdaartikel ON anbieter_nr = anbieternummer",
        "hinweis": "Firmenname: stammdatenindustrie.nama; Artikel: abdaartikel.",
    },
]


def baue_semantik_leitfaden() -> str:
    """Nutzer-Sprache → DB-Felder fuer NL2SQL."""
    zeilen = ["=== SEMANTISCHE FELD-ZUORDNUNG (Nutzerbegriff -> DB-Spalte) ==="]
    for eintrag in SEMANTISCHE_FELDALIASE:
        zeilen.append(
            f"- Nutzer sagt: {', '.join(eintrag['nutzer_begriffe'][:6])} …\n"
            f"  -> Tabelle {eintrag['db_tabelle']}, Felder: {', '.join(eintrag['db_felder'])}\n"
            f"  -> Filter: {eintrag['filter_beispiel']}\n"
            f"  -> {eintrag['hinweis']}"
        )
    zeilen.append(
        "\nBEISPIEL-ABFRAGE:\n"
        "Frage: 'Firmen in Akquiseklasse 3 mit Apotheken-Fokus'\n"
        "SQL: SELECT TOP 50 akquiseklasse, Marktzielgruppe, emarktzielgruppe, nama, nameb, ort, plz "
        "FROM stammdatenindustrie WHERE akquiseklasse = 3 "
        "AND (Marktzielgruppe LIKE '%Apothek%' OR emarktzielgruppe LIKE '%Apothek%')"
    )
    return "\n".join(zeilen)


WIKI_FRAGETYPEN = [
    {
        "thema": "dokument_vertrag",
        "signale": [
            "vertrag", "klausel", "was steht in", "dokument", "pdf", "formular ausfuellen",
            "anleitung", "verfahren", "prozess beschreibung", "wie lauft ab",
        ],
        "hinweis": "Antwort steht in hinterlegten Dokumenten, nicht in DB-Feldern.",
    },
    {
        "thema": "qualitativ_unstrukturiert",
        "signale": [
            "zusammenfassung des dokuments", "inhalt der datei", "was besagt der brief",
        ],
        "hinweis": "Freitext aus Dateien/Wiki, nicht tabellarisch.",
    },
]

# Fragentypen → Tabellen, Suchfelder, Joins (aus data_dictionary abgeleitet).
SQL_FRAGETYPEN = [
    {
        "thema": "personen_kontakt_hierarchie",
        "signale": [
            "wer ist", "ansprechpartner", "kontakt", "person", "vorname", "nachname",
            "telefon", "mobil", "email", "hierarchie", "position", "funktion",
            "geschaeftsfuehrer", "gf", "leiter", "manager", "titel",
        ],
        "tabellen": ["crm_personen", "ref_funktionen", "stammdatenindustrie", "Whitelist_Kontakte"],
        "suchfelder": [
            "crm_personen.vorname", "crm_personen.nachname", "crm_personen.funktionsbezeichnung",
            "crm_personen.emailpers", "crm_personen.telefon", "crm_personen.mobil",
            "ref_funktionen.ebene", "ref_funktionen.funktionsbezeichnung",
            "stammdatenindustrie.nama", "stammdatenindustrie.nameb",
            "Whitelist_Kontakte.Vorname", "Whitelist_Kontakte.Nachname",
        ],
        "ausgabefelder": [
            "vorname", "nachname", "funktionsbezeichnung", "telefon", "mobil", "emailpers",
            "nama", "nameb", "ort", "ebene",
        ],
        "joins": [
            "crm_personen.kundennumm = stammdatenindustrie.kundennumm",
            "crm_personen.funktionid = ref_funktionen.funktionid",
            "Whitelist_Kontakte.indpersonid = crm_personen.personid",
        ],
        "beispiele": [
            "Wer ist Ansprechpartner bei Hexal?",
            "Telefonnummer von Mueller bei Bayer",
            "Alle GF in der Datenbank",
        ],
    },
    {
        "thema": "firmen_adressen",
        "signale": [
            "adresse", "anschrift", "wo sitzt", "firmenname", "firma", "unternehmen",
            "anbieter", "hersteller", "plz", "ort", "strasse", "deutschland", "land",
            "website", "internet", "linkedin url",
        ],
        "tabellen": ["stammdatenindustrie"],
        "suchfelder": [
            "stammdatenindustrie.nama", "stammdatenindustrie.nameb", "stammdatenindustrie.kurzname",
            "stammdatenindustrie.ort", "stammdatenindustrie.plz", "stammdatenindustrie.LKZ",
        ],
        "ausgabefelder": [
            "nama", "nameb", "kurzname", "strasse", "hausnr", "plz", "ort", "LKZ",
            "telefon", "fax", "email", "internetadresse", "LinkedinURL",
        ],
        "joins": [],
        "beispiele": [
            "Adresse von Klosterfrau",
            "Alle Firmen in Koeln",
            "Hersteller in Deutschland",
        ],
    },
    {
        "thema": "apotheken",
        "signale": [
            "apotheke", "apotheken", "stammdatenapo", "betriebsstaette", "bganr",
            "apothekengruppe", "nielsen", "bundesland",
        ],
        "tabellen": ["stammdatenapo"],
        "suchfelder": [
            "stammdatenapo.nama", "stammdatenapo.kurzname", "stammdatenapo.ort",
            "stammdatenapo.plz", "stammdatenapo.bundesland", "stammdatenapo.Apogrupp",
        ],
        "ausgabefelder": [
            "nama", "nameb", "kurzname", "strasse", "hausnr", "plz", "ort", "bundesland",
            "telefon", "email", "MAZahl", "groessenklasse", "Apogrupp", "bearbStatus",
        ],
        "joins": [],
        "beispiele": [
            "Apotheken in Muenchen mit mehr als 10 Mitarbeitern",
            "Welche Apothekengruppe hat Apotheke X?",
        ],
    },
    {
        "thema": "produkte_artikel",
        "signale": [
            "produkt", "artikel", "pzn", "warengruppe", "sortiment", "stellt her",
            "produziert", "herstellen", "hersteller", "anbieter", "vertreibt", "wirkstoff",
            "rx", "otc", "abda",
        ],
        "tabellen": ["abdaartikel", "stammdatenindustrie"],
        "suchfelder": [
            "abdaartikel.artikelname", "abdaartikel.artikelname_hauptbegriff",
            "abdaartikel.wirkstegrl", "abdaartikel.abdawarengruppe", "abdaartikel.imswarengruppe",
            "abdaartikel.anbietername", "stammdatenindustrie.nama",
        ],
        "ausgabefelder": [
            "nama", "nameb", "ort", "LKZ", "artikelname", "pzn", "abgaberegelung", "anzahl_artikel",
        ],
        "joins": ["abdaartikel.anbieter_nr = stammdatenindustrie.anbieternummer"],
        "beispiele": [
            "Wer stellt in Deutschland Hustensaft her?",
            "Alle Rx-Artikel von Ratiopharm",
        ],
    },
    {
        "thema": "topprodukte_sortiment",
        "signale": [
            "topprodukt", "top produkt", "wichtigste produkte", "sortiment",
            "sortimentsstruktur", "markenstruktur", "produktschwerpunkt", "marken",
            "wie viele artikel", "anzahl artikel", "anzahlabda", "anzahlrx",
        ],
        "tabellen": ["stammdatenindustrie", "abdaartikel"],
        "suchfelder": [
            "stammdatenindustrie.nama", "stammdatenindustrie.topprodukte",
            "stammdatenindustrie.top_produkte", "stammdatenindustrie.gl_produkt1",
            "stammdatenindustrie.sortiment", "stammdatenindustrie.produktschwerpunkt",
        ],
        "ausgabefelder": [
            "nama", "nameb", "gl_produkt1", "gl_produkt2", "gl_produkt3",
            "topprodukte", "top_produkte", "sortiment", "sortimentsstruktur",
            "markenstruktur", "anzahlabda", "anzahlrx", "anzahlnonrx", "produktschwerpunkt",
        ],
        "joins": ["abdaartikel.anbieter_nr = stammdatenindustrie.anbieternummer"],
        "beispiele": [
            "Top-Produkte von Sanofi",
            "Welches Sortiment hat Merz?",
            "Firmen mit den meisten ABDA-Artikeln",
        ],
    },
    {
        "thema": "marktsegment_marktbearbeitung",
        "signale": [
            "marktbearbeitung", "akquiseklasse", "marktzielgruppe", "marktorientierung",
            "kategorie", "marktfunktion", "funktion", "segment", "zielgruppe",
            "apotheken fokus", "apotheken-fokus", "apothekenfokus",
            "hauptgruppe", "untergruppe", "zugehoerigkeit", "umsatzklasse", "groessenklasse",
            "d2p", "veredelung", "akquise",
        ],
        "tabellen": ["stammdatenindustrie"],
        "suchfelder": [
            "stammdatenindustrie.akquiseklasse",
            "stammdatenindustrie.Marktzielgruppe",
            "stammdatenindustrie.emarktzielgruppe",
            "stammdatenindustrie.funktion", "stammdatenindustrie.Kategorie",
            "stammdatenindustrie.hauptgruppe", "stammdatenindustrie.ugruppe",
            "stammdatenindustrie.nama",
        ],
        "ausgabefelder": [
            "nama", "nameb", "ort", "plz", "akquiseklasse", "funktion", "efunktion",
            "Marktzielgruppe", "emarktzielgruppe", "Kategorie", "ekategorie",
            "hauptgruppe", "ugruppe", "zugehoerigkeit",
            "groessenklasse", "umsatzklasse", "d2p_score", "veredelung_score",
        ],
        "joins": [],
        "beispiele": [
            "Firmen in Akquiseklasse 3 mit Apotheken-Fokus",
            "Alle Firmen in Akquiseklasse 1",
            "Marktzielgruppe von Hexal",
        ],
    },
    {
        "thema": "firmen_profil_strategie",
        "signale": [
            "narrativ", "purpose", "zielsetzung", "ambition", "strategie",
            "trigger", "entscheider", "begruendung", "marktposition", "daseinszweck",
        ],
        "tabellen": ["stammdatenindustrie"],
        "suchfelder": ["stammdatenindustrie.nama", "stammdatenindustrie.nameb"],
        "ausgabefelder": [
            "nama", "nameb", "narrativ", "purpose", "begruendung", "trigger_events",
            "entscheider", "ambition", "zielsetzung", "d2p_begruendung",
        ],
        "joins": [],
        "beispiele": [
            "Was ist das Narrativ von Bayer?",
            "Trigger-Events bei Firma X",
        ],
    },
    {
        "thema": "crm_aktivitaeten",
        "signale": [
            "aktivitaet", "aktivität", "linkedin post", "touchpoint", "reaktion",
            "vernetzung", "trigger historie", "event", "letztes like", "kommentar",
        ],
        "tabellen": [
            "crm_aktivitaeten", "crm_firmen_aktivitaeten", "crm_firmen_trigger_historie",
            "crm_personen", "stammdatenindustrie",
        ],
        "suchfelder": [
            "crm_personen.vorname", "crm_personen.nachname",
            "stammdatenindustrie.nama", "crm_firmen_trigger_historie.event_typ",
        ],
        "ausgabefelder": [
            "post_text", "status", "aktivitaet_typ", "datum", "event_typ", "beschreibung",
            "letztes_like_datum", "vernetzungs_status", "naechster_touchpoint_am",
        ],
        "joins": [
            "crm_aktivitaeten.personid = crm_personen.personid",
            "crm_firmen_aktivitaeten.kundennumm = stammdatenindustrie.kundennumm",
            "crm_firmen_trigger_historie.kundennumm = stammdatenindustrie.kundennumm",
        ],
        "beispiele": [
            "Letzte LinkedIn-Aktivitaet von Person X",
            "Trigger-Events bei Klosterfrau",
        ],
    },
    {
        "thema": "linkedin_connections",
        "signale": [
            "linkedin", "connection", "vernetzt", "einladung", "profil",
        ],
        "tabellen": ["Connections", "Invitations_Normalized", "crm_personen"],
        "suchfelder": [
            "Connections.FirstName", "Connections.LastName", "Connections.Company",
            "crm_personen.linkedin_canonical_url",
        ],
        "ausgabefelder": [
            "FirstName", "LastName", "Company", "Position", "EmailAddress", "Connected_On",
        ],
        "joins": [
            "Connections.canonical_url = crm_personen.linkedin_canonical_url",
            "Invitations_Normalized.personurl = crm_personen.linkedin_canonical_url",
        ],
        "beispiele": [
            "LinkedIn-Kontakte bei Firma Y",
            "Wann verbunden mit Person Z?",
        ],
    },
    {
        "thema": "whitelist_kontakte",
        "signale": [
            "whitelist", "freigegeben", "prioritaet", "priorität", "ansprache", "du sie",
        ],
        "tabellen": ["Whitelist_Kontakte", "stammdatenindustrie", "crm_personen"],
        "suchfelder": [
            "Whitelist_Kontakte.Vorname", "Whitelist_Kontakte.Nachname",
            "Whitelist_Kontakte.Firma_Projekt", "Whitelist_Kontakte.Prioritaet",
        ],
        "ausgabefelder": [
            "Vorname", "Nachname", "Email_Gesch", "Tel_Gesch", "Tel_Mobil",
            "Anrede", "Ansprache", "Prioritaet", "Position", "Firma_Projekt",
        ],
        "joins": [
            "Whitelist_Kontakte.indkundennumm = stammdatenindustrie.kundennumm",
            "Whitelist_Kontakte.indpersonid = crm_personen.personid",
        ],
        "beispiele": [
            "Whitelist-Kontakte mit Prioritaet hoch",
            "Freigegebene Kontakte bei Firma X",
        ],
    },
    {
        "thema": "listen_zaehlen_vergleichen",
        "signale": [
            "wie viele", "anzahl", "liste", "alle", "welche", "top", "ranking",
            "vergleich", "groesste", "kleinste", "meiste", "wenigste",
        ],
        "tabellen": ["stammdatenindustrie", "crm_personen", "abdaartikel", "stammdatenapo"],
        "suchfelder": [],
        "ausgabefelder": [],
        "joins": [],
        "beispiele": [
            "Wie viele Hersteller in Bayern?",
            "Top 10 Firmen nach Artikelanzahl",
        ],
    },
]


def _format_fragetyp_block(eintrag: dict, kompakt: bool = False) -> str:
    zeilen = [f"### {eintrag['thema']}"]
    if not kompakt:
        zeilen.append(f"Signale: {', '.join(eintrag.get('signale', [])[:12])}")
    zeilen.append(f"Tabellen: {', '.join(eintrag['tabellen'])}")
    if eintrag.get("suchfelder"):
        zeilen.append(f"Suchfelder: {', '.join(eintrag['suchfelder'][:8])}")
    if eintrag.get("ausgabefelder"):
        zeilen.append(f"Ausgabe: {', '.join(eintrag['ausgabefelder'][:10])}")
    if eintrag.get("joins"):
        zeilen.append(f"JOINs: {'; '.join(eintrag['joins'])}")
    if not kompakt and eintrag.get("beispiele"):
        zeilen.append(f"Beispiel: {eintrag['beispiele'][0]}")
    return "\n".join(zeilen)


def baue_klassifikator_leitfaden() -> str:
    """Kompakter Leitfaden fuer Auto-Routing (SQL vs. Wiki)."""
    sql_themen = "\n".join(_format_fragetyp_block(t, kompakt=True) for t in SQL_FRAGETYPEN)
    wiki_signale = ", ".join(s for w in WIKI_FRAGETYPEN for s in w["signale"])
    return f"""
STANDARDREGEL: Fast alle Fragen -> 'datenbank' (SQL). Nur echtes Dokumentenwissen -> 'wissen'.

SQL-THEMEN (data_dictionary):
{sql_themen}

NUR WIKI bei: {wiki_signale}
Ausnahme: Auch narrativ/purpose/trigger_events in stammdatenindustrie -> SQL, nicht Wiki.
"""


def baue_sql_feld_leitfaden() -> str:
    """Ausfuehrlicher Feld-Mapping-Leitfaden fuer NL2SQL."""
    bloecke = [_format_fragetyp_block(t) for t in SQL_FRAGETYPEN]
    return """
=== FRAGETYP-ROUTING (data_dictionary) ===
Schritt 1: Fragentyp erkennen (Signale unten).
Schritt 2: Passende Tabelle(n) und JOINs waehlen.
Schritt 3: Textsuche in [SUCH FELD]-Spalten (data_dictionary markiert diese).
Schritt 4: SELECT nur relevante Ausgabefelder, nicht SELECT * bei JOINs.

""" + "\n\n".join(bloecke) + """

=== GLOBALE JOIN-REGELN ===
Siehe db_joins.csv (vollstaendiger JOIN-Graph) und db_tabellen.csv (Tabellenrollen).

""" + baue_semantik_leitfaden() + """

=== ACCESS-SQL ===
- SELECT TOP 50 bei Listen
- GROUP BY statt SELECT DISTINCT mit ORDER BY auf Alias
- Textsuche: LIKE '%' mit OR-Synonymen
"""


def ist_offensichtliche_wiki_frage(frage: str) -> bool:
    """Schnelle Heuristik fuer klare Dokumentenfragen."""
    text = (frage or "").lower()
    return any(s in text for s in (
        "vertrag", "klausel", "formular ausfüllen", "formular ausfuellen",
        "was steht im dokument", "was steht in dem dokument",
        "verfahren beschreibung", "laut vertrag",
    ))
