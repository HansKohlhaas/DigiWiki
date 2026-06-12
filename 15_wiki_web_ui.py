import streamlit as st
import os
import json
from datetime import datetime, timedelta
import win32com.client
import pythoncom
import sounddevice as sd
import wave
import speech_recognition as sr
import pyodbc
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- START: NL2SQL LOGIK (v2.9 - Mit CSV Data Dictionary) ---
@st.cache_data
@st.cache_data
def lade_textdatei(dateipfad):
    if not os.path.exists(dateipfad):
        return f"Fehler: Datei {dateipfad} nicht gefunden."
    
    # Versuch 1: UTF-8 (für die db_schema.txt)
    try:
        with open(dateipfad, "r", encoding="utf-8-sig") as f:
            return f.read()
    # Versuch 2: Fallback auf Windows-1252 (für Excel-CSVs mit Umlauten)
    except UnicodeDecodeError:
        with open(dateipfad, "r", encoding="windows-1252") as f:
            return f.read()

def uebersetze_frage_in_sql(nutzer_frage, schema_text, dictionary_csv):
    client = OpenAI()
    system_prompt = f"""
    Du bist ein SQL-Experte für Microsoft Access (Zugriff via pyodbc). 
    Übersetze die Frage des Nutzers in eine syntaktisch korrekte Access-SQL-Abfrage.
    
    === DATENBANK-SCHEMA ===
    {schema_text}
    
    === DATA DICTIONARY (GESCHÄFTSLOGIK ALS CSV) ===
    {dictionary_csv}
    
    === BEISPIELE ZUR ORIENTIERUNG ===
    Frage: "Welche Industriekunden planen eine Sortimentsausweitung?"
    SQL: SELECT * FROM stammdatenindustrie WHERE (trigger_events LIKE '%Sortimentsausweitung%' OR trigger_events LIKE '%neue Produkte%' OR trigger_events LIKE '%Portfolio%' OR trigger_events LIKE '%Expansion%')
    
    Frage: "In welchen Unternehmen heißt der Geschäftsführer Müller?"
    SQL: SELECT DISTINCT stammdatenindustrie.* FROM stammdatenindustrie INNER JOIN crm_personen ON stammdatenindustrie.kundennumm = crm_personen.kundennumm WHERE crm_personen.funktionsbezeichnung LIKE '%Geschäftsführer%' AND crm_personen.nachname LIKE '%Müller%'

    Frage: "Welche Hersteller haben Hustensaft im Programm?"
    SQL: SELECT DISTINCT stammdatenindustrie.* FROM stammdatenindustrie INNER JOIN abdaartikel ON stammdatenindustrie.anbieternummer = abdaartikel.anbieter_nr WHERE (abdaartikel.artikelname LIKE '%Hustensaft%' OR abdaartikel.artikelname LIKE '%Hustensirup%' OR abdaartikel.artikelname LIKE '%Hustenlöser%' OR abdaartikel.artikelname LIKE '%Bronchial%')
    
    === STRIKTE REGELN ===
    1. Antworte AUSSCHLIESSLICH mit dem SQL-Code. Keine Erklärungen.
    2. Schreibe das gesamte SQL-Statement zwingend in EINE EINZIGE ZEILE (keine Zeilenumbrüche).
    3. Nutze für Textsuchen IMMER das Prozentzeichen '%' als Wildcard.
    4. SEMANTISCHE TEXTSUCHE: Wenn in Textfeldern nach Konzepten gesucht wird, generiere 3-5 Synonyme und verknüpfe sie mit OR.
    5. PERSONEN & FUNKTIONEN: Wenn nach Namen/Titeln gefragt wird, nutze zwingend 'crm_personen' und verknüpfe per INNER JOIN über 'kundennumm'.
    6. PRODUKTSUCHE (WICHTIG): Gehe NICHT über die Warengruppe, das liefert falsche Treffer. Wenn nach einer Produktart gefragt wird, generiere stattdessen 4-5 passende Synonyme/Fachbegriffe für den Artikelnamen (z.B. Sirup, Löser, Saft) und suche mit OR in 'abdaartikel.artikelname'. Verknüpfe dann per INNER JOIN mit 'stammdatenindustrie'.
    7. ANTI-HALLUZINATION: Erfinde keine eigenen Spalten.
    8. Entferne jegliches Markdown (wie ```sql).
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": nutzer_frage}
            ],
            temperature=0.2 # Leicht erhöht von 0 auf 0.2, damit die KI kreativer bei den Synonymen wird
        )
        
        # Bereinigung der KI-Ausgabe
        sql_raw = response.choices[0].message.content.strip()
        sql_clean = sql_raw.replace("```sql", "").replace("```", "").replace("\n", " ").strip()
        return sql_clean
        
    except Exception as e:
        return f"Fehler bei der KI-Übersetzung: {e}"

def fuehre_sql_aus(sql_query, db_pfad=r"C:\CodexProjekte\FirmenApp\Digibest_Master.accdb"):
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_pfad};"
    try:
        conn = pyodbc.connect(conn_str)
        df = pd.read_sql(sql_query, conn)
        conn.close()
        return df
    except Exception as e:
        return f"Fehler bei der Datenbankabfrage: {e}"
# --- ENDE: NL2SQL LOGIK ---

# ==========================================
# 1. SEITEN-KONFIGURATION (Mobile First)
# ==========================================

st.set_page_config(
    page_title="DigiWiki Master-Zentrale",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Schema und Dictionary laden
db_schema = lade_textdatei(r"C:\Digibest_Wiki_Projekt\db_schema.txt")
db_dictionary = lade_textdatei(r"C:\Digibest_Wiki_Projekt\data_dictionary.csv")

os.makedirs("Mail_Downloads", exist_ok=True)
os.makedirs("Mail_Uploads", exist_ok=True)

# Kompatibilität für Streamlit Dialog-Overlay sichern
if hasattr(st, "dialog"):
    modal_dialog = st.dialog
elif hasattr(st, "experimental_dialog"):
    modal_dialog = st.experimental_dialog
else:
    modal_dialog = lambda title: lambda func: func

# ==========================================
# 2. OUTLOOK- & AUDIO-FUNKTIONEN
# ==========================================
@st.cache_data(ttl=600)
def hole_outlook_konten():
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
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

def hole_outlook_woche():
    pythoncom.CoInitialize()
    heute = datetime.now().date()
    in_einer_woche = heute + timedelta(days=7)
    termine_liste, aufgaben_liste = [], []
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        calendar = ns.GetDefaultFolder(9)
        appointments = calendar.Items
        appointments.IncludeRecurrences = True
        appointments.Sort("[Start]")
        
        restric_filter = f"[Start] >= '{heute.strftime('%d.%m.%Y')} 00:00' AND [Start] <= '{in_einer_woche.strftime('%d.%m.%Y')} 23:59'"
        wochen_termine = appointments.Restrict(restric_filter)
        
        for app in wochen_termine:
            start_lokal = app.Start
            termine_liste.append({
                "Datum": start_lokal.strftime("%d.%m.%Y"),
                "Zeit": start_lokal.strftime("%H:%M"),
                "Betreff": app.Subject,
                "Ort": app.Location if app.Location else ""
            })
            
        tasks_folder = ns.GetDefaultFolder(13)
        for task in tasks_folder.Items:
            if not task.Complete:
                fälligkeit = task.DueDate.strftime("%d.%m.%Y") if task.DueDate and task.DueDate.year < 4500 else "Kein Datum"
                aufgaben_liste.append({"Aufgabe": task.Subject, "Fällig": fälligkeit})
    except:
        return None, "Outlook-Verbindung eingeschränkt."
    return {"termine": termine_liste, "aufgaben": aufgaben_liste}, None

def aufnahme_von_pc_mikrofon(dauer=20):
    fs = 16000
    temp_datei = "temp_ui_aufnahme.wav"
    try:
        audio_array = sd.rec(int(dauer * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        
        with wave.open(temp_datei, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(fs)
            wf.writeframes(audio_array.tobytes())
            
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_datei) as source:
            audio_daten = recognizer.record(source)
            text = recognizer.recognize_google(audio_daten, language="de-DE")
            
        if os.path.exists(temp_datei):
            os.remove(temp_datei)
        return text
    except Exception as e:
        if os.path.exists(temp_datei):
            os.remove(temp_datei)
        return f"Fehler bei der Erkennung: {str(e)}"

# ==========================================
# 3. DATENBANK- & FILTER-LOGIK
# ==========================================
@st.cache_data(ttl=300)
def lade_whitelist():
    conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=C:\CodexProjekte\FirmenApp\Digibest_Master.accdb;'
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("SELECT Email_Gesch, Vorname, Nachname, Ansprache FROM Whitelist_Kontakte WHERE Email_Gesch IS NOT NULL")
        rows = cursor.fetchall()
        spalten = [column[0] for column in cursor.description]
        df = pd.DataFrame.from_records(rows, columns=spalten)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Datenbank-Fehler: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=120)
def hole_relevante_emails(whitelist_df):
    if whitelist_df.empty: return []
    pythoncom.CoInitialize()
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    ziel_konten = ['hans@kohlhaas.eu', 'kohlhaas@digibest.eu']
    relevante_mails = []
    
    whitelist_emails = whitelist_df['Email_Gesch'].str.lower().str.strip().tolist()

    for store in outlook.Stores:
        if store.DisplayName.lower().strip() in ziel_konten:
            try:
                inbox = store.GetDefaultFolder(6)
                messages = inbox.Items
                messages.Sort("[ReceivedTime]", True)
                anzahl = len(messages)
                
                for i in range(1, min(200, anzahl) + 1):
                    msg = messages[i]
                    if msg.Class != 43: continue
                    
                    sender = msg.SenderEmailAddress
                    if msg.SenderEmailType == "EX":
                        eu = msg.Sender.GetExchangeUser()
                        if eu: sender = eu.PrimarySmtpAddress
                    sender = sender.lower().strip()
                    
                    if sender in whitelist_emails:
                        kontakt = whitelist_df[whitelist_df['Email_Gesch'].str.lower().str.strip() == sender].iloc[0]
                        
                        anhaenge_lokal = []
                        if msg.Attachments.Count > 0:
                            for att_idx in range(1, msg.Attachments.Count + 1):
                                try:
                                    att = msg.Attachments[att_idx]
                                    sicherer_name = f"{int(datetime.now().timestamp())}_{att.FileName}"
                                    speicher_pfad = os.path.abspath(os.path.join("Mail_Downloads", sicherer_name))
                                    att.SaveAsFile(speicher_pfad)
                                    anhaenge_lokal.append({"name": att.FileName, "pfad": speicher_pfad})
                                except: pass
                        
                        relevante_mails.append({
                            "Name": f"{kontakt['Vorname']} {kontakt['Nachname']}",
                            "Ansprache": kontakt['Ansprache'],
                            "Email": sender,
                            "Betreff": msg.Subject,
                            "Inhalt": msg.Body,
                            "Anhaenge": anhaenge_lokal
                        })
            except: pass
    return relevante_mails

def lade_json_daten(dateipfad):
    if os.path.exists(dateipfad):
        try:
            with open(dateipfad, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

status_daten = lade_json_daten("./wiki_stand.json")
quarantaene_daten = lade_json_daten("./wiki_quarantaene.json")

def ermittle_schicht_neu_anzahl(aktueller_gesamtstand):
    snapshot_pfad = "./wiki_schicht_snapshot.json"
    jetzt = datetime.now()
    schwellenwert = jetzt.replace(hour=22, minute=30, second=0, microsecond=0)
    if jetzt < schwellenwert: schwellenwert -= timedelta(days=1)
    basis_schluessel = schwellenwert.strftime("%Y-%m-%d")
    snapshot_daten = lade_json_daten(snapshot_pfad)
    
    if basis_schluessel not in snapshot_daten:
        snapshot_daten[basis_schluessel] = aktueller_gesamtstand
        try:
            with open(snapshot_pfad, 'w', encoding='utf-8') as f: json.dump(snapshot_daten, f, indent=4)
        except: pass
            
    basis_wert = snapshot_daten.get(basis_schluessel, aktueller_gesamtstand)
    return max(0, aktueller_gesamtstand - basis_wert)

anzahl_gelernt = len(status_daten)
anzahl_neu_seit_2230 = ermittle_schicht_neu_anzahl(anzahl_gelernt)
anzahl_quarantaene = len(quarantaene_daten)

dateipfade = list(status_daten.keys())
vorschlaege = [os.path.splitext(os.path.basename(p))[0] for p in dateipfade[-3:]] if len(dateipfade) >= 3 else ["Kundenübersicht", "Produktliste", "Vertragsstatus"]

# ==========================================
# 4. AGENTEN-FUNKTIONEN & BRANDVOICE
# ==========================================
def lade_brandvoice(aktiv=True):
    if not aktiv:
        return "Schreibe im ganz normalen, freundlichen, sachlichen und partnerschaftlichen Tagesgeschäft-Stil. Vermeide jegliche Marketing-Floskeln, künstliche Textstrukturen oder Verkaufsformeln."
    return """
    PFLICHT-BRANDVOICE: Du schreibst für DigiBest in deutscher Sprache. Ton: klar, zahlenfest, respektvoll-direkt. Keine Floskeln, keine Buzzwords.
    Hausformel: Hook → Definition → Mechanik → Beleg/Beispiel → Konsequenz → Lösung → CTA.
    KERNBEGRIFFE: Medienbruch, Rückfragen, Liegezeit, strukturierte/standardisierte Bestelldaten, ERP-Übergabe.
    """

def generiere_mail_entwurf(original_text, anweisung, ansprache, absender_name, brandvoice):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = f"Du bist Hans Kohlhaas, Geschäftsführer von DigiBest. Antworte auf: {original_text}\nPartner: {absender_name} ({ansprache})\nStil: {brandvoice}\nAnweisung: {anweisung}\nSchreibe NUR den reinen Mail-Text."
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.4)
        return response.choices[0].message.content
    except Exception as e: return f"Fehler bei der KI-Generierung: {e}"

def sende_email_via_outlook(empfaenger_email, betreff, inhalt, absender_konto_name, anhaenge_pfade=None):
    pythoncom.CoInitialize()
    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = None
    target_account = None
    
    if absender_konto_name:
        ziel_clean = absender_konto_name.lower().strip()
        for account in outlook.Session.Accounts:
            try:
                if (ziel_clean == account.SmtpAddress.lower().strip()) or (ziel_clean == account.DisplayName.lower().strip()):
                    target_account = account
                    break
            except: pass
            
    # Outlook-Native Kopplung: Direkt im passenden Entwürfe-Ordner erstellen
    if target_account:
        try:
            store = target_account.DeliveryStore
            drafts_folder = store.GetDefaultFolder(16)
            mail = drafts_folder.Items.Add(0)
            mail.SendUsingAccount = target_account
        except Exception:
            mail = outlook.CreateItem(0)
            mail.SendUsingAccount = target_account
    else:
        mail = outlook.CreateItem(0)

    mail.To = empfaenger_email
    mail.Subject = "AW: " + betreff
    mail.Body = inhalt
                
    if anhaenge_pfade:
        for pfad in anhaenge_pfade:
            if os.path.exists(pfad):
                try: mail.Attachments.Add(pfad)
                except Exception as e: st.error(f"Konnte Anhang nicht anfügen: {e}")
    try:
        mail.Send()
        return True
    except Exception as e:
        st.error(f"Kritischer Outlook-Sendefehler: {e}")
        return False

def logge_aktivitaet_in_access(email, aktion, betreff):
    conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=C:\CodexProjekte\FirmenApp\Digibest_Master.accdb;'
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        try: cursor.execute("SELECT TOP 1 * FROM Aktivitaeten")
        except:
            cursor.execute("CREATE TABLE Aktivitaeten (ID COUNTER PRIMARY KEY, Datum VARCHAR(50), Kontakt_Email VARCHAR(100), Aktion VARCHAR(100), Betreff VARCHAR(255))")
            conn.commit()
        cursor.execute("INSERT INTO Aktivitaeten (Datum, Kontakt_Email, Aktion, Betreff) VALUES (?, ?, ?, ?)", datetime.now().strftime("%d.%m.%Y %H:%M:%S"), email, aktion, betreff)
        conn.commit()
        conn.close()
    except Exception: pass

# ==========================================
# 5. DIALOG FÜR MOBILE ANHÄNGE
# ==========================================
@modal_dialog("📎 Anhänge hinzufügen")
def upload_overlay(mail_id):
    st.write("Wähle Bilder oder Dokumente von deinem Gerät aus:")
    hochgeladene_dateien = st.file_uploader("Dateien auswählen", accept_multiple_files=True, key=f"overlay_upload_{mail_id}")
    
    if st.button("Hochladen bestätigen", key=f"btn_confirm_upload_{mail_id}"):
        if hochgeladene_dateien:
            if f"staged_files_{mail_id}" not in st.session_state:
                st.session_state[f"staged_files_{mail_id}"] = []
                
            for idx, f in enumerate(hochgeladene_dateien):
                file_bytes = f.getvalue()
                file_size = len(file_bytes)
                sicherer_dateiname = f"{int(datetime.now().timestamp())}_{idx}_{file_size}_{f.name}"
                ziel_pfad = os.path.abspath(os.path.join("Mail_Uploads", sicherer_dateiname))
                
                if not any(str(file_size) in p for p in st.session_state[f"staged_files_{mail_id}"]):
                    with open(ziel_pfad, "wb") as out_f: 
                        out_f.write(file_bytes)
                    st.session_state[f"staged_files_{mail_id}"].append(ziel_pfad)
        st.rerun()

# ==========================================
# 6. FUSIONIERTES CSS
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .sidebar-header { color: #0062cc; font-weight: bold; font-size: 18px; margin-bottom: 15px; }
    div.stButton > button { width: 100%; background-color: #ffffff; border: 1px solid #cbd5e1; color: #0f172a; border-radius: 6px; }
    div.stButton > button:hover { border-color: #0062cc; color: #0062cc; }
    .outlook-card { background-color: #ffffff; padding: 14px; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 10px; font-size: 14px; }
    .file-staged { background-color: #cbd5e1; padding: 6px 12px; border-radius: 4px; margin-bottom: 4px; font-size: 13px; color: #1e293b; display: inline-block; margin-right: 5px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 7. SIDEBAR & HEADER
# ==========================================
with st.sidebar:
    st.markdown("<div class='sidebar-header'>📊 System-Status</div>", unsafe_allow_html=True)
    st.metric(label="Verarbeitete Dokumente (Gesamt)", value=f"{anzahl_gelernt} Stück")
    st.metric(label="✨ Neu seit gestern 22:30 h", value=f"{anzahl_neu_seit_2230} Stück", delta=f"+{anzahl_neu_seit_2230}" if anzahl_neu_seit_2230 > 0 else None)
    st.metric(label="In Quarantäne", value=f"{anzahl_quarantaene} Stück")
    st.markdown("---")
    if st.button("🔄 Chat-Verlauf zurücksetzen"):
        st.session_state.chat_historie = []
        st.rerun()

col_logo, col_title = st.columns([1, 8])
with col_logo:
    if os.path.exists("LogoDigiBestrundCMYK.jpg"): st.image("LogoDigiBestrundCMYK.jpg", width=80)
with col_title:
    st.title("DigiWiki Zentrale")
    st.caption(f"Master-Cockpit | Stand: {datetime.now().strftime('%d.%m.%Y')}")

st.markdown("---")

# ==========================================
# 8. HAUPTBEREICH (Tabs)
# ==========================================
if "chat_historie" not in st.session_state: st.session_state.chat_historie = []

tab_chat, tab_agenda, tab_mails = st.tabs(["💬 Wiki-Chat & Werkzeuge", "📅 Outlook Agenda", "📬 Mails & KI-Agent"])

# --- REITER 1: CHAT & WERKZEUGE ---
with tab_chat:
    st.markdown("### ⚡ Schnellabfragen & Werkzeuge")
    col1, col2, col3, col_mic = st.columns([2, 2, 2, 2])
    vorauswahl_frage = None

    with col1:
        if st.button(f"🔍 {vorschlaege[0]}", key="btn_q1"): vorauswahl_frage = f"Gib mir Details zu {vorschlaege[0]}."
    with col2:
        if st.button(f"🔍 {vorschlaege[1]}", key="btn_q2"): vorauswahl_frage = f"Gib mir Details zu {vorschlaege[1]}."
    with col3:
        if st.button(f"🔍 {vorschlaege[2]}", key="btn_q3"): vorauswahl_frage = f"Gib mir Details zu {vorschlaege[2]}."
        
    with col_mic:
        if st.button("🎤 Spracheingabe (PC-Mic)", key="btn_chat_mic"):
            with st.spinner("🎙️ Ich höre zu... (20 Sek. Aufnahme läuft)"):
                gesprochener_text = aufnahme_von_pc_mikrofon(dauer=20)
                if gesprochener_text and not gesprochener_text.startswith("Fehler"): vorauswahl_frage = gesprochener_text
                else: st.error(gesprochener_text)

    for r in st.session_state.chat_historie:
        with st.chat_message(r["rolle"]): st.markdown(r["text"])

    eingabe_frage = st.chat_input("Stelle eine Frage an die Datenbank...")
    frage = eingabe_frage if eingabe_frage else vorauswahl_frage

    if frage:
        with st.chat_message("user"): st.markdown(frage)
        st.session_state.chat_historie.append({"rolle": "user", "text": frage})

        with st.chat_message("assistant"):
            with st.spinner("Übersetze Frage & durchsuche Datenbank..."):
                try:
                    # 1. KI übersetzt Text in SQL
                    generiertes_sql = uebersetze_frage_in_sql(frage, db_schema, db_dictionary)
                    
                    # Diagnose: Zeigt das SQL einklappbar an
                    with st.expander("Generiertes SQL-Statement anzeigen"):
                        st.code(generiertes_sql, language="sql")
                    
                    # 2. Access führt SQL aus
                    ergebnis = fuehre_sql_aus(generiertes_sql)
                    
                    # 3. Ergebnis anzeigen
                    if isinstance(ergebnis, pd.DataFrame):
                        if ergebnis.empty:
                            antwort = "Die Datenbank hat für diese Anfrage keine Treffer gefunden."
                            st.info(antwort)
                            st.session_state.chat_historie.append({"rolle": "assistant", "text": antwort})
                        else:
                            st.success(f"{len(ergebnis)} Datensätze gefunden:")
                            st.dataframe(ergebnis)
                            st.session_state.chat_historie.append({"rolle": "assistant", "text": f"Tabelle mit {len(ergebnis)} Zeilen generiert."})
                    else:
                        st.error(ergebnis)
                        st.session_state.chat_historie.append({"rolle": "assistant", "text": f"Fehler: {ergebnis}"})
                except Exception as e: 
                    st.error(f"❌ **Fehler:** {str(e)}")

# --- REITER 2: OUTLOOK AGENDA ---
with tab_agenda:
    st.markdown("### 📅 Meine Termine & Agenda")
    col_cal, col_task = st.columns(2)
    outlook_daten, fehler = hole_outlook_woche()

    with col_cal:
        st.markdown("#### 🕒 Terminkalender")
        if fehler: st.info(fehler)
        elif outlook_daten and outlook_daten["termine"]:
            for t in outlook_daten["termine"]:
                ort_text = f" – 📍 {t['Ort']}" if t['Ort'] else ""
                st.markdown(f"<div class='outlook-card'><b>📅 {t['Datum']} | {t['Zeit']} Uhr</b> | {t['Betreff']}{ort_text}</div>", unsafe_allow_html=True)
        else: st.write("-")

    with col_task:
        st.markdown("#### 🎯 Offene Aufgaben")
        if fehler: st.write("-")
        elif outlook_daten and outlook_daten["aufgaben"]:
            for a in outlook_daten["aufgaben"]:
                st.markdown(f"<div class='outlook-card'>📌 {a['Aufgabe']} <br><small style='color:#ef4444;'>Fällig: {a['Fällig']}</small></div>", unsafe_allow_html=True)
        else: st.write("-")

# --- REITER 3: RELEVANTE MAILS ---
with tab_mails:
    st.markdown("### 📬 Posteingang & KI-Agent")
    outlook_konten = hole_outlook_konten()
    whitelist_df = lade_whitelist()
    
    if whitelist_df.empty:
        st.info("Die Whitelist ist leer oder die Datenbank aktuell gesperrt.")
    else:
        mails = hole_relevante_emails(whitelist_df)
        
        if not mails:
            st.info("Keine Mails von freigegebenen Kontakten gefunden.")
        else:
            for i, mail in enumerate(mails):
                with st.expander(f"📧 {mail['Name']} | {mail['Betreff']}"):
                    if mail['Anhaenge']:
                        st.markdown("**📎 Empfangene Anhänge:**")
                        for att in mail['Anhaenge']: st.write(f"- `{att['name']}`")
                    
                    st.text_area("Original-Mail", mail['Inhalt'], height=150, key=f"mail_text_{i}")
                    
                    col_empf, col_abs = st.columns(2)
                    with col_empf:
                        editierter_empfaenger = st.text_input("Senden an:", value=mail['Email'], key=f"edit_to_{i}")
                    with col_abs:
                        default_idx = 0
                        if "kohlhaas@digibest.eu" in outlook_konten: default_idx = outlook_konten.index("kohlhaas@digibest.eu")
                        gewaehltes_konto = st.selectbox("Senden von:", outlook_konten, index=default_idx, key=f"edit_from_{i}")

                    bv_aktiv = st.checkbox("DigiBest Brandvoice anwenden", value=False, key=f"bv_toggle_{i}")
                    aktuelle_brandvoice = lade_brandvoice(bv_aktiv)

                    anweisung = st.text_input("Anweisung für die KI (Tipp: Smartphone-Diktat nutzen!):", placeholder="z.B. Bitte kurz absagen...", key=f"anweisung_field_{i}")
                    
                    if st.button("✨ KI Entwurf generieren", key=f"btn_generate_{i}"):
                        with st.spinner("Erstelle Entwurf..."):
                            entwurf = generiere_mail_entwurf(mail['Inhalt'], anweisung, mail['Ansprache'], mail['Name'], aktuelle_brandvoice)
                            st.session_state[f"draft_{i}"] = entwurf
                            st.rerun()

                    if f"draft_{i}" in st.session_state:
                        editierter_text = st.text_area("Entwurf (editierbar):", value=st.session_state[f"draft_{i}"], height=200, key=f"form_edit_draft_{i}")
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Ausgelagerter Upload-Dialog Aufruf
                        if st.button("📎 Anhänge hinzufügen", key=f"btn_open_dialog_{i}"):
                            upload_overlay(i)

                        staged_files = st.session_state.get(f"staged_files_{i}", [])
                        if staged_files:
                            st.markdown("<div style='margin-bottom:10px;'><b>Bereit zum Mitsenden:</b></div>", unsafe_allow_html=True)
                            for f_pfad in staged_files:
                                anzeige_name = "_".join(os.path.basename(f_pfad).split("_")[3:])
                                st.markdown(f"<span class='file-staged'>✔️ {anzeige_name}</span>", unsafe_allow_html=True)
                            
                            if st.button("🗑️ Anhänge leeren", key=f"clear_files_{i}"):
                                st.session_state[f"staged_files_{i}"] = []
                                st.rerun()
                                
                            st.markdown("<br>", unsafe_allow_html=True)

                        if st.button("🚀 Jetzt senden & in Access protokollieren", key=f"send_final_{i}"):
                            with st.spinner("Versand läuft..."):
                                if sende_email_via_outlook(editierter_empfaenger, mail['Betreff'], editierter_text, gewaehltes_konto, staged_files):
                                    logge_aktivitaet_in_access(editierter_empfaenger, f"E-Mail gesendet (KI) von {gewaehltes_konto}", mail['Betreff'])
                                    st.success("Mail erfolgreich versandt!")
                                    
                                    if f"staged_files_{i}" in st.session_state: del st.session_state[f"staged_files_{i}"]
                                    del st.session_state[f"draft_{i}"]
                                    st.cache_data.clear()
                                    st.rerun()