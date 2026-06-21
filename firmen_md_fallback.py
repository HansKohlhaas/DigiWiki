"""Stufe 3: Gezielter MD-Fallback per kundennumm (kein Chroma).

Liest CRM-Website-MD ({kundennumm}_*.md) nur fuer eine bekannte Firma,
wenn SQL und Live-Web keine Antwort liefern.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from config import WATCH_ROOTS, WATCH_TEXT_ENCODINGS, ist_crm_archiv_datei

MD_MAX_BYTES = 1_500_000
MD_MAX_DATEIEN = 3
MD_MAX_CHARS_AUSGABE = 80_000


@dataclass
class MdFallbackErgebnis:
    ok: bool
    kundennumm: str = ""
    firmenname: str = ""
    text: str = ""
    dateien: list[str] = field(default_factory=list)
    fehler: str = ""


def finde_crm_md_dateien(kundennumm: str) -> list[Path]:
    kn = (kundennumm or "").strip()
    if not kn.isdigit():
        return []
    prefix = f"{kn}_".lower()
    gefunden: dict[str, Path] = {}
    for root in WATCH_ROOTS:
        if not root.exists():
            continue
        for pfad in root.rglob("*.md"):
            if not ist_crm_archiv_datei(str(pfad), pfad.name):
                continue
            if not pfad.name.lower().startswith(prefix):
                continue
            key = str(pfad.resolve())
            alt = gefunden.get(key)
            if alt is None or pfad.stat().st_mtime > alt.stat().st_mtime:
                gefunden[key] = pfad
    return sorted(gefunden.values(), key=lambda p: p.stat().st_mtime, reverse=True)


def _lese_textdatei(pfad: Path) -> str:
    raw = pfad.read_bytes()[:MD_MAX_BYTES]
    for enc in WATCH_TEXT_ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _relevante_abschnitte(text: str, frage: str, max_chars: int = 30_000) -> str:
    if len(text) <= max_chars:
        return text
    words = [w for w in re.split(r"\W+", (frage or "").lower()) if len(w) > 3]
    if not words:
        return text[:max_chars]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    scored = [(sum(1 for w in words if w in p.lower()), p) for p in paragraphs]
    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    parts: list[str] = []
    total = 0
    for score, p in scored:
        if score == 0 and parts:
            continue
        if total + len(p) > max_chars:
            break
        parts.append(p)
        total += len(p)
    return "\n\n".join(parts) if parts else text[:max_chars]


def firmen_md_fallback(
    frage: str,
    kundennumm: str,
    firmenname: str = "",
) -> MdFallbackErgebnis:
    kn = (kundennumm or "").strip()
    if not kn:
        return MdFallbackErgebnis(ok=False, fehler="Keine kundennumm fuer MD-Fallback.")
    dateien = finde_crm_md_dateien(kn)
    if not dateien:
        return MdFallbackErgebnis(
            ok=False,
            kundennumm=kn,
            firmenname=firmenname,
            fehler=f"Keine MD-Dateien fuer kundennumm {kn} gefunden.",
        )
    bloecke: list[str] = []
    genutzt: list[str] = []
    total = 0
    for pfad in dateien[:MD_MAX_DATEIEN]:
        try:
            roh = _lese_textdatei(pfad)
        except OSError:
            continue
        auszug = _relevante_abschnitte(roh, frage)
        if total + len(auszug) > MD_MAX_CHARS_AUSGABE:
            auszug = auszug[: MD_MAX_CHARS_AUSGABE - total]
        if not auszug.strip():
            continue
        bloecke.append(f"### {pfad.name}\n\n{auszug}")
        genutzt.append(str(pfad))
        total += len(auszug)
        if total >= MD_MAX_CHARS_AUSGABE:
            break
    text = "\n\n---\n\n".join(bloecke)
    return MdFallbackErgebnis(
        ok=bool(text.strip()),
        kundennumm=kn,
        firmenname=firmenname,
        text=text,
        dateien=genutzt,
        fehler="" if text.strip() else "MD-Dateien leer oder nicht lesbar.",
    )


def ist_einzel_firma_md_fallback_frage(frage: str) -> bool:
    from firmen_live_recherche import ist_einzel_firma_live_web_frage

    return ist_einzel_firma_live_web_frage(frage)
