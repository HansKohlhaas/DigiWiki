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
    LIVE_WEB_HEADLESS,
    LIVE_WEB_MAX_CHARS,
    LIVE_WEB_MD_SPEICHERN,
    LIVE_WEB_PERSISTENT_PROFILE,
    LIVE_WEB_PFLEGE_PAUSE_S,
    LIVE_WEB_TIMEOUT_S,
    LIVE_WEB_TTL_DAYS,
    LIVE_WEB_USER_DATA_DIR,
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
MAX_IMPRESSUM_VERSUCHE_PFLEGE = 3
MAX_SEITEN_LADUNGEN = 6

_STORAGE_STATE_DATEI = LIVE_WEB_USER_DATA_DIR / "storage_state.json"


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
    personen_sync_fehler: str = ""
    personen_abgelehnt: int = 0


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


_URL_ROH_UNGUELTIG_RE = re.compile(r'[\s<>"\'|\\^\[\]{}`]')


def pruefe_url_fuer_live_web(roh: str) -> tuple[str, str]:
    """URL fuer Playwright aufbereiten; leer + Fehlermeldung bei Ungueltigkeit."""
    text = str(roh or "").strip().strip(".,;)]'\"")
    if not text or text.lower() in ("none", "nan", "-", "n/a", "keine", "null"):
        return "", "URL fehlt"

    lower = text.lower()
    if lower.startswith(("mailto:", "javascript:", "tel:", "ftp:", "file:")):
        return "", f"Keine Web-Adresse ({text.split(':', 1)[0]})"

    if _URL_ROH_UNGUELTIG_RE.search(text):
        return "", "URL enthaelt ungueltige Sonderzeichen (Leerzeichen, Anfuehrungszeichen o.ae.)"

    if "#" in text:
        vor_fragment = text.split("#", 1)[0].rstrip("/")
        probe = vor_fragment if lower.startswith(("http://", "https://")) else f"https://{vor_fragment.lstrip('/')}"
        if "#" in (urlparse(probe).netloc or ""):
            return "", "URL enthaelt # an ungueltiger Stelle"
        text = vor_fragment

    if not text.lower().startswith(("http://", "https://")):
        text = "https://" + text.lstrip("/")

    try:
        parsed = urlparse(text)
    except Exception:
        return "", "URL konnte nicht gelesen werden"

    if parsed.scheme not in ("http", "https"):
        return "", f"Nur http/https erlaubt (nicht {parsed.scheme})"

    netloc = (parsed.netloc or "").strip()
    if not netloc:
        return "", "URL ohne Hostname"

    host = netloc.rsplit("@", 1)[-1].split(":", 1)[0]
    if host.startswith(".") or host.endswith(".") or ".." in host:
        return "", "Hostname ungueltig"
    if not re.match(r"^[a-zA-Z0-9.\-]+$", host) and not re.match(
        r"^\d{1,3}(\.\d{1,3}){3}$", host
    ):
        return "", "Hostname enthaelt ungueltige Zeichen"
    if "." not in host and host.lower() != "localhost" and not re.match(
        r"^\d{1,3}(\.\d{1,3}){3}$", host
    ):
        return "", "Hostname ohne gueltige Domain"

    path = parsed.path or ""
    if "%" in path and re.search(r"%(?![0-9A-Fa-f]{2})", path):
        return "", "URL mit ungueltiger Kodierung"

    bereinigt = f"{parsed.scheme}://{netloc}{path}".rstrip("/")
    if parsed.query:
        bereinigt = f"{bereinigt}?{parsed.query}"
    return bereinigt, ""


def _normalisiere_url(roh: str) -> str:
    url, _ = pruefe_url_fuer_live_web(roh)
    return url


def _text_ist_cookie_wand(text: str) -> bool:
    t = (text or "").strip()
    if len(t) > 600:
        return False
    return bool(re.search(r"cookie|consent|datenschutz|einwilligung|privacy", t, re.I))


