"""Laedt Tabellen-Rollen und JOIN-Graph fuer NL2SQL (db_tabellen.csv, db_joins.csv)."""

from __future__ import annotations

import csv
from pathlib import Path

from config import BASE_DIR, DICTIONARY_PATH

TABELLEN_PATH = BASE_DIR / "db_tabellen.csv"
JOINS_PATH = BASE_DIR / "db_joins.csv"

__all__ = [
    "TABELLEN_PATH",
    "JOINS_PATH",
    "lade_tabellen_meta",
    "lade_joins",
    "baue_tabellen_leitfaden",
    "baue_joins_leitfaden",
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
        "Personen ueber kundennumm, Artikel ueber anbieternummer/anbieter_nr verbinden."
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
        "- Person + Firma: crm_personen JOIN stammdatenindustrie ON kundennumm\n"
        "- Person + Hierarchie: + ref_funktionen ON funktionid\n"
        "- Produkt + Hersteller: abdaartikel JOIN stammdatenindustrie ON anbieter_nr = anbieternummer\n"
        "- Firma + Trigger: crm_firmen_trigger_historie JOIN stammdatenindustrie ON kundennumm\n"
        "- Whitelist: JOIN stammdatenindustrie / stammdatenapo / crm_personen\n"
        "- Access: kundennumm/personid Typen ggf. mit CStr() angleichen"
    )
    return "\n".join(zeilen)


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
        + baue_joins_leitfaden()
    )
