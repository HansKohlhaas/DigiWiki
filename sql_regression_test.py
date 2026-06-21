#!/usr/bin/env python3
"""SQL-Regression: typische Firmenfragen gegen NL2SQL + Access.

Interner Test vor Phase A (Kaskade). Schreibt sql_regression_ergebnis.md.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyodbc
from dotenv import load_dotenv
from openai import OpenAI

from config import ACCESS_DB_PATH, DICTIONARY_PATH, SCHEMA_PATH, SQL_DEFAULT_TOP
from sql_db_meta import baue_db_meta_leitfaden
from sql_frage_katalog import (
    baue_klassifikator_leitfaden,
    baue_semantik_leitfaden,
    baue_sql_feld_leitfaden,
    ist_offensichtliche_wiki_frage,
)

ROOT = Path(__file__).resolve().parent
ERGEBNIS_MD = ROOT / "Projektdokumente" / "_intern" / "sql_regression_ergebnis.md"

load_dotenv(ROOT / ".env")


@dataclass
class TestFall:
    nr: str
    frage: str
    erwartet_typ: str
    sql_muss_enthalten: list[str] = field(default_factory=list)
    min_zeilen: int = 0
    hinweis: str = ""


TESTFAELLE = [
    TestFall("1", "Was ist das Narrativ von Hexal?", "datenbank", ["stammdatenindustrie", "narrativ"], 1),
    TestFall("2", "Marktzielgruppe von Hexal", "datenbank", ["stammdatenindustrie", "marktzielgruppe"], 1),
    TestFall("3", "Top-Produkte von Hexal", "datenbank", ["stammdatenindustrie", "topprodu"], 1),
    TestFall(
        "3b",
        "Welche Produkte hat Hexal?",
        "datenbank",
        ["abdaartikel", "anbieter_nr"],
        1,
        "ArtikelDB via anbieternummer, nicht nur topprodukte",
    ),
    TestFall(
        "4",
        "Wer ist Geschäftsführer bei Hexal?",
        "datenbank",
        ["crm_personen", "ref_funktionen"],
        0,
        "0 Zeilen ok wenn GF nicht gepflegt — SQL-Struktur zählt",
    ),
    TestFall(
        "5",
        "Firmen in Akquiseklasse 3 mit Apotheken-Fokus",
        "datenbank",
        ["stammdatenindustrie", "akquiseklasse"],
        0,
        "Filter Marktzielgruppe LIKE Apothek erwartet",
    ),
    TestFall("6", "D2P-Score und Begründung von Hexal", "datenbank", ["stammdatenindustrie", "d2p"], 1),
    TestFall(
        "7",
        "Wie viele ABDA-Artikel hat Hexal?",
        "datenbank",
        ["abdaartikel"],
        1,
        "JOIN anbieternummer/anbieter_nr",
    ),
    TestFall(
        "8",
        "Adresse und Website von Sanofi-Aventis Deutschland",
        "datenbank",
        ["stammdatenindustrie"],
        1,
    ),
    TestFall("9", "Wer stellt Hustensaft her?", "datenbank", ["abdaartikel"], 1),
    TestFall("10", "Welche Ansprechpartner hat Hexal mit Telefon?", "datenbank", ["crm_personen"], 0),
    TestFall("W1", "Wie läuft unser Bestellablauf ab?", "wissen", []),
    TestFall("W2", "Brandvoice Hans zu Emotionalität", "wissen", []),
]


def _eindeutige_spaltennamen(namen):
    gesehen: dict[str, int] = {}
    ergebnis = []
    for name in namen:
        basis = name or "spalte"
        if basis in gesehen:
            gesehen[basis] += 1
            ergebnis.append(f"{basis}_{gesehen[basis]}")
        else:
            gesehen[basis] = 0
            ergebnis.append(basis)
    return ergebnis


def fuehre_sql_aus(sql_query: str):
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    try:
        conn = pyodbc.connect(conn_str, timeout=15)
        try:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            if cursor.description is None:
                return pd.DataFrame(), None
            spalten = _eindeutige_spaltennamen([d[0] for d in cursor.description])
            zeilen = [tuple(row) for row in cursor.fetchall()]
            return pd.DataFrame.from_records(zeilen, columns=spalten), None
        finally:
            conn.close()
    except Exception as e:
        return None, str(e)


def klassifiziere_chat_frage(frage: str) -> str:
    if ist_offensichtliche_wiki_frage(frage):
        return "wissen"
    client = OpenAI()
    prompt = f"""
    Ordne die Nutzerfrage einem Antwortweg zu: 'datenbank' (SQL) oder 'wissen' (Wiki-Dokumente).

    {baue_klassifikator_leitfaden()}

    Antworte AUSSCHLIESSLICH als JSON: {{"typ": "datenbank" | "wissen", "begruendung": "kurz"}}
    Im Zweifel: "datenbank".

    Frage: "{frage}"
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        typ = json.loads(response.choices[0].message.content).get("typ", "datenbank")
        return typ if typ in ("datenbank", "wissen") else "datenbank"
    except Exception:
        return "datenbank"


