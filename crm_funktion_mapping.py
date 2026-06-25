"""TF-IDF-Zuordnung und Live-Suche: crm_funktion_synonyme ↔ ref_funktionen."""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import pyodbc
from dotenv import load_dotenv

load_dotenv()

from config import ACCESS_DB_PATH

DEFAULT_SCHWELLE = 0.4
SYNONYM_SUBSTRING_MIN = 4
DEFAULT_CSV = Path(__file__).resolve().parent / "mapped_funktions_ids.csv"


@dataclass
class FunktionMappingErgebnis:
    geprueft: int = 0
    zugeordnet: int = 0
    geschrieben: int = 0
    offen: int = 0
    bereits_mit_id: int = 0
    gesamt: int = 0
    dry_run: bool = False
    db_path: str = ""
    csv_path: str = ""
    schwellenwert: float = DEFAULT_SCHWELLE
    details: list[dict[str, Any]] = field(default_factory=list)
    fehler: str = ""


def _conn_str(db_path: str | None = None) -> str:
    pfad = Path(db_path or ACCESS_DB_PATH)
    return f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={pfad};"


def _leer(wert) -> bool:
    if wert is None:
        return True
    return str(wert).strip() == ""


def _norm_key(s: str) -> str:
    s = (s or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _synonym_spalten(conn) -> tuple[str, str]:
    """ID-Spalte in crm_funktion_synonyme (funktion_id oder funktionid)."""
    cur = conn.cursor()
    cur.execute("SELECT TOP 1 * FROM crm_funktion_synonyme")
    cols = [str(c[0] or "").lower() for c in cur.description]
    if "funktion_id" in cols:
        return "funktion_id", "funktionsbezeichnung"
    if "funktionid" in cols:
        return "funktionid", "funktionsbezeichnung"
    return "funktionid", "funktionsbezeichnung"


@lru_cache(maxsize=1)
def _synonym_spalten_cache() -> tuple[str, str]:
    if not Path(ACCESS_DB_PATH).exists():
        return "funktionid", "funktionsbezeichnung"
    conn = pyodbc.connect(_conn_str(), timeout=12)
    try:
        return _synonym_spalten(conn)
    finally:
        conn.close()


def _lade_referenz_funktionen(conn) -> list[dict[str, str]]:
    cur = conn.cursor()
    cur.execute(
        "SELECT funktionid, funktionsbezeichnung FROM ref_funktionen "
        "WHERE funktionsbezeichnung IS NOT NULL ORDER BY funktionid"
    )
    return [
        {
            "funktionid": str(row[0] or "").strip(),
            "funktionsbezeichnung": str(row[1] or "").strip(),
        }
        for row in cur.fetchall()
        if str(row[0] or "").strip() and str(row[1] or "").strip()
    ]


def _synonym_statistik(conn) -> tuple[int, int]:
    id_col, _ = _synonym_spalten(conn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM crm_funktion_synonyme")
    gesamt = int(cur.fetchone()[0] or 0)
    cur.execute(
        f"SELECT COUNT(*) FROM crm_funktion_synonyme "
        f"WHERE {id_col} IS NULL OR Trim({id_col}) = ''"
    )
    leer = int(cur.fetchone()[0] or 0)
    return gesamt, leer


def _lade_synonyme_ohne_id(conn) -> list[str]:
    id_col, bez_col = _synonym_spalten(conn)
    cur = conn.cursor()
    cur.execute(f"SELECT {bez_col}, {id_col} FROM crm_funktion_synonyme")
    return [
        str(row[0] or "").strip()
        for row in cur.fetchall()
        if str(row[0] or "").strip() and _leer(row[1])
    ]


@lru_cache(maxsize=1)
def _synonym_liste_mit_id() -> list[dict[str, str]]:
    """Alle Synonyme mit gesetzter funktion_id/funktionid."""
    if not Path(ACCESS_DB_PATH).exists():
        return []
    conn = pyodbc.connect(_conn_str(), timeout=12)
    try:
        id_col, bez_col = _synonym_spalten(conn)
        cur = conn.cursor()
        cur.execute(f"SELECT {bez_col}, {id_col} FROM crm_funktion_synonyme")
        return [
            {
                "funktionsbezeichnung": str(row[0] or "").strip(),
                "funktionid": str(row[1] or "").strip(),
            }
            for row in cur.fetchall()
            if str(row[0] or "").strip() and not _leer(row[1])
        ]
    finally:
        conn.close()


def _referenz_bezeichnung_fuer_id(funktionid: str) -> str:
    fid = str(funktionid or "").strip()
    if not fid:
        return ""
    for row in _referenz_liste_kurz():
        if row["funktionid"] == fid:
            return row["funktionsbezeichnung"]
    return ""


def _schreibe_csv(pfad: Path, details: list[dict[str, Any]]) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "funktionsbezeichnung",
                "new_funktionid",
                "referenz_funktionsbezeichnung",
                "score",
                "status",
            ],
            delimiter=";",
        )
        writer.writeheader()
        for d in details:
            writer.writerow(
                {
                    "funktionsbezeichnung": d["funktionsbezeichnung"],
                    "new_funktionid": d["funktionid"],
                    "referenz_funktionsbezeichnung": d["referenz"],
                    "score": d["score"],
                    "status": d["status"],
                }
            )


