"""Brandvoice-Kontext fuer E-Mail- und WhatsApp-Entwuerfe (Hans vs. DigiBest)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader

from config import BASE_DIR, WATCH_STATE_PATH

BRANDVOICE_RADIO = [
    {"id": "hans", "label": "BV Hans"},
    {"id": "digi", "label": "BV Digi"},
    {"id": "ohne", "label": "Ohne"},
]

# Legacy-Alias fuer Abwaertskompatibilitaet
BRANDVOICE_OPTIONEN = BRANDVOICE_RADIO

BRANDVOICE_PROFILE = {
    "hans": {
        "name": "Brandvoice Hans",
        "beschreibung": (
            "Persoenliche Stimme von Hans Kohlhaas: direkt, erfahren, "
            "menschlich, Beziehungsebene, weniger Corporate-Sprech."
        ),
        "datei_marker": [
            "brandvoice_hans",
            "personal_brandvoice",
        ],
    },
    "digi": {
        "name": "Brandvoice DigiBest",
        "beschreibung": (
            "Unternehmens-Stimme DigiBest: klar, professionell, "
            "marktorientiert, verlaesslich, B2B-Pharma/Apotheke."
        ),
        "datei_marker": [
            "brandvoice_guide_digibest",
            "brandvoice_kurzprofil_digibest",
            "brandvoice_voicefingerprint_digibest",
            "brandvoice_promptbibliothek_digibest",
        ],
    },
}

MAX_KONTEXT_ZEICHEN = 6000
MAX_WIKI_KONTEXT_ZEICHEN = 28000

BRANDVOICE_STOPWOERTER = frozenset({
    "was", "steht", "in", "der", "die", "das", "den", "dem", "des", "ein", "eine",
    "zum", "zur", "thema", "brandvoice", "brand", "voice", "hans", "digi", "digibest",
    "wie", "welche", "gibt", "sagt", "sagt", "laut", "dazu", "bitte", "wiki",
})


def liste_brandvoice_optionen() -> list[str]:
    return [o["id"] for o in BRANDVOICE_RADIO]


def brandvoice_radio_labels() -> dict[str, str]:
    return {o["id"]: o["label"] for o in BRANDVOICE_RADIO}


_index_cache: tuple[float, tuple[str, ...]] = (0.0, ())


def _indexierte_pfade() -> tuple[str, ...]:
    """Pfade aus wiki_stand.json; Cache wird bei Datei-Aenderung invalidiert."""
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
            pfade = tuple(pfad for pfad in daten if isinstance(pfad, str))
        elif isinstance(daten, list):
            pfade = tuple(pfad for pfad in daten if isinstance(pfad, str))
        else:
            pfade = ()
        _index_cache = (mtime, pfade)
        return pfade
    except (json.JSONDecodeError, OSError):
        _index_cache = (mtime, ())
        return ()


def _finde_brandvoice_dateien(stimme: str) -> list[Path]:
    profil = BRANDVOICE_PROFILE.get(stimme)
    if not profil:
        return []
    marker = profil["datei_marker"]
    gefunden: list[Path] = []
    for pfad_str in _indexierte_pfade():
        name = os.path.basename(pfad_str).lower()
        if not name.endswith(".docx"):
            continue
        if any(m in name for m in marker):
            p = Path(pfad_str)
            if p.exists():
                gefunden.append(p)
    return gefunden


def lade_brandvoice_kontext(stimme: str) -> str:
    """Laedt Textauszuege aus den indexierten Brandvoice-Dateien."""
    if stimme not in BRANDVOICE_PROFILE:
        return ""
    teile: list[str] = []
    for pfad in _finde_brandvoice_dateien(stimme):
        try:
            text = _lade_datei_text(pfad)
            if text:
                teile.append(f"--- {pfad.name} ---\n{text}")
        except Exception:
            continue
    kontext = "\n\n".join(teile)
    if len(kontext) > MAX_KONTEXT_ZEICHEN:
        kontext = kontext[:MAX_KONTEXT_ZEICHEN] + "\n[... gekuerzt ...]"
    return kontext


def erkenne_brandvoice_wiki_frage(frage: str) -> str | None:
    """Erkennt Wiki-Fragen zu Brandvoice-Dokumenten -> hans oder digi."""
    text = (frage or "").lower()
    if "brandvoice" not in text and "brand voice" not in text:
        return None
    if "hans" in text:
        return "hans"
    if "digi" in text:
        return "digi"
    return "hans"


def _suchbegriffe_aus_frage(frage: str) -> list[str]:
    woerter = re.findall(r"[\wäöüßÄÖÜ]+", (frage or "").lower())
    return [
        w for w in woerter
        if len(w) >= 4 and w not in BRANDVOICE_STOPWOERTER
    ]


def _extrahiere_abschnitte(text: str, begriffe: list[str], fenster: int = 450) -> str:
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
    try:
        import docx2txt

        text = docx2txt.process(str(pfad))
        if text and text.strip():
            return text.strip()
    except ImportError:
        pass
    except Exception:
        pass
    try:
        docs = Docx2txtLoader(str(pfad)).load()
        return "\n".join(d.page_content for d in docs if d.page_content).strip()
    except Exception:
        return ""


def lade_brandvoice_kontext_fuer_frage(stimme: str, frage: str) -> tuple[str, list[str]]:
    """Voller Brandvoice-Text bzw. relevante Abschnitte fuer Wiki-Q&A."""
    if stimme not in BRANDVOICE_PROFILE:
        return "", []
    begriffe = _suchbegriffe_aus_frage(frage)
    teile: list[str] = []
    quellen: list[str] = []
    for pfad in _finde_brandvoice_dateien(stimme):
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


def ermittle_brandvoice(
    *,
    manuell: str = "auto",
    original_text: str = "",
    ansprache: str = "Sie",
    ist_neue_nachricht: bool = False,
) -> str:
    """Waehlt hans oder digi. Bei auto: heuristisch aus Mail-Charakter."""
    if manuell in BRANDVOICE_PROFILE:
        return manuell
    if ist_neue_nachricht and not original_text.strip():
        return "digi"
    text = (original_text or "").lower()
    if ansprache == "Du":
        return "hans"
    persoenlich = (
        "freundliche grüße", "liebe grüße", "hallo hans", "du ", " dir", " dein",
        "persoenlich", "privat", "danke dir", "bei dir",
    )
    if any(p in text for p in persoenlich):
        return "hans"
    corporate = (
        "digibest", "apotheke", "pharma", "angebot", "produkt", "msv",
        "geschäftsführung", "firma", "unternehmen", "sehr geehrte",
    )
    if any(p in text for p in corporate):
        return "digi"
    return "hans" if ansprache == "Du" else "digi"


def baue_brandvoice_prompt_block(stimme: str) -> str:
    profil = BRANDVOICE_PROFILE[stimme]
    kontext = lade_brandvoice_kontext(stimme)
    block = (
        f"BRANDVOICE: {profil['name']}\n"
        f"Stilvorgabe: {profil['beschreibung']}\n"
        "Halte dich strikt an Tonalitaet, Wortwahl und Anrede aus dem Brandvoice-Kontext.\n"
    )
    if kontext:
        block += f"\nBRANDVOICE-REFERENZ (Auszug aus Dokumenten):\n{kontext}\n"
    else:
        block += (
            "\n(Hinweis: Brandvoice-Dokumente nicht geladen – nutze Stilvorgabe oben.)\n"
        )
    return block


def brandvoice_auswahl_block(wahl: str) -> str:
    """Prompt-Teil je nach Radio-Auswahl: hans, digi oder ohne."""
    if wahl == "ohne":
        return (
            "Keine Brandvoice-Vorgabe. Ton: klar, respektvoll-direkt, "
            "professionell auf Deutsch.\n"
        )
    if wahl in BRANDVOICE_PROFILE:
        return baue_brandvoice_prompt_block(wahl)
    return brandvoice_auswahl_block("ohne")
