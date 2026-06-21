"""Frage-Routing und Feld-Mapping fuer NL2SQL, abgeleitet aus data_dictionary.csv.

Die meisten Nutzerfragen lassen sich ueber strukturierte Tabellen beantworten.
Wiki-RAG ist nur fuer echtes Dokumentenwissen (Vertraege, Verfahren, Formulare) gedacht.
"""

from __future__ import annotations

from config import SQL_DEFAULT_TOP
from sql_db_meta import baue_access_join_regeln

__all__ = [
    "baue_semantik_leitfaden",
    "baue_klassifikator_leitfaden",
    "baue_sql_feld_leitfaden",
    "firma_suche_like",
    "firma_vollname_expr",
    "bereinige_access_sql",
    "baue_direkt_sql_folgefrage",
    "baue_direkt_sql_firma_produkte",
    "baue_sql_abda_artikel_kundennumm",
    "ist_topprodukte_frage",
    "ist_artikelkatalog_frage",
    "ist_offensichtliche_wiki_frage",
    "SEMANTISCHE_FELDALIASE",
    "SQL_FRAGETYPEN",
    "WIKI_FRAGETYPEN",
]

TOPPRODUKT_SIGNALE = (
    "top-produkt",
    "top produkt",
    "topprodukt",
    "wichtigste produkte",
    "sortimentsstruktur",
    "markenstruktur",
    "produktschwerpunkt",
    "sortiment von",
    "sortiment hat",
    "welches sortiment",
    "gl_produkt",
)

ARTIKELKATALOG_SIGNALE = (
    "welche produkte",
    "produkte haben",
    "produktkatalog",
    "produktliste",
    "produkte hat",
    "produkte von",
    "produkte bei",
    "artikeldb",
    "artikel db",
    "abda-artikel",
    "abda artikel",
    "rx-artikel",
    "otc-artikel",
    "pzn",
    "wirkstoff",
)

ARTIKEL_SUCH_STOPWORDS = frozenset({
    "welche", "haben", "produkte", "produkt", "artikel", "bitte", "denn", "die", "der", "das",
    "den", "dem", "des", "ein", "eine", "einer", "eines", "noch", "auch", "dazu", "davon",
    "deren", "ihre", "ihren", "ihrer", "sind", "hat", "von", "bei", "was", "gibt", "zeige",
})


def ist_topprodukte_frage(frage: str) -> bool:
    text = (frage or "").lower()
    return any(s in text for s in TOPPRODUKT_SIGNALE)


def ist_artikelkatalog_frage(frage: str) -> bool:
    """Einzel-Firma: Artikel aus abdaartikel (nicht nur Freitext topprodukte)."""
    text = (frage or "").lower()
    if ist_topprodukte_frage(frage):
        return False
    if any(s in text for s in ARTIKELKATALOG_SIGNALE):
        return True
    if "produkt" in text and "top" not in text:
        return True
    if "artikel" in text and "anzahl" not in text and "wie viele" not in text:
        return True
    return False


def baue_sql_abda_artikel_kundennumm(kundennumm: str, frage: str = "", top: int | None = None) -> str:
    """ArtikelDB: abdaartikel JOIN stammdatenindustrie ueber anbieter_nr = anbieternummer."""
    kn = (kundennumm or "").strip().replace("'", "''")
    top = top or SQL_DEFAULT_TOP
    text = (frage or "").lower()
    filter_teile = [f"s.kundennumm = '{kn}'"]
    suchwoerter = [
        w.strip(".,?!")
        for w in text.split()
        if len(w.strip(".,?!")) > 3
        and w.strip(".,?!").lower() not in ARTIKEL_SUCH_STOPWORDS
    ]
    if suchwoerter:
        like_teile = []
        for w in suchwoerter[:3]:
            esc = w.replace("'", "''")
            like_teile.append(
                f"(a.artikelname LIKE '%{esc}%' OR a.artikelname_hauptbegriff LIKE '%{esc}%' "
                f"OR a.wirkstegrl LIKE '%{esc}%')"
            )
        filter_teile.append("(" + " OR ".join(like_teile) + ")")
    where = " AND ".join(filter_teile)
    return (
        f"SELECT TOP {top} s.nama, s.nameb, s.anbieternummer, a.artikelname, a.pzn, "
        f"a.abgaberegelung, a.abdawarengruppe, a.wirkstegrl, a.artikeltyp "
        f"FROM (abdaartikel AS a INNER JOIN stammdatenindustrie AS s "
        f"ON a.anbieter_nr = s.anbieternummer) WHERE {where} ORDER BY a.artikelname"
    )


