import streamlit as st

from dotenv import load_dotenv

load_dotenv()

# ==========================================
# SINGLE-SESSION-TAKEOVER (optional, standard: AUS)
# Nur aktiv wenn DIGIWIKI_SINGLE_SESSION=true in .env
# ==========================================
import os as _os
import uuid as _uuid
import tempfile as _tempfile

from config import SINGLE_SESSION_TAKEOVER

_AKTIVE_SESSION_DATEI = _os.path.join(_tempfile.gettempdir(), "digiwiki_active_session.token")


def _eigene_session_id():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        return ctx.session_id if ctx else None
    except Exception:
        return None


def _beende_andere_sessions(eigene_id):
    """Beendet best effort alle anderen aktiven Streamlit-Sessions sofort."""
    try:
        from streamlit.runtime import get_instance
        rt = get_instance()
        for info in list(rt._session_mgr.list_active_sessions()):
            sid = info.session.id
            if eigene_id and sid != eigene_id:
                rt.close_session(sid)
    except Exception:
        pass


def _aktives_token_lesen():
    try:
        with open(_AKTIVE_SESSION_DATEI, "r", encoding="ascii") as f:
            return f.read().strip()
    except OSError:
        return ""


def _aktives_token_schreiben(token):
    try:
        with open(_AKTIVE_SESSION_DATEI, "w", encoding="ascii") as f:
            f.write(token)
    except OSError:
        pass


if SINGLE_SESSION_TAKEOVER:
    if "session_token" not in st.session_state:
        st.session_state.session_token = _uuid.uuid4().hex
        _beende_andere_sessions(_eigene_session_id())
        _aktives_token_schreiben(st.session_state.session_token)
    elif _aktives_token_lesen() not in ("", st.session_state.session_token):
        st.session_state.clear()
        st.warning(
            "Diese Sitzung wurde in einem anderen Fenster oder auf einem anderen Geraet "
            "uebernommen. Bitte die Seite neu laden, um hier weiterzuarbeiten."
        )
        st.stop()

# --- Initialisierung des Session-States (Sicherheits-Block) ---
if "router_state" not in st.session_state:
    st.session_state.router_state = None
if "chat_historie" not in st.session_state:
    st.session_state.chat_historie = []
if "pending_global_cmd" not in st.session_state:
    st.session_state.pending_global_cmd = None
if "pending_chat_frage" not in st.session_state:
    st.session_state.pending_chat_frage = None
if "wa_selected_id" not in st.session_state:
    st.session_state.wa_selected_id = None
if "wa_suchbegriff" not in st.session_state:
    st.session_state.wa_suchbegriff = ""
if "ne_mail_suchbegriff" not in st.session_state:
    st.session_state.ne_mail_suchbegriff = ""
if "ne_mail_kontakt_key" not in st.session_state:
    st.session_state.ne_mail_kontakt_key = None
if "kontakt_historie" not in st.session_state:
    st.session_state.kontakt_historie = []
if "letzter_kontakt" not in st.session_state:
    st.session_state.letzter_kontakt = ""
if "chat_qa_paare" not in st.session_state:
    st.session_state.chat_qa_paare = []
if "chat_qa_naechste_id" not in st.session_state:
    st.session_state.chat_qa_naechste_id = 0
if "frage_kontext" not in st.session_state:
    from frage_kontext import FrageKontext

    st.session_state.frage_kontext = FrageKontext().to_dict()
import re
import os
import io
import json
import hashlib
import speech_recognition as sr
from datetime import datetime, timedelta
import win32com.client
import pythoncom
import requests
import pyodbc
import pandas as pd
import warnings

warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")
from openai import OpenAI
from dotenv import load_dotenv
from urllib.parse import quote
from config import (
    ACCESS_DB_PATH,
    ANTWORTEN_DIR,
    DICTIONARY_PATH,
    MAIL_DOWNLOAD_DIR,
    MAIL_UPLOAD_DIR,
    SCHEMA_PATH,
    SQL_DEFAULT_TOP,
    WHATSAPP_CLOUD_API_TOKEN,
    WHATSAPP_CLOUD_API_VERSION,
    WHATSAPP_DEFAULT_COUNTRY_CODE,
    WHATSAPP_PHONE_NUMBER_ID,
    liste_wissensbereiche,
)
from ask_wiki import frage_das_wiki
from antworten_export import exportiere_markierte_paare
from brandvoice import BRANDVOICE_RADIO, brandvoice_auswahl_block, brandvoice_radio_labels
from sql_frage_katalog import (
    baue_klassifikator_leitfaden,
    baue_sql_feld_leitfaden,
    baue_semantik_leitfaden,
    baue_direkt_sql_folgefrage,
    baue_direkt_sql_firma_produkte,
    bereinige_access_sql,
    firma_suche_like,
    ist_offensichtliche_wiki_frage,
    ist_verfahren_wiki_frage,
)
from sql_db_meta import baue_db_meta_leitfaden
from wissens_kaskade import (
    AUTO_MODUS_LABEL,
    erlaube_wiki_fallback,
    kaskaden_quellen_caption,
    meldung_sql_leer,
)
from firmen_live_recherche import (
    extrahiere_firmen_suchbegriff,
    firmen_live_recherche,
    ist_einzel_firma_live_web_frage,
    suche_firma_in_db,
)
from firmen_md_fallback import firmen_md_fallback, ist_einzel_firma_md_fallback_frage
from orakel_synthese import erzeuge_firmen_synthese, soll_synthese_anwenden, synthese_aktiv

# ==========================================
# 1. SEITEN-KONFIGURATION (Mobile First)
# ==========================================
st.set_page_config(
    page_title="DigiWiki Master-Zentrale",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed" # Sidebar standardmäßig einklappen
)

os.makedirs(MAIL_DOWNLOAD_DIR, exist_ok=True)
os.makedirs(MAIL_UPLOAD_DIR, exist_ok=True)

if hasattr(st, "dialog"):
    modal_dialog = st.dialog
elif hasattr(st, "experimental_dialog"):
    modal_dialog = st.experimental_dialog
else:
    modal_dialog = lambda title: lambda func: func

def lade_json_daten(dateipfad):
    if os.path.exists(dateipfad):
        try:
            with open(dateipfad, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

# ==========================================
# 2. HILFSFUNKTIONEN & DATENBANK
# ==========================================
def extrahiere_url(text):
    """Sucht nach der ersten URL im Text (z.B. Teams/Zoom-Links im Body)."""
    if not text: return None
    treffer = re.search(r'(https?://[^\s]+)', text)
    return treffer.group(1) if treffer else None

@st.cache_data
def lade_textdatei(dateipfad):
    if not os.path.exists(dateipfad):
        return f"Fehler: Datei {dateipfad} nicht gefunden."
    try:
        with open(dateipfad, "r", encoding="utf-8-sig") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(dateipfad, "r", encoding="windows-1252") as f:
            return f.read()

db_schema = lade_textdatei(SCHEMA_PATH)
db_dictionary = lade_textdatei(DICTIONARY_PATH)

def _sql_escape(wert):
    return str(wert or "").replace("'", "''")


def _baue_suchteile(suchtext):
    """Zerlegt Suchtext in Tokens (Vorname, Nachname, Firma, …)."""
    raw = str(suchtext or "").strip()
    if not raw:
        return []
    return [t.strip() for t in raw.split() if t.strip()]


def _baue_namen_filter(teile, vorname_feld, nachname_feld):
    if not teile:
        return "1=0"
    if len(teile) >= 2:
        vorname, nachname = _sql_escape(teile[0]), _sql_escape(teile[-1])
        return (
            f"({vorname_feld} LIKE '%{vorname}%' AND {nachname_feld} LIKE '%{nachname}%')"
        )
    t = _sql_escape(teile[0])
    return f"({vorname_feld} LIKE '%{t}%' OR {nachname_feld} LIKE '%{t}%')"


def _baue_firma_filter(teile, stamm_alias="s"):
    if not teile:
        return "1=0"
    teile_filter = [firma_suche_like(t, alias=stamm_alias) for t in teile]
    return "(" + " OR ".join(teile_filter) + ")"


def _baue_kontakt_suchfilter(teile, vorname_feld, nachname_feld, stamm_alias="s"):
    """Name (Vor-/Nachname) oder Firma über nama & nameb."""
    name = _baue_namen_filter(teile, vorname_feld, nachname_feld)
    firma = _baue_firma_filter(teile, stamm_alias=stamm_alias)
    return f"(({name}) OR ({firma}))"


def _baue_crm_where(teile):
    return _baue_kontakt_suchfilter(teile, "p.vorname", "p.nachname", stamm_alias="s")


def _baue_wl_where(teile):
    return _baue_kontakt_suchfilter(teile, "w.[Vorname]", "w.[Nachname]", stamm_alias="s")


def _ansprache_aus_kontakt(row):
    """Sie/Du aus Whitelist.Ansprache (nicht Anrede/Herr/Frau)."""
    for key in ("wl_ansprache", "Ansprache", "ansprache"):
        wert = str(row.get(key) or "").strip()
        if not wert or wert.lower() in ("none", "nan"):
            continue
        lower = wert.lower()
        if lower == "du" or " du" in f" {lower} ":
            return "Du"
        if lower == "sie" or " sie" in f" {lower} ":
            return "Sie"
    return "Sie"


def _crm_from_join():
    return """
        FROM ((crm_personen AS p
        LEFT JOIN stammdatenindustrie AS s ON p.kundennumm = s.kundennumm)
        LEFT JOIN Whitelist_Kontakte AS w ON w.indpersonid = p.personid)
    """


def _wl_from_join():
    return """
        FROM Whitelist_Kontakte AS w
        LEFT JOIN stammdatenindustrie AS s ON w.indkundennumm = s.kundennumm
    """


def _kontakt_firma_aus_row(row):
    wert = str(row.get("firma") or "").strip()
    if wert and wert.lower() not in ("none", "nan"):
        return wert
    return ""


def _ne_mail_entwurf_zuruecksetzen():
    st.session_state.pop("ne_mail_entwurf_edit", None)
    st.session_state.pop("ne_mail_entwurf_pending", None)


def _ne_mail_entwurf_bereitstellen(text):
    st.session_state.ne_mail_entwurf_pending = text


def _ne_mail_entwurf_widget_sync():
    if "ne_mail_entwurf_pending" in st.session_state:
        st.session_state["ne_mail_entwurf_edit"] = st.session_state.pop("ne_mail_entwurf_pending")


def _bereinige_telefon_df(df):
    if df.empty:
        return df
    for col in ("mobil", "telefon"):
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).replace(["None", "nan"], "")
    df["num_score"] = df.get("mobil", "").str.len() + df.get("telefon", "").str.len()
    return df.sort_values("num_score", ascending=False).head(5)


def _normalisiere_kontakt_df(df):
    """Vereinheitlicht CRM- und WL-Zeilen für Telefon, E-Mail und Messenger."""
    if df.empty:
        return df

    df = df.copy()

    if "mobiltelefon" in df.columns:
        df["mobil"] = df["mobil"].fillna(df["mobiltelefon"])
        df = df.drop(columns=["mobiltelefon"], errors="ignore")
    if "wl_mobil" in df.columns:
        df["mobil"] = df.get("mobil", pd.Series(dtype=object)).fillna(df["wl_mobil"])
    if "wl_telefon" in df.columns:
        df["telefon"] = df.get("telefon", pd.Series(dtype=object)).fillna(df["wl_telefon"])
    if "wl_linkedin" in df.columns:
        basis = df["linkedin_url"] if "linkedin_url" in df.columns else pd.Series([None] * len(df))
        df["linkedin_url"] = basis.fillna(df["wl_linkedin"])

    df = df.drop(columns=["wl_mobil", "wl_telefon", "wl_linkedin"], errors="ignore")

    spalten_map = {
        "Vorname": "vorname",
        "Nachname": "nachname",
        "indpersonid": "personid",
        "Email_Gesch": "email_gesch",
        "Email_Priv": "email_priv",
        "LinkedIn_URL": "linkedin_url",
    }
    df = df.rename(columns={k: v for k, v in spalten_map.items() if k in df.columns})

    if "emailpers" in df.columns and "email_pers" not in df.columns:
        df["email_pers"] = df["emailpers"]
    elif "email_pers" in df.columns:
        df["email_pers"] = df["email_pers"].fillna(df.get("emailpers"))

    if "wl_ansprache" in df.columns:
        basis = df["ansprache"] if "ansprache" in df.columns else pd.Series([None] * len(df))
        df["ansprache"] = basis.fillna(df["wl_ansprache"])
        df = df.drop(columns=["wl_ansprache"], errors="ignore")

    df["personid"] = (
        df.get("personid", pd.Series(dtype=object))
        .fillna("")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .replace(["nan", "None"], "")
    )

    for col in ("mobil", "telefon", "email_pers", "email_gesch", "email_priv", "vorname", "nachname", "firma"):
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).replace(["None", "nan"], "")

    if "anrede" in df.columns:
        df["Anrede"] = df["anrede"]
    if "ansprache" in df.columns:
        df["Ansprache"] = df["ansprache"]

    return df


