import streamlit as st

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
if "ne_mail_entwurf" not in st.session_state:
    st.session_state.ne_mail_entwurf = ""
import re
import os
import json
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
    DICTIONARY_PATH,
    MAIL_DOWNLOAD_DIR,
    MAIL_UPLOAD_DIR,
    SCHEMA_PATH,
    WHATSAPP_CLOUD_API_TOKEN,
    WHATSAPP_CLOUD_API_VERSION,
    WHATSAPP_DEFAULT_COUNTRY_CODE,
    WHATSAPP_PHONE_NUMBER_ID,
)

load_dotenv()

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
    teile_filter = []
    for t in teile:
        e = _sql_escape(t)
        teile_filter.append(f"{stamm_alias}.nama LIKE '%{e}%'")
    return "(" + " OR ".join(teile_filter) + ")"


def _baue_kontakt_suchfilter(teile, vorname_feld, nachname_feld, stamm_alias="s"):
    """Name (Vor-/Nachname) oder Firma über stammdatenindustrie.nama."""
    name = _baue_namen_filter(teile, vorname_feld, nachname_feld)
    firma = _baue_firma_filter(teile, stamm_alias=stamm_alias)
    return f"(({name}) OR ({firma}))"


def _baue_crm_where(teile):
    return _baue_kontakt_suchfilter(teile, "p.vorname", "p.nachname", stamm_alias="s")


def _baue_wl_where(teile):
    return _baue_kontakt_suchfilter(teile, "w.[Vorname]", "w.[Nachname]", stamm_alias="s")


def _crm_from_join():
    return """
        FROM crm_personen AS p
        LEFT JOIN stammdatenindustrie AS s ON p.kundennumm = s.kundennumm
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


def _bereinige_telefon_df(df):
    if df.empty:
        return df
    for col in ("mobil", "telefon"):
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).replace(["None", "nan"], "")
    df["num_score"] = df.get("mobil", "").str.len() + df.get("telefon", "").str.len()
    return df.sort_values("num_score", ascending=False).head(5)


@st.cache_data(ttl=60)
def suche_telefonnummer(such_name):
    """Zweistufige Suche: zuerst crm_personen, sonst Whitelist-Fallback."""
    if not such_name:
        return pd.DataFrame()

    teile = _baue_suchteile(such_name)
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
                s.nama AS firma,
                'CRM' AS quelle
            {_crm_from_join()}
            WHERE {_baue_crm_where(teile)}
        """
        df = pd.read_sql(query_crm, conn)

        if not df.empty:
            if "mobiltelefon" in df.columns:
                df["mobil"] = df["mobil"].fillna(df["mobiltelefon"])
                df = df.drop(columns=["mobiltelefon"])
            conn.close()
            return _bereinige_telefon_df(df)

        query_wl = f"""
            SELECT DISTINCT
                w.indpersonid,
                w.Vorname,
                w.Nachname,
                w.Tel_Mobil,
                w.Tel_Gesch,
                w.Anrede,
                w.Ansprache,
                w.LinkedIn_URL,
                s.nama AS firma,
                'WL' AS quelle
            {_wl_from_join()}
            WHERE {_baue_wl_where(teile)}
        """
        df = pd.read_sql(query_wl, conn)
        conn.close()

        if df.empty:
            return df

        df = df.rename(columns={
            "indpersonid": "personid",
            "Vorname": "vorname",
            "Nachname": "nachname",
            "Tel_Mobil": "mobil",
            "Tel_Gesch": "telefon",
            "LinkedIn_URL": "linkedin_url",
        })
        return _bereinige_telefon_df(df)

    except Exception:
        return pd.DataFrame()


def _ist_gueltige_email(wert):
    wert = str(wert or "").strip()
    return bool(wert) and wert.lower() not in ("none", "nan") and "@" in wert


