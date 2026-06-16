import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _env_path(name: str, default: str) -> Path:
    value = os.getenv(name, default).strip()
    return Path(value).expanduser()


def _env_paths(name: str, defaults: list[str]) -> list[Path]:
    raw_value = os.getenv(name, "").strip()
    if raw_value:
        parts = [part.strip().strip('"') for part in raw_value.replace("\n", ";").split(";")]
        return [Path(part).expanduser() for part in parts if part]
    return [Path(default).expanduser() for default in defaults]


ACCESS_DB_PATH = _env_path("DIGIWIKI_ACCESS_DB", r"C:\CodexProjekte\FirmenApp\Digibest_Master.accdb")
CHROMA_DB_PATH = _env_path("DIGIWIKI_CHROMA_DB", str(BASE_DIR / "Chroma_DB"))
WATCH_ROOTS = _env_paths(
    "DIGIWIKI_WATCH_ROOTS",
    [r"C:\Eigene Projekte", r"C:\Verwaltung"],
)
WATCH_STATE_PATH = BASE_DIR / "wiki_stand.json"
WATCH_MANIFEST_PATH = BASE_DIR / "wiki_manifest.json"
WATCH_QUARANTINE_PATH = BASE_DIR / "wiki_quarantaene.json"
WATCH_SNAPSHOT_PATH = BASE_DIR / "wiki_schicht_snapshot.json"
WATCH_MANIFEST_VERSION = 2
WATCH_MAX_FILE_MB = float(os.getenv("DIGIWIKI_MAX_FILE_MB", "5.0"))
WATCH_BATCH_SIZE = int(os.getenv("DIGIWIKI_BATCH_SIZE", "100"))
WATCH_RETRY_COUNT = int(os.getenv("DIGIWIKI_RETRY_COUNT", "5"))
WATCH_RETRY_DELAY_SECONDS = int(os.getenv("DIGIWIKI_RETRY_DELAY_SECONDS", "60"))
WATCH_RELEVANTE_ENDUNGEN = (".txt", ".md", ".pdf", ".docx", ".csv")
WATCH_TEXT_ENCODINGS = ("utf-8", "cp1252")
SCHEMA_PATH = BASE_DIR / "db_schema.txt"
DICTIONARY_PATH = BASE_DIR / "data_dictionary.csv"
MAIL_DOWNLOAD_DIR = BASE_DIR / "Mail_Downloads"
MAIL_UPLOAD_DIR = BASE_DIR / "Mail_Uploads"
STREAMLIT_HOST = os.getenv("DIGIWIKI_STREAMLIT_HOST", "0.0.0.0")
STREAMLIT_PORT = int(os.getenv("DIGIWIKI_STREAMLIT_PORT", "8501"))
API_HOST = os.getenv("DIGIWIKI_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("DIGIWIKI_API_PORT", "8000"))
WHATSAPP_DEFAULT_COUNTRY_CODE = os.getenv("DIGIWIKI_WHATSAPP_DEFAULT_COUNTRY_CODE", "49")
WHATSAPP_CLOUD_API_TOKEN = os.getenv("DIGIWIKI_WHATSAPP_CLOUD_API_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID = os.getenv("DIGIWIKI_WHATSAPP_PHONE_NUMBER_ID", "").strip()
WHATSAPP_CLOUD_API_VERSION = os.getenv("DIGIWIKI_WHATSAPP_CLOUD_API_VERSION", "v19.0")


def chroma_db_path_str() -> str:
    """ASCII-sicherer Pfad zur Chroma-DB fuer chromadb 1.x.

    Der Rust-basierte HNSW-Reader von chromadb >=1.x kann einen Index NICHT aus
    einem Pfad mit Nicht-ASCII-Zeichen laden (hier das 'ue' in 'Makrouebungen').
    Die SQLite-Metadaten funktionieren zwar, aber das Laden des HNSW-Index schlaegt
    mit 'Error loading hnsw index' fehl. Auf Windows weichen wir daher auf den
    8.3-Kurzpfad (rein ASCII) aus; sonst bleibt es beim Originalpfad.
    """
    pfad = str(CHROMA_DB_PATH)
    if os.name == "nt" and not pfad.isascii():
        try:
            import ctypes

            puffer = ctypes.create_unicode_buffer(4096)
            laenge = ctypes.windll.kernel32.GetShortPathNameW(pfad, puffer, 4096)
            if laenge and puffer.value and puffer.value.isascii():
                return puffer.value
        except Exception:
            pass
    return pfad


WISSENSBEREICHE = {
    "vollzugriff": {
        "beschreibung": "Gesamte Wissensbasis ohne Filter",
        "keywords": [],
    },
    "verfahren": {
        "beschreibung": "Verfahren, Abläufe, Leitfäden, Arbeitsanweisungen",
        "keywords": ["verfahren", "prozess", "ablauf", "workflow", "arbeitsanweisung", "leitfaden", "checkliste", "handbuch"],
    },
    "formulare": {
        "beschreibung": "Tabellen, Vorlagen, Muster und Master",
        "keywords": ["formular", "vorlage", "muster", "mustervorlage", "antrag", "template"],
    },
    "vertraege": {
        "beschreibung": "Verträge, Vereinbarungen, AGB und rechtliche Dokumente",
        "keywords": ["vertrag", "vertraeg", "vereinbarung", "nda", "agb", "lizenz", "datenschutz"],
    },
    "datenbank": {
        "beschreibung": "Datenbankinhalte, Strukturen, Exporte, Schemas und SQL",
        "keywords": ["datenbank", "schema", "sql", "access", "export", "struktur", "csv", "postgres", "db"],
    },
    "aktuell": {
        "beschreibung": "Aktuelle Stände, Reports, Protokolle und Statusinfos",
        "keywords": ["aktuell", "gewicht", "stand", "report", "protokoll", "snapshot", "arbeitskalender"],
    },
}


def normalisiere_text(text: str) -> str:
    return str(text or "").replace("\\", "/").lower()


def liste_wissensbereiche() -> list[str]:
    return list(WISSENSBEREICHE.keys())


def ist_gueltiger_wissensbereich(name: str | None) -> bool:
    return name in WISSENSBEREICHE


def ermittle_wissensbereich(pfad: str, dateiname: str | None = None) -> str:
    text = f"{normalisiere_text(pfad)} {normalisiere_text(dateiname)}"
    for bereich, daten in WISSENSBEREICHE.items():
        if bereich == "vollzugriff":
            continue
        if any(keyword in text for keyword in daten["keywords"]):
            return bereich
    return "vollzugriff"


def ist_beobachtete_datei(dateiname: str) -> bool:
    return dateiname.lower().endswith(WATCH_RELEVANTE_ENDUNGEN)