def baue_direkt_sql_firma_produkte(
    frage: str,
    kundennumm: str = "",
    firmen_such: str = "",
) -> str | None:
    """Direkt-SQL fuer Produktfragen (Top-Felder vs. ArtikelDB)."""
    if not ist_topprodukte_frage(frage) and not ist_artikelkatalog_frage(frage):
        return None
    top = SQL_DEFAULT_TOP
    kn = (kundennumm or "").strip().replace("'", "''")
    if ist_topprodukte_frage(frage):
        if kn:
            basis = f"FROM stammdatenindustrie WHERE kundennumm = '{kn}'"
        elif firmen_such:
            basis = f"FROM stammdatenindustrie WHERE {firma_suche_like(firmen_such)}"
        else:
            return None
        return (
            f"SELECT TOP {top} nama, nameb, topprodukte, top_produkte, gl_produkt1, gl_produkt2, "
            f"gl_produkt3, sortiment, produktschwerpunkt {basis}"
        )
    if kn:
        return baue_sql_abda_artikel_kundennumm(kn, frage)
    if firmen_such:
        where = firma_suche_like(firmen_such, "s")
        return (
            f"SELECT TOP {top} s.nama, s.nameb, s.anbieternummer, a.artikelname, a.pzn, "
            f"a.abgaberegelung, a.abdawarengruppe, a.wirkstegrl, a.artikeltyp "
            f"FROM (abdaartikel AS a INNER JOIN stammdatenindustrie AS s "
            f"ON a.anbieter_nr = s.anbieternummer) WHERE {where} ORDER BY a.artikelname"
        )
    return None

# Nutzer-Begriffe → echte DB-Spalten (data_dictionary + Live-DB abgeglichen).
# WICHTIG: Spalte "marktorientierung" existiert NICHT – Nutzer meinen Marktzielgruppe/emarktzielgruppe.


def firma_vollname_expr(alias: str = "") -> str:
    """Access-SQL: Firmenname als nama & nameb (ODBC-kompatibel, ohne Nz())."""
    prefix = f"{alias}." if alias else ""
    n, b = f"{prefix}nama", f"{prefix}nameb"
    return (
        f"Trim(IIf({n} Is Null, '', {n}) "
        f"& IIf({b} Is Null, '', IIf({n} Is Null, {b}, ' ' & {b})))"
    )


def firma_suche_like(suchbegriff: str, alias: str = "") -> str:
    """LIKE-Filter fuer Firmensuche: concat(nama, nameb) plus Einzelfeld-Fallback."""
    esc = (suchbegriff or "").replace("'", "''")
    prefix = f"{alias}." if alias else ""
    voll = firma_vollname_expr(alias)
    return (
        f"({voll} LIKE '%{esc}%' OR {prefix}nama LIKE '%{esc}%' OR {prefix}nameb LIKE '%{esc}%')"
    )


def bereinige_access_sql(sql: str) -> str:
    """Haeufige LLM-Fehler vor ODBC-Ausfuehrung bereinigen."""
    s = (sql or "").strip()
    s = s.replace("```sql", "").replace("```", "").replace("\n", " ").strip()
    while s.endswith(";"):
        s = s[:-1].strip()
    return s


def baue_direkt_sql_folgefrage(frage: str, kundennumm: str, thema: str = "") -> str | None:
    """Sichere SQL-Vorlagen fuer Folgefragen mit bekannter kundennumm (ohne LLM)."""
    kn = (kundennumm or "").strip().replace("'", "''")
    if not kn:
        return None
    text = (frage or "").lower()
    thema = (thema or "").lower()
    top = SQL_DEFAULT_TOP
    basis = f"FROM stammdatenindustrie WHERE kundennumm = '{kn}'"

    if "narrativ" in text or thema == "narrativ":
        return (
            f"SELECT TOP {top} nama, nameb, narrativ, purpose, ambition, zielsetzung, begruendung "
            f"{basis}"
        )
    if thema == "produkte" or "produkt" in text or "artikel" in text:
        if ist_topprodukte_frage(frage):
            return (
                f"SELECT TOP {top} nama, nameb, topprodukte, top_produkte, gl_produkt1, gl_produkt2, "
                f"gl_produkt3, sortiment, produktschwerpunkt {basis}"
            )
        return baue_sql_abda_artikel_kundennumm(kn, frage)
    if any(x in text for x in ("marktzielgruppe", "akquiseklasse", "segment")) or thema == "markt":
        return (
            f"SELECT TOP {top} nama, nameb, Marktzielgruppe, emarktzielgruppe, akquiseklasse, "
            f"funktion, Kategorie {basis}"
        )
    if "d2p" in text:
        return f"SELECT TOP {top} nama, nameb, d2p_score, d2p_begruendung {basis}"
    if any(x in text for x in ("adresse", "website", "plz", "ort", "telefon")) or thema == "region":
        return (
            f"SELECT TOP {top} nama, nameb, strasse, hausnr, plz, ort, LKZ, telefon, "
            f"internetadresse, email {basis}"
        )
    if thema in ("firma", "narrativ", "produkte", "markt", "region") and any(
        s in text for s in ("deren", " davon", "dazu", " auch", "noch")
    ):
        return f"SELECT TOP {top} nama, nameb, narrativ, purpose, Marktzielgruppe, topprodukte {basis}"
    return None