def _zusammenfuehren_kontakte(df_crm, df_wl):
    df_crm = _normalisiere_kontakt_df(df_crm)
    df_wl = _normalisiere_kontakt_df(df_wl)

    if df_crm.empty:
        return df_wl.reset_index(drop=True)
    if df_wl.empty:
        return df_crm.reset_index(drop=True)

    crm_ids = {pid for pid in df_crm["personid"].astype(str) if pid}
    wl_only = df_wl[~df_wl["personid"].astype(str).isin(crm_ids)]
    return pd.concat([df_crm, wl_only], ignore_index=True)


@st.cache_data(ttl=60)
def suche_kontakte(such_name):
    """Einheitliche Kontaktsuche (CRM + Whitelist) für Telefon, E-Mail und Messenger."""
    if not str(such_name or "").strip():
        return pd.DataFrame()

    teile = _baue_suchteile(such_name)
    if not teile:
        return pd.DataFrame()

    conn_str = fr'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};'
    try:
        conn = pyodbc.connect(conn_str, timeout=5)

        query_crm = f"""
            SELECT DISTINCT
                p.personid,
                p.vorname,
                p.nachname,
                p.mobil,
                p.mobiltelefon,
                p.telefon,
                p.linkedin AS linkedin_url,
                p.emailpers AS email_pers,
                p.anrede,
                w.Ansprache AS wl_ansprache,
                w.Email_Gesch AS email_gesch,
                w.Email_Priv AS email_priv,
                w.Tel_Mobil AS wl_mobil,
                w.Tel_Gesch AS wl_telefon,
                w.LinkedIn_URL AS wl_linkedin,
                s.nama AS firma,
                'CRM' AS quelle
            {_crm_from_join()}
            WHERE {_baue_crm_where(teile)}
        """
        df_crm = pd.read_sql(query_crm, conn)

        query_wl = f"""
            SELECT DISTINCT
                w.indpersonid AS personid,
                w.Vorname AS vorname,
                w.Nachname AS nachname,
                w.Tel_Mobil AS mobil,
                w.Tel_Gesch AS telefon,
                w.Email_Gesch AS email_gesch,
                w.Email_Priv AS email_priv,
                w.Anrede AS anrede,
                w.Ansprache AS ansprache,
                w.LinkedIn_URL AS linkedin_url,
                s.nama AS firma,
                'WL' AS quelle
            {_wl_from_join()}
            WHERE {_baue_wl_where(teile)}
        """
        df_wl = pd.read_sql(query_wl, conn)
        conn.close()

        return _zusammenfuehren_kontakte(df_crm, df_wl)

    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60)
def suche_telefonnummer(such_name):
    """Telefon/LinkedIn aus der einheitlichen Kontaktsuche."""
    df = suche_kontakte(such_name)
    if df.empty:
        return df
    return _bereinige_telefon_df(df)


@st.cache_data(ttl=60)
def suche_email_kontakte(such_name):
    """E-Mail-Empfänger aus der einheitlichen Kontaktsuche."""
    return suche_kontakte(such_name)


@st.cache_data(ttl=60)
def suche_whatsapp_kontakte(such_name):
    """Messenger-Kontakte mit Mobilnummer aus der einheitlichen Kontaktsuche."""
    df = suche_kontakte(such_name)
    if df.empty:
        return df

    mobil_ok = df["mobil"].astype(str).str.strip() != ""
    df = df.loc[mobil_ok].copy()
    if df.empty:
        return df

    return df.drop_duplicates(subset=["mobil"]).reset_index(drop=True)


def _ist_gueltige_email(wert):
    wert = str(wert or "").strip()
    return bool(wert) and wert.lower() not in ("none", "nan") and "@" in wert


def baue_email_optionen_aus_kontakt(row):
    """Liefert wählbare Empfänger-Adressen je nach Quelle (CRM / Whitelist)."""
    optionen = []
    quelle = str(row.get("quelle", "")).upper()
    email_pers = row.get("email_pers") or row.get("emailpers")
    if quelle == "CRM":
        if _ist_gueltige_email(email_pers):
            optionen.append({"label": "Persönlich (CRM)", "email": str(email_pers).strip()})
    else:
        if _ist_gueltige_email(row.get("email_gesch")):
            optionen.append({"label": "Geschäftlich (Whitelist)", "email": str(row.get("email_gesch")).strip()})
        if _ist_gueltige_email(row.get("email_priv")):
            optionen.append({"label": "Privat (Whitelist)", "email": str(row.get("email_priv")).strip()})
    return optionen


def kontakt_email_schluessel(row):
    quelle = str(row.get("quelle", "X")).upper()
    personid = str(row.get("personid", "") or "").strip() or "ohne_id"
    return f"{quelle}_{personid}"