@lru_cache(maxsize=1)
def _tfidf_matcher():
    """Vectorizer + Referenz-Matrix (einmal pro Prozess)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    if not Path(ACCESS_DB_PATH).exists():
        return None, None, []

    conn = pyodbc.connect(_conn_str(), timeout=12)
    try:
        referenz = _lade_referenz_funktionen(conn)
    finally:
        conn.close()

    if not referenz:
        return None, None, []

    texte = [r["funktionsbezeichnung"] for r in referenz]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform(texte)
    return vectorizer, matrix, referenz


def finde_funktionid_fuer_bezeichnung(
    text: str,
    schwellenwert: float = DEFAULT_SCHWELLE,
) -> tuple[str, str, float]:
    """
    Beste funktionid zu Freitext per TF-IDF (char n-grams).
    Returns: (funktionid, funktionsbezeichnung, score) — leer bei keinem Treffer.
    """
    if _leer(text):
        return "", "", 0.0

    vectorizer, matrix, referenz = _tfidf_matcher()
    if vectorizer is None or matrix is None or not referenz:
        return "", "", 0.0

    from sklearn.metrics.pairwise import cosine_similarity

    query = vectorizer.transform([str(text).strip()])
    scores = cosine_similarity(query, matrix)[0]
    idx = int(scores.argmax())
    score = float(scores[idx])
    if score <= schwellenwert:
        return "", "", score

    treffer = referenz[idx]
    return treffer["funktionid"], treffer["funktionsbezeichnung"], score


@lru_cache(maxsize=1)
def _synonym_tfidf_matcher():
    """TF-IDF gegen crm_funktion_synonyme (nur Eintraege mit ID)."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    synonyme = _synonym_liste_mit_id()
    if not synonyme:
        return None, None, []

    texte = [s["funktionsbezeichnung"] for s in synonyme]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform(texte)
    return vectorizer, matrix, synonyme


def _substring_synonym_match(text: str) -> dict[str, str] | None:
    key = _norm_key(text)
    if not key:
        return None
    best: dict[str, str] | None = None
    best_len = 0
    for row in _synonym_liste_mit_id():
        syn = _norm_key(row["funktionsbezeichnung"])
        if not syn or len(syn) < SYNONYM_SUBSTRING_MIN:
            continue
        if syn == key:
            return row
        if syn in key or key in syn:
            if len(syn) > best_len:
                best = row
                best_len = len(syn)
    return best


def finde_funktion_aus_synonymen(
    text: str,
    schwellenwert: float = DEFAULT_SCHWELLE,
) -> tuple[str, str, str]:
    """
    Primaere Zuordnung ueber crm_funktion_synonyme: exakt, Teilstring, TF-IDF.
    Returns: (funktionid, ref_funktionsbezeichnung, quelle) — leer bei keinem Treffer.
    """
    if _leer(text):
        return "", "", ""

    key = _norm_key(text)
    for row in _synonym_liste_mit_id():
        if _norm_key(row["funktionsbezeichnung"]) == key:
            fid = row["funktionid"]
            return fid, _referenz_bezeichnung_fuer_id(fid), "synonym_exakt"

    teil = _substring_synonym_match(text)
    if teil:
        fid = teil["funktionid"]
        return fid, _referenz_bezeichnung_fuer_id(fid), "synonym_teil"

    vectorizer, matrix, synonyme = _synonym_tfidf_matcher()
    if vectorizer is not None and matrix is not None and synonyme:
        from sklearn.metrics.pairwise import cosine_similarity

        query = vectorizer.transform([str(text).strip()])
        scores = cosine_similarity(query, matrix)[0]
        idx = int(scores.argmax())
        score = float(scores[idx])
        if score > schwellenwert:
            fid = synonyme[idx]["funktionid"]
            return fid, _referenz_bezeichnung_fuer_id(fid), "synonym_tfidf"

    return "", "", ""


