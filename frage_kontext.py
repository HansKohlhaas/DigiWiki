"""Gespraechskontext fuer Folgefragen (Firma, Thema, Schluesselfakten)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pyodbc

from config import ACCESS_DB_PATH
from firmen_live_recherche import extrahiere_firmen_suchbegriff

PROFIL_SPALTEN = (
    "produktschwerpunkt",
    "sortiment",
    "topprodukte",
    "top_produkte",
    "hauptgruppe",
    "Kategorie",
    "Marktzielgruppe",
    "emarktzielgruppe",
)

REGION_SPALTEN = (
    "plz",
    "ort",
    "LKZ",
    "PLZ",
    "Ort",
    "gl_plz",
    "gl_ort",
)


FOLGE_FRAGEN_SIGNALE = (
    " und ",
    " auch ",
    " deren ",
    " davon ",
    " dort ",
    " bei der ",
    " bei dem ",
    " bei den ",
    " wer noch",
    " welche ",
    " wie viele",
    " telefon",
    " email",
    " e-mail",
    " ansprechpartner",
    " top-produkte",
    " top produkte",
    " narrativ",
    " marktzielgruppe",
    " d2p",
    " sortiment",
    " schwerpunkt",
    " regional",
    " region",
    " in der region",
    " aus der region",
    " bundesland",
    " plz ",
    " sitz ",
    " standort",
    " dieselbe",
    " dazu ",
    " davon ",
    " noch ",
    " weitere ",
    " weitere",
)

PRONOMEN_SIGNALE = (
    " deren ",
    " dessen ",
    " sie ",
    " er ",
    " die ",
    " das ",
    " dem ",
    " den ",
    " dort ",
    " da ",
)


@dataclass
class FrageKontext:
    letzte_frage: str = ""
    letzte_antwort_typ: str = ""
    firma: str = ""
    kundennumm: str = ""
    person: str = ""
    thema: str = ""
    produktschwerpunkt: str = ""
    region: str = ""
    schluessel_fakten: list[str] = field(default_factory=list)

    def hat_kontext(self) -> bool:
        return bool(self.letzte_frage or self.firma or self.kundennumm)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, daten: dict[str, Any] | None) -> FrageKontext:
        if not daten:
            return cls()
        return cls(
            letzte_frage=str(daten.get("letzte_frage") or ""),
            letzte_antwort_typ=str(daten.get("letzte_antwort_typ") or ""),
            firma=str(daten.get("firma") or ""),
            kundennumm=str(daten.get("kundennumm") or ""),
            person=str(daten.get("person") or ""),
            thema=str(daten.get("thema") or ""),
            produktschwerpunkt=str(daten.get("produktschwerpunkt") or ""),
            region=str(daten.get("region") or ""),
            schluessel_fakten=list(daten.get("schluessel_fakten") or []),
        )


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _erkenne_thema(frage: str) -> str:
    text = _norm(frage)
    if any(x in text for x in ("gf", "geschäftsf", "geschaeftsf", "vorstand", "ceo", "leitung")):
        return "fuehrung"
    if any(x in text for x in ("plz", "ort ", " region", "regional", "bayern", "nrw", "sued", "nord", "west", "ost")):
        return "region"
    if any(x in text for x in ("top-produkt", "top produkt", "sortiment", "produktschwerpunkt")):
        return "topprodukte"
    if any(x in text for x in ("produkt", "artikel", "pzn", "wirkstoff", "husten", "diabetes")):
        return "produkte"
    if any(x in text for x in ("narrativ", "purpose", "zielsetzung", "strategie")):
        return "narrativ"
    if any(x in text for x in ("marktzielgruppe", "akquiseklasse", "segment")):
        return "markt"
    if any(x in text for x in ("ansprechpartner", "kontakt", "telefon", "email")):
        return "kontakte"
    if any(x in text for x in ("hersteller", "husten", "abda", "artikel")):
        return "produkte_markt"
    return "firma"


def ist_folgefrage(frage: str, kontext: FrageKontext | None) -> bool:
    if not kontext or not kontext.hat_kontext():
        return False
    text = f" {_norm(frage)} "
    if extrahiere_firmen_suchbegriff(frage):
        return False
    if any(s in text for s in FOLGE_FRAGEN_SIGNALE):
        return True
    if len(frage.split()) <= 6 and any(s in text for s in PRONOMEN_SIGNALE):
        return True
    return False


FIRMEN_THEMEN = frozenset({"narrativ", "produkte", "markt", "region", "firma", "produkte_markt"})


def _firma_anzeigename(nama: str, nameb: str) -> str:
    """Anzeigename: nameb wenn Firmenform, sonst nama + nameb."""
    na = (nama or "").strip()
    nb = (nameb or "").strip()
    firmen_marker = ("gmbh", " ag", " kg", " se", " inc", " ltd", "vertriebsgesellschaft", "gesellschaft")
    if nb and any(m in nb.lower() for m in firmen_marker):
        return nb
    if na and nb:
        return f"{na} {nb}".strip()
    return na or nb


def _extrahiere_firma_aus_df(spalten: list[str], zeile: dict[str, Any]) -> tuple[str, str]:
    nama = _wert_aus_zeile(zeile, "nama", "Nama")
    nameb = _wert_aus_zeile(zeile, "nameb", "Nameb")
    firma = _firma_anzeigename(nama, nameb)
    kn = ""
    for key in ("kundennumm", "Kundennumm", "kundennr"):
        if key in zeile and str(zeile[key] or "").strip():
            kn = str(zeile[key]).strip()
            break
    if not firma:
        for key in ("firmenname", "Firma", "firma"):
            if key in zeile and str(zeile[key] or "").strip():
                firma = str(zeile[key]).strip()
                break
    return firma, kn


def _wert_aus_zeile(zeile: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in zeile and str(zeile[key] or "").strip():
            return str(zeile[key]).strip()
        lower_map = {str(k).lower(): v for k, v in zeile.items()}
        if key.lower() in lower_map and str(lower_map[key.lower()] or "").strip():
            return str(lower_map[key.lower()]).strip()
    return ""


def _extrahiere_profil_und_region(zeile: dict[str, Any]) -> tuple[str, str]:
    produkt = ""
    for key in PROFIL_SPALTEN:
        val = _wert_aus_zeile(zeile, key)
        if val and len(val) > 2:
            produkt = val[:220]
            break

    plz = _wert_aus_zeile(zeile, "plz", "PLZ", "gl_plz")
    ort = _wert_aus_zeile(zeile, "ort", "Ort", "gl_ort")
    lkz = _wert_aus_zeile(zeile, "LKZ", "lkz")
    region_teile = [p for p in (plz, ort, lkz) if p]
    region = ", ".join(region_teile)
    return produkt, region


def _lade_firmen_profil_aus_db(kundennumm: str) -> tuple[str, str]:
    if not kundennumm or not Path(ACCESS_DB_PATH).exists():
        return "", ""
    sql = (
        "SELECT produktschwerpunkt, sortiment, topprodukte, hauptgruppe, Kategorie, "
        "Marktzielgruppe, plz, ort, LKZ "
        "FROM stammdatenindustrie WHERE kundennumm = ?"
    )
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    try:
        conn = pyodbc.connect(conn_str, timeout=8)
        try:
            cur = conn.cursor()
            cur.execute(sql, (kundennumm,))
            row = cur.fetchone()
            if not row:
                return "", ""
            cols = [d[0] for d in cur.description]
            zeile = dict(zip(cols, row))
            return _extrahiere_profil_und_region(zeile)
        finally:
            conn.close()
    except Exception:
        return "", ""


def _extrahiere_region_aus_mehreren_zeilen(ergebnis_df) -> str:
    """Bei Listen-Abfragen gemeinsame Region erkennen (z. B. gleiche PLZ/Ort)."""
    if ergebnis_df is None or getattr(ergebnis_df, "empty", True):
        return ""
    regionen: set[str] = set()
    for _, row in ergebnis_df.head(20).iterrows():
        _, region = _extrahiere_profil_und_region(row.to_dict())
        if region:
            regionen.add(region)
    if len(regionen) == 1:
        return regionen.pop()
    if len(regionen) <= 3:
        return " | ".join(sorted(regionen))
    return ""


def _baue_fakten_liste(
    row: dict[str, Any],
    produkt: str,
    region: str,
    person: str,
    live_personen: list[dict[str, str]] | None,
    listen_anzahl: int | None = None,
) -> list[str]:
    fakten: list[str] = []
    if produkt:
        fakten.append(f"Produktschwerpunkt: {produkt[:180]}")
    if region:
        fakten.append(f"Region/Sitz: {region}")
    markt = _wert_aus_zeile(row, "Marktzielgruppe", "emarktzielgruppe")
    if markt:
        fakten.append(f"Marktzielgruppe: {markt[:120]}")
    if person:
        fakten.append(f"Person: {person}")
    if listen_anzahl is not None:
        fakten.append(f"{listen_anzahl} Datensaetze")
    elif not fakten:
        for col in row:
            val = row.get(col)
            if val is None or str(val).strip() == "":
                continue
            if str(col).lower() in ("kundennumm", "personid"):
                continue
            fakten.append(f"{col}: {val}")
            if len(fakten) >= 4:
                break
    if live_personen:
        namen = [p.get("name") or f"{p.get('vorname', '')} {p.get('nachname', '')}".strip() for p in live_personen[:5]]
        namen = [n for n in namen if n]
        if namen:
            fakten.append("Personen: " + ", ".join(namen))
    return fakten[:6]


def _extrahiere_person_aus_df(zeile: dict[str, Any]) -> str:
    vor = str(zeile.get("vorname") or zeile.get("Vorname") or "").strip()
    nach = str(zeile.get("nachname") or zeile.get("Nachname") or "").strip()
    return f"{vor} {nach}".strip()


def aktualisiere_kontext(
    kontext: FrageKontext,
    frage: str,
    antwort_typ: str,
    ergebnis_df=None,
    live_firma: str = "",
    live_kundennumm: str = "",
    live_personen: list[dict[str, str]] | None = None,
) -> FrageKontext:
    kontext.letzte_frage = (frage or "").strip()
    kontext.letzte_antwort_typ = antwort_typ or ""
    kontext.thema = _erkenne_thema(frage)

    firma = live_firma or extrahiere_firmen_suchbegriff(frage) or kontext.firma
    kn = live_kundennumm or kontext.kundennumm
    person = kontext.person
    produkt = kontext.produktschwerpunkt
    region = kontext.region
    row: dict[str, Any] = {}
    listen_anzahl: int | None = None

    if ergebnis_df is not None and not getattr(ergebnis_df, "empty", True):
        row = ergebnis_df.iloc[0].to_dict()
        df_firma, df_kn = _extrahiere_firma_aus_df(list(ergebnis_df.columns), row)
        if df_firma:
            firma = df_firma
        if df_kn:
            kn = df_kn
        person_aus_df = _extrahiere_person_aus_df(row)
        if person_aus_df:
            person = person_aus_df
        p, r = _extrahiere_profil_und_region(row)
        if p:
            produkt = p
        if r:
            region = r
        if len(ergebnis_df) > 1:
            listen_anzahl = len(ergebnis_df)
            gemeinsame_region = _extrahiere_region_aus_mehreren_zeilen(ergebnis_df)
            if gemeinsame_region:
                region = gemeinsame_region

    if kn and (not produkt or not region):
        db_produkt, db_region = _lade_firmen_profil_aus_db(kn)
        if db_produkt and not produkt:
            produkt = db_produkt
        if db_region and not region:
            region = db_region

    kontext.firma = firma or kontext.firma
    kontext.kundennumm = kn or kontext.kundennumm
    kontext.person = person or kontext.person
    kontext.produktschwerpunkt = produkt or kontext.produktschwerpunkt
    kontext.region = region or kontext.region
    kontext.schluessel_fakten = _baue_fakten_liste(
        row, kontext.produktschwerpunkt, kontext.region, kontext.person, live_personen, listen_anzahl
    )
    return kontext


def bereichere_frage(frage: str, kontext: FrageKontext) -> str:
    if not ist_folgefrage(frage, kontext):
        return frage
    extras: list[str] = []
    if kontext.kundennumm:
        extras.append(f"kundennumm {kontext.kundennumm}")
    if kontext.firma:
        extras.append(f"Firma {kontext.firma}")
    if kontext.person and kontext.thema not in FIRMEN_THEMEN:
        extras.append(f"Person {kontext.person}")
    if kontext.thema:
        extras.append(f"Thema {kontext.thema}")
    if kontext.produktschwerpunkt:
        extras.append(f"Produktschwerpunkt {kontext.produktschwerpunkt[:100]}")
    if kontext.region:
        extras.append(f"Region/Sitz {kontext.region}")
    if kontext.letzte_frage:
        extras.append(f"vorige Frage: {kontext.letzte_frage}")
    if kontext.schluessel_fakten:
        extras.append("Fakten: " + "; ".join(kontext.schluessel_fakten[:3]))
    if not extras:
        return frage
    return f"{frage.strip()} (Bezug: {', '.join(extras)})"


def baue_sql_kontext_block(kontext: FrageKontext) -> str:
    if not kontext.hat_kontext():
        return ""
    zeilen = [
        "=== GESPRAECHSKONTEXT (Folgefrage) ===",
        f"Letzte Frage: {kontext.letzte_frage}",
    ]
    if kontext.kundennumm:
        zeilen.append(f"kundennumm: {kontext.kundennumm}")
        if kontext.firma:
            zeilen.append(f"Firma (Info): {kontext.firma}")
        zeilen.append(
            f"PFLICHT: WHERE kundennumm = '{kontext.kundennumm}' — kein Firmenname-LIKE, "
            "kein Personenname als Firma."
        )
    elif kontext.firma:
        zeilen.append(f"Firma: {kontext.firma}")
        zeilen.append(
            "Firma filtern mit nama+nameb verkettet (siehe FIRMA_SUCHE im Leitfaden), "
            "nicht nur nama."
        )
    if kontext.person and kontext.thema not in FIRMEN_THEMEN:
        zeilen.append(f"Person: {kontext.person}")
    elif kontext.person and kontext.thema in FIRMEN_THEMEN:
        zeilen.append(
            f"Hinweis: Person {kontext.person} nicht als Firmenfilter — Frage bezieht sich auf die Firma."
        )
    if kontext.thema:
        zeilen.append(f"Thema: {kontext.thema}")
    if kontext.produktschwerpunkt:
        zeilen.append(f"Produktschwerpunkt: {kontext.produktschwerpunkt}")
    if kontext.region:
        zeilen.append(f"Region/Sitz: {kontext.region}")
    if kontext.schluessel_fakten:
        zeilen.append("Schluesselfakten: " + "; ".join(kontext.schluessel_fakten))
    if kontext.thema in FIRMEN_THEMEN:
        zeilen.append(
            "Bei Firmenfeldern (narrativ, purpose, sortiment, Marktzielgruppe): "
            "kundennumm aus Kontext bevorzugen."
        )
    else:
        zeilen.append(
            "Bei unklarer Folgefrage: dieselbe Firma/Person filtern (kundennumm oder Firmenname nama+nameb)."
        )
    zeilen.append(
        "Bei Produkt-/Marktfragen: produktschwerpunkt, sortiment, topprodukte, hauptgruppe beruecksichtigen. "
        "Bei 'Welche Produkte/Artikel hat Firma X': abdaartikel JOIN stammdatenindustrie "
        "ON anbieter_nr = anbieternummer (nicht nur topprodukte-Freitext). "
        "Nur bei explizit 'Top-Produkte' oder 'Sortiment': stammdatenindustrie.topprodukte. "
        "Bei regionalen Folgefragen: plz, ort, LKZ aus stammdatenindustrie nutzen."
    )
    return "\n".join(zeilen)


def baue_wiki_kontext_block(kontext: FrageKontext) -> str:
    if not kontext.hat_kontext():
        return ""
    profil = ""
    if kontext.produktschwerpunkt:
        profil = f" Schwerpunkt: {kontext.produktschwerpunkt[:120]}."
    if kontext.region:
        profil += f" Region: {kontext.region}."
    return (
        f"Gespraechskontext: zuletzt ging es um {kontext.firma or kontext.thema or kontext.letzte_frage}.{profil} "
        f"Schluesselfakten: {'; '.join(kontext.schluessel_fakten[:3]) if kontext.schluessel_fakten else kontext.letzte_frage}"
    )


def kontext_caption(kontext: FrageKontext) -> str:
    if not kontext.hat_kontext():
        return ""
    teile = []
    if kontext.firma:
        teile.append(kontext.firma)
    if kontext.kundennumm:
        teile.append(f"#{kontext.kundennumm}")
    if kontext.produktschwerpunkt:
        teile.append(kontext.produktschwerpunkt[:40] + ("…" if len(kontext.produktschwerpunkt) > 40 else ""))
    if kontext.region:
        teile.append(kontext.region)
    if kontext.thema:
        teile.append(kontext.thema)
    return "Kontext: " + " · ".join(teile)
