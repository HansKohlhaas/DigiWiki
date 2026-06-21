"""Verfahren-Direktpfad: Anleitungen aus Einrichtung + Schulung (ohne Chroma-Rauschen)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from config import WATCH_ROOTS, WATCH_STATE_PATH, ist_verfahren_pfad
from sql_frage_katalog import ist_verfahren_wiki_frage

MAX_WIKI_KONTEXT_ZEICHEN = 28000
VERFAHREN_ENDUNGEN = (".docx", ".pdf", ".md", ".txt")

VERFAHREN_STOPWOERTER = frozenset({
    "wie", "was", "wird", "wird", "digibest", "eigentlich", "fuer", "fur", "die", "der",
    "das", "den", "dem", "des", "ein", "eine", "und", "oder", "bei", "zum", "zur",
    "anleitung", "verfahren", "schulung", "einrichtung", "bitte", "wiki",
})

_index_cache: tuple[float, tuple[str, ...]] = (0.0, ())


def erkenne_verfahren_wiki_frage(frage: str) -> bool:
    return ist_verfahren_wiki_frage(frage)


def _indexierte_pfade() -> tuple[str, ...]:
    global _index_cache
    mtime = WATCH_STATE_PATH.stat().st_mtime if WATCH_STATE_PATH.exists() else 0.0
    if _index_cache[0] == mtime:
        return _index_cache[1]
    if not WATCH_STATE_PATH.exists():
        _index_cache = (mtime, ())
        return ()
    try:
        daten = json.loads(WATCH_STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(daten, dict):
            pfade = tuple(p for p in daten if isinstance(p, str))
        else:
            pfade = ()
        _index_cache = (mtime, pfade)
        return pfade
    except (json.JSONDecodeError, OSError):
        _index_cache = (mtime, ())
        return ()


def _scan_verfahren_ordner() -> list[Path]:
    gefunden: dict[str, Path] = {}
    for root in WATCH_ROOTS:
        root = Path(root)
        if not root.exists():
            continue
        for pfad in root.rglob("*"):
            if not pfad.is_file():
                continue
            if pfad.suffix.lower() not in VERFAHREN_ENDUNGEN:
                continue
            if not ist_verfahren_pfad(str(pfad), pfad.name):
                continue
            gefunden[str(pfad.resolve())] = pfad.resolve()
    return sorted(gefunden.values(), key=lambda p: p.name.lower())


def finde_verfahren_dateien() -> list[Path]:
    gefunden: dict[str, Path] = {}
    for pfad_str in _indexierte_pfade():
        if not ist_verfahren_pfad(pfad_str):
            continue
        if not pfad_str.lower().endswith(VERFAHREN_ENDUNGEN):
            continue
        p = Path(pfad_str)
        if p.exists():
            gefunden[str(p.resolve())] = p.resolve()
    for p in _scan_verfahren_ordner():
        gefunden[str(p)] = p
    return sorted(gefunden.values(), key=lambda p: p.name.lower())


def _suchbegriffe_aus_frage(frage: str) -> list[str]:
    woerter = re.findall(r"[\wäöüßÄÖÜ]+", (frage or "").lower())
    return [w for w in woerter if len(w) >= 4 and w not in VERFAHREN_STOPWOERTER]


def _extrahiere_abschnitte(text: str, begriffe: list[str], fenster: int = 500) -> str:
    if not begriffe or not text:
        return text
    text_lower = text.lower()
    stellen: list[tuple[int, int]] = []
    for begriff in begriffe:
        idx = 0
        while True:
            pos = text_lower.find(begriff, idx)
            if pos < 0:
                break
            stellen.append((max(0, pos - fenster), min(len(text), pos + len(begriff) + fenster)))
            idx = pos + len(begriff)
    if not stellen:
        return ""
    stellen.sort()
    merged: list[tuple[int, int]] = []
    for start, end in stellen:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return "\n...\n".join(text[s:e].strip() for s, e in merged)


def _lade_datei_text(pfad: Path) -> str:
    ext = pfad.suffix.lower()
    if ext == ".docx":
        try:
            import docx2txt

            text = docx2txt.process(str(pfad))
            if text and text.strip():
                return text.strip()
        except Exception:
            pass
        try:
            from langchain_community.document_loaders import Docx2txtLoader

            docs = Docx2txtLoader(str(pfad)).load()
            return "\n".join(d.page_content for d in docs if d.page_content).strip()
        except Exception:
            return ""
    if ext in (".md", ".txt"):
        for enc in ("utf-8", "cp1252"):
            try:
                return pfad.read_text(encoding=enc).strip()
            except Exception:
                continue
        return ""
    if ext == ".pdf":
        try:
            from langchain_community.document_loaders import PyPDFLoader

            docs = PyPDFLoader(str(pfad)).load()
            return "\n".join(d.page_content for d in docs if d.page_content).strip()
        except Exception:
            return ""
    return ""


def lade_verfahren_kontext_fuer_frage(frage: str) -> tuple[str, list[str]]:
    begriffe = _suchbegriffe_aus_frage(frage)
    teile: list[str] = []
    quellen: list[str] = []
    for pfad in finde_verfahren_dateien():
        text = _lade_datei_text(pfad)
        if not text:
            continue
        abschnitt = _extrahiere_abschnitte(text, begriffe) or text
        teile.append(f"--- {pfad.name} ---\n{abschnitt}")
        quellen.append(pfad.name)
    kontext = "\n\n".join(teile)
    if len(kontext) > MAX_WIKI_KONTEXT_ZEICHEN:
        kontext = kontext[:MAX_WIKI_KONTEXT_ZEICHEN] + "\n[... gekuerzt ...]"
    return kontext, quellen
