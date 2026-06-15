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
from langchain_community.document_loaders import UnstructuredPowerPointLoader
from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader, UnstructuredExcelLoader
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from config import (
    CHROMA_DB_PATH,
    WATCH_BATCH_SIZE,
    WATCH_MANIFEST_PATH,
    WATCH_MAX_FILE_MB,
    WATCH_QUARANTINE_PATH,
    WATCH_RETRY_COUNT,
    WATCH_RETRY_DELAY_SECONDS,
    WATCH_ROOTS,
    WATCH_SNAPSHOT_PATH,
    WATCH_STATE_PATH,
    WATCH_MANIFEST_VERSION,
    WATCH_RELEVANTE_ENDUNGEN,
    ermittle_wissensbereich,
    ist_beobachtete_datei,
)

# --- KONFIGURATION ---
# Diese Ordner werden jede Nacht gescannt. Die Liste kommt aus config.py,
# damit die Pfade nur an einer Stelle gepflegt werden muessen.
BEOBACHTETE_ORDNER = [str(pfad) for pfad in WATCH_ROOTS]
DATENBANK_ORDNER = str(CHROMA_DB_PATH)
STATUS_DATEI = WATCH_STATE_PATH
MANIFEST_DATEI = WATCH_MANIFEST_PATH
QUARANTAENE_DATEI = WATCH_QUARANTINE_PATH
SNAPSHOT_DATEI = WATCH_SNAPSHOT_PATH
MAX_DATEI_GROESSE_MB = WATCH_MAX_FILE_MB

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


def lade_manifest():
    if not os.path.exists(MANIFEST_DATEI):
        return {}

    try:
        with open(MANIFEST_DATEI, 'r', encoding='utf-8') as f:
            daten = json.load(f)
    except Exception:
        return {}

    if isinstance(daten, dict):
        return daten

    return {}


def speichere_manifest(daten):
    with open(MANIFEST_DATEI, 'w', encoding='utf-8') as f:
        json.dump(daten, f, indent=4)


def manifest_ist_aktuell(daten):
    return daten.get("__manifest_version__") == WATCH_MANIFEST_VERSION


def markiere_manifest_version(daten):
    daten["__manifest_version__"] = WATCH_MANIFEST_VERSION
    return daten


def drucke_beobachtete_ordner():
    print("\n📂 Beobachtete Verzeichnisse:")
    for ordner in BEOBACHTETE_ORDNER:
        print(f"  - {ordner}")

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
        start_ordner = str(start_ordner)
        if not os.path.exists(start_ordner):
            continue
        for ordnerpfad, ordnernamen, dateinamen in os.walk(start_ordner):
            ordnernamen[:] = [d for d in ordnernamen if d.lower() not in IGNORIERTE_ORDNER]
            for dateiname in dateinamen:
                if ist_beobachtete_datei(dateiname):
                    pfad = os.path.abspath(os.path.join(ordnerpfad, dateiname))
                    try:
                        stat = os.stat(pfad)
                        aktuelle_dateien[pfad] = {"mtime": stat.st_mtime, "size": stat.st_size}
                    except FileNotFoundError:
                        continue
    return aktuelle_dateien


def loesche_vektor_eintrag(vektor_datenbank, pfad):
    try:
        vektor_datenbank.delete(where={"source": pfad})
    except Exception:
        try:
            vektor_datenbank._collection.delete(where={"source": pfad})
        except Exception:
            pass


def erkenne_loader(pfad):
    if pfad.lower().endswith('.pdf'):
        return PyPDFLoader(pfad)
    if pfad.lower().endswith('.docx'):
        return Docx2txtLoader(pfad)
    if pfad.lower().endswith('.pptx'):
        return UnstructuredPowerPointLoader(pfad)
    if pfad.lower().endswith('.xlsx'):
        return UnstructuredExcelLoader(pfad, mode="elements")
    if pfad.lower().endswith('.csv'):
        return CSVLoader(file_path=pfad, encoding="utf-8", csv_args={'delimiter': ';'})
    return TextLoader(pfad, encoding="utf-8")


def lade_dokumente_fuer_pfad(pfad):
    loader = erkenne_loader(pfad)
    try:
        return loader.load()
    except Exception:
        if pfad.lower().endswith('.csv'):
            loader = CSVLoader(file_path=pfad, encoding="cp1252", csv_args={'delimiter': ';'})
            return loader.load()
        raise


def markiere_dokumente(dokumente, pfad, metadaten):
    bereich = ermittle_wissensbereich(pfad, os.path.basename(pfad))
    for dokument in dokumente:
        dokument.metadata = dict(dokument.metadata or {})
        dokument.metadata["source"] = pfad
        dokument.metadata["mtime"] = metadaten["mtime"]
        dokument.metadata["size"] = metadaten["size"]
        dokument.metadata["bereich"] = bereich
    return dokumente

