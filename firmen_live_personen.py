"""Vorstand/GF aus Live-Web-Text parsen und in crm_personen schreiben."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pyodbc

from config import ACCESS_DB_PATH, PERSONEN_KI_PLAUSIBILITAET
TITEL_PATTERN = re.compile(r"^(?:Dr\.?|Prof\.?|Dipl\.?-?\w*\.?)\s+", re.I)
ANREDE_PATTERN = re.compile(r"^(Herr|Frau|Hr\.|Fr\.)\s+", re.I)

LISTEN_FUEHRUNG_RE = re.compile(
    r"(?im)^\s*"
    r"(Vorstand|Geschäftsführer|Geschaeftsfuehrer|Geschäftsführerin|Geschaeftsfuehrerin|"
    r"Geschäftsführung|Geschaeftsfuehrung|Vertretungsberechtigte(?:r)?|"
    r"Vertretungsberechtigter\s+Geschäftsführer|"
    r"Aufsichtsrat(?:svorsitzende(?:r)?)?|Vorsitzende(?:r)?\s+des\s+Aufsichtsrates?"
    r"|Managing\s+Director|CEO|GF)\s*:?\s*(.+?)\s*$"
)

ROLLEN_NUR_ZEILE_RE = re.compile(
    r"(?im)^\s*"
    r"(Vorstand|Geschäftsführer(?:in)?|Geschaeftsfuehrer(?:in)?|Geschäftsführung|"
    r"Geschaeftsfuehrung|Vertretungsberechtigte(?:r)?|"
    r"Vertretungsberechtigter\s+Geschäftsführer|CEO|Managing\s+Director)\s*:?\s*$"
)

INLINE_FUEHRUNG_RE = re.compile(
    r"(?im)^\s*"
    r"(Geschäftsführer(?:in)?|Geschaeftsfuehrer(?:in)?|Vertretungsberechtigte[r]?|"
    r"Vorstandsvorsitzende[r]?|CEO)\s+"
    r"(.+)$"
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

FUNKTION_KATALOG_FALLBACK: list[dict[str, str]] = [
    {"funktionid": "5", "ebene": "1", "funktionsbezeichnung": "Vorstandsvorsitzender"},
    {"funktionid": "6", "ebene": "2", "funktionsbezeichnung": "Vorstand"},
    {"funktionid": "11", "ebene": "2", "funktionsbezeichnung": "Aufsichtsrat"},
    {"funktionid": "12", "ebene": "2", "funktionsbezeichnung": "Geschäftsführer"},
    {"funktionid": "12", "ebene": "2", "funktionsbezeichnung": "Geschäftsführerin"},
    {"funktionid": "12", "ebene": "2", "funktionsbezeichnung": "CEO"},
    {"funktionid": "12", "ebene": "2", "funktionsbezeichnung": "Managing Director"},
]

_funktions_katalog_cache: list[dict[str, str]] | None = None


@dataclass
class PersonenSyncErgebnis:
    ok: bool = True
    neu: int = 0
    vorhanden: int = 0
    aktualisiert: int = 0
    personen: list[dict[str, str]] = field(default_factory=list)
    fehler: str = ""
    abgelehnt_plausibilitaet: int = 0
    ki_geprueft: bool = False


@dataclass
class PersonenPruefErgebnis:
    personen: list[dict[str, str]] = field(default_factory=list)
    abgelehnt: int = 0
    ki_verwendet: bool = False
    hinweise: list[str] = field(default_factory=list)


RECHTLICH_SUFFIX_RE = re.compile(
    r"\s+und\s+(?:Verantwortlich|verantwortlich|gemäß|gemaess|inhalte nach|§|\d+\s*Abs\.)",
    re.I,
)
KEIN_NAME_SIGNAL_RE = re.compile(
    r"§|abs\.|mstv|tmkg|tmg|verantwortlich|sinn von|inhalte nach|"
    r"ust[\-\s]?id|handelsregister|amtsgericht|straße|strasse|str\.|"
    r"telefon|tel\.|fax|datenschutz|impressum|cookie|umsatzsteuer|"
    r"vertretungsberechtigt(?!e[r]?\s*$)",
    re.I,
)
NAME_ZEICHEN_RE = re.compile(r"^[\wäöüÄÖÜß.\-'\s]+$")
STOPWORT_VORNAME_NACHNAME = frozenset(
    {"und", "der", "die", "das", "für", "fur", "von", "im", "in", "am", "dem", "den", "des", "sinn"}
)


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


def lade_funktions_katalog() -> list[dict[str, str]]:
    """ref_funktionen aus CRM (gecacht) fuer KI-Zuordnung funktionid."""
    global _funktions_katalog_cache
    if _funktions_katalog_cache is not None:
        return _funktions_katalog_cache

    if not Path(ACCESS_DB_PATH).exists():
        _funktions_katalog_cache = FUNKTION_KATALOG_FALLBACK
        return _funktions_katalog_cache

    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    try:
        conn = pyodbc.connect(conn_str, timeout=8)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT funktionid, ebene, funktionsbezeichnung "
                "FROM ref_funktionen ORDER BY funktionid"
            )
            rows = [
                {
                    "funktionid": str(r[0] or "").strip(),
                    "ebene": str(r[1] or "").strip(),
                    "funktionsbezeichnung": str(r[2] or "").strip(),
                }
                for r in cur.fetchall()
                if str(r[0] or "").strip()
            ]
            _funktions_katalog_cache = rows or FUNKTION_KATALOG_FALLBACK
        finally:
            conn.close()
    except Exception:
        _funktions_katalog_cache = FUNKTION_KATALOG_FALLBACK
    return _funktions_katalog_cache


def _funktions_katalog_text_fuer_ki() -> str:
    syn_map: dict[str, list[str]] = {}
    try:
        from crm_funktion_mapping import synonyme_beispiele_pro_funktionid

        syn_map = synonyme_beispiele_pro_funktionid(max_pro_id=6)
    except Exception:
        pass
    zeilen: list[str] = []
    for row in lade_funktions_katalog():
        ebene = row.get("ebene") or "?"
        fid = row["funktionid"]
        syn_hinweis = ""
        if syn_map.get(fid):
            syn_hinweis = f" | Bekannte Berufsbezeichnungen: {', '.join(syn_map[fid])}"
        zeilen.append(
            f"- funktionid {fid}: {row['funktionsbezeichnung']} (Ebene {ebene}){syn_hinweis}"
        )
    return "\n".join(zeilen)


def _normalisiere_anrede(anrede: str, kontext: str = "") -> str:
    a = (anrede or "").strip()
    lower = a.lower()
    if lower in ("herr", "hr.", "hr", "m"):
        return "Herr"
    if lower in ("frau", "fr.", "fr", "w"):
        return "Frau"
    if a:
        return ""
    ctx = (kontext or "").lower()
    if re.search(r"\bfrau\b", ctx):
        return "Frau"
    if re.search(r"\bherr\b", ctx):
        return "Herr"
    if re.search(r"geschäftsführerin|geschaeftsfuehrerin", ctx, re.I):
        return "Frau"
    return ""


def _funktion_aus_katalog(
    funktionid: str,
    funktionsbezeichnung: str,
    fallback_rolle: str = "",
) -> tuple[str, str]:
    katalog = lade_funktions_katalog()
    fid = str(funktionid or "").strip()
    fbez = (funktionsbezeichnung or "").strip()

    if fid:
        treffer = [r for r in katalog if r["funktionid"] == fid]
        if treffer:
            if fbez:
                for row in treffer:
                    if _norm(row["funktionsbezeichnung"]) == _norm(fbez):
                        return row["funktionid"], row["funktionsbezeichnung"]
            return treffer[0]["funktionid"], treffer[0]["funktionsbezeichnung"]

    if fbez or fallback_rolle:
        suchtext = fbez or fallback_rolle
        try:
            from crm_funktion_mapping import (
                finde_funktion_aus_synonymen,
                finde_funktionid_fuer_bezeichnung,
            )

            sid, sbez, _ = finde_funktion_aus_synonymen(suchtext)
            if sid:
                return sid, sbez or suchtext
        except Exception:
            pass

        for row in katalog:
            if _norm(row["funktionsbezeichnung"]) == _norm(suchtext):
                return row["funktionid"], row["funktionsbezeichnung"]
        for row in katalog:
            if _norm(suchtext) in _norm(row["funktionsbezeichnung"]) or _norm(
                row["funktionsbezeichnung"]
            ) in _norm(suchtext):
                return row["funktionid"], row["funktionsbezeichnung"]

        try:
            from crm_funktion_mapping import finde_funktionid_fuer_bezeichnung

            fid_tfidf, bez_tfidf, _ = finde_funktionid_fuer_bezeichnung(suchtext)
            if fid_tfidf:
                return fid_tfidf, bez_tfidf
        except Exception:
            pass

    return _funktion_ref(fbez or fallback_rolle)


def _person_felder_normalisieren(person: dict[str, str]) -> dict[str, str]:
    kontext = person.get("quelle_kontext", "")
    fid, fbez = _funktion_aus_katalog(
        person.get("funktionid", ""),
        person.get("funktionsbezeichnung", ""),
    )
    return {
        **person,
        "anrede": _normalisiere_anrede(person.get("anrede", ""), kontext),
        "funktionid": fid,
        "funktionsbezeichnung": fbez,
    }


def _bereinige_namen_roh(roh: str) -> str:
    text = (roh or "").strip()
    text = RECHTLICH_SUFFIX_RE.split(text, maxsplit=1)[0]
    text = re.split(
        r"[;:]\s*(?:Verantwortlich|Inhaltlich|§|Datenschutz|Umsatzsteuer)",
        text,
        maxsplit=1,
        flags=re.I,
    )[0]
    return text.strip(" .;,")


def _split_namensliste(roh: str) -> list[str]:
    roh = _bereinige_namen_roh(roh)
    if not roh:
        return []
    teile = re.split(r",|\s+und\s+|\s*&\s*", roh, flags=re.I)
    out: list[str] = []
    for teil in teile:
        t = teil.strip(" .;")
        if not t or len(t) < 3:
            continue
        if _ist_offensichtlich_kein_personenname("", t) or _ist_offensichtlich_kein_personenname(t, t):
            continue
        out.append(t)
    return out


def _ist_offensichtlich_kein_personenname(vorname: str, nachname: str) -> bool:
    vor = (vorname or "").strip()
    nach = (nachname or "").strip()
    voll = f"{vor} {nach}".strip()
    if not nach or len(nach) < 2:
        return True
    if len(voll) > 90:
        return True
    if KEIN_NAME_SIGNAL_RE.search(voll):
        return True
    if vor.lower().startswith("und ") or nach.lower().startswith("und "):
        return True
    for teil in (vor.lower(), nach.lower()):
        if teil in STOPWORT_VORNAME_NACHNAME:
            return True
    if vor and len(vor.split()) > 4:
        return True
    if not NAME_ZEICHEN_RE.match(voll):
        return True
    if not re.search(r"[A-ZÄÖÜ]", nach) or not re.search(r"[a-zäöüß]", nach, re.I):
        return True
    return False


def filtere_personen_regeln(personen: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    gueltig: list[dict[str, str]] = []
    abgelehnt = 0
    for person in personen:
        if _ist_offensichtlich_kein_personenname(
            person.get("vorname", ""), person.get("nachname", "")
        ):
            abgelehnt += 1
            continue
        gueltig.append(person)
    return gueltig, abgelehnt


def _pruefe_personen_ki(
    personen: list[dict[str, str]],
    impressum_text: str,
    firmenname: str,
) -> PersonenPruefErgebnis:
    if not personen or not os.getenv("OPENAI_API_KEY"):
        return PersonenPruefErgebnis(personen=personen)

    kandidaten = [
        {
            "index": i,
            "anrede": p.get("anrede", ""),
            "titel": p.get("titel", ""),
            "vorname": p.get("vorname", ""),
            "nachname": p.get("nachname", ""),
            "funktionid": p.get("funktionid", ""),
            "funktionsbezeichnung": p.get("funktionsbezeichnung", ""),
            "kontext": p.get("quelle_kontext", "")[:200],
        }
        for i, p in enumerate(personen)
    ]
    katalog = _funktions_katalog_text_fuer_ki()
    prompt = f"""Du pruefst extrahierte Fuehrungskraefte aus einem deutschen Impressum VOR dem CRM-Import.

