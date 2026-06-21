"""Markierte Chat-Antworten zusammenfassen und als Markdown in Ordner Antworten speichern."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from config import ANTWORTEN_DIR

__all__ = [
    "ANTWORTEN_DIR",
    "erzeuge_dateiname",
    "baue_markdown_dokument",
    "fasse_antworten_zusammen",
    "speichere_antworten_dokument",
    "exportiere_markierte_paare",
]


def _slug(text: str, max_len: int = 55) -> str:
    text = (
        (text or "")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
        .replace("ß", "ss")
    )
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", " ", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        text = "digiwiki-antworten"
    return text[:max_len].strip("-")


def erzeuge_dateiname(paare: list[dict], titel_vorschlag: str = "") -> str:
    """Sprechender Dateiname ohne Endung: YYYY-MM-DD_kurztitel."""
    datum = datetime.now().strftime("%Y-%m-%d")
    if titel_vorschlag.strip():
        kern = _slug(titel_vorschlag.strip())
    elif len(paare) == 1:
        kern = _slug(paare[0].get("frage", "antwort"))
    else:
        kern = _slug(paare[0].get("frage", ""))[:30]
        kern = f"{kern}-{len(paare)}-fragen" if kern else f"wiki-{len(paare)}-fragen"
    return f"{datum}_{kern}"


def erzeuge_titel_ki(paare: list[dict]) -> str:
    """Kurzer Dokumenttitel per KI (3–6 Wörter)."""
    fragen = "\n".join(f"- {p.get('frage', '')[:200]}" for p in paare[:8])
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Erzeuge einen kurzen deutschen Dokumenttitel (3 bis 6 Woerter) "
                        "fuer eine Zusammenfassung dieser Fragen. Nur den Titel, ohne Anfuehrungszeichen.\n\n"
                        f"{fragen}"
                    ),
                }
            ],
            temperature=0.2,
            max_tokens=40,
        )
        titel = (response.choices[0].message.content or "").strip().strip('"').strip("'")
        return titel or "DigiWiki Antworten"
    except Exception:
        return "DigiWiki Antworten"


def fasse_antworten_zusammen(paare: list[dict], dokument_titel: str) -> str:
    """Gesamtzusammenfassung aller markierten Q&A-Paare."""
    bloecke = []
    for i, p in enumerate(paare, 1):
        typ = p.get("typ", "wiki")
        quellen = p.get("quellen") or []
        q_hinweis = f"\nQuellen: {', '.join(quellen)}" if quellen else ""
        antwort = p.get("antwort", "")
        if p.get("sql_markdown"):
            antwort = f"{antwort}\n\n{p['sql_markdown'][:4000]}"
        bloecke.append(
            f"### Frage {i} ({typ})\n{p.get('frage', '')}\n\n**Antwort:**\n{antwort[:3500]}{q_hinweis}"
        )
    kontext = "\n\n---\n\n".join(bloecke)
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du fasst DigiWiki-Rechercheergebnisse fuer den Geschaeftsfuehrer zusammen. "
                        "Deutsch, professionell, strukturiert. Nenne Kernaussagen, Gemeinsamkeiten, "
                        "offene Luecken. Erfinde nichts — nur aus dem Kontext."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Dokumenttitel: {dokument_titel}\n\n{kontext[:12000]}",
                },
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        return f"*(Zusammenfassung konnte nicht erzeugt werden: {e})*"


def baue_markdown_dokument(
    paare: list[dict],
    dokument_titel: str,
    gesamtzusammenfassung: str,
) -> str:
    """Vollstaendiges Markdown-Dokument."""
    jetzt = datetime.now().strftime("%d.%m.%Y %H:%M")
    typ_anzahl = {}
    for p in paare:
        t = p.get("typ", "wiki")
        typ_anzahl[t] = typ_anzahl.get(t, 0) + 1
    meta = ", ".join(f"{k}: {v}" for k, v in typ_anzahl.items())

    zeilen = [
        f"# {dokument_titel}",
        "",
        f"**Erstellt:** {jetzt}  ",
        f"**Anzahl Fragen:** {len(paare)}  ",
        f"**Antworttypen:** {meta}  ",
        "",
        "---",
        "",
        "## Gesamtzusammenfassung",
        "",
        gesamtzusammenfassung,
        "",
        "---",
        "",
        "## Einzelantworten",
        "",
    ]

    for i, p in enumerate(paare, 1):
        typ = p.get("typ", "wiki")
        typ_label = {"wiki": "Wiki", "sql": "SQL", "wiki_fallback": "Wiki (Fallback)"}.get(typ, typ)
        zeilen.extend([f"### {i}. {p.get('frage', '').strip()}", "", f"*Antworttyp: {typ_label}*", ""])
        zeilen.append(p.get("antwort", "").strip())
        zeilen.append("")
        if p.get("sql_markdown"):
            zeilen.extend(["**Daten (Auszug):**", "", p["sql_markdown"], ""])
        quellen = p.get("quellen") or []
        if quellen:
            zeilen.append("**Quellen:** " + ", ".join(quellen))
            zeilen.append("")
        zeilen.append("---")
        zeilen.append("")

    zeilen.append("*Generiert mit DigiWiki – Antworten-Export.*")
    return "\n".join(zeilen)


def speichere_antworten_dokument(inhalt: str, dateiname_ohne_ext: str) -> Path:
    """Speichert Markdown unter ANTWORTEN_DIR; bei Kollision Suffix -2, -3 …"""
    ANTWORTEN_DIR.mkdir(parents=True, exist_ok=True)
    basis = _slug(dateiname_ohne_ext, max_len=80) or "digiwiki-antworten"
    if not basis[0].isdigit():
        basis = f"{datetime.now().strftime('%Y-%m-%d')}_{basis}"
    ziel = ANTWORTEN_DIR / f"{basis}.md"
    suffix = 2
    while ziel.exists():
        ziel = ANTWORTEN_DIR / f"{basis}-{suffix}.md"
        suffix += 1
    ziel.write_text(inhalt, encoding="utf-8")
    return ziel


def exportiere_markierte_paare(
    paare: list[dict],
    titel_manuell: str = "",
    ki_titel: bool = True,
) -> tuple[Path, str]:
    """
    Markierte Paare zusammenfassen und speichern.
    Returns: (pfad, dokument_titel)
    """
    if not paare:
        raise ValueError("Keine markierten Antworten zum Exportieren.")

    if titel_manuell.strip():
        dokument_titel = titel_manuell.strip()
    elif ki_titel:
        dokument_titel = erzeuge_titel_ki(paare)
    else:
        dokument_titel = "DigiWiki Antworten"

    zusammenfassung = fasse_antworten_zusammen(paare, dokument_titel)
    markdown = baue_markdown_dokument(paare, dokument_titel, zusammenfassung)
    dateiname = erzeuge_dateiname(paare, dokument_titel)
    pfad = speichere_antworten_dokument(markdown, dateiname)
    return pfad, dokument_titel