@st.cache_data(ttl=60)
def suche_email_kontakte(such_name):
    """Zweistufige Suche für neue E-Mails: zuerst CRM, sonst Whitelist."""
    if not str(such_name or "").strip():
        return pd.DataFrame()

    teile = _baue_suchteile(such_name)
    conn_str = fr'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};'
    try:
        conn = pyodbc.connect(conn_str, timeout=5)

        query_crm = f"""
            SELECT DISTINCT
                p.personid,
                p.vorname,
                p.nachname,
                p.emailpers,
                p.anrede,
                s.nama AS firma,
                'CRM' AS quelle
            {_crm_from_join()}
            WHERE {_baue_crm_where(teile)}
        """
        df = pd.read_sql(query_crm, conn)

        if not df.empty:
            conn.close()
            return df

        query_wl = f"""
            SELECT DISTINCT
                w.indpersonid,
                w.Vorname,
                w.Nachname,
                w.Email_Gesch,
                w.Email_Priv,
                w.Anrede,
                w.Ansprache,
                s.nama AS firma,
                'WL' AS quelle
            {_wl_from_join()}
            WHERE {_baue_wl_where(teile)}
        """
        df = pd.read_sql(query_wl, conn)
        conn.close()

        if df.empty:
            return df

        return df.rename(columns={
            "indpersonid": "personid",
            "Vorname": "vorname",
            "Nachname": "nachname",
            "Email_Gesch": "email_gesch",
            "Email_Priv": "email_priv",
        })

    except Exception:
        return pd.DataFrame()


def baue_email_optionen_aus_kontakt(row):
    """Liefert wählbare Empfänger-Adressen je nach Quelle (CRM / Whitelist)."""
    optionen = []
    quelle = str(row.get("quelle", "")).upper()
    if quelle == "CRM":
        if _ist_gueltige_email(row.get("emailpers")):
            optionen.append({"label": "Persönlich (CRM)", "email": str(row.get("emailpers")).strip()})
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
def suche_whatsapp_kontakte(such_name):
    """Sucht in crm_personen und Whitelist_Kontakte nach Name (beide Tabellen, Mobilnummer nötig)."""
    if not str(such_name or "").strip():
        return pd.DataFrame()

    teile = _baue_suchteile(such_name)
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
                s.nama AS firma,
                'CRM' AS quelle
            {_crm_from_join()}
            WHERE {_baue_crm_where(teile)}
        """
        df_crm = pd.read_sql(query_crm, conn)
        if not df_crm.empty and "mobiltelefon" in df_crm.columns:
            df_crm["mobil"] = df_crm["mobil"].fillna(df_crm["mobiltelefon"])
            df_crm = df_crm.drop(columns=["mobiltelefon"])

        query_wl = f"""
            SELECT DISTINCT
                w.indpersonid,
                w.Vorname,
                w.Nachname,
                w.Tel_Mobil,
                w.Tel_Gesch,
                s.nama AS firma,
                'WL' AS quelle
            {_wl_from_join()}
            WHERE {_baue_wl_where(teile)}
        """
        df_wl = pd.read_sql(query_wl, conn)
        conn.close()

        if not df_wl.empty:
            df_wl = df_wl.rename(columns={
                "indpersonid": "personid",
                "Vorname": "vorname",
                "Nachname": "nachname",
                "Tel_Mobil": "mobil",
                "Tel_Gesch": "telefon",
            })

        df = pd.concat([df_crm, df_wl], ignore_index=True)
        if df.empty:
            return df

        df["personid"] = (
            df["personid"]
            .fillna("")
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .replace(["nan", "None"], "")
        )
        for col in ("mobil", "telefon"):
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).replace(["None", "nan"], "")

        mobil_ok = df["mobil"].str.strip() != ""
        return df.loc[mobil_ok].drop_duplicates(subset=["mobil"]).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


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
    except Exception as e:
        st.error(f"Datenbank-Fehler beim Laden der Whitelist: {e}")
        return pd.DataFrame()

# ==========================================
# 3. KI LOGIK (NL2SQL & Sprach-Router)
# ==========================================
def analysiere_sprachkommando(kommando_text):
    """Weist den Freitext einer der drei Aktionen (Anruf, Notiz, SQL) zu."""
    client = OpenAI()
    prompt = f"""
    Analysiere den folgenden Befehl und ordne ihn in eine dieser drei Kategorien ein:
    1. 'anruf': Der Nutzer möchte jemanden anrufen (Name extrahieren).
    2. 'notiz': Der Nutzer möchte sich etwas notieren/merken (Inhalt extrahieren).
    3. 'datenbank': Eine allgemeine Frage, die in der SQL-Datenbank gesucht werden soll.

    Antworte AUSSCHLIESSLICH im JSON-Format:
    {{"kategorie": "anruf" | "notiz" | "datenbank", "ziel_name": "Name der Person falls Anruf, sonst leer", "text_inhalt": "Notiztext oder Suchfrage"}}

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

