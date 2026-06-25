"""KI-Datenbankpflege: Firmen ohne crm_personen per Live-Web anreichern."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd
import pyodbc

from config import ACCESS_DB_PATH
from firmen_live_recherche import (
    LIVE_WEB_PFLEGE_PAUSE_S,
    firmen_live_recherche,
    pruefe_url_fuer_live_web,
)
from firmen_live_personen import bereinige_und_pruefe_personen, extrahiere_fuehrung_personen

PFLEGE_QUELLE = "KI-Datenpflege"
PFLEGE_VALIDATION = "auto_ki"

LINKEDIN_FIRMA_RE = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/[\w\-%.]+/?",
    re.I,
)

SQL_KANDIDATEN = """
SELECT s.kundennumm, s.nama, s.nameb, s.ort, s.akquiseklasse, s.LinkedinURL,
       s.aktuelle_haupt_url, s.internetadresse, s.gl_web
FROM stammdatenindustrie AS s
LEFT JOIN crm_personen AS c ON s.kundennumm = c.kundennumm
WHERE s.akquiseklasse = ? AND c.kundennumm IS NULL
ORDER BY s.nama, s.nameb
"""


@dataclass
class PflegeErgebnis:
    ok: bool
    kundennumm: str = ""
    firmenname: str = ""
    ort: str = ""
    status: str = ""
    detail: str = ""
    personen_neu: int = 0
    personen_vorhanden: int = 0
    stamm_aktualisiert: bool = False
    url: str = ""
    fehler: str = ""


@dataclass
class PflegeLaufStatus:
    akquiseklasse: int = 1
    modus: str = "dauerbetrieb"
    intervall_minuten: int = 5
    aktiv: bool = False
    index: int = 0
    gesamt: int = 0
    ergebnisse: list[dict] = field(default_factory=list)
    letzte_aktion: str = ""


def firma_vollname(row: dict | pd.Series) -> str:
    nama = str(row.get("nama") or row.get("Nama") or "").strip()
    nameb = str(row.get("nameb") or row.get("Nameb") or "").strip()
    return " ".join(p for p in (nama, nameb) if p)


def firma_url_aus_row(row: dict | pd.Series) -> tuple[str, str]:
    letzter_fehler = ""
    for key in ("aktuelle_haupt_url", "internetadresse", "gl_web"):
        url, fehler = pruefe_url_fuer_live_web(str(row.get(key) or ""))
        if url:
            return url, ""
        if fehler and fehler != "URL fehlt":
            letzter_fehler = fehler
    if letzter_fehler:
        return "", letzter_fehler
    return "", "Keine Website-URL in Stammdaten"


def lade_pflege_kandidaten(akquiseklasse: int) -> pd.DataFrame:
    if not Path(ACCESS_DB_PATH).exists():
        return pd.DataFrame()
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    try:
        conn = pyodbc.connect(conn_str, timeout=12)
        try:
            return pd.read_sql(SQL_KANDIDATEN, conn, params=[int(akquiseklasse)])
        finally:
            conn.close()
    except Exception:
        return pd.DataFrame()


def extrahiere_linkedin_firma_url(text: str) -> str:
    m = LINKEDIN_FIRMA_RE.search(text or "")
    if not m:
        return ""
    url = m.group(0).rstrip("/")
    if not url.lower().startswith("http"):
        url = "https://" + url.lstrip("/")
    return url


def aktualisiere_stammdaten_aus_pflege(
    kundennumm: str,
    linkedin_url: str = "",
    web_url: str = "",
) -> bool:
    if not kundennumm or not Path(ACCESS_DB_PATH).exists():
        return False
    updates: list[str] = []
    params: list = []
    heute = datetime.now()
    if linkedin_url:
        updates.extend(
            [
                "LinkedinURL = ?",
                "linkedin_url_quelle = ?",
                "linkedin_url_geprueft_am = ?",
            ]
        )
        params.extend([linkedin_url[:255], PFLEGE_QUELLE, heute])
    if web_url:
        updates.append("aktuelle_haupt_url = ?")
        params.append(web_url[:255])
    if not updates:
        return False
    sql = f"UPDATE stammdatenindustrie SET {', '.join(updates)} WHERE kundennumm = ?"
    params.append(kundennumm)
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    try:
        conn = pyodbc.connect(conn_str, timeout=12)
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except Exception:
        return False


def pflege_eine_firma(
    row: dict | pd.Series,
    browser_session=None,
) -> PflegeErgebnis:
    kundennumm = str(row.get("kundennumm") or "").strip()
    firmenname = firma_vollname(row)
    ort = str(row.get("ort") or "").strip()
    url, url_fehler = firma_url_aus_row(row)
    linkedin_bestehend = str(row.get("LinkedinURL") or "").strip()

    if not kundennumm:
        return PflegeErgebnis(ok=False, status="uebersprungen", fehler="Keine kundennumm")
    if not firmenname:
        return PflegeErgebnis(
            ok=False,
            kundennumm=kundennumm,
            status="uebersprungen",
            fehler="Kein Firmenname",
        )
    if not url:
        return PflegeErgebnis(
            ok=False,
            kundennumm=kundennumm,
            firmenname=firmenname,
            ort=ort,
            status="uebersprungen",
            fehler=url_fehler or "Keine Website-URL in Stammdaten",
        )

    frage = f"Wer ist der Geschäftsführer von {firmenname}?"
    if browser_session is not None and LIVE_WEB_PFLEGE_PAUSE_S > 0:
        import time

        time.sleep(LIVE_WEB_PFLEGE_PAUSE_S)
    live = firmen_live_recherche(
        frage,
        kundennumm=kundennumm,
        firmenname=firmenname,
        url=url,
        md_speichern=False,
        force_pflege=True,
        sync_quelle=PFLEGE_QUELLE,
        sync_validation=PFLEGE_VALIDATION,
        browser_session=browser_session,
    )

    if not live.ok:
        return PflegeErgebnis(
            ok=False,
            kundennumm=kundennumm,
            firmenname=firmenname,
            ort=ort,
            url=url,
            status="fehler",
            fehler=live.fehler or "Live-Web fehlgeschlagen",
        )

    linkedin_neu = ""
    if not linkedin_bestehend and live.text:
        linkedin_neu = extrahiere_linkedin_firma_url(live.text)
    stamm_ok = aktualisiere_stammdaten_aus_pflege(
        kundennumm,
        linkedin_url=linkedin_neu,
        web_url=url if not str(row.get("aktuelle_haupt_url") or "").strip() else "",
    )

    personen_neu = live.personen_neu or 0
    personen_vorhanden = live.personen_vorhanden or 0
    personen_aktualisiert = live.personen_aktualisiert or 0
    roh_personen = extrahiere_fuehrung_personen(live.text or "")
    pruef = bereinige_und_pruefe_personen(
        roh_personen,
        live.text or "",
        firmenname,
    )
    erkannte = len(pruef.personen)
    roh_anzahl = len(roh_personen)

    if live.personen_sync_fehler:
        return PflegeErgebnis(
            ok=False,
            kundennumm=kundennumm,
            firmenname=firmenname,
            ort=ort,
            url=live.url or url,
            status="fehler",
            fehler=f"CRM-Sync: {live.personen_sync_fehler}",
            detail=f"{erkannte} plausibel ({roh_anzahl} roh, {live.personen_abgelehnt} abgelehnt)",
        )

    if personen_neu == 0 and personen_aktualisiert == 0 and not stamm_ok:
        grund = (
            f"{erkannte} plausibel, {live.personen_abgelehnt} abgelehnt "
            f"({roh_anzahl} roh aus Impressum)"
            if roh_anzahl
            else f"Kein GF-Format im Impressum ({len(live.text or '')} Zeichen Text)"
        )
        return PflegeErgebnis(
            ok=False,
            kundennumm=kundennumm,
            firmenname=firmenname,
            ort=ort,
            url=live.url or url,
            status="keine_daten",
            fehler=grund,
            detail=(live.text or "")[:200],
        )

    detail_teile = []
    if personen_neu:
        detail_teile.append(f"{personen_neu} Person(en) neu")
    if personen_aktualisiert:
        detail_teile.append(f"{personen_aktualisiert} aktualisiert")
    if live.personen_abgelehnt:
        detail_teile.append(f"{live.personen_abgelehnt} unplausibel verworfen")
    if personen_vorhanden:
        detail_teile.append(f"{personen_vorhanden} bereits vorhanden")
    if stamm_ok:
        detail_teile.append("Stammdaten aktualisiert")

    return PflegeErgebnis(
        ok=True,
        kundennumm=kundennumm,
        firmenname=firmenname,
        ort=ort,
        url=live.url or url,
        status="ok",
        detail=", ".join(detail_teile) or "Verarbeitet",
        personen_neu=personen_neu,
        personen_vorhanden=personen_vorhanden,
        stamm_aktualisiert=stamm_ok,
    )


def ergebnis_zu_dict(erg: PflegeErgebnis) -> dict:
    return {
        "zeit": datetime.now().strftime("%H:%M:%S"),
        "kundennumm": erg.kundennumm,
        "firma": erg.firmenname,
        "ort": erg.ort,
        "status": erg.status,
        "detail": erg.detail or erg.fehler,
        "personen_neu": erg.personen_neu,
        "url": erg.url,
    }


def im_pflege_zeitfenster(jetzt: datetime, start: time, ende: time) -> bool:
    """Liegt jetzt im täglichen Laufzeitfenster? (ende < start = über Mitternacht)"""
    if start == ende:
        return True
    t = jetzt.time()
    if start < ende:
        return start <= t < ende
    return t >= start or t < ende


def naechster_pflege_fenster_beginn(jetzt: datetime, start: time, ende: time) -> datetime:
    if im_pflege_zeitfenster(jetzt, start, ende):
        return jetzt
    d = jetzt.date()
    t = jetzt.time()
    if start < ende:
        if t < start:
            return datetime.combine(d, start)
        return datetime.combine(d + timedelta(days=1), start)
    return datetime.combine(d, start)


def naechste_pflege_aktion(
    jetzt: datetime,
    *,
    pausen_ende: datetime | None,
    fenster_von: time,
    fenster_bis: time,
    fenster_aktiv: bool,
) -> tuple[datetime | None, str]:
    """Früheste Fortsetzung (Firmen-Pause und/oder Tagesfenster)."""
    kandidaten: list[tuple[datetime, str]] = []
    if pausen_ende and pausen_ende > jetzt:
        kandidaten.append((pausen_ende, "pause"))
    if fenster_aktiv and not im_pflege_zeitfenster(jetzt, fenster_von, fenster_bis):
        fb = naechster_pflege_fenster_beginn(jetzt, fenster_von, fenster_bis)
        if fb > jetzt:
            kandidaten.append((fb, "fenster"))
    if not kandidaten:
        return None, ""
    return max(kandidaten, key=lambda x: x[0])


def format_pflege_zeitfenster(start: time, ende: time) -> str:
    return f"{start.strftime('%H:%M')}–{ende.strftime('%H:%M')}"