FIRMA: {firmenname or "unbekannt"}

CRM-FUNKTIONSKATALOG (NUR diese funktionid + passende funktionsbezeichnung verwenden).
Bekannte Berufsbezeichnungen aus crm_funktion_synonyme sind den jeweiligen funktionid zugeordnet:
{katalog}

ANREDE-REGELN:
- Nur "Herr", "Frau" oder "" (leer)
- Aus Impressum (Herr/Frau vor Name), aus Rolle (z.B. Geschäftsführerin -> Frau) oder Kontext ableiten

IMPRESSUM-AUSZUG:
{(impressum_text or "")[:4500]}

KANDIDATEN:
{json.dumps(kandidaten, ensure_ascii=False)}

AUFGABE:
- Nur echte Personen behalten; Rechtstexte ablehnen (§, MStV, "Verantwortlich im Sinn von" ohne Person)
- Vorname, Nachname, Titel korrigieren
- funktionid und funktionsbezeichnung dem KATALOG entnehmen (exakte ID, passende Bezeichnung)
- anrede setzen

Antworte NUR als JSON:
{{"personen":[{{"index":0,"gueltig":true,"anrede":"Herr","titel":"Dr.","vorname":"Max","nachname":"Mustermann","funktionid":"12","funktionsbezeichnung":"Geschäftsführer"}}],"abgelehnt_gruende":[]}}"""

    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        roh = (response.choices[0].message.content or "").strip()
        daten = json.loads(roh)
    except Exception as exc:
        return PersonenPruefErgebnis(
            personen=personen,
            hinweise=[f"KI-Plausibilitaet uebersprungen: {exc}"],
        )

    gueltig: list[dict[str, str]] = []
    abgelehnt = 0
    hinweise = [str(g) for g in daten.get("abgelehnt_gruende") or [] if g]

    index_map = {i: p for i, p in enumerate(personen)}
    for eintrag in daten.get("personen") or []:
        if not eintrag.get("gueltig"):
            abgelehnt += 1
            continue
        idx = eintrag.get("index")
        basis = index_map.get(idx)
        if basis is None:
            continue
        vor = str(eintrag.get("vorname") or basis.get("vorname", "")).strip()
        nach = str(eintrag.get("nachname") or basis.get("nachname", "")).strip()
        if _ist_offensichtlich_kein_personenname(vor, nach):
            abgelehnt += 1
            continue
        kontext = str(basis.get("quelle_kontext", "") or "")
        anrede = _normalisiere_anrede(
            str(eintrag.get("anrede") or basis.get("anrede", "")),
            kontext=f"{kontext} {eintrag.get('funktionsbezeichnung', '')}",
        )
        fid, fbez = _funktion_aus_katalog(
            str(eintrag.get("funktionid") or basis.get("funktionid", "")),
            str(
                eintrag.get("funktionsbezeichnung")
                or eintrag.get("funktion")
                or basis.get("funktionsbezeichnung", "")
            ),
            fallback_rolle=basis.get("funktionsbezeichnung", ""),
        )
        gueltig.append(
            {
                **basis,
                "anrede": anrede,
                "titel": str(eintrag.get("titel") or basis.get("titel", "")).strip(),
                "vorname": vor,
                "nachname": nach,
                "funktionid": fid,
                "funktionsbezeichnung": fbez,
            }
        )

    if not gueltig and personen:
        return PersonenPruefErgebnis(personen=personen, hinweise=hinweise or ["KI lehnte alle ab"])

    return PersonenPruefErgebnis(
        personen=gueltig or personen,
        abgelehnt=abgelehnt,
        ki_verwendet=True,
        hinweise=hinweise,
    )


def bereinige_und_pruefe_personen(
    personen: list[dict[str, str]],
    impressum_text: str = "",
    firmenname: str = "",
    *,
    ki_pruefen: bool | None = None,
) -> PersonenPruefErgebnis:
    """Regeln + optional KI vor CRM-Sync."""
    if not personen:
        return PersonenPruefErgebnis()

    gefiltert, abg_regeln = filtere_personen_regeln(personen)
    if ki_pruefen is None:
        ki_pruefen = PERSONEN_KI_PLAUSIBILITAET

    if not gefiltert:
        return PersonenPruefErgebnis(abgelehnt=abg_regeln, hinweise=["Alle Kandidaten per Regel abgelehnt"])

    if not ki_pruefen:
        angereichert = [_person_felder_normalisieren(p) for p in gefiltert]
        return PersonenPruefErgebnis(personen=angereichert, abgelehnt=abg_regeln)

    ki = _pruefe_personen_ki(gefiltert, impressum_text, firmenname)
    return PersonenPruefErgebnis(
        personen=ki.personen,
        abgelehnt=abg_regeln + ki.abgelehnt,
        ki_verwendet=ki.ki_verwendet,
        hinweise=ki.hinweise,
    )


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


def _ist_namenszeile(zeile: str) -> bool:
    s = (zeile or "").strip()
    if len(s) < 4 or len(s) > 90:
        return False
    if "@" in s or re.search(r"https?://", s, re.I):
        return False
    if re.search(
        r"(straße|strasse|telefon|tel\.|fax|ust|hrb|amtsgericht|register|"
        r"handelsregister|datenschutz|impressum|cookie|umsatzsteuer)",
        s,
        re.I,
    ):
        return False
    return bool(re.search(r"[A-ZÄÖÜ]", s)) and bool(re.search(r"[a-zäöüß]", s))


def _person_hinzufuegen(
    personen: list[dict[str, str]],
    gesehen: set[tuple[str, str]],
    rolle: str,
    name_roh: str,
    kontext: str,
) -> None:
    funktionid, funktion = _funktion_ref(rolle)
    for name in _split_namensliste(name_roh):
        anrede, titel, vorname, nachname = _name_zu_felder(name)
        if not nachname or _ist_offensichtlich_kein_personenname(vorname, nachname):
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
                "quelle_kontext": kontext[:250],
            }
        )


def extrahiere_fuehrung_personen(text: str) -> list[dict[str, str]]:
    """Impressum: GF/Vorstand aus typischen Zeilen- und Blockformaten."""
    personen: list[dict[str, str]] = []
    gesehen: set[tuple[str, str]] = set()
    zeilen = (text or "").splitlines()

    for m in LISTEN_FUEHRUNG_RE.finditer(text or ""):
        _person_hinzufuegen(personen, gesehen, m.group(1), m.group(2), m.group(0))

    for m in INLINE_FUEHRUNG_RE.finditer(text or ""):
        name = (m.group(2) or "").strip()
        if name and _ist_namenszeile(name):
            _person_hinzufuegen(personen, gesehen, m.group(1), name, m.group(0))

    for i, zeile in enumerate(zeilen):
        m = ROLLEN_NUR_ZEILE_RE.match(zeile.strip())
        if not m:
            continue
        rolle = m.group(1)
        namen_teile: list[str] = []
        for folge in zeilen[i + 1 : i + 8]:
            s = folge.strip()
            if not s:
                if namen_teile:
                    break
                continue
            if ROLLEN_NUR_ZEILE_RE.match(s) or LISTEN_FUEHRUNG_RE.match(s):
                break
            if _ist_namenszeile(s):
                namen_teile.append(s)
            elif namen_teile:
                break
        if namen_teile:
            _person_hinzufuegen(
                personen,
                gesehen,
                rolle,
                ", ".join(namen_teile),
                f"{zeile.strip()} -> {' | '.join(namen_teile)}",
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
    update_status_basis: str = "DigiWiki-LiveWeb",
    validation_status: str = "auto_web",
) -> PersonenSyncErgebnis:
    if not personen:
        return PersonenSyncErgebnis(ok=True)
    if not kundennumm or not Path(ACCESS_DB_PATH).exists():
        return PersonenSyncErgebnis(ok=False, fehler="CRM-Datenbank nicht erreichbar.")

    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    ergebnis = PersonenSyncErgebnis()
    heute = datetime.now().strftime("%Y-%m-%d")
    if update_status_basis == "KI-Datenpflege":
        quelle = "KI-Datenpflege"
    else:
        quelle = f"{update_status_basis} {quelle_url}".strip()[:120]

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
                                    validation_status,
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
                            validation_status,
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