def synonyme_beispiele_pro_funktionid(max_pro_id: int = 8) -> dict[str, list[str]]:
    """Kurze Synonym-Listen pro funktionid (z. B. fuer KI-Prompt)."""
    by_id: dict[str, list[str]] = defaultdict(list)
    for row in _synonym_liste_mit_id():
        fid = row["funktionid"]
        if len(by_id[fid]) < max_pro_id:
            by_id[fid].append(row["funktionsbezeichnung"])
    return dict(by_id)


@lru_cache(maxsize=1)
def _synonym_tabelle_cache() -> dict[str, str]:
    """Exakte Synonym-Tabelle funktionsbezeichnung -> funktionid."""
    return {
        _norm_key(row["funktionsbezeichnung"]): row["funktionid"]
        for row in _synonym_liste_mit_id()
        if row["funktionsbezeichnung"]
    }


def synonym_funktionid(text: str) -> tuple[str, str]:
    """Exakter Treffer in crm_funktion_synonyme."""
    fid, bez, _ = finde_funktion_aus_synonymen(text)
    return fid, bez


@lru_cache(maxsize=1)
def _referenz_liste_kurz() -> list[dict[str, str]]:
    if not Path(ACCESS_DB_PATH).exists():
        return []
    conn = pyodbc.connect(_conn_str(), timeout=12)
    try:
        return _lade_referenz_funktionen(conn)
    finally:
        conn.close()


def cache_leeren() -> None:
    _tfidf_matcher.cache_clear()
    _synonym_tfidf_matcher.cache_clear()
    _synonym_spalten_cache.cache_clear()
    _synonym_liste_mit_id.cache_clear()
    _synonym_tabelle_cache.cache_clear()
    _referenz_liste_kurz.cache_clear()


def mappe_funktion_synonyme(
    db_path: str | None = None,
    schwellenwert: float = DEFAULT_SCHWELLE,
    dry_run: bool = False,
    csv_path: str | Path | None = DEFAULT_CSV,
) -> FunktionMappingErgebnis:
    """
    Fuellt leere funktionid in crm_funktion_synonyme per TF-IDF gegen ref_funktionen.

    dry_run=True: nur Vorschau + CSV, keine UPDATEs in Access.
    """
    pfad = Path(db_path or ACCESS_DB_PATH)
    if not pfad.exists():
        return FunktionMappingErgebnis(fehler=f"Datenbank nicht gefunden: {pfad}")

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: F401
    except ImportError:
        return FunktionMappingErgebnis(
            fehler="scikit-learn fehlt. In .venv: pip install scikit-learn",
        )

    cache_leeren()
    ergebnis = FunktionMappingErgebnis(
        dry_run=dry_run,
        db_path=str(pfad),
        schwellenwert=schwellenwert,
    )

    conn = pyodbc.connect(_conn_str(str(pfad)), timeout=12)
    try:
        gesamt, leer = _synonym_statistik(conn)
        ergebnis.gesamt = gesamt
        ergebnis.bereits_mit_id = gesamt - leer

        referenz = _lade_referenz_funktionen(conn)
        offene = _lade_synonyme_ohne_id(conn)
        if not referenz:
            return FunktionMappingErgebnis(fehler="ref_funktionen ist leer.")
        if not offene:
            return ergebnis

        texte_ref = [r["funktionsbezeichnung"] for r in referenz]
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        matrix_ref = vectorizer.fit_transform(texte_ref)

        from sklearn.metrics.pairwise import cosine_similarity

        cur = conn.cursor()
        for bezeichnung in offene:
            ergebnis.geprueft += 1
            query = vectorizer.transform([bezeichnung])
            scores = cosine_similarity(query, matrix_ref)[0]
            idx = int(scores.argmax())
            score = float(scores[idx])

            if score <= schwellenwert:
                ergebnis.offen += 1
                ergebnis.details.append(
                    {
                        "funktionsbezeichnung": bezeichnung,
                        "funktionid": "",
                        "referenz": "",
                        "score": round(score, 3),
                        "status": "offen",
                    }
                )
                continue

            fid = referenz[idx]["funktionid"]
            ref_bez = referenz[idx]["funktionsbezeichnung"]
            if not dry_run:
                id_col, bez_col = _synonym_spalten(conn)
                cur.execute(
                    f"UPDATE crm_funktion_synonyme SET {id_col} = ? "
                    f"WHERE {bez_col} = ? "
                    f"AND ({id_col} IS NULL OR Trim({id_col}) = '')",
                    (fid, bezeichnung),
                )
                ergebnis.geschrieben += max(int(cur.rowcount or 0), 0)
            ergebnis.zugeordnet += 1
            ergebnis.details.append(
                {
                    "funktionsbezeichnung": bezeichnung,
                    "funktionid": fid,
                    "referenz": ref_bez,
                    "score": round(score, 3),
                    "status": "vorschau" if dry_run else "zugeordnet",
                }
            )

        if not dry_run and ergebnis.geschrieben:
            conn.commit()
            cache_leeren()
        elif not dry_run and ergebnis.zugeordnet and not ergebnis.geschrieben:
            conn.rollback()

        if csv_path and ergebnis.details:
            csv_ziel = Path(csv_path)
            _schreibe_csv(csv_ziel, ergebnis.details)
            ergebnis.csv_path = str(csv_ziel)
    except Exception as exc:
        return FunktionMappingErgebnis(fehler=str(exc))
    finally:
        conn.close()

    return ergebnis