def uebersetze_frage_in_sql(nutzer_frage: str, schema_text: str, dictionary_csv: str) -> str:
    client = OpenAI()
    system_prompt = f"""
    Du bist ein SQL-Experte für Microsoft Access (Zugriff via pyodbc).
    Übersetze die Frage des Nutzers in eine syntaktisch korrekte Access-SQL-Abfrage.

    === DATENBANK-SCHEMA ===
    {schema_text}

    === DATA DICTIONARY ===
    {dictionary_csv}

    {baue_db_meta_leitfaden()}

    {baue_sql_feld_leitfaden()}

    {baue_semantik_leitfaden()}

    === STRIKTE REGELN ===
    1. Antworte AUSSCHLIESSLICH mit dem SQL-Code in EINER Zeile.
    2. Schritt 1: Tabellenrolle aus db_tabellen waehlen. Schritt 2: JOINs aus db_joins.
    3. Nutze fuer Textsuchen IMMER LIKE mit '%'.
    4. JOINs nur aus db_joins.csv; bei Typ-Unterschied kundennumm/personid CStr() nutzen.
    5. Apotheken-Fokus -> Marktzielgruppe/emarktzielgruppe LIKE '%Apothek%', NICHT apotheken_fokus.
    6. Access: SELECT TOP {SQL_DEFAULT_TOP} bei Listen.
    7. TOP-PRODUKTE / Sortiment: NUR stammdatenindustrie.topprodukte – KEIN JOIN abdaartikel.
    8. Welche Produkte/Artikel einer Firma: abdaartikel JOIN anbieter_nr = anbieternummer.
    9. Entferne Markdown.
    10. FIRMA SUCHEN: nama & nameb verketten (IIf…), nicht nur nama LIKE.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": nutzer_frage},
        ],
        temperature=0.2,
    )
    sql_raw = response.choices[0].message.content.strip()
    return sql_raw.replace("```sql", "").replace("```", "").replace("\n", " ").strip()


def _sql_ok(sql: str, muster: list[str]) -> tuple[bool, list[str]]:
    fehlend = []
    norm = (sql or "").lower()
    for m in muster:
        if m.lower() not in norm:
            fehlend.append(m)
    return len(fehlend) == 0, fehlend


def _df_kurz(df: pd.DataFrame, max_rows: int = 3) -> str:
    if df is None or df.empty:
        return "*(keine Zeilen)*"
    auszug = df.head(max_rows)
    return auszug.to_string(index=False, max_colwidth=40)


def main() -> int:
    if not Path(ACCESS_DB_PATH).exists():
        print(f"[FEHLER] Datenbank nicht gefunden: {ACCESS_DB_PATH}")
        return 1

    schema_text = SCHEMA_PATH.read_text(encoding="utf-8", errors="replace")
    dictionary_csv = DICTIONARY_PATH.read_text(encoding="utf-8", errors="replace")

    zeilen_md = [
        "# SQL-Regression – Ergebnis",
        "",
        f"**Stand:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**DB:** `{ACCESS_DB_PATH}`",
        "",
        "| # | Frage | Klassifikation | SQL ok | Zeilen | Status |",
        "|---|-------|----------------|--------|--------|--------|",
    ]

    ok_count = 0
    total = len(TESTFAELLE)

    for tf in TESTFAELLE:
        print(f"\n=== #{tf.nr}: {tf.frage}")
        typ = klassifiziere_chat_frage(tf.frage)
        typ_ok = typ == tf.erwartet_typ
        print(f"  Klassifikation: {typ} {'OK' if typ_ok else 'FEHLER (erwartet ' + tf.erwartet_typ + ')'}")

        sql = ""
        sql_struktur_ok = True
        fehlend: list[str] = []
        zeilen = "-"
        sql_fehler = None
        status = "OK"

        if tf.erwartet_typ == "datenbank":
            sql = uebersetze_frage_in_sql(tf.frage, schema_text, dictionary_csv)
            print(f"  SQL: {sql[:120]}...")
            sql_struktur_ok, fehlend = _sql_ok(sql, tf.sql_muss_enthalten)
            if not sql_struktur_ok:
                print(f"  SQL-Struktur fehlt: {fehlend}")
            df, sql_fehler = fuehre_sql_aus(sql)
            if sql_fehler:
                print(f"  DB-Fehler: {sql_fehler}")
                status = "DB-FEHLER"
            elif df is not None:
                zeilen = str(len(df))
                print(f"  Zeilen: {zeilen}")
                if len(df) < tf.min_zeilen:
                    status = "LEER"
            else:
                status = "DB-FEHLER"
        else:
            if typ_ok:
                status = "OK"
            else:
                status = "KLASSIFIZIERUNG"

        if tf.erwartet_typ == "datenbank":
            gesamt_ok = typ_ok and sql_struktur_ok and sql_fehler is None and (
                status != "LEER" or tf.min_zeilen == 0
            )
        else:
            gesamt_ok = typ_ok

        if gesamt_ok:
            ok_count += 1
        elif status == "OK" and not gesamt_ok:
            status = "TEILWEISE"

        kurz_status = "✅" if gesamt_ok else "❌"
        zeilen_md.append(
            f"| {tf.nr} | {tf.frage[:45]} | {typ}{'✓' if typ_ok else '✗'} | "
            f"{'✓' if sql_struktur_ok or tf.erwartet_typ != 'datenbank' else '✗'} | {zeilen} | {kurz_status} {status} |"
        )

        zeilen_md.extend([
            "",
            f"### #{tf.nr} {tf.frage}",
            "",
            f"- **Erwartet:** `{tf.erwartet_typ}` | **Ist:** `{typ}`",
        ])
        if tf.hinweis:
            zeilen_md.append(f"- *Hinweis:* {tf.hinweis}")
        if sql:
            zeilen_md.append(f"- **SQL:** `{sql}`")
            if fehlend:
                zeilen_md.append(f"- **Fehlend in SQL:** {', '.join(fehlend)}")
            if sql_fehler:
                zeilen_md.append(f"- **DB-Fehler:** {sql_fehler}")
            elif df is not None:
                zeilen_md.append(f"- **Ergebnis ({len(df)} Zeilen):**")
                zeilen_md.append("```")
                zeilen_md.append(_df_kurz(df))
                zeilen_md.append("```")
        zeilen_md.append("")

    zeilen_md.insert(4, f"**Ergebnis:** {ok_count}/{total} bestanden")
    zeilen_md.insert(5, "")

    ERGEBNIS_MD.parent.mkdir(parents=True, exist_ok=True)
    ERGEBNIS_MD.write_text("\n".join(zeilen_md), encoding="utf-8")

    print(f"\n{'=' * 50}")
    print(f"Ergebnis: {ok_count}/{total} bestanden")
    print(f"Report: {ERGEBNIS_MD}")
    return 0 if ok_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
