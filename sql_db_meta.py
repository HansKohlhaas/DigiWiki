"""Laedt Tabellen-Rollen und JOIN-Graph fuer NL2SQL (db_tabellen.csv, db_joins.csv)."""

from __future__ import annotations

import csv
from pathlib import Path

from config import BASE_DIR, DICTIONARY_PATH

TABELLEN_PATH = BASE_DIR / "db_tabellen.csv"
JOINS_PATH = BASE_DIR / "db_joins.csv"
SPALTEN_PATH = BASE_DIR / "db_spalten.csv"

__all__ = [
    "TABELLEN_PATH",
    "JOINS_PATH",
    "SPALTEN_PATH",
    "lade_tabellen_meta",
    "lade_joins",
    "lade_spalten_meta",
    "baue_tabellen_leitfaden",
    "baue_joins_leitfaden",
    "baue_spalten_leitfaden",
    "baue_access_join_regeln",
    "baue_db_meta_leitfaden",
]


def _lese_csv(pfad: Path) -> list[dict[str, str]]:
    if not pfad.exists():
        return []
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            with open(pfad, newline="", encoding=enc) as f:
                return list(csv.DictReader(f, delimiter=";"))
        except UnicodeDecodeError:
            continue
    return []


def lade_tabellen_meta() -> list[dict[str, str]]:
    return _lese_csv(TABELLEN_PATH)


def lade_joins() -> list[dict[str, str]]:
    return _lese_csv(JOINS_PATH)


def lade_spalten_meta(tabelle: str | None = None) -> list[dict[str, str]]:
    rows = _lese_csv(SPALTEN_PATH)
    if tabelle:
        return [r for r in rows if r.get("Tabelle") == tabelle]
    return rows


def baue_tabellen_leitfaden() -> str:
    zeilen = ["=== TABELLEN-ROLLEN (db_tabellen.csv) ==="]
    for t in lade_tabellen_meta():
        hub = " [HUB]" if (t.get("Ist_Hub") or "").lower() == "ja" else ""
        zeilen.append(
            f"- {t.get('Tabelle', '')}{hub}: {t.get('Beschreibung', '')}\n"
            f"  PK: {t.get('Primaerschluessel', '')} | Fragen: {t.get('Typische_Fragentypen', '')}"
        )
    zeilen.append(
        "\nHUB-Regel: stammdatenindustrie ist Zentrum fuer Firmen/Markt. "
        "Alle Spalten: db_spalten.csv. Personen ueber kundennumm, "
        "Artikel ueber anbieternummer/anbieter_nr verbinden."
    )
    return "\n".join(zeilen)


def baue_joins_leitfaden() -> str:
    zeilen = ["=== JOIN-GRAPH (db_joins.csv) ==="]
    for j in lade_joins():
        zeilen.append(
            f"- {j.get('Von_Tabelle', '')}.{j.get('Von_Spalte', '')} "
            f"-> {j.get('Nach_Tabelle', '')}.{j.get('Nach_Spalte', '')} "
            f"({j.get('Kardinalitaet', '')}): {j.get('Beschreibung', '')}\n"
            f"  SQL: {j.get('SQL_JOIN', '')}"
        )
    zeilen.append(
        "\nPfad-Hinweise:\n"
        "- Person + Firma + Hierarchie (GF): siehe baue_access_join_regeln – Klammern Pflicht\n"
        "- Person + Firma: crm_personen JOIN stammdatenindustrie ON kundennumm\n"
        "- Person + Hierarchie: ref_funktionen per funktionid (LEFT JOIN nach Klammer-Regel)\n"
        "  GF/Vorstand: rf.ebene IN ('1','2') ODER rf.funktionsbezeichnung LIKE '%Geschaeftsf%'\n"
        "  NICHT stammdatenindustrie.funktion – das ist die Marktrolle der Firma, nicht die Personenposition\n"
        "- Produkt + Hersteller: abdaartikel JOIN stammdatenindustrie ON anbieter_nr = anbieternummer\n"
        "- Firma + Trigger: crm_firmen_trigger_historie JOIN stammdatenindustrie ON kundennumm\n"
        "- Whitelist: JOIN stammdatenindustrie / stammdatenapo / crm_personen\n"
        "- Access: kundennumm/personid Typen ggf. mit CStr() angleichen"
    )
    return "\n".join(zeilen)