_BOT_BLOCK_RE = re.compile(
    r"cloudflare|captcha|recaptcha|hcaptcha|access denied|zugriff verweigert|"
    r"bot detected|automated access|security check|ddos protection|"
    r"ray id|please enable javascript|ungewöhnlichen traffic|unusual traffic|"
    r"nicht autorisiert|forbidden|403 forbidden",
    re.I,
)


def _text_ist_bot_block(text: str, titel: str = "") -> bool:
    probe = f"{titel}\n{text}".strip()[:4000]
    if not probe:
        return False
    if not _BOT_BLOCK_RE.search(probe):
        return False
    return len(probe) < 1200 or bool(
        re.search(r"cloudflare|captcha|recaptcha|hcaptcha|ray id|ddos", probe, re.I)
    )


class LiveWebBrowserSession:
    """Ein Chrome pro Datenbankpflege-Lauf – verhindert Profil-Neustarts in Endlosschleife."""

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self.cookie_domains: set[str] = set()

    @property
    def context(self) -> Any:
        return self._context

    def ensure_context(self) -> Any:
        if self._context is not None:
            return self._context
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser, self._context = _playwright_context_erstellen(self._playwright)
        return self._context

    def close(self) -> None:
        ctx, browser, pw = self._context, self._browser, self._playwright
        self._context = None
        self._browser = None
        self._playwright = None
        self.cookie_domains.clear()
        if ctx is not None:
            try:
                _playwright_storage_speichern(ctx)
            except Exception:
                pass
            try:
                for pg in list(ctx.pages):
                    try:
                        pg.close()
                    except Exception:
                        pass
                ctx.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if pw is not None:
            try:
                pw.stop()
            except Exception:
                pass


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


