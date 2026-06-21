"""Stufe 2: Live-Website-Recherche fuer EINZEL-Firmen (Playwright + installierter Chrome).

Kein Einsatz bei Produkt-/Marktlisten ('Wer stellt Hustensaft her?' -> nur SQL).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import pyodbc

from config import (
    ACCESS_DB_PATH,
    LIVE_WEB_BROWSER_CHANNEL,
    LIVE_WEB_CACHE_PATH,
    LIVE_WEB_CRM_SYNC,
    LIVE_WEB_ENABLED,
    LIVE_WEB_MAX_CHARS,
    LIVE_WEB_MD_SPEICHERN,
    LIVE_WEB_TIMEOUT_S,
    LIVE_WEB_TTL_DAYS,
    MD_LIVE_DIR,
)
from sql_frage_katalog import firma_vollname_expr

# Mehrfirmen-/Produktsuche -> SQL (abdaartikel), kein Live-Web
PRODUKT_MARKT_LISTEN_SIGNALE = (
    "wer stellt",
    "wer produziert",
    "wer vertreibt",
    "welche hersteller",
    "welche firmen",
    "liste der",
    "alle hersteller",
    "marktuebersicht",
    "marktübersicht",
    "branchenuebersicht",
    "branchenübersicht",
    "top 10",
    "top ten",
)

EINZEL_FIRMA_KONTEXT = (
    " bei ",
    " von ",
    " für ",
    " firma ",
    " unternehmen ",
    " ag",
    " gmbh",
    " se",
)

# Bei Fuehrungsfragen zusaetzlich Impressum / Legal-Seiten laden
FUEHRUNG_FRAGEN_SIGNALE = (
    "geschäftsf",
    "geschaeftsf",
    " gf ",
    "vorstand",
    "vorständ",
    "vorstaend",
    "ceo",
    "management",
    "wer leitet",
    "wer führt",
    "wer fuehrt",
    "aufsichtsrat",
)

IMPRESSUM_LINK_RE = re.compile(
    r"impressum|imprint|legal-notice|rechtliche[\-_]?hinweise|/legal(?:/|$)",
    re.I,
)
FUEHRUNG_LINK_RE = re.compile(
    r"vorstand|geschäftsf|geschaeftsf|management|leadership|fuehrung|führung|executive",
    re.I,
)
FUEHRUNG_TEXT_RE = re.compile(
    r"vorstand|geschäftsf|geschaeftsf|management board|executive board|"
    r"vertretungsberechtigt|handelsregister",
    re.I,
)

IMPRESSUM_PFAD_VERSUCHE = (
    "/impressum",
    "/Impressum",
    "/de/impressum",
    "/legal/impressum",
    "/unternehmen/impressum",
)

MAX_ZUSATZ_SEITEN = 2


@dataclass
class LiveWebErgebnis:
    ok: bool
    kundennumm: str = ""
    firmenname: str = ""
    url: str = ""
    text: str = ""
    md_pfad: str = ""
    aus_cache: bool = False
    fehler: str = ""
    personen_neu: int = 0
    personen_vorhanden: int = 0
    personen_aktualisiert: int = 0
    personen_liste: list[dict[str, str]] | None = None


def ist_produkt_markt_liste_frage(frage: str) -> bool:
    text = f" {(frage or '').lower()} "
    if not any(signal in text for signal in PRODUKT_MARKT_LISTEN_SIGNALE):
        return False
    return not any(ctx in text for ctx in EINZEL_FIRMA_KONTEXT)


def ist_einzel_firma_live_web_frage(frage: str) -> bool:
    """Live-Web nur bei klarer Einzel-Firmenfrage, nicht bei Hustensaft & Co."""
    from wissens_kaskade import ist_firmen_markt_frage

    if not LIVE_WEB_ENABLED:
        return False
    if not ist_firmen_markt_frage(frage):
        return False
    if ist_produkt_markt_liste_frage(frage):
        return False
    return True


def extrahiere_firmen_suchbegriff(frage: str) -> str | None:
    text = (frage or "").strip()
    if not text:
        return None
    m = re.search(
        r"(?:bei|von|für|firma|unternehmen)\s+([A-Za-zÄÖÜäöüß0-9][\w\s\-\.&\+]{1,60}?)"
        r"(?:\?|$|\s+(?:mit|und|in|hat|ist|sind|gibt|zeige|narrativ|website|gf|geschäftsf))",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(" .,-")
    m = re.search(
        r"(?:narrativ|briefing|website|sortiment|top[\-\s]?produkte|d2p|marktzielgruppe)\s+(?:von|bei)\s+(\S.+?)\?",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(" .,-")
    return None


def _normalisiere_url(roh: str) -> str:
    url = (roh or "").strip()
    if not url:
        return ""
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    return url


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE)
    return re.sub(r"_+", "_", s).strip("_")[:60] or "firma"


def _lade_cache() -> dict[str, Any]:
    if not LIVE_WEB_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(LIVE_WEB_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _speichere_cache(daten: dict[str, Any]) -> None:
    LIVE_WEB_CACHE_PATH.write_text(
        json.dumps(daten, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _cache_fresh(eintrag: dict[str, Any]) -> bool:
    ts = eintrag.get("abgerufen_am")
    if not ts:
        return False
    try:
        zeit = datetime.fromisoformat(ts)
    except ValueError:
        return False
    return datetime.now() - zeit < timedelta(days=LIVE_WEB_TTL_DAYS)


def suche_firma_in_db(suchbegriff: str) -> dict[str, str] | None:
    if not suchbegriff or not Path(ACCESS_DB_PATH).exists():
        return None
    like = f"%{suchbegriff.replace('*', '').replace('%', '')}%"
    voll = firma_vollname_expr()
    sql = (
        "SELECT TOP 1 kundennumm, nama, nameb, "
        "aktuelle_haupt_url, internetadresse, gl_web "
        "FROM stammdatenindustrie "
        f"WHERE {voll} LIKE ? OR nama LIKE ? OR nameb LIKE ? "
        "ORDER BY nama"
    )
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    try:
        conn = pyodbc.connect(conn_str, timeout=8)
        try:
            cur = conn.cursor()
            cur.execute(sql, (like, like, like))
            row = cur.fetchone()
            if not row:
                return None
            url = _normalisiere_url(
                row.aktuelle_haupt_url or row.internetadresse or row.gl_web
            )
            voller_name = " ".join(
                p for p in (str(row.nama or "").strip(), str(row.nameb or "").strip()) if p
            )
            return {
                "kundennumm": str(row.kundennumm or "").strip(),
                "firmenname": voller_name or suchbegriff,
                "url": url,
            }
        finally:
            conn.close()
    except Exception:
        return None


def _html_zu_text(html: str) -> str:
    """Hauptinhalt extrahieren – ohne Navigation, Header, Footer, Cookie-Banner."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()
        for tag in soup(["nav", "header", "footer", "aside"]):
            tag.decompose()
        for tag in soup.find_all(
            attrs={"role": re.compile(r"navigation|banner|contentinfo", re.I)}
        ):
            tag.decompose()
        for tag in soup.find_all(
            class_=re.compile(
                r"nav|menu|footer|header|cookie|consent|banner|breadcrumb|"
                r"sidebar|skip-link|megamenu|site-header|site-footer",
                re.I,
            )
        ):
            tag.decompose()

        root = None
        for sel in (
            "main",
            "[role=main]",
            "article",
            ".main",
            "#main",
            ".page-content",
            ".content",
            "#content",
            ".richtext",
        ):
            found = soup.select_one(sel)
            if found and len(found.get_text(strip=True)) > 60:
                root = found
                break
        if root is None:
            root = soup.body or soup

        text = root.get_text("\n", strip=True)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    return _bereinige_text(text)


