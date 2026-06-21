"""Vorstand/GF aus Live-Web-Text parsen und in crm_personen schreiben."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pyodbc

from config import ACCESS_DB_PATH

TITEL_PATTERN = re.compile(r"^(?:Dr\.?|Prof\.?|Dipl\.?-?\w*\.?)\s+", re.I)
ANREDE_PATTERN = re.compile(r"^(Herr|Frau|Hr\.|Fr\.)\s+", re.I)

LISTEN_FUEHRUNG_RE = re.compile(
    r"(?im)^\s*"
    r"(Vorstand|Geschäftsführer|Geschaeftsfuehrer|Geschäftsführerin|Geschaeftsfuehrerin|"
    r"Aufsichtsrat(?:svorsitzende(?:r)?)?|Vorsitzende(?:r)?\s+des\s+Aufsichtsrates?"
    r"|Managing\s+Director|CEO)\s*:\s*(.+?)\s*$"
)

FUNKTION_ZU_REF = {
    "vorstand": ("6", "Vorstand"),
    "geschäftsführer": ("12", "Geschäftsführer"),
    "geschaeftsfuehrer": ("12", "Geschäftsführer"),
    "geschäftsführerin": ("12", "Geschäftsführerin"),
    "geschaeftsfuehrerin": ("12", "Geschäftsführerin"),
    "aufsichtsrat": ("11", "Aufsichtsrat"),
    "aufsichtsratsvorsitzender": ("11", "Aufsichtsratsvorsitzender"),
    "aufsichtsratsvorsitzende": ("11", "Aufsichtsratsvorsitzende"),
    "vorsitzende des aufsichtsrates": ("11", "Aufsichtsratsvorsitzende"),
    "vorsitzender des aufsichtsrates": ("11", "Aufsichtsratsvorsitzender"),
    "managing director": ("12", "Managing Director"),
    "ceo": ("12", "CEO"),
}


@dataclass
class PersonenSyncErgebnis:
    ok: bool = True
    neu: int = 0
    vorhanden: int = 0
    aktualisiert: int = 0
    personen: list[dict[str, str]] = field(default_factory=list)
    fehler: str = ""


def _norm(s: str) -> str:
    s = (s or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _funktion_ref(rolle: str) -> tuple[str, str]:
    key = _norm(rolle)
    if key in FUNKTION_ZU_REF:
        return FUNKTION_ZU_REF[key]
    if "vorstand" in key and "vorsitz" in key:
        return "5", "Vorstandsvorsitzender"
    if "vorstand" in key:
        return "6", "Vorstand"
    if "aufsichtsrat" in key:
        return "11", "Aufsichtsrat"
    if "geschaeftsf" in key or "geschäftsf" in key:
        return "12", "Geschäftsführer"
    return "11", rolle.strip()[:80]


def _split_namensliste(roh: str) -> list[str]:
    teile = [t.strip(" .;") for t in (roh or "").split(",")]
    return [t for t in teile if t and len(t) > 2]


def _name_zu_felder(name: str) -> tuple[str, str, str, str]:
    name = re.sub(r"\s+", " ", (name or "").strip())
    anrede = ""
    m = ANREDE_PATTERN.match(name)
    if m:
        anrede = m.group(1).replace("Hr.", "Herr").replace("Fr.", "Frau")
        name = name[m.end() :].strip()
    titel = ""
    m = TITEL_PATTERN.match(name)
    if m:
        titel = m.group(0).strip()
        name = name[m.end() :].strip()
    woerter = name.split()
    if not woerter:
        return anrede, titel, "", ""
    if len(woerter) == 1:
        return anrede, titel, "", woerter[0]
    return anrede, titel, " ".join(woerter[:-1]), woerter[-1]


def extrahiere_fuehrung_personen(text: str) -> list[dict[str, str]]:
    """Impressum-Zeilen wie 'Vorstand: A, B, C' in Personen-Dicts zerlegen."""
    personen: list[dict[str, str]] = []
    gesehen: set[tuple[str, str]] = set()

    for m in LISTEN_FUEHRUNG_RE.finditer(text or ""):
        rolle = m.group(1).strip()
        funktionid, funktion = _funktion_ref(rolle)
        for name_roh in _split_namensliste(m.group(2)):
            anrede, titel, vorname, nachname = _name_zu_felder(name_roh)
            if not nachname:
                continue
            key = (_norm(nachname), _norm(vorname))
            if key in gesehen:
                continue
            gesehen.add(key)
            personen.append(
                {
                    "anrede": anrede,
                    "titel": titel,
                    "vorname": vorname,
                    "nachname": nachname,
                    "funktionid": funktionid,
                    "funktionsbezeichnung": funktion,
                    "quelle_kontext": m.group(0).strip()[:250],
                }
            )
    return personen


def _naechste_personid(cur) -> str:
    cur.execute("SELECT MAX(CLng(personid)) FROM crm_personen")
    row = cur.fetchone()
    return str(int(row[0] or 0) + 1)


def _lade_firmen_personen(cur, kundennumm: str) -> list[dict[str, str]]:
    cur.execute(
        "SELECT personid, anrede, titel, vorname, nachname, funktionid, funktionsbezeichnung "
        "FROM crm_personen WHERE kundennumm = ?",
        (kundennumm,),
    )
    return [
        {
            "personid": str(r[0] or "").strip(),
            "anrede": str(r[1] or "").strip(),
            "titel": str(r[2] or "").strip(),
            "vorname": str(r[3] or "").strip(),
            "nachname": str(r[4] or "").strip(),
            "funktionid": str(r[5] or "").strip(),
            "funktionsbezeichnung": str(r[6] or "").strip(),
        }
        for r in cur.fetchall()
    ]


def _finde_duplikat(person: dict[str, str], bestehend: list[dict[str, str]]) -> dict[str, str] | None:
    ziel_nach = _norm(person["nachname"])
    ziel_vor = _norm(person["vorname"])
    for alt in bestehend:
        if _norm(alt["nachname"]) != ziel_nach:
            continue
        if ziel_vor and alt["vorname"] and _norm(alt["vorname"]) != ziel_vor:
            continue
        return alt
    return None


def sync_nach_crm_personen(
    kundennumm: str,
    personen: list[dict[str, str]],
    quelle_url: str = "",
    dry_run: bool = False,
) -> PersonenSyncErgebnis:
    if not personen:
        return PersonenSyncErgebnis(ok=True)
    if not kundennumm or not Path(ACCESS_DB_PATH).exists():
        return PersonenSyncErgebnis(ok=False, fehler="CRM-Datenbank nicht erreichbar.")

    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    ergebnis = PersonenSyncErgebnis()
    heute = datetime.now().strftime("%Y-%m-%d")
    quelle = f"DigiWiki-LiveWeb {quelle_url}".strip()[:120]

    try:
        conn = pyodbc.connect(conn_str, timeout=12)
        try:
            cur = conn.cursor()
            bestehend = _lade_firmen_personen(cur, kundennumm)

            for person in personen:
                dup = _finde_duplikat(person, bestehend)
                if dup:
                    ergebnis.vorhanden += 1
                    ergebnis.personen.append(
                        {
                            "status": "vorhanden",
                            "personid": dup["personid"],
                            "anrede": person.get("anrede", ""),
                            "titel": person.get("titel", ""),
                            "vorname": person.get("vorname", ""),
                            "nachname": person.get("nachname", ""),
                            "name": f"{person['vorname']} {person['nachname']}".strip(),
                            "funktionid": person["funktionid"],
                            "funktion": person["funktionsbezeichnung"],
                        }
                    )
                    if not dry_run:
                        neue_anrede = person.get("anrede", "") if not dup.get("anrede") else dup["anrede"]
                        neuer_titel = person.get("titel", "") if not dup.get("titel") else dup["titel"]
                        neue_fid = person["funktionid"]
                        neue_funk = person["funktionsbezeichnung"]
                        if dup["funktionid"] in ("5", "6", "12"):
                            neue_fid = dup["funktionid"]
                            neue_funk = dup["funktionsbezeichnung"] or neue_funk
                        aendern = (
                            neue_anrede != dup.get("anrede", "")
                            or neuer_titel != dup.get("titel", "")
                            or (
                                person["funktionid"] in ("5", "6", "12")
                                and dup["funktionid"] not in ("5", "6", "12")
                            )
                        )
                        if aendern:
                            cur.execute(
                                "UPDATE crm_personen SET anrede = ?, titel = ?, "
                                "funktionid = ?, funktionsbezeichnung = ?, "
                                "update_status = ?, validation_status = ? "
                                "WHERE personid = ?",
                                (
                                    neue_anrede,
                                    neuer_titel,
                                    neue_fid,
                                    neue_funk,
                                    quelle,
                                    "auto_web",
                                    dup["personid"],
                                ),
                            )
                            ergebnis.aktualisiert += 1
                    continue

                personid = _naechste_personid(cur)
                if not dry_run:
                    cur.execute(
                        "INSERT INTO crm_personen "
                        "(personid, kundennumm, anrede, titel, vorname, nachname, funktionid, "
                        "funktionsbezeichnung, update_status, validation_status, anfuegedatum) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            personid,
                            kundennumm,
                            person.get("anrede", ""),
                            person.get("titel", ""),
                            person.get("vorname", ""),
                            person.get("nachname", ""),
                            person["funktionid"],
                            person["funktionsbezeichnung"],
                            quelle,
                            "auto_web",
                            heute,
                        ),
                    )
                bestehend.append(
                    {
                        "personid": personid,
                        "vorname": person.get("vorname", ""),
                        "nachname": person.get("nachname", ""),
                        "funktionid": person["funktionid"],
                        "funktionsbezeichnung": person["funktionsbezeichnung"],
                    }
                )
                ergebnis.neu += 1
                ergebnis.personen.append(
                    {
                        "status": "neu",
                        "personid": personid,
                        "anrede": person.get("anrede", ""),
                        "titel": person.get("titel", ""),
                        "vorname": person.get("vorname", ""),
                        "nachname": person.get("nachname", ""),
                        "name": f"{person['vorname']} {person['nachname']}".strip(),
                        "funktionid": person["funktionid"],
                        "funktion": person["funktionsbezeichnung"],
                    }
                )

            if not dry_run:
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        return PersonenSyncErgebnis(ok=False, fehler=str(e))

    return ergebnis
