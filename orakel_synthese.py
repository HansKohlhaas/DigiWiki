"""Stufe 4: KI-Synthese aus SQL + Stammfelder (+ optional Web/MD).

Kombiniert z. B. ABDA-Artikelliste und Top-Produkte-Freitext zu einem Briefing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import pyodbc

from config import ACCESS_DB_PATH, ORAKEL_SYNTHESE_ENABLED, SQL_DEFAULT_TOP
from sql_frage_katalog import (
    baue_sql_abda_artikel_kundennumm,
    firma_suche_like,
    ist_artikelkatalog_frage,
    ist_topprodukte_frage,
)

SYNTHESE_MAX_DF_ZEILEN = 35
SYNTHESE_ARTIKEL_STICHPROBE = 30

BRIEFING_SIGNALE = (
    "briefing",
    "überblick",
    "ueberblick",
    "zusammenfassung",
    "narrativ",
    "purpose",
    "strategie",
    "einordnung",
)

STAMM_FELDER = (
    "kundennumm",
    "nama",
    "nameb",
    "anbieternummer",
    "topprodukte",
    "top_produkte",
    "gl_produkt1",
    "gl_produkt2",
    "gl_produkt3",
    "sortiment",
    "produktschwerpunkt",
    "hauptgruppe",
    "Kategorie",
    "Marktzielgruppe",
    "emarktzielgruppe",
    "narrativ",
    "purpose",
    "zielsetzung",
    "ambition",
)


@dataclass
class SyntheseErgebnis:
    ok: bool
    text: str = ""
    quellen: list[str] = field(default_factory=list)
    fehler: str = ""


def synthese_aktiv() -> bool:
    return ORAKEL_SYNTHESE_ENABLED


def _df_kompakt(df: pd.DataFrame | None, max_zeilen: int = SYNTHESE_MAX_DF_ZEILEN) -> str:
    if df is None or df.empty:
        return ""
    auszug = df.head(max_zeilen)
    try:
        md = auszug.to_markdown(index=False)
    except Exception:
        md = auszug.to_string(index=False)
    if len(df) > max_zeilen:
        md += f"\n(… {len(df) - max_zeilen} weitere Zeilen)"
    return md


def _kn_aus_df(df: pd.DataFrame) -> str:
    for col in df.columns:
        if str(col).lower() == "kundennumm":
            val = df[col].iloc[0]
            if pd.notna(val):
                return str(val).strip().replace(".0", "")
    return ""


def _spalten_lower(df: pd.DataFrame) -> set[str]:
    return {str(c).lower() for c in df.columns}


def ist_firmen_briefing_frage(frage: str) -> bool:
    text = (frage or "").lower()
    return any(s in text for s in BRIEFING_SIGNALE)


def soll_synthese_anwenden(frage: str, sql_df: pd.DataFrame) -> bool:
    if not synthese_aktiv() or sql_df is None or sql_df.empty:
        return False
    if ist_artikelkatalog_frage(frage) or ist_topprodukte_frage(frage):
        return True
    if ist_firmen_briefing_frage(frage):
        return True
    cols = _spalten_lower(sql_df)
    if "artikelname" in cols or "topprodukte" in cols or "narrativ" in cols:
        return True
    return False


def lade_firmen_stamm(kundennumm: str = "", firmen_such: str = "") -> dict[str, Any]:
    if not Path(ACCESS_DB_PATH).exists():
        return {}
    kn = (kundennumm or "").strip()
    felder = ", ".join(STAMM_FELDER)
    if kn:
        sql = f"SELECT TOP 1 {felder} FROM stammdatenindustrie WHERE kundennumm = ?"
        params: tuple[Any, ...] = (kn,)
    elif firmen_such:
        sql = (
            f"SELECT TOP 1 {felder} FROM stammdatenindustrie "
            f"WHERE {firma_suche_like(firmen_such)} ORDER BY nama"
        )
        params = ()
    else:
        return {}
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            row = cur.fetchone()
            if not row:
                return {}
            cols = [d[0] for d in cur.description]
            daten = dict(zip(cols, row))
            nama = str(daten.get("nama") or "").strip()
            nameb = str(daten.get("nameb") or "").strip()
            daten["firmenname"] = nameb or nama or firmen_such
            if daten.get("kundennumm") is not None:
                daten["kundennumm"] = str(daten["kundennumm"]).strip().replace(".0", "")
            return daten
        finally:
            conn.close()
    except Exception:
        return {}


def lade_artikel_stichprobe(kundennumm: str, limit: int = SYNTHESE_ARTIKEL_STICHPROBE) -> pd.DataFrame:
    kn = (kundennumm or "").strip()
    if not kn:
        return pd.DataFrame()
    sql = baue_sql_abda_artikel_kundennumm(kn, top=limit)
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    try:
        conn = pyodbc.connect(conn_str, timeout=15)
        try:
            return pd.read_sql(sql, conn)
        finally:
            conn.close()
    except Exception:
        return pd.DataFrame()


def _format_stamm_block(stamm: dict[str, Any]) -> str:
    if not stamm:
        return ""
    zeilen = [f"Firma: {stamm.get('firmenname', '')} (kundennumm {stamm.get('kundennumm', '')})"]
    for key in STAMM_FELDER:
        if key in ("kundennumm", "nama", "nameb"):
            continue
        val = stamm.get(key)
        if val is not None and str(val).strip():
            zeilen.append(f"{key}: {str(val).strip()[:800]}")
    return "\n".join(zeilen)


def bereite_synthese_quellen(
    frage: str,
    sql_df: pd.DataFrame | None,
    kundennumm: str = "",
    firmen_such: str = "",
    web_text: str = "",
    md_text: str = "",
) -> tuple[dict[str, str], list[str]]:
    """Kontextbloecke und Quellenlabels fuer die KI-Synthese."""
    if sql_df is None:
        sql_df = pd.DataFrame()
    cols = _spalten_lower(sql_df) if not sql_df.empty else set()
    kn = (kundennumm or _kn_aus_df(sql_df) or "").strip()
    stamm = lade_firmen_stamm(kundennumm=kn, firmen_such=firmen_such if not kn else "")
    kn = kn or str(stamm.get("kundennumm") or "").strip()
    quellen: list[str] = []
    bloecke: dict[str, str] = {
        "firma": stamm.get("firmenname") or firmen_such or "Unbekannt",
        "kundennumm": kn,
    }

    if "artikelname" in cols:
        quellen.append("SQL ArtikelDB")
        bloecke["artikel_db"] = _df_kompakt(sql_df)
        bloecke["stamm_sortiment"] = _format_stamm_block(stamm)
        if stamm.get("topprodukte") or stamm.get("sortiment"):
            quellen.append("Stamm Top-Produkte")
    elif cols and any(
        c in cols for c in ("topprodukte", "top_produkte", "gl_produkt1", "narrativ", "purpose")
    ):
        quellen.append("SQL Stamm")
        bloecke["stamm_sql"] = _df_kompakt(sql_df)
        if kn:
            artikel_df = lade_artikel_stichprobe(kn)
            if not artikel_df.empty:
                bloecke["artikel_db"] = _df_kompakt(artikel_df)
                quellen.append("ArtikelDB")
    elif not sql_df.empty:
        quellen.append("SQL")
        bloecke["sql_ergebnis"] = _df_kompakt(sql_df)
        if stamm:
            bloecke["stamm_zusatz"] = _format_stamm_block(stamm)
    elif stamm:
        bloecke["stamm_sortiment"] = _format_stamm_block(stamm)
        quellen.append("SQL Stamm")
        if kn and (ist_artikelkatalog_frage(frage) or ist_topprodukte_frage(frage)):
            artikel_df = lade_artikel_stichprobe(kn)
            if not artikel_df.empty:
                bloecke["artikel_db"] = _df_kompakt(artikel_df)
                quellen.append("ArtikelDB")

    if web_text.strip():
        bloecke["live_web"] = web_text.strip()[:12000]
        quellen.append("Live-Web")
    if md_text.strip():
        bloecke["md_archiv"] = md_text.strip()[:12000]
        quellen.append("MD-Archiv")

    return bloecke, quellen


def erzeuge_firmen_synthese(
    frage: str,
    sql_df: pd.DataFrame | None = None,
    kundennumm: str = "",
    firmen_such: str = "",
    web_text: str = "",
    md_text: str = "",
) -> SyntheseErgebnis:
    if not synthese_aktiv():
        return SyntheseErgebnis(ok=False, fehler="Synthese deaktiviert.")
    if sql_df is None:
        sql_df = pd.DataFrame()
    if sql_df.empty and not web_text.strip() and not md_text.strip():
        return SyntheseErgebnis(ok=False, fehler="Keine Quellen fuer Synthese.")

    bloecke, quellen = bereite_synthese_quellen(
        frage,
        sql_df,
        kundennumm=kundennumm,
        firmen_such=firmen_such,
        web_text=web_text,
        md_text=md_text,
    )
    if not quellen:
        return SyntheseErgebnis(ok=False, fehler="Keine verwertbaren Quellen.")

    kontext_text = "\n\n".join(
        f"=== {key.upper()} ===\n{val}" for key, val in bloecke.items() if val and key not in ("firma", "kundennumm")
    )

    prompt = f"""Du erstellst ein kompaktes Firmen-Briefing auf Deutsch fuer den Geschaeftsfuehrer von DigiBest (C-Level, praezise, ohne Floskeln).

REGELN:
1. Nutze AUSSCHLIESSLICH die bereitgestellten Quellen — nichts erfinden.
2. Wenn ArtikelDB-Daten vorliegen: wichtigste Produktgruppen/Wirkstoffe strukturiert darstellen (nicht jede Zeile aufzaehlen).
3. Wenn Top-Produkte/Sortiment-Freitext vorliegt: mit Artikelliste abgleichen und einordnen.
4. Fehlende Infos klar benennen, nicht fuellen.
5. Struktur: **Kurzueberblick** (2–3 Saetze), **Sortiment & Produkte**, optional **Markt/Strategie** — nur wenn Daten da sind.
6. Am Ende eine Zeile: *Quellen: …* mit {', '.join(quellen)}

FIRMA: {bloecke.get('firma')} (#{bloecke.get('kundennumm')})

NUTZERFRAGE: {frage}

QUELLEN:
{kontext_text}
"""

    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            return SyntheseErgebnis(ok=False, fehler="Leere KI-Antwort.")
        return SyntheseErgebnis(ok=True, text=text, quellen=quellen)
    except Exception as exc:
        return SyntheseErgebnis(ok=False, fehler=str(exc))