def baue_spalten_leitfaden(tabelle: str = "stammdatenindustrie") -> str:
    spalten = lade_spalten_meta(tabelle)
    if not spalten:
        return ""
    zeilen = [f"=== SPALTEN-LEITFADEN: {tabelle} (db_spalten.csv) ==="]
    kategorien: dict[str, list[dict[str, str]]] = {}
    for s in spalten:
        kat = s.get("Info_Kategorie") or "Sonstiges"
        kategorien.setdefault(kat, []).append(s)
    for kat in sorted(kategorien):
        zeilen.append(f"\n--- {kat} ---")
        for s in kategorien[kat]:
            tag = s.get("Such_Tag") or ""
            zeilen.append(
                f"- {s.get('Spalte', '')} ({s.get('Datentyp', '')}, {s.get('Info_Typ', '')}) "
                f"{tag}: {s.get('Beschreibung', '')}"
            )
            if s.get("Join_FK"):
                zeilen.append(f"  FK: {s['Join_FK']}")
            if s.get("NL_Hinweis"):
                zeilen.append(f"  SQL: {s['NL_Hinweis']}")
    zeilen.append(
        "\nLegende Such_Tag: [PK]=Schluessel [FK]=Fremdschluessel [SUCH]=Textsuche "
        "[FILTER]=exakter/kategorischer Filter [LEER]=nicht filtern [AUSGABE]=nur anzeigen "
        "[INTERN]=Workflow/Metadaten"
    )
    return "\n".join(zeilen)


def baue_access_join_regeln() -> str:
    """Microsoft Access verlangt Klammern bei gemischten JOIN-Typen."""
    return """
=== ACCESS JOIN-SYNTAX (PFLICHT bei 2+ JOINs oder INNER+LEFT gemischt) ===
Access akzeptiert NICHT: ... INNER JOIN ... ON ... LEFT JOIN ... ohne Klammern davor.

Muster Person + Firma + Hierarchie (GF-Fragen):
FROM (crm_personen AS p INNER JOIN stammdatenindustrie AS s ON p.kundennumm = s.kundennumm) LEFT JOIN ref_funktionen AS rf ON p.funktionid = rf.funktionid

Muster Person + Firma + Whitelist (nur LEFT JOINs):
FROM ((crm_personen AS p LEFT JOIN stammdatenindustrie AS s ON p.kundennumm = s.kundennumm) LEFT JOIN Whitelist_Kontakte AS w ON w.indpersonid = p.personid)

Muster Artikel + Hersteller (nur INNER JOIN – keine Extra-Klammer noetig):
FROM abdaartikel AS a INNER JOIN stammdatenindustrie AS s ON a.anbieter_nr = s.anbieternummer

Regel: INNER JOINs zuerst in Klammern gruppieren, danach LEFT JOINs aussen anfuegen.
Bei drei LEFT JOINs: doppelt verschachteln wie im Whitelist-Muster oben.
"""


def baue_db_meta_leitfaden() -> str:
    dict_hinweis = (
        f"Data Dictionary: {DICTIONARY_PATH.name} (Felder/Synonyme)\n"
        if DICTIONARY_PATH.exists()
        else ""
    )
    return (
        dict_hinweis
        + baue_tabellen_leitfaden()
        + "\n\n"
        + baue_spalten_leitfaden("stammdatenindustrie")
        + "\n\n"
        + baue_joins_leitfaden()
        + "\n\n"
        + baue_access_join_regeln()
    )