def _bereinige_text(text: str) -> str:
    """Doppelte Menuezeilen und leeren Ballast entfernen."""
    lines = [ln.strip() for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if ln]

    ohne_folge_duplikate: list[str] = []
    prev = None
    for ln in lines:
        if ln == prev:
            continue
        ohne_folge_duplikate.append(ln)
        prev = ln

    from collections import Counter

    haeufigkeit = Counter(ohne_folge_duplikate)
    gefiltert: list[str] = []
    for ln in ohne_folge_duplikate:
        if haeufigkeit[ln] >= 3 and len(ln) <= 45 and ":" not in ln:
            continue
        gefiltert.append(ln)

    text = "\n".join(gefiltert)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:LIVE_WEB_MAX_CHARS]


def ist_fuehrungs_frage(frage: str) -> bool:
    text = f" {(frage or '').lower()} "
    return any(signal in text for signal in FUEHRUNG_FRAGEN_SIGNALE)


def _gleiche_domain(basis_url: str, kandidat: str) -> bool:
    b = urlparse(basis_url).netloc.lower().removeprefix("www.")
    k = urlparse(kandidat).netloc.lower().removeprefix("www.")
    return bool(b and k and b == k)


def _norm_seiten_url(basis_url: str, href: str) -> str:
    url = _normalisiere_url(urljoin(basis_url, (href or "").strip()))
    if not _gleiche_domain(basis_url, url):
        return ""
    return url.split("#", 1)[0].rstrip("/") or url