# --- HAUPTPROGRAMM ---
def aktualisiere_gehirn():
    print("🕵️ Wiki-Wächter startet seinen Rundgang...")
    drucke_beobachtete_ordner()
    
    gespeicherter_status = lade_json(STATUS_DATEI)
    gespeicherter_manifest = lade_manifest()
    tatsaechliche_dateien = sammle_aktuelle_dateien(WATCH_ROOTS)
    manifest_alt = not manifest_ist_aktuell(gespeicherter_manifest)

    if manifest_alt and gespeicherter_status:
        gespeicherter_manifest = {
            pfad: tatsaechliche_dateien.get(pfad)
            for pfad in gespeicherter_status.keys()
            if pfad in tatsaechliche_dateien
        }
        gespeicherter_manifest = {pfad: meta for pfad, meta in gespeicherter_manifest.items() if meta}

    gesamtstand_vorher = len(gespeicherter_status)
    
    quarantaene_liste = lade_json(QUARANTAENE_DATEI)
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
    vektor_datenbank = Chroma(persist_directory=DATENBANK_ORDNER, embedding_function=embeddings)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    alte_pfade = set(gespeicherter_status.keys())
    aktuelle_pfade = set(tatsaechliche_dateien.keys())
    
    geloescht = alte_pfade - aktuelle_pfade
    neu = aktuelle_pfade - alte_pfade
    veraendert = {
        pfad
        for pfad in (alte_pfade & aktuelle_pfade)
        if gespeicherter_manifest.get(pfad) != tatsaechliche_dateien[pfad]
    }

    if manifest_alt:
        neu = aktuelle_pfade
        veraendert = set()
        geloescht = set()
    
    zu_verarbeiten = neu.union(veraendert)
    
    erfolgreich_gelernt = []
    fehler_dateien = []
    quarantaene_neu = []

    if manifest_alt:
        print("🔄 Manifest-Version gewechselt. Starte einmalige Neuindizierung mit Bereichsmetadaten...")
        for pfad in aktuelle_pfade:
            loesche_vektor_eintrag(vektor_datenbank, pfad)
        gespeicherter_status.clear()
        gespeicherter_manifest.clear()
        speichere_json(STATUS_DATEI, gespeicherter_status)
        speichere_manifest(markiere_manifest_version(gespeicherter_manifest))
    elif geloescht or veraendert:
        for pfad in geloescht.union(veraendert):
            try:
                loesche_vektor_eintrag(vektor_datenbank, pfad)
                if pfad in gespeicherter_status:
                    del gespeicherter_status[pfad]
                if pfad in gespeicherter_manifest:
                    del gespeicherter_manifest[pfad]
            except Exception:
                pass 
        speichere_json(STATUS_DATEI, gespeicherter_status)
        speichere_manifest(markiere_manifest_version(gespeicherter_manifest))

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
                    loader = None
                    dokumente = None
                    text_stuecke = None

                    if pfad in quarantaene_liste:
                        continue
                    
                    metadaten = tatsaechliche_dateien.get(pfad)
                    if not metadaten:
                        continue

                    groesse_mb = metadaten["size"] / (1024 * 1024)
                    if groesse_mb > MAX_DATEI_GROESSE_MB:
                        quarantaene_liste[pfad] = f"{groesse_mb:.1f} MB"
                        quarantaene_neu.append(pfad)
                        speichere_json(QUARANTAENE_DATEI, quarantaene_liste)
                        continue
                    
                    print(f"  🔍 Lese: {os.path.basename(pfad)} ...")
                    
                    try:
                        dokumente = lade_dokumente_fuer_pfad(pfad)
                        dokumente = markiere_dokumente(dokumente, pfad, metadaten)
                        text_stuecke = text_splitter.split_documents(dokumente)
                        
                        if len(text_stuecke) > 0:
                            for i in range(0, len(text_stuecke), WATCH_BATCH_SIZE):
                                batch = text_stuecke[i:i + WATCH_BATCH_SIZE]
                                erfolgreich = False
                                versuche = 0
                                while not erfolgreich and versuche < WATCH_RETRY_COUNT:
                                    try:
                                        vektor_datenbank.add_documents(batch)
                                        erfolgreich = True
                                        time.sleep(1) 
                                    except Exception as e:
                                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                                            time.sleep(WATCH_RETRY_DELAY_SECONDS)
                                            versuche += 1
                                        else:
                                            raise e
                                if not erfolgreich: raise Exception("API blockiert.")
                                    
                            erfolgreich_gelernt.append(pfad)
                            gespeicherter_status[pfad] = metadaten["mtime"]
                            gespeicherter_manifest[pfad] = metadaten
                            markiere_manifest_version(gespeicherter_manifest)
                            speichere_json(STATUS_DATEI, gespeicherter_status)
                            speichere_manifest(gespeicherter_manifest)
                            
                        else:
                            gespeicherter_status[pfad] = metadaten["mtime"]
                            gespeicherter_manifest[pfad] = metadaten
                            markiere_manifest_version(gespeicherter_manifest)
                            speichere_json(STATUS_DATEI, gespeicherter_status)
                            speichere_manifest(gespeicherter_manifest)
                            
                    except Exception as e:
                        fehler_dateien.append(pfad)
                        
                    finally:
                        if 'loader' in locals():
                            del loader
                        if 'dokumente' in locals():
                            del dokumente
                        if 'text_stuecke' in locals():
                            del text_stuecke
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