def _parse_schwelle(argv: list[str]) -> float:
    for i, arg in enumerate(argv):
        if arg in ("--schwelle", "-s") and i + 1 < len(argv):
            return float(argv[i + 1])
        if arg.startswith("--schwelle="):
            return float(arg.split("=", 1)[1])
    return DEFAULT_SCHWELLE


def _drucke_zeile(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("cp1252", errors="replace").decode("cp1252"))


if __name__ == "__main__":
    import sys

    dry = "--dry" in sys.argv or "-n" in sys.argv
    ohne_csv = "--no-csv" in sys.argv
    schwelle = _parse_schwelle(sys.argv)

    modus = "VORSCHAU (Dry-Run, keine DB-Aenderung)" if dry else "SCHREIBEN in Access"
    _drucke_zeile(f"Modus: {modus}")
    _drucke_zeile(f"Schwellenwert: {schwelle}")

    res = mappe_funktion_synonyme(
        dry_run=dry,
        schwellenwert=schwelle,
        csv_path=None if ohne_csv else DEFAULT_CSV,
    )
    if res.fehler:
        print("FEHLER:", res.fehler)
        raise SystemExit(1)

    _drucke_zeile(f"Datenbank: {res.db_path}")
    _drucke_zeile(
        f"Synonyme gesamt: {res.gesamt}, bereits mit funktionid: {res.bereits_mit_id}, "
        f"noch leer: {res.gesamt - res.bereits_mit_id}"
    )
    if res.geprueft == 0 and res.gesamt:
        _drucke_zeile("Alle Synonyme haben bereits eine funktionid — nichts zu tun.")
        raise SystemExit(0)

    _drucke_zeile(
        f"Geprueft: {res.geprueft}, zugeordnet (Score > {res.schwellenwert}): "
        f"{res.zugeordnet}, offen: {res.offen}"
    )
    if not dry:
        _drucke_zeile(f"In Access geschrieben (UPDATE rowcount): {res.geschrieben}")
        if res.zugeordnet and not res.geschrieben:
            _drucke_zeile(
                "Hinweis: Treffer gefunden, aber 0 Zeilen aktualisiert "
                "(evtl. bereits belegt oder WHERE passt nicht)."
            )
        elif not res.zugeordnet:
            _drucke_zeile(
                f"Hinweis: Keine neuen Zuordnungen — alle {res.geprueft} offenen "
                f"Synonyme liegen unter Schwellenwert {res.schwellenwert}. "
                f"CSV pruefen oder --schwelle senken (z. B. --schwelle 0.35)."
            )
    else:
        _drucke_zeile("Dry-Run: Es wurde nichts in Access geschrieben.")

    if res.csv_path:
        _drucke_zeile(f"CSV: {res.csv_path}")

    for d in res.details:
        zeile = (
            f"  {d['status']:10} {d['score']:.3f}  "
            f"{d['funktionsbezeichnung']!r} -> {d['funktionid']}"
        )
        _drucke_zeile(zeile)