def _url_schluessel(url: str) -> str:
    p = urlparse((url or "").lower())
    netloc = p.netloc.removeprefix("www.")
    path = p.path.rstrip("/") or "/"
    return f"{netloc}{path}"


def _uniq_urls(urls: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if not url:
            continue
        key = _url_schluessel(url)
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
    return out


def _impressum_kandidaten(basis_url: str, hrefs: list[str] | None = None) -> list[str]:
    impressum: list[str] = []
    for href in hrefs or []:
        url = _norm_seiten_url(basis_url, href)
        if url and IMPRESSUM_LINK_RE.search(url):
            impressum.append(url)
    origin = f"{urlparse(basis_url).scheme}://{urlparse(basis_url).netloc}"
    for pfad in IMPRESSUM_PFAD_VERSUCHE:
        impressum.append(_norm_seiten_url(origin + "/", pfad))
    return _uniq_urls(impressum)


def _sammle_seiten_links(basis_url: str, hrefs: list[str], frage: str) -> list[str]:
    """Impressum und ggf. Fuehrungs-Unterseiten aus Linkliste priorisieren."""
    if not ist_fuehrungs_frage(frage):
        return []

    impressum = _impressum_kandidaten(basis_url, hrefs)
    fuehrung: list[str] = []
    for href in hrefs:
        url = _norm_seiten_url(basis_url, href)
        if not url:
            continue
        if FUEHRUNG_LINK_RE.search(url) and not IMPRESSUM_LINK_RE.search(url):
            fuehrung.append(url)

    return _uniq_urls(impressum + fuehrung)[:MAX_ZUSATZ_SEITEN]


def _kombiniere_seiten_texte(seiten: list[tuple[str, str]]) -> str:
    teile: list[str] = []
    gesamt = 0
    for titel, text in seiten:
        block = f"## {titel}\n\n{text.strip()}\n"
        if gesamt + len(block) > LIVE_WEB_MAX_CHARS:
            rest = LIVE_WEB_MAX_CHARS - gesamt
            if rest > 500:
                teile.append(block[:rest] + "\n\n[… gekürzt …]")
            break
        teile.append(block)
        gesamt += len(block)
    return "\n".join(teile).strip()


def _cookie_hinweis_wegklicken(page) -> None:
    for label in (
        "Alle akzeptieren",
        "Alles akzeptieren",
        "Akzeptieren",
        "Zustimmen",
        "Accept all",
        "Accept",
    ):
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(label), re.I))
            if btn.count() > 0:
                btn.first.click(timeout=1200)
                page.wait_for_timeout(400)
                return
        except Exception:
            continue


def _playwright_seite_laden(page, url: str) -> str:
    page.goto(url, wait_until="domcontentloaded", timeout=LIVE_WEB_TIMEOUT_S * 1000)
    page.wait_for_timeout(1500)
    _cookie_hinweis_wegklicken(page)
    page.wait_for_timeout(800)
    return _html_zu_text(page.content())