FIRMA_SUCHE_SQL_HINWEIS = (
    "Firmenname-Suche in stammdatenindustrie: IMMER nama & nameb verketten "
    f"(z. B. {firma_vollname_expr()} LIKE '%Suchbegriff%'). "
    "Nicht nur nama – nameb enthaelt oft GmbH, Deutschland, GB …"
)


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
        "hinweis": "funktion = Kurzbezeichnung, efunktion = Detail. Marktrolle der FIRMA – nicht Personen-Hierarchie (dafuer ref_funktionen).",
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
        "filter_beispiel": firma_suche_like("Hexal"),
        "hinweis": "Firmenname: nama & nameb verketten (siehe FIRMA_SUCHE). Artikel: abdaartikel.",
    },
    {
        "nutzer_begriffe": [
            "geschaeftsfuehrer", "geschäftsführer", "gf", "vorstand", "vorstandsvorsitzender",
            "inhaber", "hierarchie", "hierarchiestufe", "ebene", "position", "leiter",
            "apothekenleiter", "kam", "key account", "ansprechpartner ebene",
        ],
        "db_tabelle": "ref_funktionen (+ crm_personen)",
        "db_felder": [
            "ref_funktionen.ebene", "ref_funktionen.funktionsbezeichnung",
            "crm_personen.funktionsbezeichnung", "crm_personen.funktionid",
        ],
        "filter_beispiel": (
            "FROM (crm_personen AS p INNER JOIN stammdatenindustrie AS s ON p.kundennumm = s.kundennumm) "
            "LEFT JOIN ref_funktionen AS rf ON p.funktionid = rf.funktionid "
            "WHERE rf.ebene IN ('1', '2')"
        ),
        "hinweis": (
            "Personen-Hierarchie ueber ref_funktionen (JOIN per funktionid), "
            "NICHT stammdatenindustrie.funktion (Marktrolle der Firma). "
            "ebene: 1=Vorstand/Inhaber, 2=GF/Vorstand/Apothekenleiter, 3=Leiter/KAM, 4=Mitarbeiter."
        ),
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
        "\nBEISPIEL-ABFRAGEN:\n"
        "1) Firmen in Akquiseklasse 3 mit Apotheken-Fokus\n"
        f"   SELECT TOP {SQL_DEFAULT_TOP} akquiseklasse, Marktzielgruppe, emarktzielgruppe, nama, nameb, ort, plz "
        "FROM stammdatenindustrie WHERE akquiseklasse = 3 "
        "AND (Marktzielgruppe LIKE '%Apothek%' OR emarktzielgruppe LIKE '%Apothek%')\n"
        "2) Wer ist GF bei Hexal?\n"
        f"   SELECT TOP {SQL_DEFAULT_TOP} p.vorname, p.nachname, rf.funktionsbezeichnung, rf.ebene, s.nama "
        "FROM (crm_personen AS p INNER JOIN stammdatenindustrie AS s ON p.kundennumm = s.kundennumm) "
        "LEFT JOIN ref_funktionen AS rf ON p.funktionid = rf.funktionid "
        "WHERE " + firma_suche_like("Hexal", "s") + " AND rf.ebene IN ('1', '2')\n"
        "3) Top-Produkte von Hexal (Freitext-Zusammenfassung)\n"
        f"   SELECT TOP {SQL_DEFAULT_TOP} nama, nameb, topprodukte, top_produkte, gl_produkt1, gl_produkt2, gl_produkt3 "
        "FROM stammdatenindustrie WHERE " + firma_suche_like("Hexal") + " "
        "(KEIN JOIN abdaartikel)\n"
        "4) Welche Produkte hat Hexal? (ArtikelDB)\n"
        f"   SELECT TOP {SQL_DEFAULT_TOP} s.nama, s.nameb, a.artikelname, a.pzn, a.abgaberegelung "
        "FROM (abdaartikel AS a INNER JOIN stammdatenindustrie AS s ON a.anbieter_nr = s.anbieternummer) "
        "WHERE " + firma_suche_like("Hexal", "s") + " ORDER BY a.artikelname"
    )
    return "\n".join(zeilen)