def _html_zu_text(html: str, legal_seite: bool = False) -> str:
    """Hauptinhalt extrahieren; bei Impressum/Legal Footer und Rechtstext behalten."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()

        if legal_seite:
            for tag in soup.find_all(class_=re.compile(r"cookie|consent|banner", re.I)):
                tag.decompose()
            root = None
            for sel in (
                "#impressum",
                ".impressum",
                ".legal",
                "#legal",
                "main",
                "[role=main]",
                "article",
                ".page-content",
                ".content",
                "#content",
            ):
                found = soup.select_one(sel)
                if found and len(found.get_text(strip=True)) > 30:
                    root = found
                    break
            if root is None:
                found = soup.find(class_=re.compile(r"impressum|legal-notice", re.I))
                if found and len(found.get_text(strip=True)) > 30:
                    root = found
            if root is None:
                found = soup.find(id=re.compile(r"impressum|legal", re.I))
                if found and len(found.get_text(strip=True)) > 30:
                    root = found
            if root is None:
                root = soup.body or soup
            text = root.get_text("\n", strip=True)
        else:
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


def _cookie_hinweis_wegklicken(page, gruendlich: bool = False) -> None:
    """Cookie-Banner per echtem Browser-Klick schliessen (kein HTTP-Request)."""
    labels = (
        "Alle akzeptieren",
        "Alles akzeptieren",
        "Allen zustimmen",
        "Akzeptieren und fortfahren",
        "Akzeptieren",
        "Zustimmen",
        "Einverstanden",
        "OK",
        "Verstanden",
        "Accept all cookies",
        "Accept all",
        "Accept All",
        "Accept",
        "I agree",
        "Agree",
        "Allow all",
        "Allow all cookies",
    )
    seiten = [page, *page.frames]
    durchlaeufe = 3 if gruendlich else 2
    for _ in range(durchlaeufe):
        for ziel in seiten:
            for label in labels:
                for rolle in ("button", "link"):
                    try:
                        btn = ziel.get_by_role(rolle, name=re.compile(re.escape(label), re.I))
                        if btn.count() > 0:
                            btn.first.click(timeout=2000)
                            page.wait_for_timeout(700)
                            return
                    except Exception:
                        continue
            for sel in (
                "#onetrust-accept-btn-handler",
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                "#CybotCookiebotDialogBodyButtonAccept",
                ".cc-btn-accept-all",
                ".cm-btn-primary",
                "[data-testid='uc-accept-all-button']",
                "button[id*='accept-all' i]",
                "button[class*='accept-all' i]",
                "a[class*='accept-all' i]",
                "[data-cookiefirst-action='accept']",
                "button[data-action='accept']",
                ".uc-btn-accept-all",
                "#cmpwelcomebtnyes a",
                "#cmpwelcomebtnyes",
            ):
                try:
                    loc = ziel.locator(sel)
                    if loc.count() > 0:
                        loc.first.click(timeout=2000)
                        page.wait_for_timeout(700)
                        return
                except Exception:
                    continue
        page.wait_for_timeout(1000 if gruendlich else 500)


def _playwright_storage_speichern(context) -> None:
    if not LIVE_WEB_PERSISTENT_PROFILE:
        return
    LIVE_WEB_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(_STORAGE_STATE_DATEI))


def _playwright_context_erstellen(playwright) -> tuple[Any, Any]:
    """Browser-Kontext; mit Profilordner wie echter Chrome (Cookies bleiben erhalten)."""
    channel = LIVE_WEB_BROWSER_CHANNEL if LIVE_WEB_BROWSER_CHANNEL.lower() != "chromium" else None
    launch_args: list[str] = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-restore-session-state",
        "--disable-session-crashed-bubble",
    ]
    init_script = (
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    common = {
        "headless": LIVE_WEB_HEADLESS,
        "locale": "de-DE",
        "timezone_id": "Europe/Berlin",
        "viewport": {"width": 1920, "height": 1080},
        "args": launch_args,
        "ignore_default_args": ["--enable-automation"],
    }

    if LIVE_WEB_PERSISTENT_PROFILE:
        LIVE_WEB_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        persistent_kwargs: dict[str, Any] = {
            **common,
            "user_data_dir": str(LIVE_WEB_USER_DATA_DIR),
        }
        if channel:
            persistent_kwargs["channel"] = channel
        context = playwright.chromium.launch_persistent_context(**persistent_kwargs)
        context.add_init_script(init_script)
        return None, context

    browser_kwargs: dict[str, Any] = {
        "headless": LIVE_WEB_HEADLESS,
        "args": launch_args,
    }
    if channel:
        browser_kwargs["channel"] = channel
    browser = playwright.chromium.launch(**browser_kwargs)

    context_kwargs: dict[str, Any] = {
        "locale": "de-DE",
        "timezone_id": "Europe/Berlin",
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "extra_http_headers": {"Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"},
    }
    if _STORAGE_STATE_DATEI.exists():
        context_kwargs["storage_state"] = str(_STORAGE_STATE_DATEI)

    context = browser.new_context(**context_kwargs)
    context.add_init_script(init_script)
    return browser, context


def _ist_legal_url(url: str) -> bool:
    return bool(re.search(r"impressum|imprint|legal|rechtliche", url or "", re.I))


def _pflege_impressum_einmal(
    page,
    start: str,
    session: LiveWebBrowserSession | None,
) -> tuple[str, list[str]]:
    """Datenbankpflege: maximal Startseite + ein Impressum, kein URL-Durchprobieren."""
    besucht: list[str] = []
    start = _normalisiere_url(start)
    if not start:
        return "", besucht

    text_start = _playwright_seite_laden(
        page, start, gruendlich=True, session=session, legal_seite=False
    )
    besucht.append(start)

    if FUEHRUNG_TEXT_RE.search(text_start) and len(text_start.strip()) >= 80:
        legal_text = _html_zu_text(page.content(), legal_seite=True)
        if len(legal_text.strip()) > len(text_start.strip()):
            return legal_text, besucht
        return text_start, besucht

    imp_url = ""
    try:
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        for href in hrefs or []:
            kandidat = _norm_seiten_url(start, href)
            if kandidat and IMPRESSUM_LINK_RE.search(kandidat):
                imp_url = kandidat
                break
    except Exception:
        pass

    if not imp_url:
        origin = f"{urlparse(start).scheme}://{urlparse(start).netloc}"
        imp_url = _norm_seiten_url(origin + "/", "/impressum")

    if imp_url and _url_schluessel(imp_url) != _url_schluessel(start):
        page.wait_for_timeout(1200)
        text_imp = _playwright_seite_laden(
            page, imp_url, gruendlich=True, session=session, legal_seite=True
        )
        besucht.append(imp_url)
        if len(text_imp.strip()) >= 40:
            return text_imp, besucht

    return _html_zu_text(page.content(), legal_seite=True) or text_start, besucht


def _playwright_seite_laden(
    page,
    url: str,
    gruendlich: bool = False,
    session: LiveWebBrowserSession | None = None,
    legal_seite: bool = False,
) -> str:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    cookies_bekannt = session is not None and domain in session.cookie_domains
    legal = legal_seite or _ist_legal_url(url)
    gruendlich_eff = gruendlich or not cookies_bekannt

    page.goto(url, wait_until="domcontentloaded", timeout=LIVE_WEB_TIMEOUT_S * 1000)
    page.wait_for_timeout(2200 if not cookies_bekannt else 1500)

    titel = ""
    try:
        titel = page.title() or ""
    except Exception:
        pass

    if not cookies_bekannt or gruendlich_eff:
        _cookie_hinweis_wegklicken(page, gruendlich=gruendlich_eff)
        if gruendlich_eff:
            page.wait_for_timeout(900)
            _cookie_hinweis_wegklicken(page, gruendlich=False)
    page.wait_for_timeout(800)

    text = _html_zu_text(page.content(), legal_seite=legal)
    if _text_ist_bot_block(text, titel):
        page.wait_for_timeout(2500)
        _cookie_hinweis_wegklicken(page, gruendlich=True)
        page.wait_for_timeout(1000)
        text = _html_zu_text(page.content(), legal_seite=legal)
    if session is not None and domain and not _text_ist_cookie_wand(text) and not _text_ist_bot_block(text, titel):
        session.cookie_domains.add(domain)
    return text


def _playwright_firmen_recherche(
    start_url: str,
    frage: str,
    gruendlich: bool = False,
    session: LiveWebBrowserSession | None = None,
) -> tuple[str, list[str]]:
    """Bei Fuehrungsfragen direkt Impressum; sonst Hauptinhalt der Startseite."""

    besuchte: list[str] = []
    besuchte_keys: set[str] = set()
    seiten: list[tuple[str, str]] = []
    fuehrung = ist_fuehrungs_frage(frage)
    seiten_ladungen = 0
    eigene_session: LiveWebBrowserSession | None = None

    def merke_besuch(url: str) -> bool:
        key = _url_schluessel(url)
        if key in besuchte_keys:
            return False
        besuchte_keys.add(key)
        besuchte.append(url)
        return True

    def seite_holen(page, url: str, titel: str) -> str | None:
        nonlocal seiten_ladungen
        if seiten_ladungen >= MAX_SEITEN_LADUNGEN:
            return None
        if not merke_besuch(url):
            return None
        seiten_ladungen += 1
        try:
            text = _playwright_seite_laden(
                page, url, gruendlich=gruendlich, session=session or eigene_session
            )
        except Exception:
            return None
        if len(text.strip()) < 40:
            return None
        seiten.append((titel, text))
        return text

    if session is not None:
        context = session.ensure_context()
    else:
        eigene_session = LiveWebBrowserSession()
        context = eigene_session.ensure_context()

    page = context.new_page()
    try:
        start = _normalisiere_url(start_url)

        if fuehrung and gruendlich:
            text, besucht_pflege = _pflege_impressum_einmal(
                page, start, session or eigene_session
            )
            besuchte.extend(besucht_pflege)
            if text and len(text.strip()) >= 40:
                seiten.append(
                    (f"Impressum ({besucht_pflege[-1] if besucht_pflege else start})", text)
                )
        elif fuehrung:
            impressum_liste = _impressum_kandidaten(start)
            if gruendlich:
                impressum_liste = impressum_liste[:MAX_IMPRESSUM_VERSUCHE_PFLEGE]

            gefunden: tuple[str, str] | None = None
            cookie_blockiert = False
            for ziel in impressum_liste:
                if seiten_ladungen >= MAX_SEITEN_LADUNGEN:
                    break
                if _url_schluessel(ziel) in besuchte_keys:
                    continue
                seiten_ladungen += 1
                merke_besuch(ziel)
                try:
                    text = _playwright_seite_laden(
                        page,
                        ziel,
                        gruendlich=gruendlich,
                        session=session or eigene_session,
                    )
                except Exception:
                    continue
                if _text_ist_cookie_wand(text):
                    cookie_blockiert = True
                    break
                if len(text.strip()) < 40:
                    continue
                if FUEHRUNG_TEXT_RE.search(text):
                    gefunden = (ziel, text)
                    break
                if gefunden is None:
                    gefunden = (ziel, text)

            if gefunden:
                seiten.append((f"Impressum ({gefunden[0]})", gefunden[1]))
            elif not cookie_blockiert and seiten_ladungen < MAX_SEITEN_LADUNGEN:
                if merke_besuch(start):
                    seiten_ladungen += 1
                    try:
                        page.goto(
                            start,
                            wait_until="domcontentloaded",
                            timeout=LIVE_WEB_TIMEOUT_S * 1000,
                        )
                        page.wait_for_timeout(1200)
                        _cookie_hinweis_wegklicken(page, gruendlich=gruendlich)
                        hrefs = page.eval_on_selector_all(
                            "a[href]", "els => els.map(e => e.href)"
                        )
                        for ziel in _sammle_seiten_links(start, hrefs, frage):
                            if seiten_ladungen >= MAX_SEITEN_LADUNGEN:
                                break
                            if _url_schluessel(ziel) in besuchte_keys:
                                continue
                            seiten_ladungen += 1
                            merke_besuch(ziel)
                            try:
                                text = _playwright_seite_laden(
                                    page,
                                    ziel,
                                    gruendlich=gruendlich,
                                    session=session or eigene_session,
                                )
                            except Exception:
                                continue
                            if len(text.strip()) < 40:
                                continue
                            seiten.append((f"Impressum ({ziel})", text))
                            break
                    except Exception:
                        pass
        else:
            seite_holen(page, start, f"Startseite ({start})")
    finally:
        try:
            page.close()
        except Exception:
            pass
        if eigene_session is not None:
            eigene_session.close()

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
    force: bool = False,
    sync_quelle: str | None = None,
    sync_validation: str | None = None,
    firmenname: str = "",
) -> tuple[int, int, int, list[dict[str, str]], str, int]:
    if not LIVE_WEB_CRM_SYNC:
        return 0, 0, 0, [], "", 0
    if not force and not ist_fuehrungs_frage(frage):
        return 0, 0, 0, [], "", 0
    from firmen_live_personen import (
        bereinige_und_pruefe_personen,
        extrahiere_fuehrung_personen,
        sync_nach_crm_personen,
    )

    roh = extrahiere_fuehrung_personen(text)
    pruef = bereinige_und_pruefe_personen(roh, text, firmenname)
    personen = pruef.personen
    if not personen:
        if roh:
            hinweis = "; ".join(pruef.hinweise[:2]) or (
                f"{pruef.abgelehnt} Kandidat(en) nicht plausibel"
            )
            return 0, 0, 0, [], f"Plausibilitaet: {hinweis}", pruef.abgelehnt
        return 0, 0, 0, [], "", 0
    basis = sync_quelle or "DigiWiki-LiveWeb"
    validation = sync_validation or "auto_web"
    if pruef.ki_verwendet and validation == "auto_ki":
        validation = "ki_plausibel"
    sync = sync_nach_crm_personen(
        kundennumm,
        personen,
        quelle_url=url,
        update_status_basis=basis,
        validation_status=validation,
    )
    if not sync.ok:
        return 0, 0, 0, [], sync.fehler or "CRM-Sync fehlgeschlagen", pruef.abgelehnt
    return (
        sync.neu,
        sync.vorhanden,
        sync.aktualisiert,
        sync.personen,
        "",
        pruef.abgelehnt,
    )


def firmen_live_recherche(
    frage: str,
    kundennumm: str | None = None,
    firmenname: str | None = None,
    url: str | None = None,
    md_speichern: bool | None = None,
    force_pflege: bool = False,
    sync_quelle: str | None = None,
    sync_validation: str | None = None,
    browser_session: LiveWebBrowserSession | None = None,
) -> LiveWebErgebnis:
    if not force_pflege and not ist_einzel_firma_live_web_frage(frage):
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

    roh_url = url or ""
    url, url_fehler = pruefe_url_fuer_live_web(roh_url)
    if not url:
        return LiveWebErgebnis(
            ok=False,
            kundennumm=kundennumm or "",
            firmenname=firmenname or "",
            fehler=url_fehler or "Keine gueltige Website-URL in CRM hinterlegt.",
        )

    cache = _lade_cache()
    cache_modus = "pflege_v1" if force_pflege else (
        "fuehrung_v3" if ist_fuehrungs_frage(frage) else "basis_v2"
    )
    key = f"{kundennumm or url}:{cache_modus}"
    if not force_pflege and key in cache and _cache_fresh(cache[key]):
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
        text, besuchte_urls = _playwright_firmen_recherche(
            url,
            frage,
            gruendlich=force_pflege,
            session=browser_session,
        )
    except ImportError:
        return LiveWebErgebnis(
            ok=False,
            fehler="Playwright fehlt. In .venv: pip install playwright && playwright install chrome",
        )
    except Exception as e:
        return LiveWebErgebnis(ok=False, url=url, firmenname=firmenname or "", fehler=str(e))

    if not text or len(text) < 80:
        hinweis = "Website lieferte zu wenig lesbaren Text"
        if text and (
            re.search(r"cookie|consent|datenschutz|einwilligung", text, re.I)
            or _text_ist_bot_block(text)
        ):
            profil_hinweis = ""
            if LIVE_WEB_PERSISTENT_PROFILE:
                profil_hinweis = (
                    f" Tipp: DIGIWIKI_LIVE_WEB_HEADLESS=false in .env, einmal Cookies "
                    f"im sichtbaren Chrome bestaetigen (Profil: {LIVE_WEB_USER_DATA_DIR})."
                )
            if _text_ist_bot_block(text):
                hinweis = (
                    "Seite blockiert automatisierten Zugriff (Bot-Schutz/Cloudflare)."
                    f"{profil_hinweis}"
                )
            else:
                hinweis = f"Cookie-Wand blockiert Inhalt (Playwright/Chrome).{profil_hinweis}"
        return LiveWebErgebnis(
            ok=False,
            url=url,
            firmenname=firmenname or "",
            fehler=f"{hinweis} (Cookie-Wall oder Block).",
        )

    if (
        not force_pflege
        and ist_fuehrungs_frage(frage)
        and not FUEHRUNG_TEXT_RE.search(text)
    ):
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

    personen_neu, personen_vorhanden, personen_aktualisiert, personen_liste, sync_fehler, abgelehnt = (
        _sync_fuehrung_personen(
            kundennumm or "",
            text,
            url,
            frage,
            force=force_pflege,
            sync_quelle=sync_quelle,
            sync_validation=sync_validation,
            firmenname=firmenname or "",
        )
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
        personen_sync_fehler=sync_fehler,
        personen_abgelehnt=abgelehnt,
    )
