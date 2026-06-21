#!/usr/bin/env python3
"""
Extrahiert Personen/Leitungsangaben aus CRM-Website-MD-Archiven und schreibt
den Abgleich mit crm_personen / stammdatenindustrie in eine Access-Tabelle.

Tabelle: md_personen_abgleich (Schluessel: kundennumm fuer JOINs)

Aufruf:
    python md_personen_abgleich.py
    python md_personen_abgleich.py --dry-run
    python md_personen_abgleich.py --limit 100
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pyodbc

from config import ACCESS_DB_PATH, WATCH_TEXT_ENCODINGS

TABELLEN_NAME = "md_personen_abgleich"
DEFAULT_MD_ORDNER = Path(r"C:\Eigene Projekte\MD")
MAX_DATEI_BYTES = 1_500_000

FUNKTION_KEYWORDS = (
    "geschäftsführer",
    "geschaeftsfuehrer",
    "geschäftsführerin",
    "geschaeftsfuehrerin",
    "ceo",
    "vorstand",
    "managing director",
    "geschäftsführung",
    "geschaeftsfuehrung",
    "inhaber",
    "inhaberin",
    "prokurist",
    "gesellschafter",
    "aufsichtsrat",
    "leiter",
    "head of",
    "chief",
)

FUNKTION_PATTERN = re.compile(
    r"(?i)(geschäftsführer(?:in)?|geschaeftsfuehrer(?:in)?|ceo|vorstand|"
    r"managing\s+director|inhaber(?:in)?|prokurist|gesellschafter|"
    r"aufsichtsrat(?:svorsitzende(?:r)?)?|chief\s+\w+|head\s+of\s+\w+|"
    r"leiter(?:in)?\s+\w+)"
)

FALSE_POSITIVE_FRAGMENTS = (
    "taetig", "verantwortet", "mittelstaendisch", "dienstleistungs",
    "unternehmen", "smitglied", "deutschland", "gmbh", "holding",
    "pharmasgp", "astrazeneca", "management", "intelligence", "design",
    "graphic", "brand", "business", "graphic design", "head of",
    "vorstandsmitglied zur", "der pharmasgp", "und gesellschafter ein",
)

GENERIC_EINWORT = {
    "management", "design", "intelligence", "leiter", "inhaber", "prokurist",
    "gesellschafter", "vorstand", "ceo", "deutschland", "marketing",
}

KUNDENNUMM_PATTERN = re.compile(r"^(\d+)_")

TITEL_PATTERN = re.compile(r"^(?:dr\.?|prof\.?|dipl\.?-?\w*\.?)\s+", re.I)

ZITAT_PATTERN = re.compile(
    r"^\s*>\s*"
    r"((?:[A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+){0,4}))"
    r"(?:\s*,?\s*|\s+)"
    r"(.+)$",
    re.MULTILINE,
)

FUNKTION_ALT = (
    r"(?:geschäftsführer(?:in)?|geschaeftsfuehrer(?:in)?|ceo|vorstand|"
    r"managing\s+director|inhaber(?:in)?|prokurist|gesellschafter|"
    r"aufsichtsrat(?:svorsitzende(?:r)?)?|chief\s+\w+|head\s+of\s+\w+|"
    r"leiter(?:in)?\s+\w+)"
)

NAME_VOR_FUNKTION = re.compile(
    r"((?:Dr\.|Prof\.)?\s*[A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+){0,4})"
    r"\s*[,–-]\s*"
    r"(" + FUNKTION_ALT + r"(?:\s+[\w\s&]+)?)",
    re.I,
)

FUNKTION_VOR_NAME = re.compile(
    FUNKTION_ALT + r"\s*[:–-]?\s*"
    r"((?:Dr\.|Prof\.)?\s*[A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+){0,4})",
    re.I,
)


def lese_datei_text(pfad: Path, max_bytes: int = MAX_DATEI_BYTES) -> str:
    raw = pfad.read_bytes()[:max_bytes]
    for enc in WATCH_TEXT_ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def norm_text(s: str) -> str:
    s = (s or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def norm_name(s: str) -> str:
    s = TITEL_PATTERN.sub("", (s or "").strip())
    return norm_text(s)


def nachname_aus(name: str) -> str:
    teile = norm_name(name).split()
    return teile[-1] if teile else ""


def enthaelt_fuehrungs_keyword(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in FUNKTION_KEYWORDS)


def bereinige_funktion(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[:250]


def bereinige_name(name: str) -> str | None:
    name = re.sub(r"\s+", " ", (name or "").strip(" ,.;>"))
    if not name or len(name) < 4:
        return None
    lower = name.lower()
    if lower in {"hexal", "sandoz", "impressum", "datenschutz", "linkedin"}:
        return None
    if not re.search(r"[A-ZÄÖÜ]", name):
        return None
    woerter = name.split()
    if len(woerter) > 5:
        return None
    norm = norm_name(name)
    if any(fp in norm for fp in FALSE_POSITIVE_FRAGMENTS):
        return None
    if len(woerter) == 1 and norm in GENERIC_EINWORT:
        return None
    # Mindestens ein Wort mit 3+ Buchstaben, das nicht generisch ist
    name_woerter = [w for w in woerter if w.lower() not in {"dr", "prof", "und", "der", "die", "von"}]
    if not name_woerter:
        return None
    if all(w.lower() in GENERIC_EINWORT for w in name_woerter):
        return None
    return name[:120]


def extrahiere_personen(text: str) -> list[dict[str, str]]:
    treffer: list[dict[str, str]] = []
    gesehen: set[tuple[str, str]] = set()

    def hinzufuegen(name: str, funktion: str, quelle: str, kontext: str = "") -> None:
        name = bereinige_name(name)
        if not name:
            return
        funktion = bereinige_funktion(funktion)
        if not enthaelt_fuehrungs_keyword(funktion) and quelle != "zitat":
            return
        key = (norm_name(name), norm_text(funktion))
        if key in gesehen:
            return
        gesehen.add(key)
        treffer.append(
            {
                "person_name": name,
                "person_funktion": funktion,
                "quelle_typ": quelle,
                "md_kontext": (kontext or f"{name} – {funktion}")[:400],
            }
        )

    for m in ZITAT_PATTERN.finditer(text):
        hinzufuegen(m.group(1), m.group(2), "zitat", m.group(0).strip()[:400])

    for m in NAME_VOR_FUNKTION.finditer(text):
        hinzufuegen(m.group(1), m.group(2), "name_funktion", m.group(0).strip()[:400])

    for m in FUNKTION_VOR_NAME.finditer(text):
        hinzufuegen(m.group(1), m.group(0).split(":")[0], "funktion_name", m.group(0).strip()[:400])

    for zeile in text.splitlines():
        if not enthaelt_fuehrungs_keyword(zeile):
            continue
        if len(zeile) > 500 or zeile.count("{") > 2:
            continue
        m = re.search(
            r"((?:Dr\.|Prof\.)?\s*[A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+){0,3})"
            r".{0,40}?"
            r"(?i:geschäftsführer(?:in)?|geschaeftsfuehrer(?:in)?|ceo|vorstand|inhaber(?:in)?)",
            zeile,
        )
        if m:
            funktion_m = FUNKTION_PATTERN.search(zeile[m.start(1) :])
            funktion = funktion_m.group(0) if funktion_m else "Fuehrung"
            hinzufuegen(m.group(1), funktion, "zeile", zeile.strip()[:400])

    return treffer


def kundennumm_aus_dateiname(name: str) -> str | None:
    m = KUNDENNUMM_PATTERN.match(name)
    return m.group(1) if m else None


def lade_db_kontext(conn) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    cur = conn.cursor()
    stamm: dict[str, dict] = {}

    cur.execute(
        "SELECT kundennumm, nama, entscheider, gefundene_personen FROM stammdatenindustrie"
    )
    for row in cur.fetchall():
        kn = str(row[0] or "").strip()
        if kn:
            stamm[kn] = {
                "firmenname": str(row[1] or "").strip(),
                "entscheider": str(row[2] or "").strip(),
                "gefundene_personen": str(row[3] or "").strip(),
            }

    cur.execute("SELECT kundennumm, nama FROM stammdatenapo")
    for row in cur.fetchall():
        kn = str(row[0] or "").strip()
        if kn and kn not in stamm:
            stamm[kn] = {
                "firmenname": str(row[1] or "").strip(),
                "entscheider": "",
                "gefundene_personen": "",
            }

    personen: dict[str, list[dict]] = {}
    cur.execute(
        "SELECT kundennumm, vorname, nachname, funktionsbezeichnung FROM crm_personen"
    )
    for row in cur.fetchall():
        kn = str(row[0] or "").strip()
        if not kn:
            continue
        personen.setdefault(kn, []).append(
            {
                "name": " ".join(p for p in (str(row[1] or "").strip(), str(row[2] or "").strip()) if p),
                "funktion": str(row[3] or "").strip(),
            }
        )
    return stamm, personen


def parse_entscheider(text: str) -> list[str]:
    if not text:
        return []
    namen = []
    for teil in re.split(r"\||;", text):
        teil = teil.strip()
        if not teil:
            continue
        name = re.sub(r"\([^)]*\)", "", teil).strip(" ,")
        if name:
            namen.append(name)
    return namen


def name_in_text(name: str, haystack: str) -> bool:
    n = norm_name(name)
    h = norm_text(haystack)
    if not n or not h:
        return False
    if n in h:
        return True
    nn = nachname_aus(name)
    return len(nn) >= 4 and f" {nn} " in f" {h} "


def vergleiche_mit_db(
    person: dict[str, str],
    stamm: dict | None,
    crm_liste: list[dict],
) -> dict[str, str | bool]:
    name = person["person_name"]
    in_crm = False
    in_entscheider = False
    in_gefunden = False
    crm_match = ""

    for p in crm_liste:
        voller = p["name"] or p["funktion"]
        if name_in_text(name, voller) or (p["name"] and name_in_text(p["name"], name)):
            in_crm = True
            crm_match = p["name"] or p["funktion"]
            break
        if p["funktion"] and name_in_text(name, p["funktion"]):
            in_crm = True
            crm_match = p["funktion"]
            break

    if stamm:
        if name_in_text(name, stamm.get("entscheider", "")):
            in_entscheider = True
        if name_in_text(name, stamm.get("gefundene_personen", "")):
            in_gefunden = True
        for en in parse_entscheider(stamm.get("entscheider", "")):
            if name_in_text(name, en):
                in_entscheider = True

    if in_crm or in_entscheider or in_gefunden:
        status = "in_db"
    elif stamm and (stamm.get("entscheider") or crm_liste):
        status = "nur_in_md"
    else:
        status = "nur_in_md_db_leer"

    return {
        "in_crm_personen": in_crm,
        "in_entscheider": in_entscheider,
        "in_gefundene_personen": in_gefunden,
        "abgleich_status": status,
        "crm_match": crm_match[:250],
    }


def finde_md_ordner() -> Path:
    if os.getenv("DIGIWIKI_MD_ORDNER"):
        return Path(os.getenv("DIGIWIKI_MD_ORDNER", "")).expanduser()
    if DEFAULT_MD_ORDNER.is_dir():
        return DEFAULT_MD_ORDNER
    for root in (Path(r"C:\Eigene Projekte"), Path(r"C:\Verwaltung")):
        kandidat = root / "MD"
        if kandidat.is_dir():
            return kandidat
    return DEFAULT_MD_ORDNER


def erstelle_tabelle(cur) -> None:
    try:
        cur.execute(f"DROP TABLE [{TABELLEN_NAME}]")
    except pyodbc.Error:
        pass
    cur.execute(
        f"""
        CREATE TABLE [{TABELLEN_NAME}] (
            id COUNTER PRIMARY KEY,
            kundennumm TEXT(20),
            firmenname TEXT(255),
            md_dateiname TEXT(255),
            person_name TEXT(255),
            person_funktion TEXT(255),
            md_kontext MEMO,
            quelle_typ TEXT(50),
            in_crm_personen YESNO,
            in_entscheider YESNO,
            in_gefundene_personen YESNO,
            abgleich_status TEXT(50),
            crm_match TEXT(255),
            analysiert_am DATETIME
        )
        """
    )


def analysiere(md_ordner: Path, limit: int | None = None, dry_run: bool = False) -> dict:
    md_dateien = sorted(md_ordner.glob("*.md"))
    if limit:
        md_dateien = md_dateien[:limit]

    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    conn = pyodbc.connect(conn_str)
    stamm_map, personen_map = lade_db_kontext(conn)

    ergebnis_zeilen: list[dict] = []
    stats = {
        "dateien_gesamt": len(md_dateien),
        "dateien_mit_keywords": 0,
        "dateien_mit_personen": 0,
        "personen_gesamt": 0,
        "nur_in_md": 0,
        "in_db": 0,
    }

    for pfad in md_dateien:
        kn = kundennumm_aus_dateiname(pfad.name)
        if not kn:
            continue
        try:
            text = lese_datei_text(pfad)
        except OSError:
            continue
        if not enthaelt_fuehrungs_keyword(text):
            continue
        stats["dateien_mit_keywords"] += 1

        personen = extrahiere_personen(text)
        if not personen:
            continue
        stats["dateien_mit_personen"] += 1

        stamm = stamm_map.get(kn)
        firmenname = (stamm or {}).get("firmenname") or pfad.stem.split("_", 1)[-1].replace("_", " ")
        crm_liste = personen_map.get(kn, [])

        for person in personen:
            if firmenname and name_in_text(person["person_name"], firmenname):
                continue
            abgleich = vergleiche_mit_db(person, stamm, crm_liste)
            stats["personen_gesamt"] += 1
            if abgleich["abgleich_status"] == "nur_in_md":
                stats["nur_in_md"] += 1
            elif abgleich["abgleich_status"] == "in_db":
                stats["in_db"] += 1

            ergebnis_zeilen.append(
                {
                    "kundennumm": kn,
                    "firmenname": firmenname,
                    "md_dateiname": pfad.name,
                    **person,
                    **abgleich,
                    "analysiert_am": datetime.now(),
                }
            )

    if not dry_run:
        cur = conn.cursor()
        erstelle_tabelle(cur)
        insert_sql = f"""
            INSERT INTO [{TABELLEN_NAME}] (
                kundennumm, firmenname, md_dateiname, person_name, person_funktion,
                md_kontext, quelle_typ, in_crm_personen, in_entscheider,
                in_gefundene_personen, abgleich_status, crm_match, analysiert_am
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for row in ergebnis_zeilen:
            cur.execute(
                insert_sql,
                (
                    row["kundennumm"],
                    row["firmenname"],
                    row["md_dateiname"],
                    row["person_name"],
                    row["person_funktion"],
                    row["md_kontext"],
                    row["quelle_typ"],
                    row["in_crm_personen"],
                    row["in_entscheider"],
                    row["in_gefundene_personen"],
                    row["abgleich_status"],
                    row["crm_match"],
                    row["analysiert_am"],
                ),
            )
        conn.commit()

    conn.close()
    stats["zeilen_geschrieben"] = len(ergebnis_zeilen)
    stats["tabelle"] = TABELLEN_NAME
    stats["datenbank"] = str(ACCESS_DB_PATH)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="MD-Personen vs. CRM-DB in Access-Tabelle")
    parser.add_argument("--md-ordner", type=Path, default=None, help="Ordner mit CRM-MD-Dateien")
    parser.add_argument("--limit", type=int, default=None, help="Nur erste N Dateien (Test)")
    parser.add_argument("--dry-run", action="store_true", help="Analyse ohne DB-Schreiben")
    args = parser.parse_args()

    md_ordner = args.md_ordner or finde_md_ordner()
    if not md_ordner.is_dir():
        print(f"MD-Ordner nicht gefunden: {md_ordner}", file=sys.stderr)
        return 1

    print(f"MD-Ordner:     {md_ordner}")
    print(f"Access-DB:     {ACCESS_DB_PATH}")
    print(f"Tabelle:       {TABELLEN_NAME}")
    if args.dry_run:
        print("Modus:         dry-run (kein Schreiben)")
    print("Analyse laeuft …")

    stats = analysiere(md_ordner, limit=args.limit, dry_run=args.dry_run)

    print()
    print("--- Ergebnis ---")
    for key, val in stats.items():
        print(f"  {key}: {val}")
    if not args.dry_run:
        print()
        print(f"Fertig. In Access: SELECT * FROM {TABELLEN_NAME} WHERE abgleich_status = 'nur_in_md';")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
