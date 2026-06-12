import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import os
import json
import time
import smtplib
import gc
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader, UnstructuredExcelLoader
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# --- KONFIGURATION ---
HAUPT_ORDNER = [     
    r"C:\Eigene Projekte",
    r"C:\CodexProjekte\FirmenApp\Projekt",
    r"C:\Verwaltung"
]

DATENBANK_ORDNER = "./digibest_chroma_db"
STATUS_DATEI = "./wiki_stand.json"
QUARANTAENE_DATEI = "./wiki_quarantaene.json"
SNAPSHOT_DATEI = "./wiki_schicht_snapshot.json"
MAX_DATEI_GROESSE_MB = 5.0

RELEVANTE_ENDUNGEN = ('.txt', '.md', '.pdf', '.docx', '.xlsx', '.csv')
IGNORIERTE_ORDNER = {'windows', 'appdata', '$recycle.bin', 'node_modules', '.git'}

# --- HILFSFUNKTIONEN ---
def lade_json(dateipfad):
    if os.path.exists(dateipfad):
        try:
            with open(dateipfad, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def speichere_json(dateipfad, daten):
    with open(dateipfad, 'w', encoding='utf-8') as f:
        json.dump(daten, f, indent=4)

def ermittle_schicht_neu_anzahl(aktueller_gesamtstand):
    jetzt = datetime.now()
    schwellenwert = jetzt.replace(hour=22, minute=30, second=0, microsecond=0)
    if jetzt < schwellenwert: 
        schwellenwert -= timedelta(days=1)
    basis_schluessel = schwellenwert.strftime("%Y-%m-%d")
    
    snapshot_daten = lade_json(SNAPSHOT_DATEI)
    
    # Wenn für die aktuelle Schicht noch kein Startwert existiert, setzen wir ihn JETZT
    if basis_schluessel not in snapshot_daten:
        snapshot_daten[basis_schluessel] = aktueller_gesamtstand
        speichere_json(SNAPSHOT_DATEI, snapshot_daten)
        
    basis_wert = snapshot_daten.get(basis_schluessel, aktueller_gesamtstand)
    return max(0, aktueller_gesamtstand - basis_wert)

def sende_bericht(erfolgreich, fehler, geloescht, quarantaene_neu, gesamt_vorher, gesamt_nachher, schicht_neu):
    absender = os.getenv("EMAIL_ABSENDER")
    passwort = os.getenv("EMAIL_PASSWORT")
    empfaenger = os.getenv("EMAIL_EMPFAENGER")
    server = os.getenv("SMTP_SERVER")
    port = os.getenv("SMTP_PORT")

    if not all([absender, passwort, empfaenger, server, port]):
        return

    betreff = f"🤖 DigiWiki: Gehirn aktualisiert ({gesamt_nachher} Dateien)"
    
    nachricht = "Der DigiWiki-Wächter hat seinen Rundgang beendet.\n\n"
    nachricht += "📊 DATENBANK-STATUS:\n"
    nachricht += f"- Vorheriger Stand: {gesamt_vorher} Dateien\n"
    nachricht += f"- Neuer Gesamtstand: {gesamt_nachher} Dateien\n\n"
    
    nachricht += "📈 AKTUELLE SCHICHT (Seit 22:30 Uhr):\n"
    nachricht += f"- In dieser Schicht gelernt: +{schicht_neu} Dateien\n\n"
    
    nachricht += "⚙️ DETAILS ZU DIESEM LAUF:\n"
    nachricht += f"- Jetzt im Durchlauf gelernt: {len(erfolgreich)}\n"
    nachricht += f"- Veraltet / Entfernt: {geloescht}\n"
    nachricht += f"- Fehlerhaft: {len(fehler)}\n"
    nachricht += f"- Neue Quarantäne: {len(quarantaene_neu)}\n\n"
    
    if quarantaene_neu:
        nachricht += "⚠️ NEU IN QUARANTÄNE:\n"
        for d in quarantaene_neu:
            nachricht += f"  - {os.path.basename(d)}\n"

    msg = MIMEText(nachricht, 'plain', 'utf-8')
    msg['Subject'] = betreff
    msg['From'] = absender
    msg['To'] = empfaenger

    try:
        with smtplib.SMTP(server, int(port)) as server:
            server.starttls()
            server.login(absender, passwort)
            server.send_message(msg)
    except Exception as e:
        print(f"⚠️ E-Mail Fehler: {e}")

def sammle_aktuelle_dateien(start_ordner_liste):
    aktuelle_dateien = {}
    for start_ordner in start_ordner_liste:
        if not os.path.exists(start_ordner):
            continue
        for ordnerpfad, ordnernamen, dateinamen in os.walk(start_ordner):
            ordnernamen[:] = [d for d in ordnernamen if d.lower() not in IGNORIERTE_ORDNER]
            for dateiname in dateinamen:
                if dateiname.lower().endswith(RELEVANTE_ENDUNGEN):
                    pfad = os.path.abspath(os.path.join(ordnerpfad, dateiname))
                    aktuelle_dateien[pfad] = os.path.getmtime(pfad)
    return aktuelle_dateien

# --- HAUPTPROGRAMM ---
def aktualisiere_gehirn():
    print("🕵️ Wiki-Wächter startet seinen Rundgang...")
    
    gespeicherter_status = lade_json(STATUS_DATEI)
    gesamtstand_vorher = len(gespeicherter_status)
    
    quarantaene_liste = lade_json(QUARANTAENE_DATEI)
    tatsaechliche_dateien = sammle_aktuelle_dateien(HAUPT_ORDNER)
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
    vektor_datenbank = Chroma(persist_directory=DATENBANK_ORDNER, embedding_function=embeddings)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    alte_pfade = set(gespeicherter_status.keys())
    aktuelle_pfade = set(tatsaechliche_dateien.keys())
    
    geloescht = alte_pfade - aktuelle_pfade
    neu = aktuelle_pfade - alte_pfade
    veraendert = {pfad for pfad in (alte_pfade & aktuelle_pfade) if tatsaechliche_dateien[pfad] > gespeicherter_status[pfad]}
    
    zu_verarbeiten = neu.union(veraendert)
    
    erfolgreich_gelernt = []
    fehler_dateien = []
    quarantaene_neu = []

    if geloescht or veraendert:
        for pfad in geloescht.union(veraendert):
            try:
                vektor_datenbank._collection.delete(where={"source": pfad})
                if pfad in gespeicherter_status:
                    del gespeicherter_status[pfad]
            except Exception:
                pass 
        speichere_json(STATUS_DATEI, gespeicherter_status)

    if zu_verarbeiten:
        dateien_nach_ordner = {}
        for pfad in zu_verarbeiten:
            ordner = os.path.dirname(pfad)
            if ordner not in dateien_nach_ordner:
                dateien_nach_ordner[ordner] = []
            dateien_nach_ordner[ordner].append(pfad)

        try:
            for ordner, dateien in dateien_nach_ordner.items():
                print(f"\n📂 Prüfe Verzeichnis: {ordner}")
                
                for pfad in dateien:
                    if pfad in quarantaene_liste:
                        continue
                    
                    groesse_mb = os.path.getsize(pfad) / (1024 * 1024)
                    if groesse_mb > MAX_DATEI_GROESSE_MB:
                        quarantaene_liste[pfad] = f"{groesse_mb:.1f} MB"
                        quarantaene_neu.append(pfad)
                        speichere_json(QUARANTAENE_DATEI, quarantaene_liste)
                        continue
                    
                    print(f"  🔍 Lese: {os.path.basename(pfad)} ...")
                    
                    loader = None
                    dokumente = None
                    text_stuecke = None
                    
                    try:
                        if pfad.lower().endswith('.pdf'): loader = PyPDFLoader(pfad)
                        elif pfad.lower().endswith('.docx'): loader = Docx2txtLoader(pfad)
                        elif pfad.lower().endswith('.xlsx'): loader = UnstructuredExcelLoader(pfad, mode="elements")
                        elif pfad.lower().endswith('.csv'): loader = CSVLoader(file_path=pfad, encoding="utf-8", csv_args={'delimiter': ';'})
                        else: loader = TextLoader(pfad, encoding="utf-8")
                        
                        try:
                            dokumente = loader.load()
                        except Exception:
                            if pfad.lower().endswith('.csv'):
                                loader = CSVLoader(file_path=pfad, encoding="cp1252", csv_args={'delimiter': ';'})
                                dokumente = loader.load()
                            else:
                                raise

                        text_stuecke = text_splitter.split_documents(dokumente)
                        
                        if len(text_stuecke) > 0:
                            for i in range(0, len(text_stuecke), 100):
                                batch = text_stuecke[i:i + 100]
                                erfolgreich = False
                                versuche = 0
                                while not erfolgreich and versuche < 5:
                                    try:
                                        vektor_datenbank.add_documents(batch)
                                        erfolgreich = True
                                        time.sleep(1) 
                                    except Exception as e:
                                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                                            time.sleep(60)
                                            versuche += 1
                                        else:
                                            raise e
                                if not erfolgreich: raise Exception("API blockiert.")
                                    
                            erfolgreich_gelernt.append(pfad)
                            gespeicherter_status[pfad] = tatsaechliche_dateien[pfad]
                            speichere_json(STATUS_DATEI, gespeicherter_status)
                            
                        else:
                            gespeicherter_status[pfad] = tatsaechliche_dateien[pfad]
                            speichere_json(STATUS_DATEI, gespeicherter_status)
                            
                    except Exception as e:
                        fehler_dateien.append(pfad)
                        
                    finally:
                        if loader is not None: del loader
                        if dokumente is not None: del dokumente
                        if text_stuecke is not None: del text_stuecke
                        gc.collect() 

        except KeyboardInterrupt:
            print("\n" + "🛑" * 25)
            print("⚠️ WÄCHTER MANUELL GESTOPPT (Strg+C)")
            print("🛑" * 25)

    else:
        print("\n✅ Alles auf dem neuesten Stand. Keine neuen Dateien gefunden.")

    # --- DIE NEUE ABSCHLUSS-STATISTIK ---
    gesamtstand_nachher = len(gespeicherter_status)
    schicht_neu_anzahl = ermittle_schicht_neu_anzahl(gesamtstand_nachher)

    print("\n" + "="*50)
    print("📊 RUNDGANG BEENDET - STATUS-REPORT")
    print("="*50)
    print(f"Vorheriger Stand : {gesamtstand_vorher} Dateien")
    print(f"In diesem Lauf   : +{len(erfolgreich_gelernt)} gelernt, -{len(geloescht) + len(veraendert)} entfernt/ersetzt")
    print(f"Neuer Datenstand : {gesamtstand_nachher} Dateien (Aktiv im Gehirn)")
    print("-" * 50)
    print(f"📈 Schicht-Zähler : +{schicht_neu_anzahl} Dateien (seit 22:30 Uhr)")
    print("="*50)

    # E-Mail Bericht senden
    anzahl_geloescht = len(geloescht) + len(veraendert)
    sende_bericht(erfolgreich_gelernt, fehler_dateien, anzahl_geloescht, quarantaene_neu, gesamtstand_vorher, gesamtstand_nachher, schicht_neu_anzahl)

if __name__ == "__main__":
    aktualisiere_gehirn()