@st.cache_data(ttl=60)
def lade_whatsapp_kontakte():
    if 'ACCESS_DB_PATH' not in globals() or not ACCESS_DB_PATH:
        return pd.DataFrame()
        
    conn_str = fr'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};'
    try:
        conn = pyodbc.connect(conn_str, timeout=5)
        
        # 1. Alle CRM-Personen mit Mobilnummer
        query_crm = "SELECT personid, vorname, nachname, mobil, telefon FROM crm_personen WHERE mobil IS NOT NULL OR telefon IS NOT NULL"
        df_crm = pd.read_sql(query_crm, conn)
        
        # 2. Whitelist-Kontakte mit echten Namen (wie suche_telefonnummer)
        query_wl = """
            SELECT
                indpersonid,
                Vorname,
                Nachname,
                Tel_Mobil,
                Tel_Gesch
            FROM Whitelist_Kontakte
            WHERE Tel_Mobil IS NOT NULL OR Tel_Gesch IS NOT NULL
        """
        df_wl = pd.read_sql(query_wl, conn)
        if not df_wl.empty:
            df_wl = df_wl.rename(columns={
                "indpersonid": "personid",
                "Vorname": "vorname",
                "Nachname": "nachname",
                "Tel_Mobil": "mobil",
                "Tel_Gesch": "telefon",
            })
        
        conn.close()
        
        # Beide Listen vereinen
        df_gesamt = pd.concat([df_crm, df_wl], ignore_index=True)
        df_gesamt["personid"] = (
            df_gesamt["personid"]
            .fillna("")
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .replace(["nan", "None"], "")
        )

        # Dubletten basierend auf der Mobilnummer entfernen (falls jemand in beiden steht)
        df_gesamt = df_gesamt.drop_duplicates(subset=["mobil"])
        return df_gesamt.reset_index(drop=True)
        
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def lade_whitelist():
    conn_str = fr'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};'
    try:
        conn = pyodbc.connect(conn_str, timeout=5)
        df = pd.read_sql("SELECT * FROM Whitelist_Kontakte", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

# ==========================================
# 3. KI LOGIK (NL2SQL & Sprach-Router)
# ==========================================
def analysiere_sprachkommando(kommando_text, letzter_kontakt=""):
    """Weist den Freitext einer von vier Aktionen (Anruf, Notiz, SQL, Wissen) zu.

    letzter_kontakt: zuletzt gesuchte Person/Firma, um Anschlussbefehle mit Bezug
    ('ruf ihn an', 'seine Nummer') aufzuloesen.
    """
    client = OpenAI()
    kontext_zeile = (
        f"\n    ZULETZT GENANNTER KONTAKT: \"{letzter_kontakt}\".\n"
        "    Wenn der Befehl keinen eigenen Namen nennt, sich aber per Bezug (er/sie/ihn/ihm/seine/ihre/dem)\n"
        "    auf eine Person bezieht, dann verwende diesen zuletzt genannten Kontakt als ziel_name bzw. im text_inhalt.\n"
        if str(letzter_kontakt or "").strip()
        else ""
    )
    prompt = f"""
    Analysiere den folgenden Befehl und ordne ihn in eine dieser vier Kategorien ein:
    1. 'anruf': Der Nutzer möchte jemanden anrufen (Name extrahieren).
    2. 'notiz': Der Nutzer möchte sich etwas notieren/merken (Inhalt extrahieren).
    3. 'datenbank': Strukturierte Abfrage an die CRM-/Marktdatenbank (Microsoft Access/SQL).
       Das ist der STANDARDFALL fuer fast alle Fragen. Beispiele:
       - Personen, Kontakte, Hierarchien, Telefon, E-Mail (crm_personen, ref_funktionen)
       - Firmen, Adressen, Standorte (stammdatenindustrie)
       - Apotheken (stammdatenapo)
       - Produkte, Artikel, Hersteller, Sortiment (abdaartikel, topprodukte, gl_produkt1-3)
       - Marktbearbeitung, Segmente, Akquise (akquiseklasse, Marktzielgruppe, emarktzielgruppe, Kategorie)
       - Listen, Anzahlen, Rankings, Vergleiche
       - CRM-Aktivitaeten, LinkedIn, Whitelist
       - Auch qualitative Firmenfelder in der DB: narrativ, purpose, trigger_events, zielsetzung
    4. 'wissen': NUR wenn die Antwort in Dokumenten/Vertraegen/Verfahren/Formularen liegt
       und NICHT aus Tabellenfeldern beantwortbar ist.
{kontext_zeile}
    {baue_klassifikator_leitfaden()}

    Antworte AUSSCHLIESSLICH im JSON-Format:
    {{"kategorie": "anruf" | "notiz" | "datenbank" | "wissen", "ziel_name": "Name der Person falls Anruf, sonst leer", "text_inhalt": "Notiztext oder Frage"}}

    Befehl: "{kommando_text}"
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {"kategorie": "datenbank", "text_inhalt": kommando_text}

def baue_chat_historie_text(historie, max_eintraege=10):
    """Baut aus der Chat-Historie einen Verlaufstext (Nutzer/Assistenz) fuer das RAG."""
    zeilen = []
    for eintrag in historie[-max_eintraege:]:
        rolle = "Nutzer" if eintrag.get("rolle") == "user" else "Assistenz"
        text = str(eintrag.get("text", "")).strip()
        if text:
            zeilen.append(f"{rolle}: {text}")
    return "\n".join(zeilen)


def chat_qa_hinzufuegen(frage, antwort, typ, quellen=None, sql_markdown=None):
    """Speichert strukturiertes Q&A fuer Markierung und Export. Gibt qa_id zurueck."""
    qa_id = st.session_state.chat_qa_naechste_id
    st.session_state.chat_qa_naechste_id += 1
    st.session_state.chat_qa_paare.append(
        {
            "id": qa_id,
            "frage": str(frage or "").strip(),
            "antwort": str(antwort or "").strip(),
            "typ": typ,
            "quellen": list(quellen or []),
            "sql_markdown": sql_markdown,
            "markiert": True,
            "zeit": datetime.now().isoformat(timespec="seconds"),
        }
    )
    st.session_state[f"qa_cb_{qa_id}"] = True
    st.session_state[f"qa_hide_{qa_id}"] = False
    return qa_id


def qa_checkbox_key(qa_id):
    return f"qa_cb_{qa_id}"


def qa_hide_key(qa_id):
    return f"qa_hide_{qa_id}"


def qa_ist_markiert(qa_id):
    return bool(st.session_state.get(qa_checkbox_key(qa_id), True))


def qa_ist_ausgeblendet(qa_id):
    return bool(st.session_state.get(qa_hide_key(qa_id), False))


def qa_markierte_paare():
    return [p for p in st.session_state.chat_qa_paare if qa_ist_markiert(p["id"])]


def qa_setze_alle_markiert(markiert: bool):
    for p in st.session_state.chat_qa_paare:
        p["markiert"] = markiert
        st.session_state[qa_checkbox_key(p["id"])] = markiert


def zeige_qa_export_panel():
    """Export-Bereich unterhalb des Chats."""
    anzahl = len(st.session_state.chat_qa_paare)
    markiert_n = len(qa_markierte_paare())
    titel = f"📌 Antworten exportieren ({markiert_n}/{anzahl} markiert)"
    with st.expander(titel, expanded=False):
        if anzahl == 0:
            st.info(
                "Stellen Sie zuerst eine Frage. **Unter jeder Antwort** erscheinen dann "
                "die Checkboxen **„Für Export markieren“** und **„Antwort ausblenden“**."
            )
            return

        st.caption(f"Speicherort: `{ANTWORTEN_DIR}`")
        c_all, c_none = st.columns(2)
        with c_all:
            if st.button("Alle markieren", key="qa_mark_all", use_container_width=True):
                qa_setze_alle_markiert(True)
                st.rerun()
        with c_none:
            if st.button("Alle abwählen", key="qa_mark_none", use_container_width=True):
                qa_setze_alle_markiert(False)
                st.rerun()

        for p in st.session_state.chat_qa_paare:
            icon = "☑" if qa_ist_markiert(p["id"]) else "☐"
            hide = " 👁️" if qa_ist_ausgeblendet(p["id"]) else ""
            frage_kurz = p.get("frage", "")[:100]
            st.caption(f"{icon}{hide} {frage_kurz}")

        export_titel = st.text_input(
            "Dokumenttitel (optional, sonst KI-Vorschlag)",
            key="qa_export_titel",
            placeholder="z. B. Wiki-Test Verträge Juni 2026",
        )
        if st.button("📝 Markierte zusammenfassen & speichern", type="primary", key="qa_export_btn"):
            markiert = qa_markierte_paare()
            if not markiert:
                st.warning("Bitte mindestens eine Antwort markieren (Checkbox unter der Antwort).")
            else:
                with st.spinner("Erstelle Zusammenfassung und speichere Dokument …"):
                    try:
                        pfad, doc_titel = exportiere_markierte_paare(
                            markiert,
                            titel_manuell=export_titel,
                            ki_titel=not bool(export_titel.strip()),
                        )
                        st.success(f"Gespeichert: **{pfad.name}**")
                        st.caption(f"Pfad: `{pfad}`")
                        st.info(f"Dokumenttitel: *{doc_titel}*")
                    except Exception as e:
                        st.error(f"Export fehlgeschlagen: {e}")


def _qa_paar(qa_id):
    for paar in st.session_state.chat_qa_paare:
        if paar.get("id") == qa_id:
            return paar
    return None


def _zeige_assistent_inhalt(r, qa_id):
    """Volle Antwort aus Historie oder gespeichertem Q&A-Paar rendern."""
    paar = _qa_paar(qa_id) if qa_id is not None else None
    if paar and paar.get("sql_markdown"):
        st.markdown(paar["sql_markdown"])
        return
    if paar and paar.get("antwort") and paar.get("typ") in ("live_web", "wiki", "wiki_fallback"):
        st.markdown(paar["antwort"])
        return
    st.markdown(r.get("text") or "")


def zeige_qa_aktionszeile(qa_id):
    """Export-Markierung und Ausblenden direkt unter einer Antwort."""
    if qa_id is None:
        return
    if qa_checkbox_key(qa_id) not in st.session_state:
        st.session_state[qa_checkbox_key(qa_id)] = True
    if qa_hide_key(qa_id) not in st.session_state:
        st.session_state[qa_hide_key(qa_id)] = False
    col_export, col_hide = st.columns(2)
    with col_export:
        st.checkbox("📌 Für Export markieren", key=qa_checkbox_key(qa_id))
    with col_hide:
        st.checkbox("👁️ Antwort ausblenden", key=qa_hide_key(qa_id))


def zeige_qa_markierung_checkbox(qa_id):
    """Legacy-Aufruf – Checkboxen nur noch im Verlauf (keine Doppel-Widgets)."""
    return


def zeige_chat_verlauf_mit_markierung():
    """Chat-Verlauf; unter exportierbaren Antworten Markierung und Ausblenden."""
    gesehene_qa: set[int] = set()
    assistant_idx = 0
    for r in st.session_state.chat_historie:
        with st.chat_message(r["rolle"]):
            qa_id = None
            if r.get("rolle") == "assistant":
                qa_id = r.get("qa_id")
                if qa_id is None and assistant_idx < len(st.session_state.chat_qa_paare):
                    qa_id = st.session_state.chat_qa_paare[assistant_idx].get("id")
                assistant_idx += 1

            if r.get("rolle") == "assistant" and qa_id is not None and qa_ist_ausgeblendet(qa_id):
                with st.expander("👁️ Antwort einblenden", expanded=False):
                    _zeige_assistent_inhalt(r, qa_id)
            else:
                _zeige_assistent_inhalt(r, qa_id)

            if r.get("rolle") == "assistant" and qa_id is not None and qa_id not in gesehene_qa:
                gesehene_qa.add(qa_id)
                zeige_qa_aktionszeile(qa_id)


def sql_df_zu_markdown(df, max_zeilen=40):
    """DataFrame als Markdown-Tabelle fuer Export."""
    if df is None or df.empty:
        return ""
    auszug = df.head(max_zeilen)
    try:
        md = auszug.to_markdown(index=False)
    except Exception:
        md = auszug.to_string(index=False)
    if len(df) > max_zeilen:
        md += f"\n\n*(… {len(df) - max_zeilen} weitere Zeilen nicht exportiert)*"
    return md


def _versuche_ki_synthese(
    frage: str,
    sql_df=None,
    kundennumm: str = "",
    firmen_such: str = "",
    web_text: str = "",
    md_text: str = "",
):
    """Stufe 4: Briefing aus SQL + Stamm (+ optional Web/MD)."""
    if not synthese_aktiv():
        return None
    if sql_df is not None and not sql_df.empty and not soll_synthese_anwenden(frage, sql_df):
        if not web_text.strip() and not md_text.strip():
            return None
    if (sql_df is None or sql_df.empty) and not web_text.strip() and not md_text.strip():
        return None
    return erzeuge_firmen_synthese(
        frage,
        sql_df=sql_df,
        kundennumm=kundennumm,
        firmen_such=firmen_such,
        web_text=web_text,
        md_text=md_text,
    )


def klassifiziere_chat_frage(frage):
    """Auto-Routing: SQL (strukturierte Daten) vs. Wiki-RAG (Dokumentenwissen)."""
    if ist_offensichtliche_wiki_frage(frage):
        return "wissen"
    client = OpenAI()
    prompt = f"""
    Ordne die Nutzerfrage einem Antwortweg zu: 'datenbank' (SQL) oder 'wissen' (Wiki-Dokumente).

    {baue_klassifikator_leitfaden()}

    Antworte AUSSCHLIESSLICH als JSON: {{"typ": "datenbank" | "wissen", "begruendung": "kurz"}}
    Im Zweifel: "datenbank".

    Frage: "{frage}"
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        typ = json.loads(response.choices[0].message.content).get("typ", "datenbank")
        return typ if typ in ("datenbank", "wissen") else "datenbank"
    except Exception:
        return "datenbank"


def ermittle_frage_typ(frage, modus, expliziter_typ=None):
    """Bestimmt den Antwortpfad: manueller Modus, Router-Typ oder Auto-Klassifikation."""
    if expliziter_typ in ("datenbank", "wissen"):
        return expliziter_typ
    if modus in ("datenbank", "wissen"):
        return modus
    return klassifiziere_chat_frage(frage)


def effektiver_wiki_bereich(frage: str, gewaehlt: str | None) -> str | None:
    """Verfahrensfragen fokussieren auf Einrichtung/Schulung-Anleitungen."""
    if ist_verfahren_wiki_frage(frage) and gewaehlt in (None, "vollzugriff"):
        return "verfahren"
    return gewaehlt


def uebersetze_frage_in_sql(nutzer_frage, schema_text, dictionary_csv, kontext_block=""):
    client = OpenAI()
    kontext_teil = f"\n    {kontext_block}\n" if kontext_block else ""
    system_prompt = f"""
    Du bist ein SQL-Experte für Microsoft Access (Zugriff via pyodbc). 
    Übersetze die Frage des Nutzers in eine syntaktisch korrekte Access-SQL-Abfrage.
    
    === DATENBANK-SCHEMA ===
    {schema_text}
    
    === DATA DICTIONARY ===
    {dictionary_csv}

    {baue_db_meta_leitfaden()}

    {baue_sql_feld_leitfaden()}

    {baue_semantik_leitfaden()}
    {kontext_teil}
    === STRIKTE REGELN ===
    1. Antworte AUSSCHLIESSLICH mit dem SQL-Code in EINER Zeile.
    2. Schritt 1: Tabellenrolle aus db_tabellen waehlen. Schritt 2: JOINs aus db_joins.
       Schritt 3: Felder/Synonyme aus Dictionary und semantischem Leitfaden.
    3. Nutze fuer Textsuchen IMMER LIKE mit '%'. Spalten mit [SUCH FELD] im Dictionary bevorzugen.
    4. SEMANTISCHE TEXTSUCHE: Synonyme per OR (z.B. Hustensaft -> Husten, Hustensaft, Hustenstiller).
    5. JOINs nur aus db_joins.csv; bei Typ-Unterschied kundennumm/personid CStr() nutzen.
       ACCESS-KLAMMERN: Bei INNER+LEFT gemischt IMMER Klammern (siehe ACCESS JOIN-SYNTAX).
       GF-Beispiel: FROM (crm_personen AS p INNER JOIN stammdatenindustrie AS s ON p.kundennumm = s.kundennumm) LEFT JOIN ref_funktionen AS rf ON p.funktionid = rf.funktionid
    6. MARKTBEARBEITUNG: akquiseklasse (int, =), Marktzielgruppe, emarktzielgruppe.
        Apotheken-Fokus/Marktorientierung -> Marktzielgruppe/emarktzielgruppe LIKE '%Apothek%',
        NICHT apotheken_fokus (Feld leer).
    7. SELECT nur noetige Spalten; bei JOINs kein SELECT *.
    8. Access: SELECT TOP {SQL_DEFAULT_TOP} bei Listen (Standard, env: DIGIWIKI_SQL_DEFAULT_TOP);
       explizites Nutzer-Limit (z.B. Top 10) hat Vorrang. GROUP BY statt DISTINCT+ORDER BY Alias.
    9. PRODUKTE einer Firma — zwei Faelle unterscheiden:
       a) "Top-Produkte" / "Sortiment" / produktschwerpunkt: NUR stammdatenindustrie
          (topprodukte, top_produkte, gl_produkt1–3) — KEIN JOIN abdaartikel.
       b) "Welche Produkte/Artikel hat …" / Produktkatalog: abdaartikel JOIN
          stammdatenindustrie ON a.anbieter_nr = s.anbieternummer (Anbieternummer).
          Mit bekannter kundennumm: WHERE s.kundennumm = '…'.
       ABDA-Artikelanzahl: COUNT(*) mit gleichem JOIN.
    10. Entferne Markdown.
    11. FIRMA SUCHEN (stammdatenindustrie): NIEMALS nur nama LIKE.
        Immer: Trim(IIf(nama Is Null,'',nama) & IIf(nameb Is Null,'',IIf(nama Is Null,nameb,' ' & nameb))) LIKE '%…%'
        Mit Alias s entsprechend s.nama / s.nameb. Leerzeichen zwischen nama und nameb nicht vergessen.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": nutzer_frage}
            ],
            temperature=0.2 
        )
        sql_raw = response.choices[0].message.content.strip()
        return bereinige_access_sql(sql_raw)
    except Exception as e:
        return f"Fehler bei der KI-Übersetzung: {e}"

def _eindeutige_spaltennamen(namen):
    """Macht doppelte Spaltennamen eindeutig (z.B. bei JOINs mit SELECT *).

    pandas bricht sonst mit 'Duplicate column names found' ab, wenn zwei
    verbundene Tabellen gleichnamige Spalten (kundennumm, telefon, ...) liefern.
    """
    gesehen = {}
    ergebnis = []
    for name in namen:
        basis = name or "spalte"
        if basis in gesehen:
            gesehen[basis] += 1
            ergebnis.append(f"{basis}_{gesehen[basis]}")
        else:
            gesehen[basis] = 0
            ergebnis.append(basis)
    return ergebnis


def fuehre_sql_aus(sql_query, db_pfad=ACCESS_DB_PATH):
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_pfad};"
    try:
        conn = pyodbc.connect(conn_str)
        try:
            # Bewusst ueber den Cursor (statt pd.read_sql), um doppelte Spaltennamen
            # aus JOIN/SELECT * sauber abzufangen.
            cursor = conn.cursor()
            cursor.execute(sql_query)
            if cursor.description is None:
                return pd.DataFrame()
            spalten = _eindeutige_spaltennamen([d[0] for d in cursor.description])
            zeilen = [tuple(row) for row in cursor.fetchall()]
            return pd.DataFrame.from_records(zeilen, columns=spalten)
        finally:
            conn.close()
    except Exception as e:
        return f"Fehler bei der Datenbankabfrage: {e}"

# ==========================================
# 4. OUTLOOK & NOTIZEN LOGIK
# ==========================================
@st.cache_resource
def _get_outlook_application():
    """Eine gemeinsame Outlook-COM-Sitzung pro App-Prozess (MAPI-Ressourcen schonen)."""
    pythoncom.CoInitialize()
    try:
        return win32com.client.GetActiveObject("Outlook.Application")
    except Exception:
        return win32com.client.Dispatch("Outlook.Application")


def _clear_outlook_cache():
    _get_outlook_application.clear()


def _connect_outlook():
    """Outlook-COM holen; bei Disconnect Cache leeren und einmal neu verbinden."""
    last_err = None
    for _ in range(2):
        try:
            app = _get_outlook_application()
            _ = app.Session.Accounts.Count
            return app
        except Exception as e:
            last_err = e
            _clear_outlook_cache()
    raise last_err


def _get_outlook_namespace():
    last_err = None
    for _ in range(2):
        try:
            ns = _connect_outlook().GetNamespace("MAPI")
            _ = ns.Stores.Count
            return ns
        except Exception as e:
            last_err = e
            _clear_outlook_cache()
    raise last_err


def erstelle_outlook_notiz(text_inhalt):
    """Speichert einen Text direkt als Outlook-Notiz."""
    try:
        outlook = _connect_outlook()
        note = outlook.CreateItem(5)  # 5 = olNoteItem
        note.Body = text_inhalt
        note.Save()
        return True, "Notiz erfolgreich gespeichert."
    except Exception as e:
        return False, f"Fehler beim Speichern der Notiz: {e}"

@st.cache_data(ttl=600)
def hole_outlook_konten():
    """Outlook-Konten mit stabilem idx:-Schlüssel für den Versand."""
    try:
        outlook = _connect_outlook()
        konten = []
        for i, acc in enumerate(outlook.Session.Accounts):
            smtp = str(getattr(acc, "SmtpAddress", "") or "").strip()
            name = str(getattr(acc, "DisplayName", "") or "").strip()
            label = f"{name} <{smtp}>" if smtp else (name or f"Konto {i + 1}")
            konten.append({
                "key": f"idx:{i}",
                "label": label,
                "smtp": smtp.lower(),
            })
        return konten
    except Exception:
        return [{
            "key": "idx:0",
            "label": "kohlhaas@digibest.eu",
            "smtp": "kohlhaas@digibest.eu",
        }]


def _finde_outlook_konto(outlook, absender_konto):
    if not absender_konto:
        return None

    ziel = str(absender_konto).strip()
    accounts = outlook.Session.Accounts

    if ziel.startswith("idx:"):
        try:
            return accounts.Item(int(ziel.split(":", 1)[1]) + 1)
        except Exception:
            try:
                return accounts[int(ziel.split(":", 1)[1])]
            except Exception:
                pass

    ziel_l = ziel.lower()
    for acc in accounts:
        smtp = str(getattr(acc, "SmtpAddress", "") or "").lower().strip()
        name = str(getattr(acc, "DisplayName", "") or "").lower().strip()
        label = f"{name} <{smtp}>" if smtp else name
        if ziel_l in (smtp, name, label.lower()):
            return acc
        if smtp and smtp in ziel_l:
            return acc
    return None


def _erstelle_outlook_mail(outlook, account=None):
    """Mail im Outbox-Store des gewählten Kontos anlegen (zuverlässiger als nur SendUsingAccount)."""
    ol_folder_outbox = 6
    if account is not None:
        try:
            store = account.DeliveryStore
            outbox = store.GetDefaultFolder(ol_folder_outbox)
            return outbox.Items.Add("IPM.Note")
        except Exception:
            pass
        mail = outlook.CreateItem(0)
        mail.SendUsingAccount = account
        return mail
    return outlook.CreateItem(0)

@st.cache_data(ttl=120)
def hole_outlook_woche():
    heute = datetime.now().date()
    in_einer_woche = heute + timedelta(days=7)
    termine_liste, aufgaben_liste, fehler_meldungen = [], [], []

    try:
        ns = _get_outlook_namespace()
    except Exception as e:
        return None, f"Outlook-Startfehler: {e}"

    try:
        calendar = ns.GetDefaultFolder(9)
        appointments = calendar.Items
        appointments.IncludeRecurrences = True
        appointments.Sort("[Start]")
        restric_filter = f"[Start] >= '{heute.strftime('%d.%m.%Y')} 00:00' AND [Start] <= '{in_einer_woche.strftime('%d.%m.%Y')} 23:59'"
        wochen_termine = appointments.Restrict(restric_filter)
        
        for app in wochen_termine:
            try:
                termine_liste.append({
                    "Datum": app.Start.strftime("%d.%m.%Y"),
                    "Zeit": app.Start.strftime("%H:%M"),
                    "Betreff": app.Subject,
                    "Ort": app.Location if app.Location else "",
                    "Body": app.Body if hasattr(app, 'Body') else ""
                })
            except: pass
    except Exception as e:
        fehler_meldungen.append(f"Kalender-Fehler: {e}")

    try:
        tasks_folder = ns.GetDefaultFolder(13)
        for task in tasks_folder.Items:
            try:
                if not task.Complete:
                    faelligkeit = task.DueDate.strftime("%d.%m.%Y") if (task.DueDate and task.DueDate.year < 4500) else "Kein Datum"
                    aufgaben_liste.append({
                        "Aufgabe": task.Subject, 
                        "Fällig": faelligkeit,
                        "EntryID": task.EntryID
                    })
            except: pass
    except Exception as e:
        fehler_meldungen.append(f"Aufgaben-Fehler: {e}")
        
    gesamt_fehler = " | ".join(fehler_meldungen) if fehler_meldungen else None
    return {"termine": termine_liste, "aufgaben": aufgaben_liste}, gesamt_fehler

def bearbeite_outlook_aufgabe(entry_id, aktion="erledigt"):
    try:
        ns = _get_outlook_namespace()
        task = ns.GetItemFromID(entry_id)
        if aktion == "erledigt":
            task.PercentComplete = 100
            task.Status = 2
            task.Save()
        elif aktion == "loeschen":
            task.Delete()
        hole_outlook_woche.clear()
        return True, ""
    except Exception as e:
        return False, str(e)

def erstelle_outlook_aufgabe(betreff, faellig_datum=None, details="", empfaenger_email=None):
    try:
        outlook = _connect_outlook()
        task = outlook.CreateItem(3)
        task.Subject = betreff
        if details: task.Body = details
        if faellig_datum: task.DueDate = faellig_datum.strftime("%d.%m.%Y")
        if empfaenger_email:
            task.Assign()
            recipient = task.Recipients.Add(empfaenger_email)
            recipient.Resolve()
            task.Send()
        else:
            task.Save()
        hole_outlook_woche.clear()
        return True, ""
    except Exception as e:
        return False, str(e)

# ==========================================
# 5. RESTLICHE AGENTEN / WHATSAPP FUNKTIONEN
# ==========================================
def normalisiere_linkedin_url(rohe_url):
    if not rohe_url or str(rohe_url).lower() in ["nan", "none", ""]:
        return ""
    url = str(rohe_url).strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    return url


def normalisiere_whatsapp_nummer(rohe_nummer, laendercode=None):
    rohe_nummer = str(rohe_nummer or "").strip()
    if not rohe_nummer: return ""
    digits = "".join(ch for ch in rohe_nummer if ch.isdigit())
    if not digits: return ""
    if digits.startswith("00"): digits = digits[2:]
    if digits.startswith("0") and len(digits) > 1:
        digits = f"{laendercode or WHATSAPP_DEFAULT_COUNTRY_CODE}{digits[1:]}"
    return digits

def baue_whatsapp_link(rohe_nummer, nachricht):
    nummer = normalisiere_whatsapp_nummer(rohe_nummer)
    return f"https://wa.me/{nummer}?text={quote(str(nachricht or ''))}" if nummer else None

def sende_whatsapp_via_cloud_api(rohe_nummer, nachricht):
    nummer = normalisiere_whatsapp_nummer(rohe_nummer)
    if not nummer: return False, "Ungültige Telefonnummer."
    url = f"https://graph.facebook.com/{WHATSAPP_CLOUD_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {"messaging_product": "whatsapp", "to": nummer, "type": "text", "text": {"preview_url": False, "body": str(nachricht or "")}}
    headers = {"Authorization": f"Bearer {WHATSAPP_CLOUD_API_TOKEN}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return (True, "Gesendet.") if response.ok else (False, f"Fehler: {response.text}")
    except Exception as e: return False, str(e)

def logge_aktivitaet_in_access(kanal, vorgang, kontakt_name=None, kontakt_email=None, kontakt_mobil=None, betreff=None, nachricht=None, status="ok", details=None):
    conn_str = fr'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};'
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Aktivitaeten (Datum, Kanal, Vorgang, Kontakt_Name, Kontakt_Email, Kontakt_Mobil, Betreff, Nachricht, Status, Details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            datetime.now().strftime("%d.%m.%Y %H:%M:%S"), kanal, vorgang, kontakt_name, kontakt_email, kontakt_mobil, betreff, nachricht, status, details,
        )
        conn.commit()
        conn.close()
    except: pass

@st.cache_data(ttl=60)
def lade_kontakt_aktivitaeten(kontakt_name=None, kontakt_email=None, kontakt_mobil=None, limit=5):
    conn_str = fr'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};'
    filter_teile = []
    
    if kontakt_name: 
        name_clean = str(kontakt_name).replace("'", "''")
        filter_teile.append(f"Kontakt_Name LIKE '%{name_clean}%'")
        
    if kontakt_email: 
        email_clean = str(kontakt_email).replace("'", "''")
        filter_teile.append(f"Kontakt_Email LIKE '%{email_clean}%'")
        
    if kontakt_mobil: 
        mobil_clean = str(kontakt_mobil).replace("'", "''")
        filter_teile.append(f"Kontakt_Mobil LIKE '%{mobil_clean}%'")
        
    where_clause = "WHERE " + " OR ".join(filter_teile) if filter_teile else ""
    query = f"SELECT TOP {int(limit)} Datum, Kanal, Vorgang, Kontakt_Name, Kontakt_Email, Kontakt_Mobil, Betreff, Nachricht, Status, Details FROM Aktivitaeten {where_clause} ORDER BY ID DESC"
    
    try:
        conn = pyodbc.connect(conn_str)
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except: 
        return pd.DataFrame()

@st.cache_data(ttl=120)
def hole_relevante_emails(whitelist_df):
    if whitelist_df.empty:
        return []
    try:
        outlook = _get_outlook_namespace()
    except Exception as e:
        return {"_outlook_error": str(e)}
    ziel_konten = ['hans@kohlhaas.eu', 'kohlhaas@digibest.eu']
    relevante_mails = []
    whitelist_emails = whitelist_df['Email_Gesch'].str.lower().str.strip().tolist()

    for store in outlook.Stores:
        if store.DisplayName.lower().strip() in ziel_konten:
            try:
                inbox = store.GetDefaultFolder(6)
                messages = inbox.Items
                messages.Sort("[ReceivedTime]", True)
                
                for i in range(1, min(200, len(messages)) + 1):
                    msg = messages[i]
                    if msg.Class != 43: continue
                    sender = msg.SenderEmailAddress
                    if msg.SenderEmailType == "EX" and msg.Sender.GetExchangeUser():
                        sender = msg.Sender.GetExchangeUser().PrimarySmtpAddress
                    sender = sender.lower().strip()
                    
                    if sender in whitelist_emails:
                        kontakt = whitelist_df[whitelist_df['Email_Gesch'].str.lower().str.strip() == sender].iloc[0]
                        relevante_mails.append({
                            "Name": f"{kontakt['Vorname']} {kontakt['Nachname']}",
                            "Ansprache": kontakt['Ansprache'],
                            "Email": sender,
                            "Betreff": msg.Subject,
                            "Inhalt": msg.Body,
                            "Anhaenge": [] # Gekürzt für Übersicht
                        })
            except: pass
    return relevante_mails

def generiere_mail_entwurf(original_text, anweisung, ansprache, absender_name, brandvoice_wahl="ohne"):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    ansprache = _ansprache_aus_kontakt({"ansprache": ansprache})
    stil = "vertrauliche Du-Anrede" if ansprache == "Du" else "höfliche Sie-Anrede"
    prompt = (
        f"Du schreibst im Namen von Hans Kohlhaas / DigiBest.\n"
        f"{brandvoice_auswahl_block(brandvoice_wahl)}\n"
        f"Antworte auf diese E-Mail:\n{original_text}\n\n"
        f"Partner: {absender_name}\n"
        f"Anrede-Stil: Verwende konsequent die {ansprache}-Form ({stil}).\n"
        f"Anweisung des Nutzers: {anweisung}\n"
        f"Schreibe NUR den reinen Mail-Text inkl. Anrede und Grußformel."
    )
    try:
        return client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.4).choices[0].message.content
    except Exception as e: return f"Fehler bei der KI-Generierung: {e}"


def generiere_neue_mail_entwurf(anweisung, ansprache, empfaenger_name, betreff="", brandvoice_wahl="ohne"):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    ansprache = _ansprache_aus_kontakt({"ansprache": ansprache})
    stil = "vertrauliche Du-Anrede" if ansprache == "Du" else "höfliche Sie-Anrede"
    prompt = (
        f"Du schreibst im Namen von Hans Kohlhaas / DigiBest.\n"
        f"{brandvoice_auswahl_block(brandvoice_wahl)}\n"
        f"Schreibe eine NEUE E-Mail (keine Antwort auf eine bestehende Mail).\n"
        f"Empfänger: {empfaenger_name}\n"
        f"Anrede-Stil: Verwende konsequent die {ansprache}-Form ({stil}). "
        f"Anrede, Text und Grußformel müssen durchgängig {ansprache} sein.\n"
        f"Betreff-Vorgabe: {betreff or '(noch offen)'}\n"
        f"Worum geht es: {anweisung}\n"
        f"Schreibe NUR den reinen Mail-Text inkl. Anrede und Grußformel."
    )
    try:
        return client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.4
        ).choices[0].message.content
    except Exception as e:
        return f"Fehler bei der KI-Generierung: {e}"


def generiere_whatsapp_entwurf(anweisung, ansprache, empfaenger_name, brandvoice_wahl="ohne", bezug_text=""):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    ansprache = _ansprache_aus_kontakt({"ansprache": ansprache})
    prompt = (
        f"Du schreibst eine kurze WhatsApp-Nachricht.\n"
        f"{brandvoice_auswahl_block(brandvoice_wahl)}\n"
        f"Empfänger: {empfaenger_name}\n"
        f"Anrede-Stil: {ansprache}\n"
        f"{'Bezug/Kontext: ' + bezug_text if bezug_text.strip() else ''}\n"
        f"Inhalt: {anweisung}\n"
        f"Maximal 2-4 kurze Saetze, WhatsApp-tauglich, ohne Betreffzeile."
    )
    try:
        return client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.5
        ).choices[0].message.content
    except Exception as e:
        return f"Fehler bei der KI-Generierung: {e}"


def _brandvoice_radio(key: str, default: str = "ohne") -> str:
    labels = brandvoice_radio_labels()
    optionen = [o["id"] for o in BRANDVOICE_RADIO]
    index = optionen.index(default) if default in optionen else len(optionen) - 1
    return st.radio(
        "Brandvoice",
        options=optionen,
        format_func=lambda x: labels.get(x, x),
        horizontal=True,
        key=key,
        index=index,
    )


def sende_email_via_outlook(empfaenger_email, betreff, inhalt, absender_konto, anhaenge_pfade=None, ist_antwort=False):
    outlook = _connect_outlook()
    account = _finde_outlook_konto(outlook, absender_konto)
    if absender_konto and account is None:
        st.error(f"Absender-Konto nicht gefunden: {absender_konto}")
        return False

    mail = _erstelle_outlook_mail(outlook, account)
    if account is not None:
        try:
            mail.SendUsingAccount = account
        except Exception:
            pass

    mail.To = empfaenger_email
    mail.Subject = f"AW: {betreff}" if ist_antwort else betreff
    mail.Body = inhalt
    try:
        mail.Send()
        hole_relevante_emails.clear()
        return True
    except Exception as e:
        st.error(f"Kritischer Outlook-Sendefehler: {e}")
        return False

# ==========================================
# 6. FUSIONIERTES CSS
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main .block-container { overflow-anchor: none; }
    div[data-testid="stForm"] { margin-bottom: 0.25rem; }
    .router-result-panel { min-height: 0; overflow-anchor: none; }
    .outlook-card { background-color: #ffffff; padding: 14px; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 10px; font-size: 14px; }
    .action-btn { background-color: #0062cc; color: white !important; font-weight: bold; padding: 15px; border-radius: 8px; text-align: center; text-decoration: none; display: block; margin-bottom: 10px; }
    .action-btn:hover { background-color: #004ba0; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 7. HEADER & GLOBALES KOMMANDO-FELD
# ==========================================
col_logo, col_title = st.columns([1, 8])
with col_logo:
    if os.path.exists("LogoDigiBestrundCMYK.jpg"): st.image("LogoDigiBestrundCMYK.jpg", width=60)
with col_title:
    st.markdown("#### DigiWiki Zentrale")

with st.expander("📊 System-Status & Dashboard"):
    status_daten = lade_json_daten("./wiki_stand.json")
    st.metric(label="Verarbeitete Dokumente", value=f"{len(status_daten)} Stück")
    if st.button("🔄 Chat-Verlauf leeren", use_container_width=True):
        st.session_state.chat_historie = []
        st.session_state.chat_qa_paare = []
        st.session_state.chat_qa_naechste_id = 0
        from frage_kontext import FrageKontext

        st.session_state.frage_kontext = FrageKontext().to_dict()
        st.rerun()

st.markdown("---")

# --- DIKTAT: Browser-Aufnahme + serverseitige Spracherkennung ---
# Vor allem fuer den Desktop-Browser gedacht (am Handy gibt es das Tastatur-Mikro).
def transkribiere_audio(audio_bytes):
    """Wandelt aufgenommene WAV-Audiodaten in Text um. Rueckgabe: (text, fehler)."""
    try:
        r = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(audio_bytes)) as quelle:
            audio = r.record(quelle)
        return r.recognize_google(audio, language="de-DE"), None
    except sr.UnknownValueError:
        return None, "Konnte die Aufnahme nicht verstehen. Bitte erneut versuchen."
    except sr.RequestError:
        return None, "Keine Verbindung zur Spracherkennung (Internet?)."
    except Exception as e:
        return None, f"Diktat-Fehler: {e}"


def diktat_popover(ziel_key, popover_label="🎤", hinweis="Aufnehmen – der Text wird ins Feld übernommen:"):
    """Kompakter Mikro-Button (Popover), der erkannten Text an session_state[ziel_key] anhaengt.

    WICHTIG:
    - Muss im Code VOR dem zugehoerigen Eingabe-Widget stehen, da wir session_state[ziel_key]
      sonst nicht mehr setzen duerfen (Streamlit verbietet das nach Widget-Instanzierung).
    - Darf NICHT innerhalb eines st.form stehen (audio_input wuerde erst beim Submit ausloesen).
    """
    if not hasattr(st, "audio_input"):
        return
    run_key = f"_mic_run_{ziel_key}"
    sig_key = f"_mic_sig_{ziel_key}"
    behaelter = st.popover(popover_label) if hasattr(st, "popover") else st.expander(popover_label)
    with behaelter:
        audio = st.audio_input(
            hinweis,
            key=f"_mic_audio_{ziel_key}_{st.session_state.get(run_key, 0)}",
            label_visibility="collapsed",
        )
        if audio is not None:
            audio_bytes = audio.getvalue()
            signatur = hashlib.md5(audio_bytes).hexdigest()
            if st.session_state.get(sig_key) != signatur:
                st.session_state[sig_key] = signatur
                with st.spinner("Verarbeite Sprache ..."):
                    text, fehler = transkribiere_audio(audio_bytes)
                if fehler:
                    st.warning(fehler)
                elif text:
                    bestehend = str(st.session_state.get(ziel_key, "") or "")
                    st.session_state[ziel_key] = f"{bestehend} {text}".strip() if bestehend else text
                    st.session_state[run_key] = st.session_state.get(run_key, 0) + 1
                    st.session_state[sig_key] = None
                    st.rerun()


def feld_mit_mikro(ziel_key, render_widget, mic_label="🎤"):
    """Rendert ein Eingabe-Widget (per render_widget mit key=ziel_key) mit Mikro-Button daneben.

    render_widget: callable ohne Argumente, erzeugt das Widget und gibt dessen Wert zurueck.
    Nicht innerhalb von st.form verwenden (siehe diktat_popover).
    """
    spalte_feld, spalte_mic = st.columns([0.88, 0.12])
    with spalte_mic:
        diktat_popover(ziel_key, popover_label=mic_label)
    with spalte_feld:
        return render_widget()


def merke_kontakt_keyword(begriff):
    """Merkt einen Such-/Kontaktbegriff fuer Vorschlaege und Anschlussfragen."""
    begriff = str(begriff or "").strip()
    if not begriff:
        return
    st.session_state.letzter_kontakt = begriff
    historie = [b for b in st.session_state.get("kontakt_historie", []) if b.lower() != begriff.lower()]
    historie.insert(0, begriff)
    st.session_state.kontakt_historie = historie[:8]


def zeige_kontakt_historie(ziel_key, prefix):
    """Zeigt die letzten Suchbegriffe als Buttons; ein Klick fuellt das Feld ziel_key.

    Muss im Code VOR dem zugehoerigen Feld stehen (setzt session_state[ziel_key]).
    """
    historie = st.session_state.get("kontakt_historie", [])
    if not historie:
        return
    st.caption("Zuletzt verwendet:")
    spalten = st.columns(min(len(historie), 4))
    for i, begriff in enumerate(historie[:4]):
        with spalten[i]:
            if st.button(begriff, key=f"{prefix}_{i}", use_container_width=True):
                st.session_state[ziel_key] = begriff
                st.rerun()


if hasattr(st, "audio_input"):
    with st.expander("🎤 Diktat aufnehmen (für Desktop ohne Tastatur-Mikro)"):
        audio_value = st.audio_input(
            "Aufnehmen – der erkannte Text erscheint unten editierbar im Kommando-Feld:",
            key=f"diktat_audio_{st.session_state.get('diktat_run', 0)}",
        )
        if audio_value is not None:
            audio_bytes = audio_value.getvalue()
            signatur = hashlib.md5(audio_bytes).hexdigest()
            if st.session_state.get("diktat_signatur") != signatur:
                st.session_state.diktat_signatur = signatur
                with st.spinner("Verarbeite Sprache ..."):
                    text, fehler = transkribiere_audio(audio_bytes)
                if fehler:
                    st.warning(fehler)
                elif text:
                    bestehend = st.session_state.get("global_cmd_input", "")
                    st.session_state.global_cmd_input = f"{bestehend} {text}".strip()
                    st.rerun()

# Kommando-Feld nach dem Ausfuehren leeren (vor Widget-Erstellung). Bewusst KEIN
# clear_on_submit, da das mit programmatisch gesetztem Diktat-Text kollidiert und
# nach dem ersten Absenden weitere Ausfuehrungen blockieren kann.
if st.session_state.get("cmd_clear"):
    st.session_state.global_cmd_input = ""
    st.session_state.cmd_clear = False

# DER KI-SPRACHROUTER (Entkoppelt: Eingabe -> Editieren -> Ausführen)
with st.form("form_global_cmd", clear_on_submit=False):
    global_cmd = st.text_input(
        "🎙️ Kommando (Diktieren, ggf. korrigieren, dann starten):",
        placeholder="z.B. Rufe Marc Gebur an... oder: Notiere für das Meeting...",
        key="global_cmd_input",
    )
    btn_execute = st.form_submit_button("🚀 Ausführen", use_container_width=True)

if btn_execute and global_cmd and global_cmd.strip():
    st.session_state.pending_global_cmd = global_cmd.strip()
    # Nach dem Ausfuehren: Kommando-Feld leeren + Diktat-Aufnahme zuruecksetzen,
    # damit die App fuer die naechste Anweisung bereit ist.
    st.session_state.cmd_clear = True
    _alter_audio_key = f"diktat_audio_{st.session_state.get('diktat_run', 0)}"
    st.session_state.pop(_alter_audio_key, None)
    st.session_state.diktat_run = st.session_state.get("diktat_run", 0) + 1
    st.session_state.diktat_signatur = None
    st.rerun()

if st.session_state.pending_global_cmd:
    cmd_text = st.session_state.pending_global_cmd
    st.session_state.pending_global_cmd = None
    with st.spinner("Analysiere Kommando..."):
        analyse = analysiere_sprachkommando(cmd_text, st.session_state.get("letzter_kontakt", ""))
        kategorie = analyse.get("kategorie", "datenbank")

        if kategorie == "anruf":
            such_name = (analyse.get("ziel_name", "") or "").strip()
            # Anschlussbefehl ohne expliziten Namen ("ruf ihn an") -> letzten Kontakt nutzen.
            if not such_name:
                such_name = st.session_state.get("letzter_kontakt", "")
            if such_name:
                merke_kontakt_keyword(such_name)
            st.session_state.router_state = {
                "kategorie": "anruf",
                "such_name": such_name,
                "df_tel": suche_telefonnummer(such_name),
            }
        elif kategorie == "notiz":
            notiz_text = analyse.get("text_inhalt", "")
            erfolg, msg = erstelle_outlook_notiz(notiz_text)
            st.session_state.router_state = {
                "kategorie": "notiz",
                "notiz_erfolg": erfolg,
                "notiz_msg": msg,
                "notiz_text": notiz_text,
            }
        elif kategorie == "datenbank":
            st.session_state.pending_chat_frage = {
                "frage": analyse.get("text_inhalt", cmd_text),
                "typ": "datenbank",
            }
            st.session_state.router_state = None
        else:
            # Fallback: alles andere geht als Wissensfrage an die Chroma-Wissensbasis.
            st.session_state.pending_chat_frage = {
                "frage": analyse.get("text_inhalt", cmd_text),
                "typ": "wissen",
            }
            st.session_state.router_state = None

router_panel = st.container()
with router_panel:
    if st.session_state.router_state:
        state = st.session_state.router_state

        if state.get("kategorie") == "anruf":
            such_name = state["such_name"]
            df_tel = state["df_tel"]
            if not df_tel.empty:
                def clean_for_dialer(num):
                    if not num or str(num).lower() in ["nan", "none"]: return ""
                    return "".join(c for c in str(num) if c.isdigit() or c == '+')

                found_count = 0
                for _, row in df_tel.iterrows():
                    name = f"{row.get('vorname', '')} {row.get('nachname', '')}".strip()
                    quelle = row.get("quelle", "")
                    personid = row.get("personid", "")
                    if personid:
                        st.caption(f"personid: {personid} ({quelle})")
                    if quelle == "WL":
                        meta = []
                        if row.get("Anrede"): meta.append(str(row.get("Anrede")))
                        if row.get("Ansprache"): meta.append(str(row.get("Ansprache")))
                        if meta:
                            st.caption(" · ".join(meta))
                    firma = _kontakt_firma_aus_row(row)
                    if firma:
                        st.caption(f"🏢 {firma}")
                    final_mobil = clean_for_dialer(row.get("mobil") or row.get("wl_mobil") or row.get("handy"))
                    fest = clean_for_dialer(row.get("telefon"))

                    if final_mobil:
                        st.markdown(f"<a class='action-btn' style='background-color:#16a34a;' href='tel:{final_mobil}'>📞 {name} (Mobil)</a>", unsafe_allow_html=True)
                        found_count += 1
                    if fest:
                        st.markdown(f"<a class='action-btn' style='background-color:#15803d;' href='tel:{fest}'>☎️ {name} (Festnetz)</a>", unsafe_allow_html=True)
                        found_count += 1
                    linkedin_url = normalisiere_linkedin_url(row.get("linkedin_url") or row.get("LinkedIn_URL"))
                    if linkedin_url:
                        st.markdown(
                            f"<a class='action-btn' style='background-color:#0a66c2;' href='{linkedin_url}' target='_blank'>🔗 LinkedIn-Profil</a>",
                            unsafe_allow_html=True,
                        )
                if found_count == 0:
                    st.error(f"⚠️ {such_name} hat keine hinterlegten Telefonnummern.")
            else:
                st.error(f"Konnte keinen Kontakt für '{such_name}' finden.")

        elif state.get("kategorie") == "notiz":
            if state.get("notiz_erfolg"):
                st.success(f"✅ {state.get('notiz_msg')}: {state.get('notiz_text')}")
            else:
                st.error(state.get("notiz_msg"))
    st.session_state.router_state = None

# ==========================================
# 8. HAUPTBEREICH (Tabs)
# ==========================================
if "chat_historie" not in st.session_state: st.session_state.chat_historie = []

_haupttab_labels = {
    "chat": "💬 Wiki & Daten",
    "mails": "📬 Mails & Kontakte",
    "agenda": "📅 Agenda & Notizen",
}
haupttab = st.radio(
    "Bereich",
    options=list(_haupttab_labels.keys()),
    format_func=lambda key: _haupttab_labels[key],
    horizontal=True,
    label_visibility="collapsed",
    key="haupttab",
)

# --- REITER 1: CHAT ---
if haupttab == "chat":
    _chat_modus_labels = {
        "auto": AUTO_MODUS_LABEL,
        "wissen": "🧠 Wiki-Wissen",
        "datenbank": "🗄️ Datenbank (SQL)",
    }
    col_modus, col_bereich = st.columns([1, 1])
    with col_modus:
        chat_modus = st.radio(
            "Modus",
            options=list(_chat_modus_labels.keys()),
            format_func=lambda key: _chat_modus_labels[key],
            horizontal=True,
            key="chat_modus",
        )
    with col_bereich:
        if chat_modus in ("wissen", "auto"):
            wiki_bereich = st.selectbox(
                "Wissensbereich",
                options=liste_wissensbereiche(),
                key="wiki_bereich",
            )
        else:
            wiki_bereich = None

    from frage_kontext import FrageKontext, kontext_caption

    _kontext = FrageKontext.from_dict(st.session_state.get("frage_kontext"))
    if _kontext.hat_kontext():
        st.caption(f"🧠 {kontext_caption(_kontext)} — Folgefragen beziehen sich darauf.")

    # Sprach-Eingabe (Diktat) als Alternative zum Chat-Feld unten.
    if st.session_state.pop("_clear_chat_voice", False):
        st.session_state["chat_voice_text"] = ""
    sp_mic, sp_txt, sp_btn = st.columns([0.12, 0.73, 0.15])
    with sp_mic:
        diktat_popover("chat_voice_text")
    with sp_txt:
        st.text_input(
            "Sprach-Eingabe",
            key="chat_voice_text",
            label_visibility="collapsed",
            placeholder="🎤 diktieren oder tippen, dann 'Fragen'",
        )
    with sp_btn:
        chat_voice_senden = st.button("Fragen", use_container_width=True)

    zeige_chat_verlauf_mit_markierung()

    eingabe_frage = st.chat_input("Frage ans Wiki oder die Datenbank...")

    # Frage + Typ ermitteln: direkte Eingabe nutzt den gewaehlten Modus (auto = Klassifikation),
    # eine vom Sprach-Router uebergebene Frage bringt ihren eigenen Typ mit.
    frage = None
    frage_modus = chat_modus
    frage_typ_explizit = None
    if eingabe_frage:
        frage = eingabe_frage
        frage_modus = chat_modus
    elif chat_voice_senden and (st.session_state.get("chat_voice_text", "") or "").strip():
        frage = st.session_state.get("chat_voice_text", "").strip()
        frage_modus = chat_modus
        st.session_state["_clear_chat_voice"] = True
    elif st.session_state.pending_chat_frage:
        pending = st.session_state.pending_chat_frage
        st.session_state.pending_chat_frage = None
        if isinstance(pending, dict):
            frage = pending.get("frage")
            frage_typ_explizit = pending.get("typ")
            frage_modus = "auto"
        else:
            frage = pending
            frage_typ_explizit = "wissen"
            frage_modus = "auto"

    if frage:
        from frage_kontext import (
            FrageKontext,
            aktualisiere_kontext,
            baue_sql_kontext_block,
            baue_wiki_kontext_block,
            bereichere_frage,
            ist_folgefrage,
            kontext_caption,
        )

        kontext = FrageKontext.from_dict(st.session_state.get("frage_kontext"))
        frage_original = frage
        if ist_folgefrage(frage, kontext):
            frage = bereichere_frage(frage, kontext)
            st.caption(f"🔗 Folgefrage — {kontext_caption(kontext)}")

        historie_text = baue_chat_historie_text(st.session_state.chat_historie)
        wiki_kontext = baue_wiki_kontext_block(kontext)
        if wiki_kontext:
            historie_text = f"{historie_text}\n{wiki_kontext}".strip()
        frage_typ = ermittle_frage_typ(frage, frage_modus, frage_typ_explizit)
        wiki_fallback = frage_modus == "auto" and erlaube_wiki_fallback(frage_typ, frage)
        wiki_bereich_aktiv = effektiver_wiki_bereich(frage, wiki_bereich)

        with st.chat_message("user"):
            st.markdown(frage_original)
        st.session_state.chat_historie.append({"rolle": "user", "text": frage_original})

        with st.chat_message("assistant"):
            qa_id_aktuell = None
            if frage_typ == "wissen":
                with st.spinner("Durchsuche die Wissensbasis..."):
                    ergebnis = frage_das_wiki(frage, historie_text=historie_text, bereich=wiki_bereich_aktiv)
                antwort = ergebnis.get("antwort", "")
                quellen = ergebnis.get("quellen", [])
                st.caption("🧠 Antwort aus Wiki-Wissensbasis")
                st.markdown(antwort)
                if quellen:
                    st.caption("📚 Quellen: " + ", ".join(quellen))
                hist_text = antwort
                if quellen:
                    hist_text += "\n\n*📚 Quellen: " + ", ".join(quellen) + "*"
                qa_id_aktuell = chat_qa_hinzufuegen(frage_original, antwort, "wiki", quellen=quellen)
                st.session_state.chat_historie.append({
                    "rolle": "assistant",
                    "text": hist_text,
                    "qa_id": qa_id_aktuell,
                })
                aktualisiere_kontext(kontext, frage_original, "wiki")
                st.session_state.frage_kontext = kontext.to_dict()
            else:
                sql_erfolg = False
                with st.spinner("Durchsuche Datenbank..."):
                    try:
                        direkt_sql = None
                        firmen_such = extrahiere_firmen_suchbegriff(frage_original) or kontext.firma
                        if ist_folgefrage(frage_original, kontext) and kontext.kundennumm:
                            direkt_sql = baue_direkt_sql_folgefrage(
                                frage_original, kontext.kundennumm, kontext.thema
                            )
                        if not direkt_sql:
                            direkt_sql = baue_direkt_sql_firma_produkte(
                                frage_original,
                                kundennumm=kontext.kundennumm,
                                firmen_such=firmen_such,
                            )
                        generiertes_sql = direkt_sql or uebersetze_frage_in_sql(
                            frage,
                            db_schema,
                            db_dictionary,
                            kontext_block=baue_sql_kontext_block(kontext),
                        )
                        generiertes_sql = bereinige_access_sql(generiertes_sql)
                        ergebnis = fuehre_sql_aus(generiertes_sql)

                        if isinstance(ergebnis, pd.DataFrame) and not ergebnis.empty:
                            sql_erfolg = True
                            st.caption(kaskaden_quellen_caption(frage_typ, "sql"))
                            synthese = None
                            if synthese_aktiv() and soll_synthese_anwenden(frage_original, ergebnis):
                                with st.spinner("Erstelle KI-Briefing (ArtikelDB + Stamm) …"):
                                    synthese = _versuche_ki_synthese(
                                        frage_original,
                                        sql_df=ergebnis,
                                        kundennumm=kontext.kundennumm,
                                        firmen_such=firmen_such,
                                    )
                            if synthese and synthese.ok:
                                st.caption(kaskaden_quellen_caption(frage_typ, "ki"))
                                st.markdown(synthese.text)
                            with st.expander(f"Rohdaten: {len(ergebnis)} Datensätze (SQL)", expanded=not (synthese and synthese.ok)):
                                st.dataframe(ergebnis, use_container_width=True)
                            sql_md = sql_df_zu_markdown(ergebnis)
                            if synthese and synthese.ok:
                                antwort_sql = synthese.text
                                chat_text = f"{synthese.text}\n\n---\n\n**Rohdaten ({len(ergebnis)} Zeilen)**\n\n{sql_md}"
                            else:
                                antwort_sql = f"{len(ergebnis)} Datensätze in der Datenbank gefunden."
                                chat_text = f"**{len(ergebnis)} Datensätze (SQL)**\n\n{sql_md}"
                            qa_id_aktuell = chat_qa_hinzufuegen(
                                frage_original, antwort_sql, "sql", sql_markdown=sql_md,
                            )
                            st.session_state.chat_historie.append({
                                "rolle": "assistant",
                                "text": chat_text,
                                "qa_id": qa_id_aktuell,
                            })
                            aktualisiere_kontext(kontext, frage_original, "sql", ergebnis_df=ergebnis)
                            st.session_state.frage_kontext = kontext.to_dict()
                        elif isinstance(ergebnis, pd.DataFrame) and ergebnis.empty:
                            kaskade_kn = kontext.kundennumm
                            kaskade_firma = kontext.firma
                            if not kaskade_kn and firmen_such:
                                db_hit = suche_firma_in_db(firmen_such)
                                if db_hit:
                                    kaskade_kn = db_hit.get("kundennumm", "")
                                    kaskade_firma = kaskade_firma or db_hit.get("firmenname", "")

                            live_fehler = ""
                            if ist_einzel_firma_live_web_frage(frage):
                                with st.spinner(
                                    "Live-Recherche auf Firmen-Website (installierter Chrome) …"
                                ):
                                    live = firmen_live_recherche(
                                        frage,
                                        kundennumm=kaskade_kn or None,
                                        firmenname=kaskade_firma or None,
                                    )
                                if live.ok:
                                    sql_erfolg = True
                                    st.caption(kaskaden_quellen_caption(frage_typ, "web"))
                                    if live.aus_cache:
                                        st.caption("(aus Web-Cache, max. 7 Tage)")
                                    live_synthese = None
                                    if synthese_aktiv():
                                        with st.spinner("Erstelle KI-Briefing (Web + CRM) …"):
                                            live_synthese = _versuche_ki_synthese(
                                                frage_original,
                                                kundennumm=live.kundennumm,
                                                firmen_such=live.firmenname,
                                                web_text=live.text,
                                            )
                                    if live_synthese and live_synthese.ok:
                                        st.caption(kaskaden_quellen_caption(frage_typ, "ki"))
                                        st.markdown(live_synthese.text)
                                        with st.expander(
                                            f"Live-Website: {live.firmenname}",
                                            expanded=False,
                                        ):
                                            st.markdown(
                                                f"[{live.url}]({live.url})\n\n{live.text[:8000]}"
                                            )
                                        live_antwort = live_synthese.text
                                        live_chat = (
                                            f"{live_synthese.text}\n\n---\n\n"
                                            f"**Live-Web:** [{live.url}]({live.url})"
                                        )
                                    else:
                                        st.markdown(
                                            f"**{live.firmenname}** — [{live.url}]({live.url})\n\n"
                                            f"{live.text[:12000]}"
                                        )
                                        live_antwort = (
                                            f"**{live.firmenname}** — {live.url}\n\n{live.text[:12000]}"
                                        )
                                        live_chat = live_antwort
                                    if live.personen_liste:
                                        neu = live.personen_neu or 0
                                        vorh = live.personen_vorhanden or 0
                                        akt = live.personen_aktualisiert or 0
                                        st.caption(
                                            f"crm_personen: {neu} neu, {vorh} bereits vorhanden"
                                            + (f", {akt} aktualisiert" if akt else "")
                                        )
                                        st.table(
                                            [
                                                {
                                                    "Anrede": p.get("anrede", ""),
                                                    "Titel": p.get("titel", ""),
                                                    "Vorname": p.get("vorname", ""),
                                                    "Nachname": p.get("nachname", ""),
                                                    "Funktion": p.get("funktion", ""),
                                                    "FunktionID": p.get("funktionid", ""),
                                                    "Status": p.get("status", ""),
                                                }
                                                for p in live.personen_liste
                                            ]
                                        )
                                        st.caption(
                                            "Beim nächsten Mal antwortet SQL direkt aus crm_personen "
                                            "(JOIN ref_funktionen, Ebene 1–2)."
                                        )
                                    elif live.md_pfad:
                                        st.caption(f"MD-Snapshot: `{live.md_pfad}`")
                                    qa_id_aktuell = chat_qa_hinzufuegen(
                                        frage_original,
                                        live_antwort,
                                        "live_web",
                                    )
                                    st.session_state.chat_historie.append({
                                        "rolle": "assistant",
                                        "text": live_chat,
                                        "qa_id": qa_id_aktuell,
                                    })
                                    aktualisiere_kontext(
                                        kontext,
                                        frage_original,
                                        "live_web",
                                        live_firma=live.firmenname,
                                        live_kundennumm=live.kundennumm,
                                        live_personen=live.personen_liste,
                                    )
                                    st.session_state.frage_kontext = kontext.to_dict()
                                else:
                                    live_fehler = live.fehler or "Live-Web fehlgeschlagen."
                                    kaskade_kn = kaskade_kn or live.kundennumm
                                    kaskade_firma = kaskade_firma or live.firmenname

                            if (
                                not sql_erfolg
                                and kaskade_kn
                                and ist_einzel_firma_md_fallback_frage(frage)
                            ):
                                with st.spinner("MD-Archiv (Fallback fuer diese Firma) …"):
                                    md = firmen_md_fallback(
                                        frage,
                                        kundennumm=kaskade_kn,
                                        firmenname=kaskade_firma or "",
                                    )
                                if md.ok:
                                    sql_erfolg = True
                                    st.caption(kaskaden_quellen_caption(frage_typ, "md"))
                                    titel = kaskade_firma or f"kundennumm {kaskade_kn}"
                                    md_synthese = None
                                    if synthese_aktiv():
                                        with st.spinner("Erstelle KI-Briefing (MD + CRM) …"):
                                            md_synthese = _versuche_ki_synthese(
                                                frage_original,
                                                kundennumm=kaskade_kn,
                                                firmen_such=kaskade_firma or "",
                                                md_text=md.text,
                                            )
                                    if md_synthese and md_synthese.ok:
                                        st.caption(kaskaden_quellen_caption(frage_typ, "ki"))
                                        st.markdown(md_synthese.text)
                                        with st.expander("MD-Archiv (Rohdaten)", expanded=False):
                                            st.markdown(md.text[:8000])
                                        md_antwort = md_synthese.text
                                        md_chat = f"{md_synthese.text}\n\n---\n\n**MD-Archiv** ({titel})"
                                    else:
                                        st.markdown(
                                            f"**{titel}** — MD-Website-Archiv\n\n{md.text[:12000]}"
                                        )
                                        md_antwort = f"**{titel}** — MD-Archiv\n\n{md.text[:12000]}"
                                        md_chat = md_antwort
                                    if md.dateien:
                                        st.caption(
                                            "Quellen: "
                                            + ", ".join(os.path.basename(d) for d in md.dateien)
                                        )
                                    qa_id_aktuell = chat_qa_hinzufuegen(
                                        frage_original,
                                        md_antwort,
                                        "md_fallback",
                                    )
                                    st.session_state.chat_historie.append({
                                        "rolle": "assistant",
                                        "text": md_chat,
                                        "qa_id": qa_id_aktuell,
                                    })
                                    aktualisiere_kontext(
                                        kontext,
                                        frage_original,
                                        "md_fallback",
                                        live_firma=kaskade_firma,
                                        live_kundennumm=kaskade_kn,
                                    )
                                    st.session_state.frage_kontext = kontext.to_dict()

                            if not sql_erfolg and not wiki_fallback:
                                if live_fehler:
                                    st.warning(live_fehler)
                                st.info(meldung_sql_leer(frage))
                                st.session_state.chat_historie.append({
                                    "rolle": "assistant",
                                    "text": "Keine SQL-Treffer; Kaskade ohne Ergebnis.",
                                })
                        elif isinstance(ergebnis, str) and ergebnis.startswith("Fehler"):
                            st.warning(ergebnis)
                        else:
                            st.warning(str(ergebnis))
                    except Exception as e:
                        st.warning(f"Abfrage fehlgeschlagen: {e}")

                if not sql_erfolg and wiki_fallback:
                    st.caption("Keine SQL-Treffer – Wiki-Dokumente (kein Marktdaten-Fallback) …")
                    with st.spinner("Durchsuche die Wissensbasis..."):
                        ergebnis = frage_das_wiki(frage, historie_text=historie_text, bereich=wiki_bereich_aktiv)
                    antwort = ergebnis.get("antwort", "")
                    quellen = ergebnis.get("quellen", [])
                    st.caption(kaskaden_quellen_caption(frage_typ, "wiki"))
                    st.markdown(antwort)
                    if quellen:
                        st.caption("📚 Quellen: " + ", ".join(quellen))
                    hist_text = antwort
                    if quellen:
                        hist_text += "\n\n*📚 Quellen: " + ", ".join(quellen) + "*"
                    qa_id_aktuell = chat_qa_hinzufuegen(frage_original, antwort, "wiki_fallback", quellen=quellen)
                    st.session_state.chat_historie.append({
                        "rolle": "assistant",
                        "text": hist_text,
                        "qa_id": qa_id_aktuell,
                    })
                    aktualisiere_kontext(kontext, frage_original, "wiki_fallback")
                    st.session_state.frage_kontext = kontext.to_dict()
            if qa_id_aktuell is not None:
                zeige_qa_aktionszeile(qa_id_aktuell)

    zeige_qa_export_panel()

# --- REITER 2: MAILS & WHATSAPP ---
elif haupttab == "mails":
    with st.expander("✉️ Neue E-Mail verfassen", expanded=False):
        zeige_kontakt_historie("ne_mail_such_input", "hist_ne_mail")
        c_ne_mic, c_ne_feld, c_ne_btn = st.columns([0.12, 0.73, 0.15])
        with c_ne_mic:
            diktat_popover("ne_mail_such_input")
        with c_ne_feld:
            st.text_input(
                "🔍 Empfänger suchen...",
                key="ne_mail_such_input",
                placeholder="Name oder Firma…",
                label_visibility="collapsed",
            )
        with c_ne_btn:
            btn_ne_mail_suchen = st.button("🔍", key="btn_ne_mail_suchen", use_container_width=True)

        if btn_ne_mail_suchen:
            st.session_state.ne_mail_suchbegriff = (st.session_state.get("ne_mail_such_input", "") or "").strip()
            st.session_state.ne_mail_kontakt_key = None
            merke_kontakt_keyword(st.session_state.ne_mail_suchbegriff)
            _ne_mail_entwurf_zuruecksetzen()

        ne_suchbegriff = st.session_state.ne_mail_suchbegriff
        df_ne_mail = suche_email_kontakte(ne_suchbegriff) if ne_suchbegriff else pd.DataFrame()

        if not ne_suchbegriff:
            st.caption("Name oder Firma eingeben und Suchen klicken.")
        elif df_ne_mail.empty:
            st.info("Keine Treffer gefunden.")
        else:
            for _, row in df_ne_mail.iterrows():
                name = f"{row.get('vorname', '')} {row.get('nachname', '')}".strip()
                key = kontakt_email_schluessel(row)
                optionen = baue_email_optionen_aus_kontakt(row)
                firma = _kontakt_firma_aus_row(row)
                label = f"📧 {name}" + (f" ({firma})" if firma else "") + ("" if optionen else " (keine E-Mail)")
                if st.button(label, key=f"btn_ne_mail_{key}", disabled=not optionen):
                    st.session_state.ne_mail_kontakt_key = key
                    merke_kontakt_keyword(name)
                    _ne_mail_entwurf_zuruecksetzen()
                    st.rerun()

        if st.session_state.ne_mail_kontakt_key and not df_ne_mail.empty:
            sel_rows = [
                r for _, r in df_ne_mail.iterrows()
                if kontakt_email_schluessel(r) == st.session_state.ne_mail_kontakt_key
            ]
            if sel_rows:
                _ne_mail_entwurf_widget_sync()
                row = sel_rows[0]
                name = f"{row.get('vorname', '')} {row.get('nachname', '')}".strip()
                ansprache = _ansprache_aus_kontakt(row)
                email_optionen = baue_email_optionen_aus_kontakt(row)

                st.markdown(f"**Neue E-Mail an {name}**")
                st.caption(f"Anrede-Stil: **{ansprache}** (aus Whitelist)")
                brandvoice_wahl = _brandvoice_radio("ne_mail_brandvoice")
                absender_konten = hole_outlook_konten()
                absender_keys = [k["key"] for k in absender_konten]
                absender_labels = {k["key"]: k["label"] for k in absender_konten}
                absender = st.selectbox(
                    "Absender-Konto",
                    absender_keys,
                    format_func=lambda key: absender_labels.get(key, key),
                    key="ne_mail_absender",
                )
                email_labels = [o["label"] for o in email_optionen]
                gewaehlte_label = st.radio("Empfänger-Adresse", email_labels, key="ne_mail_empf_adresse")
                empfaenger_email = next(o["email"] for o in email_optionen if o["label"] == gewaehlte_label)
                betreff = feld_mit_mikro(
                    "ne_mail_betreff",
                    lambda: st.text_input("Betreff", key="ne_mail_betreff"),
                )
                anweisung = feld_mit_mikro(
                    "ne_mail_anweisung",
                    lambda: st.text_area(
                        "Worum geht es? (diktieren oder tippen)",
                        placeholder="z.B. Terminvorschlag für nächste Woche…",
                        key="ne_mail_anweisung",
                    ),
                )
                col_gen, col_close = st.columns(2)
                with col_gen:
                    if st.button("✨ KI-Entwurf generieren", key="btn_ne_mail_gen", use_container_width=True):
                        if not anweisung.strip():
                            st.warning("Bitte kurz beschreiben, worum es geht.")
                        else:
                            with st.spinner("KI schreibt Entwurf…"):
                                _ne_mail_entwurf_bereitstellen(
                                    generiere_neue_mail_entwurf(
                                        anweisung.strip(), ansprache, name, betreff.strip(),
                                        brandvoice_wahl=brandvoice_wahl,
                                    )
                                )
                            st.rerun()
                with col_close:
                    if st.button("✖ Abbrechen", key="btn_ne_mail_close", use_container_width=True):
                        st.session_state.ne_mail_kontakt_key = None
                        _ne_mail_entwurf_zuruecksetzen()
                        st.rerun()

                entwurf = feld_mit_mikro(
                    "ne_mail_entwurf_edit",
                    lambda: st.text_area(
                        "Mail-Entwurf",
                        height=220,
                        key="ne_mail_entwurf_edit",
                    ),
                )
                if str(entwurf or "").startswith("Fehler bei der KI-Generierung:"):
                    st.error(entwurf)
                if st.button("🚀 Senden", key="btn_ne_mail_send", use_container_width=True):
                    if not betreff.strip():
                        st.warning("Bitte einen Betreff eingeben.")
                    elif not entwurf.strip():
                        st.warning("Bitte einen Mail-Text eingeben oder KI-Entwurf generieren.")
                    elif sende_email_via_outlook(
                        empfaenger_email,
                        betreff.strip(),
                        entwurf.strip(),
                        absender,
                        ist_antwort=False,
                    ):
                        st.success(f"E-Mail an {name} versendet.")
                        st.session_state.ne_mail_kontakt_key = None
                        _ne_mail_entwurf_zuruecksetzen()
                        st.rerun()

    with st.expander("📱 Manuelle WhatsApp senden"):
        zeige_kontakt_historie("wa_such_input", "hist_wa")
        c_wa_mic, c_wa_feld, c_wa_btn = st.columns([0.12, 0.73, 0.15])
        with c_wa_mic:
            diktat_popover("wa_such_input")
        with c_wa_feld:
            st.text_input(
                "🔍 Kontakt suchen...",
                key="wa_such_input",
                placeholder="Name oder Firma…",
                label_visibility="collapsed",
            )
        with c_wa_btn:
            btn_wa_suchen = st.button("🔍", key="btn_wa_suchen", use_container_width=True)

        if btn_wa_suchen:
            st.session_state.wa_suchbegriff = (st.session_state.get("wa_such_input", "") or "").strip()
            st.session_state.wa_selected_id = None
            merke_kontakt_keyword(st.session_state.wa_suchbegriff)

        suchbegriff = st.session_state.wa_suchbegriff
        df_anzeige = suche_whatsapp_kontakte(suchbegriff) if suchbegriff else pd.DataFrame()

        if not suchbegriff:
            st.caption("Name oder Firma eingeben und Suchen klicken.")
        elif df_anzeige.empty:
            st.info("Keine Treffer gefunden.")
        else:
            wa_kontakt_liste = st.container()
            with wa_kontakt_liste:
                for _, row in df_anzeige.iterrows():
                    name = f"{row['vorname']} {row['nachname']}".strip()
                    personid = str(row.get("personid", "") or "").strip()
                    if not personid:
                        personid = f"m_{normalisiere_whatsapp_nummer(row['mobil'])}"
                    firma = _kontakt_firma_aus_row(row)
                    btn_label = f"💬 {name}" + (f" ({firma})" if firma else "")
                    if st.button(btn_label, key=f"btn_wa_{personid}"):
                        st.session_state.wa_selected_id = personid
                        merke_kontakt_keyword(name)
                        st.rerun()

        if st.session_state.wa_selected_id and not df_anzeige.empty:
            sel = df_anzeige[
                df_anzeige["personid"].astype(str) == st.session_state.wa_selected_id
            ]
            if sel.empty and st.session_state.wa_selected_id.startswith("m_"):
                nummer = st.session_state.wa_selected_id[2:]
                sel = df_anzeige[
                    df_anzeige["mobil"].apply(normalisiere_whatsapp_nummer) == nummer
                ]
            if not sel.empty:
                row = sel.iloc[0]
                name = f"{row['vorname']} {row['nachname']}".strip()
                ansprache = _ansprache_aus_kontakt(row)
                brandvoice_wahl = _brandvoice_radio(f"wa_brandvoice_{st.session_state.wa_selected_id}")
                wa_anweisung = feld_mit_mikro(
                    f"wa_anweisung_{st.session_state.wa_selected_id}",
                    lambda: st.text_area(
                        "WhatsApp-Text (diktieren oder KI-Entwurf)",
                        placeholder="Kurz, worum es geht…",
                        key=f"wa_anweisung_{st.session_state.wa_selected_id}",
                    ),
                )
                if st.button("✨ KI-Entwurf", key=f"wa_gen_{st.session_state.wa_selected_id}"):
                    if not wa_anweisung.strip():
                        st.warning("Bitte kurz beschreiben, was die Nachricht enthalten soll.")
                    else:
                        st.session_state[f"wa_text_{st.session_state.wa_selected_id}"] = generiere_whatsapp_entwurf(
                            wa_anweisung.strip(), ansprache, name, brandvoice_wahl=brandvoice_wahl
                        )
                        st.rerun()
                wa_text = st.session_state.get(f"wa_text_{st.session_state.wa_selected_id}", wa_anweisung)
                wa_link = baue_whatsapp_link(row["mobil"], wa_text)
                if wa_link:
                    st.markdown(f"**An {name} senden:**")
                    st.markdown(
                        f"<a class='action-btn' href='{wa_link}' target='_blank'>Jetzt WhatsApp öffnen</a>",
                        unsafe_allow_html=True,
                    )
                if st.button("✖ Schließen", key="btn_wa_close"):
                    st.session_state.wa_selected_id = None
                    st.rerun()

    st.markdown("#### 📬 Posteingang (Whitelist)")
    absender_konten = hole_outlook_konten()
    absender_keys = [k["key"] for k in absender_konten]
    absender_labels = {k["key"]: k["label"] for k in absender_konten}
    reply_absender = st.selectbox(
        "Absender-Konto für Antworten",
        absender_keys,
        format_func=lambda key: absender_labels.get(key, key),
        key="reply_mail_absender",
    )
    reply_brandvoice = _brandvoice_radio("reply_mail_brandvoice")
    whitelist_df = lade_whitelist()
    if whitelist_df.empty:
        st.info("Die Whitelist ist leer oder die Datenbank ist nicht erreichbar.")
    else:
        mails = hole_relevante_emails(whitelist_df)
        if isinstance(mails, dict) and mails.get("_outlook_error"):
            hole_relevante_emails.clear()
            st.warning(
                f"Outlook nicht erreichbar: {mails['_outlook_error']}. "
                "Bitte Outlook neu starten und diese Seite neu laden."
            )
        elif not mails:
            st.info("Keine Mails von freigegebenen Kontakten gefunden.")
        else:
            for i, mail in enumerate(mails):
                with st.expander(f"📧 {mail['Name']} | {mail['Betreff']}"):
                    st.text_area("Original-Mail", mail['Inhalt'], height=150, key=f"mail_text_{i}")
                    anweisung = feld_mit_mikro(
                        f"anweisung_{i}",
                        lambda i=i: st.text_input("KI-Anweisung (diktieren!):", key=f"anweisung_{i}"),
                    )
                    if st.button("✨ Entwurf generieren", key=f"btn_gen_{i}"):
                        st.session_state[f"edit_{i}"] = generiere_mail_entwurf(
                            mail["Inhalt"], anweisung, mail["Ansprache"], mail["Name"],
                            brandvoice_wahl=reply_brandvoice,
                        )
                        st.rerun()
                    if f"edit_{i}" in st.session_state:
                        editierter_text = feld_mit_mikro(
                            f"edit_{i}",
                            lambda i=i: st.text_area("Entwurf:", height=200, key=f"edit_{i}"),
                        )
                        if st.button("🚀 Senden", key=f"send_{i}"):
                            if sende_email_via_outlook(
                                mail['Email'], mail['Betreff'], editierter_text, reply_absender, ist_antwort=True
                            ):
                                st.success("Versandt!")
                                del st.session_state[f"edit_{i}"]
                                st.rerun()

# --- REITER 3: AGENDA & NOTIZEN ---
elif haupttab == "agenda":
    col_cal, col_task = st.columns(2)
    outlook_daten, fehler = hole_outlook_woche()

    with col_cal:
        st.markdown("#### 🕒 Terminkalender")
        if fehler: st.info(fehler)
        elif outlook_daten and outlook_daten["termine"]:
            for t in outlook_daten["termine"]:
                ort_text = f" – 📍 {t['Ort']}" if t['Ort'] else ""
                url = extrahiere_url(t.get('Body', ''))
                if url:
                    st.markdown(f"<div class='outlook-card'><b>📅 {t['Datum']} | {t['Zeit']} Uhr</b><br><a href='{url}' target='_blank'>🔗 {t['Betreff']}</a>{ort_text}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='outlook-card'><b>📅 {t['Datum']} | {t['Zeit']} Uhr</b><br>{t['Betreff']}{ort_text}</div>", unsafe_allow_html=True)

    with col_task:
        # Felder nach dem Speichern leeren (vor Widget-Erstellung, da sonst nicht erlaubt).
        if st.session_state.pop("_clear_notiz", False):
            st.session_state["agenda_notiz_text"] = ""
        if st.session_state.pop("_clear_aufgabe", False):
            st.session_state["agenda_aufgabe_text"] = ""

        st.markdown("#### 🎯 Aufgaben & Notizen")
        with st.expander("📝 Neue Notiz (manuell)"):
            manuelle_notiz = feld_mit_mikro(
                "agenda_notiz_text",
                lambda: st.text_area("Notiz diktieren:", key="agenda_notiz_text"),
            )
            if st.button("In Outlook speichern", key="btn_notiz_speichern", use_container_width=True):
                erfolg, msg = erstelle_outlook_notiz(manuelle_notiz)
                if erfolg:
                    st.session_state["_clear_notiz"] = True
                    if hasattr(st, "toast"):
                        st.toast(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(msg)

        with st.expander("➕ Neue Aufgabe"):
            neu_betreff = feld_mit_mikro(
                "agenda_aufgabe_text",
                lambda: st.text_input("Was ist zu tun?*", key="agenda_aufgabe_text"),
            )
            neu_faellig = st.date_input("Fällig am", value=None, key="agenda_aufgabe_faellig")
            if st.button("Aufgabe anlegen", key="btn_aufgabe_anlegen", use_container_width=True):
                if str(neu_betreff or "").strip():
                    erstelle_outlook_aufgabe(neu_betreff, neu_faellig)
                    st.session_state["_clear_aufgabe"] = True
                    st.rerun()
                else:
                    st.warning("Bitte zuerst eingeben, was zu tun ist.")

        if outlook_daten and outlook_daten["aufgaben"]:
            for a in outlook_daten["aufgaben"]:
                with st.container():
                    st.markdown(f"<div class='outlook-card'>📌 <b>{a['Aufgabe']}</b><br><small color='red'>Fällig: {a['Fällig']}</small></div>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    if c1.button("✔️ Erledigt", key=f"done_{a['EntryID']}"):
                        bearbeite_outlook_aufgabe(a['EntryID'], "erledigt")
                        st.rerun()
                    if c2.button("🗑️ Löschen", key=f"del_{a['EntryID']}"):
                        bearbeite_outlook_aufgabe(a['EntryID'], "loeschen")
                        st.rerun()