def _playwright_firmen_recherche(start_url: str, frage: str) -> tuple[str, list[str]]:
    """Bei Fuehrungsfragen direkt Impressum; sonst Hauptinhalt der Startseite."""
    from playwright.sync_api import sync_playwright

    channel = LIVE_WEB_BROWSER_CHANNEL if LIVE_WEB_BROWSER_CHANNEL.lower() != "chromium" else None
    besuchte: list[str] = []
    besuchte_keys: set[str] = set()
    seiten: list[tuple[str, str]] = []
    fuehrung = ist_fuehrungs_frage(frage)

    def merke_besuch(url: str) -> bool:
        key = _url_schluessel(url)
        if key in besuchte_keys:
            return False
        besuchte_keys.add(key)
        besuchte.append(url)
        return True

    def seite_holen(page, url: str, titel: str) -> str | None:
        if not merke_besuch(url):
            return None
        try:
            text = _playwright_seite_laden(page, url)
        except Exception:
            return None
        if len(text.strip()) < 40:
            return None
        seiten.append((titel, text))
        return text

    with sync_playwright() as p:
        launch_args: dict[str, Any] = {"headless": True}
        if channel:
            launch_args["channel"] = channel
        browser = p.chromium.launch(**launch_args)
        try:
            context = browser.new_context(
                locale="de-DE",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            start = _normalisiere_url(start_url)

            if fuehrung:
                gefunden: tuple[str, str] | None = None
                for ziel in _impressum_kandidaten(start):
                    if _url_schluessel(ziel) in besuchte_keys:
                        continue
                    try:
                        text = _playwright_seite_laden(page, ziel)
                        merke_besuch(ziel)
                    except Exception:
                        continue
                    if len(text.strip()) < 40:
                        continue
                    if FUEHRUNG_TEXT_RE.search(text):
                        gefunden = (ziel, text)
                        break
                    if gefunden is None:
                        gefunden = (ziel, text)
                if gefunden:
                    seiten.append((f"Impressum ({gefunden[0]})", gefunden[1]))
                else:
                    merke_besuch(start)
                    page.goto(start, wait_until="domcontentloaded", timeout=LIVE_WEB_TIMEOUT_S * 1000)
                    page.wait_for_timeout(1500)
                    _cookie_hinweis_wegklicken(page)
                    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                    for ziel in _sammle_seiten_links(start, hrefs, frage):
                        if _url_schluessel(ziel) in besuchte_keys:
                            continue
                        try:
                            text = _playwright_seite_laden(page, ziel)
                            merke_besuch(ziel)
                        except Exception:
                            continue
                        if len(text.strip()) < 40:
                            continue
                        seiten.append((f"Impressum ({ziel})", text))
                        break
            else:
                seite_holen(page, start, f"Startseite ({start})")

            context.close()
        finally:
            browser.close()

    return _kombiniere_seiten_texte(seiten), besuchte


def speichere_live_md(
    kundennumm: str,
    firmenname: str,
    url: str,
    text: str,
    frage: str,
    besuchte_urls: list[str] | None = None,
) -> Path:
    MD_LIVE_DIR.mkdir(parents=True, exist_ok=True)
    datum = datetime.now().strftime("%Y-%m-%d")
    dateiname = f"{kundennumm}_{_slug(firmenname)}_live_{datum}.md"
    pfad = MD_LIVE_DIR / dateiname
    host = urlparse(url).netloc or url
    seiten_zeile = ""
    if besuchte_urls and len(besuchte_urls) > 1:
        seiten_zeile = f"- **seiten:** {', '.join(besuchte_urls)}\n"
    inhalt = (
        f"# Live-Snapshot: {firmenname}\n\n"
        f"- **kundennumm:** {kundennumm}\n"
        f"- **url:** {url}\n"
        f"- **host:** {host}\n"
        f"{seiten_zeile}"
        f"- **abgerufen:** {datetime.now().isoformat(timespec='seconds')}\n"
        f"- **frage:** {frage}\n"
        f"- **quelle:** Live-Web (Playwright / {LIVE_WEB_BROWSER_CHANNEL})\n\n"
        f"---\n\n"
        f"{text}\n"
    )
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad


def _sync_fuehrung_personen(
    kundennumm: str,
    text: str,
    url: str,
    frage: str,
) -> tuple[int, int, int, list[dict[str, str]]]:
    if not LIVE_WEB_CRM_SYNC or not ist_fuehrungs_frage(frage):
        return 0, 0, 0, []
    from firmen_live_personen import extrahiere_fuehrung_personen, sync_nach_crm_personen

    personen = extrahiere_fuehrung_personen(text)
    if not personen:
        return 0, 0, 0, []
    sync = sync_nach_crm_personen(kundennumm, personen, quelle_url=url)
    if not sync.ok:
        return 0, 0, 0, []
    return sync.neu, sync.vorhanden, sync.aktualisiert, sync.personen


def firmen_live_recherche(
    frage: str,
    kundennumm: str | None = None,
    firmenname: str | None = None,
    url: str | None = None,
    md_speichern: bool | None = None,
) -> LiveWebErgebnis:
    if not ist_einzel_firma_live_web_frage(frage):
        return LiveWebErgebnis(ok=False, fehler="Keine Einzel-Firmen-Live-Web-Frage.")

    if md_speichern is None:
        md_speichern = LIVE_WEB_MD_SPEICHERN

    if not kundennumm or not url:
        such = firmenname or extrahiere_firmen_suchbegriff(frage)
        if not such:
            return LiveWebErgebnis(ok=False, fehler="Kein Firmenname erkennbar.")
        db = suche_firma_in_db(such)
        if not db:
            return LiveWebErgebnis(ok=False, fehler=f"Firma nicht in CRM: {such}")
        kundennumm = db["kundennumm"]
        firmenname = db["firmenname"]
        url = db["url"]

    url = _normalisiere_url(url or "")
    if not url:
        return LiveWebErgebnis(
            ok=False,
            kundennumm=kundennumm or "",
            firmenname=firmenname or "",
            fehler="Keine Website-URL in CRM hinterlegt.",
        )

    cache = _lade_cache()
    cache_modus = "fuehrung_v3" if ist_fuehrungs_frage(frage) else "basis_v2"
    key = f"{kundennumm or url}:{cache_modus}"
    if key in cache and _cache_fresh(cache[key]):
        eintrag = cache[key]
        return LiveWebErgebnis(
            ok=True,
            kundennumm=kundennumm or "",
            firmenname=firmenname or eintrag.get("firmenname", ""),
            url=eintrag.get("url", url),
            text=eintrag.get("text", ""),
            md_pfad=eintrag.get("md_pfad", ""),
            aus_cache=True,
            personen_neu=eintrag.get("personen_neu", 0),
            personen_vorhanden=eintrag.get("personen_vorhanden", 0),
            personen_aktualisiert=eintrag.get("personen_aktualisiert", 0),
            personen_liste=eintrag.get("personen_liste") or [],
        )

    try:
        text, besuchte_urls = _playwright_firmen_recherche(url, frage)
    except ImportError:
        return LiveWebErgebnis(
            ok=False,
            fehler="Playwright fehlt. In .venv: pip install playwright && playwright install chrome",
        )
    except Exception as e:
        return LiveWebErgebnis(ok=False, url=url, firmenname=firmenname or "", fehler=str(e))

    if not text or len(text) < 80:
        return LiveWebErgebnis(
            ok=False,
            url=url,
            firmenname=firmenname or "",
            fehler="Website lieferte zu wenig lesbaren Text (Cookie-Wall oder Block).",
        )

    if ist_fuehrungs_frage(frage) and not FUEHRUNG_TEXT_RE.search(text):
        return LiveWebErgebnis(
            ok=False,
            url=url,
            firmenname=firmenname or "",
            text=text,
            fehler="Impressum/Fuehrungsseite ohne Vorstand/GF-Angaben gefunden.",
        )

    md_pfad = ""
    if md_speichern and kundennumm:
        md_pfad = str(
            speichere_live_md(
                kundennumm,
                firmenname or "",
                url,
                text,
                frage,
                besuchte_urls=besuchte_urls,
            )
        )

    personen_neu, personen_vorhanden, personen_aktualisiert, personen_liste = (
        _sync_fuehrung_personen(kundennumm or "", text, url, frage)
    )

    cache[key] = {
        "kundennumm": kundennumm,
        "firmenname": firmenname,
        "url": url,
        "besuchte_urls": besuchte_urls,
        "text": text,
        "md_pfad": md_pfad,
        "personen_neu": personen_neu,
        "personen_vorhanden": personen_vorhanden,
        "personen_aktualisiert": personen_aktualisiert,
        "personen_liste": personen_liste,
        "abgerufen_am": datetime.now().isoformat(timespec="seconds"),
    }
    _speichere_cache(cache)

    return LiveWebErgebnis(
        ok=True,
        kundennumm=kundennumm or "",
        firmenname=firmenname or "",
        url=url,
        text=text,
        md_pfad=md_pfad,
        personen_neu=personen_neu,
        personen_vorhanden=personen_vorhanden,
        personen_aktualisiert=personen_aktualisiert,
        personen_liste=personen_liste,
    )