WIKI_FRAGETYPEN = [
    {
        "thema": "dokument_vertrag",
        "signale": [
            "vertrag", "klausel", "was steht in", "dokument", "pdf", "formular ausfuellen",
            "anleitung", "arbeitsanleitung", "verfahren", "prozess beschreibung",
            "wie lauft ab", "wie läuft ab", "einrichten", "einrichtung", "eingerichtet",
            "schulung", "checkliste", "schritt fuer schritt", "schritt für schritt",
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
            "nama", "nameb", "ort", "rf.ebene", "rf.funktionsbezeichnung",
        ],
        "joins": [
            "crm_personen.kundennumm = stammdatenindustrie.kundennumm",
            "crm_personen.funktionid = ref_funktionen.funktionid",
            "Whitelist_Kontakte.indpersonid = crm_personen.personid",
        ],
        "beispiele": [
            "Wer ist Ansprechpartner bei Hexal?",
            "Telefonnummer von Mueller bei Bayer",
            "Wer ist GF bei Bayer? (ref_funktionen.ebene IN ('1','2'))",
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
            "produkt", "artikel", "pzn", "warengruppe", "stellt her",
            "produziert", "herstellen", "hersteller", "anbieter", "vertreibt", "wirkstoff",
            "rx", "otc", "abda",
            "wie viele artikel", "anzahl artikel", "anzahlabda", "anzahlrx",
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
            "topprodukt", "top produkt", "top-produkt", "wichtigste produkte",
            "sortimentsstruktur", "markenstruktur", "produktschwerpunkt",
            "sortiment von", "sortiment hat", "welches sortiment",
        ],
        "tabellen": ["stammdatenindustrie"],
        "suchfelder": [
            "stammdatenindustrie.nama", "stammdatenindustrie.topprodukte",
            "stammdatenindustrie.top_produkte", "stammdatenindustrie.gl_produkt1",
            "stammdatenindustrie.sortiment", "stammdatenindustrie.produktschwerpunkt",
        ],
        "ausgabefelder": [
            "nama", "nameb", "gl_produkt1", "gl_produkt2", "gl_produkt3",
            "topprodukte", "top_produkte", "sortiment", "sortimentsstruktur",
            "markenstruktur", "produktschwerpunkt",
        ],
        "joins": [],
        "beispiele": [
            "Top-Produkte von Sanofi -> NUR stammdatenindustrie.topprodukte, kein JOIN abdaartikel",
            "Welches Sortiment hat Merz?",
            "Welche Produkte hat Merz? -> abdaartikel JOIN anbieternummer, NICHT topprodukte",
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

""" + baue_semantik_leitfaden() + baue_access_join_regeln() + f"""

=== ACCESS-SQL ===
- SELECT TOP {SQL_DEFAULT_TOP} bei Listen (Standard-Limit, konfigurierbar via DIGIWIKI_SQL_DEFAULT_TOP)
- Nutzer nennt explizit ein Limit (z. B. Top 10) -> dieses Limit verwenden
- GROUP BY statt SELECT DISTINCT mit ORDER BY auf Alias
- Textsuche: LIKE '%' mit OR-Synonymen
- {FIRMA_SUCHE_SQL_HINWEIS}
"""


VERFAHREN_WIKI_SIGNALE = (
    "anleitung",
    "arbeitsanleitung",
    "einricht",
    "eingerichtet",
    "schulung",
    "wie lauft ab",
    "wie läuft ab",
    "checkliste",
    "schritt fuer schritt",
    "schritt für schritt",
    "was steht in der anleitung",
    "laut anleitung",
    "bestellanleitung",
    "formulierungshilfe",
)


def ist_verfahren_wiki_frage(frage: str) -> bool:
    """Fragen zu Einrichtung, Anleitungen, Abläufen → Wiki, nicht SQL."""
    text = (frage or "").lower()
    if any(s in text for s in VERFAHREN_WIKI_SIGNALE):
        return True
    if "digibest" in text and any(s in text for s in ("einricht", "anleitung", "ablauf", "schulung")):
        return True
    return False


def ist_offensichtliche_wiki_frage(frage: str) -> bool:
    """Schnelle Heuristik fuer klare Dokumentenfragen."""
    if ist_verfahren_wiki_frage(frage):
        return True
    text = (frage or "").lower()
    return any(s in text for s in (
        "vertrag", "klausel", "formular ausfüllen", "formular ausfuellen",
        "was steht im dokument", "was steht in dem dokument",
        "verfahren beschreibung", "laut vertrag",
        "prozess beschreibung",
    ))