def uebersetze_frage_in_sql(nutzer_frage, schema_text, dictionary_csv):
    client = OpenAI()
    system_prompt = f"""
    Du bist ein SQL-Experte für Microsoft Access (Zugriff via pyodbc). 
    Übersetze die Frage des Nutzers in eine syntaktisch korrekte Access-SQL-Abfrage.
    
    === DATENBANK-SCHEMA ===
    {schema_text}
    
    === DATA DICTIONARY ===
    {dictionary_csv}
    
    === STRIKTE REGELN ===
    1. Antworte AUSSCHLIESSLICH mit dem SQL-Code in EINER Zeile.
    2. Nutze für Textsuchen IMMER '%'.
    3. SEMANTISCHE TEXTSUCHE: Generiere Synonyme und nutze OR.
    4. PERSONEN: Nutze zwingend 'crm_personen' und INNER JOIN über 'kundennumm'.
    5. Entferne Markdown.
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
        return sql_raw.replace("```sql", "").replace("```", "").replace("\n", " ").strip()
    except Exception as e:
        return f"Fehler bei der KI-Übersetzung: {e}"

def fuehre_sql_aus(sql_query, db_pfad=ACCESS_DB_PATH):
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_pfad};"
    try:
        conn = pyodbc.connect(conn_str)
        df = pd.read_sql(sql_query, conn)
        conn.close()
        return df
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
    try:
        outlook = _connect_outlook()
        konten = []
        for acc in outlook.Session.Accounts:
            try:
                addr = acc.SmtpAddress
                if addr: konten.append(addr.lower().strip())
                else: konten.append(acc.DisplayName.lower().strip())
            except:
                konten.append(acc.DisplayName.lower().strip())
        return list(set(konten))
    except:
        return ["kohlhaas@digibest.eu", "hans@kohlhaas.eu"]

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

def generiere_mail_entwurf(original_text, anweisung, ansprache, absender_name):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = f"Du bist Hans Kohlhaas, Geschäftsführer von DigiBest. Antworte auf: {original_text}\nPartner: {absender_name} ({ansprache})\nTon: Klar, respektvoll-direkt.\nAnweisung: {anweisung}\nSchreibe NUR den reinen Mail-Text."
    try:
        return client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.4).choices[0].message.content
    except Exception as e: return f"Fehler bei der KI-Generierung: {e}"


def generiere_neue_mail_entwurf(anweisung, ansprache, empfaenger_name, betreff=""):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = (
        f"Du bist Hans Kohlhaas, Geschäftsführer von DigiBest. "
        f"Schreibe eine NEUE E-Mail (keine Antwort auf eine bestehende Mail).\n"
        f"Empfänger: {empfaenger_name} ({ansprache})\n"
        f"Betreff-Vorgabe: {betreff or '(noch offen)'}\n"
        f"Worum geht es: {anweisung}\n"
        f"Ton: Klar, respektvoll-direkt.\n"
        f"Schreibe NUR den reinen Mail-Text inkl. Anrede und Grußformel."
    )
    try:
        return client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.4
        ).choices[0].message.content
    except Exception as e:
        return f"Fehler bei der KI-Generierung: {e}"


def _setze_outlook_absender(mail, outlook, absender_konto):
    if not absender_konto:
        return
    ziel = str(absender_konto).lower().strip()
    for acc in outlook.Session.Accounts:
        smtp = str(getattr(acc, "SmtpAddress", "") or "").lower().strip()
        name = str(getattr(acc, "DisplayName", "") or "").lower().strip()
        if ziel in (smtp, name):
            mail.SendUsingAccount = acc
            return


def sende_email_via_outlook(empfaenger_email, betreff, inhalt, absender_konto, anhaenge_pfade=None, ist_antwort=False):
    outlook = _connect_outlook()
    mail = outlook.CreateItem(0)
    mail.To = empfaenger_email
    mail.Subject = f"AW: {betreff}" if ist_antwort else betreff
    mail.Body = inhalt
    _setze_outlook_absender(mail, outlook, absender_konto)
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
        st.rerun()

st.markdown("---")

# DER KI-SPRACHROUTER (Entkoppelt: Eingabe -> Editieren -> Ausführen)
with st.form("form_global_cmd", clear_on_submit=True):
    global_cmd = st.text_input(
        "🎙️ Kommando (Diktieren, ggf. korrigieren, dann starten):",
        placeholder="z.B. Rufe Marc Gebur an... oder: Notiere für das Meeting...",
        key="global_cmd_input",
    )
    btn_execute = st.form_submit_button("🚀 Ausführen", use_container_width=True)

if btn_execute and global_cmd and global_cmd.strip():
    st.session_state.pending_global_cmd = global_cmd.strip()
    st.rerun()

if st.session_state.pending_global_cmd:
    cmd_text = st.session_state.pending_global_cmd
    st.session_state.pending_global_cmd = None
    with st.spinner("Analysiere Kommando..."):
        analyse = analysiere_sprachkommando(cmd_text)
        kategorie = analyse.get("kategorie", "datenbank")

        if kategorie == "anruf":
            such_name = analyse.get("ziel_name", "")
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
        else:
            st.session_state.pending_chat_frage = analyse.get("text_inhalt", cmd_text)
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
    for r in st.session_state.chat_historie:
        with st.chat_message(r["rolle"]): st.markdown(r["text"])

    eingabe_frage = st.chat_input("Frage an die Datenbank...")
    frage = eingabe_frage
    if not frage and st.session_state.pending_chat_frage:
        frage = st.session_state.pending_chat_frage
        st.session_state.pending_chat_frage = None

    if frage:
        with st.chat_message("user"): st.markdown(frage)
        st.session_state.chat_historie.append({"rolle": "user", "text": frage})

        with st.chat_message("assistant"):
            with st.spinner("Durchsuche Datenbank..."):
                try:
                    generiertes_sql = uebersetze_frage_in_sql(frage, db_schema, db_dictionary)
                    ergebnis = fuehre_sql_aus(generiertes_sql)
                    
                    if isinstance(ergebnis, pd.DataFrame):
                        if ergebnis.empty:
                            st.info("Keine Treffer gefunden.")
                            st.session_state.chat_historie.append({"rolle": "assistant", "text": "Keine Treffer."})
                        else:
                            st.success(f"{len(ergebnis)} Datensätze gefunden:")
                            st.dataframe(ergebnis, use_container_width=True)
                            st.session_state.chat_historie.append({"rolle": "assistant", "text": f"Tabelle mit {len(ergebnis)} Zeilen generiert."})
                    else:
                        st.error(ergebnis)
                except Exception as e: 
                    st.error(f"❌ Fehler: {str(e)}")

# --- REITER 2: MAILS & WHATSAPP ---
elif haupttab == "mails":
    with st.expander("✉️ Neue E-Mail verfassen", expanded=False):
        with st.form("form_ne_mail_suche", clear_on_submit=False):
            ne_mail_eingabe = st.text_input(
                "🔍 Empfänger suchen...",
                value=st.session_state.ne_mail_suchbegriff,
                placeholder="Name oder Firma…",
            )
            btn_ne_mail_suchen = st.form_submit_button("🔍 Suchen", use_container_width=True)

        if btn_ne_mail_suchen:
            st.session_state.ne_mail_suchbegriff = ne_mail_eingabe.strip()
            st.session_state.ne_mail_kontakt_key = None
            st.session_state.ne_mail_entwurf = ""

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
                    st.session_state.ne_mail_entwurf = ""
                    st.rerun()

        if st.session_state.ne_mail_kontakt_key and not df_ne_mail.empty:
            sel_rows = [
                r for _, r in df_ne_mail.iterrows()
                if kontakt_email_schluessel(r) == st.session_state.ne_mail_kontakt_key
            ]
            if sel_rows:
                row = sel_rows[0]
                name = f"{row.get('vorname', '')} {row.get('nachname', '')}".strip()
                ansprache = str(row.get("ansprache") or row.get("Anrede") or row.get("anrede") or "Sie").strip()
                email_optionen = baue_email_optionen_aus_kontakt(row)

                st.markdown(f"**Neue E-Mail an {name}**")
                absender_konten = hole_outlook_konten()
                absender = st.selectbox("Absender-Konto", absender_konten, key="ne_mail_absender")
                email_labels = [o["label"] for o in email_optionen]
                gewaehlte_label = st.radio("Empfänger-Adresse", email_labels, key="ne_mail_empf_adresse")
                empfaenger_email = next(o["email"] for o in email_optionen if o["label"] == gewaehlte_label)
                betreff = st.text_input("Betreff", key="ne_mail_betreff")
                anweisung = st.text_area(
                    "Worum geht es? (diktieren oder tippen)",
                    placeholder="z.B. Terminvorschlag für nächste Woche…",
                    key="ne_mail_anweisung",
                )
                col_gen, col_close = st.columns(2)
                with col_gen:
                    if st.button("✨ KI-Entwurf generieren", key="btn_ne_mail_gen", use_container_width=True):
                        if not anweisung.strip():
                            st.warning("Bitte kurz beschreiben, worum es geht.")
                        else:
                            with st.spinner("KI schreibt Entwurf…"):
                                st.session_state.ne_mail_entwurf = generiere_neue_mail_entwurf(
                                    anweisung.strip(), ansprache, name, betreff.strip()
                                )
                            st.rerun()
                with col_close:
                    if st.button("✖ Abbrechen", key="btn_ne_mail_close", use_container_width=True):
                        st.session_state.ne_mail_kontakt_key = None
                        st.session_state.ne_mail_entwurf = ""
                        st.rerun()

                entwurf = st.text_area(
                    "Mail-Entwurf",
                    height=220,
                    key="ne_mail_entwurf",
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
                        st.session_state.ne_mail_entwurf = ""
                        st.rerun()

    with st.expander("📱 Manuelle WhatsApp senden"):
        with st.form("form_wa_suche", clear_on_submit=False):
            wa_eingabe = st.text_input(
                "🔍 Kontakt suchen...",
                value=st.session_state.wa_suchbegriff,
                placeholder="Name oder Firma…",
            )
            btn_wa_suchen = st.form_submit_button("🔍 Suchen", use_container_width=True)

        if btn_wa_suchen:
            st.session_state.wa_suchbegriff = wa_eingabe.strip()
            st.session_state.wa_selected_id = None

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
                wa_link = baue_whatsapp_link(row["mobil"], "")
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
                    anweisung = st.text_input("KI-Anweisung (diktieren!):", key=f"anweisung_{i}")
                    if st.button("✨ Entwurf generieren", key=f"btn_gen_{i}"):
                        st.session_state[f"edit_{i}"] = generiere_mail_entwurf(
                            mail["Inhalt"], anweisung, mail["Ansprache"], mail["Name"]
                        )
                        st.rerun()
                    if f"edit_{i}" in st.session_state:
                        editierter_text = st.text_area("Entwurf:", height=200, key=f"edit_{i}")
                        if st.button("🚀 Senden", key=f"send_{i}"):
                            if sende_email_via_outlook(
                                mail['Email'], mail['Betreff'], editierter_text, "kohlhaas@digibest.eu", ist_antwort=True
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
        st.markdown("#### 🎯 Aufgaben & Notizen")
        with st.expander("📝 Neue Notiz (manuell)"):
            with st.form("form_notiz", clear_on_submit=True):
                manuelle_notiz = st.text_area("Notiz diktieren:")
                if st.form_submit_button("In Outlook speichern", use_container_width=True):
                    erfolg, msg = erstelle_outlook_notiz(manuelle_notiz)
                    if erfolg: st.success(msg)
                    
        with st.expander("➕ Neue Aufgabe"):
            with st.form("form_aufgabe", clear_on_submit=True):
                neu_betreff = st.text_input("Was ist zu tun?*")
                neu_faellig = st.date_input("Fällig am", value=None)
                if st.form_submit_button("Aufgabe anlegen", use_container_width=True):
                    erstelle_outlook_aufgabe(neu_betreff, neu_faellig)
                    st.rerun()

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