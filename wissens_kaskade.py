"""Wissens-Kaskade Phase A: Routing SQL vor Wiki (Marktdaten ohne CRM-MD-Fallback).

Geplant: Stufe 2 Live-Web, Stufe 3 gezieltes MD, Stufe 4 KI-Synthese.
"""
from __future__ import annotations

from sql_frage_katalog import SQL_FRAGETYPEN, WIKI_FRAGETYPEN

AUTO_MODUS_LABEL = "🎯 Auto (SQL → Web → MD → KI)"


def ist_offensichtliche_wiki_frage_kaskade(frage: str) -> bool:
    text = (frage or "").lower()
    for typ in WIKI_FRAGETYPEN:
        if any(signal in text for signal in typ["signale"]):
            return True
    return False


def ist_firmen_markt_frage(frage: str) -> bool:
    """Fragen, die strukturierte CRM-/Marktdaten erwarten (kein Wiki-RAG-Fallback)."""
    text = (frage or "").lower()
    if ist_offensichtliche_wiki_frage_kaskade(text):
        return False
    for typ in SQL_FRAGETYPEN:
        if any(signal in text for signal in typ["signale"]):
            return True
    return False


def erlaube_wiki_fallback(frage_typ: str, frage: str) -> bool:
    """Im Auto-Modus: Wiki nur, wenn es keine Firmen-/Markt-SQL-Frage ist."""
    if frage_typ != "datenbank":
        return False
    return not ist_firmen_markt_frage(frage)


def meldung_sql_leer(frage: str) -> str:
    if ist_firmen_markt_frage(frage):
        from firmen_live_recherche import ist_einzel_firma_live_web_frage

        if ist_einzel_firma_live_web_frage(frage):
            return (
                "In der CRM-Datenbank liegen zu dieser Firmenfrage keine Treffer.\n\n"
                "Bei **Einzel-Firmen** wird als Naechstes die **Live-Website** "
                "(Chrome/Playwright) versucht, danach ggf. das **MD-Archiv** (nur diese kundennumm)."
            )
        return (
            "In der CRM-Datenbank liegen keine Treffer.\n\n"
            "Produkt-/Marktlisten (z. B. „Wer stellt Hustensaft her?“) werden "
            "**nur per SQL** beantwortet — kein Live-Web, kein Wiki-Fallback."
        )
    return (
        "Keine Treffer in der Datenbank. "
        "Fuer dokumentbezogene Fragen den Modus **Wiki-Wissen** waehlen."
    )


def kaskaden_quellen_caption(frage_typ: str, quelle: str = "sql") -> str:
    if quelle == "sql":
        return "🗄️ Stufe 1: CRM-Datenbank (SQL)"
    if quelle == "web":
        return "🌐 Stufe 2: Live-Website"
    if quelle == "md":
        return "📄 Stufe 3: MD-Archiv (Fallback)"
    if quelle == "ki":
        return "✨ Stufe 4: KI-Synthese"
    if quelle == "wiki":
        return "🧠 Wiki-Dokumente"
    return quelle
