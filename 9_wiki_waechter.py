"""Naechtlicher Wiki-Waechter: Chroma-Index aus WATCH_ROOTS aktualisieren."""
from pathlib import Path

from projekt_python import ensure_venv

ensure_venv(Path(__file__))

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import os
import json
import time
import smtplib
import ssl
import gc
from datetime import datetime, timedelta
from email.header import Header
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
    CHROMA_EXCLUDE_CRM_MD,
    BASE_DIR,
    chroma_db_path_str,
    ermittle_wissensbereich,
    ist_beobachtete_datei,
    ist_crm_archiv_datei,
)

# --- KONFIGURATION ---
# Diese Ordner werden jede Nacht gescannt. Die Liste kommt aus config.py,
# damit die Pfade nur an einer Stelle gepflegt werden muessen.
BEOBACHTETE_ORDNER = [str(pfad) for pfad in WATCH_ROOTS]
DATENBANK_ORDNER = chroma_db_path_str()
STATUS_DATEI = WATCH_STATE_PATH
MANIFEST_DATEI = WATCH_MANIFEST_PATH
QUARANTAENE_DATEI = WATCH_QUARANTINE_PATH
SNAPSHOT_DATEI = WATCH_SNAPSHOT_PATH
MAX_DATEI_GROESSE_MB = WATCH_MAX_FILE_MB

IGNORIERTE_ORDNER = {'windows', 'appdata', '$recycle.bin', 'node_modules', '.git', 'live'}

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


def _speichere_bericht_lokal(betreff: str, nachricht: str) -> Path:
    ziel = BASE_DIR / "wiki_waechter_bericht.txt"
    kopf = f"{datetime.now().isoformat(sep=' ', timespec='seconds')}\n{betreff}\n{'=' * 50}\n"
    ziel.write_text(kopf + nachricht, encoding="utf-8")
    return ziel


def _sende_smtp_mail(absender: str, passwort: str, empfaenger: str, msg: MIMEText) -> None:
    smtp_host = (os.getenv("SMTP_SERVER") or "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    timeout = max(10, int(os.getenv("SMTP_TIMEOUT", "45")))
    use_ssl = os.getenv("SMTP_USE_SSL", "").strip().lower() in ("1", "true", "yes")
    if not use_ssl and smtp_port == 465:
        use_ssl = True

    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout, context=ssl.create_default_context()) as smtp:
            smtp.login(absender, passwort)
            smtp.send_message(msg)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as smtp:
        smtp.ehlo()
        if smtp.has_extn("starttls"):
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        smtp.login(absender, passwort)
        smtp.send_message(msg)


def sende_bericht(
    erfolgreich,
    fehler,
    geloescht,
    quarantaene_neu,
    gesamt_vorher,
    gesamt_nachher,
    schicht_neu,
    crm_entfernt: int = 0,
    gespeicherter_status: dict | None = None,
):
    absender = os.getenv("EMAIL_ABSENDER")
    passwort = os.getenv("EMAIL_PASSWORT")
    empfaenger = os.getenv("EMAIL_EMPFAENGER")
    smtp_host = os.getenv("SMTP_SERVER")
    port = os.getenv("SMTP_PORT")

    aktiv = gesamt_nachher
    if gespeicherter_status:
        aktiv = sum(1 for p in gespeicherter_status if not ist_crm_archiv_datei(p))

    betreff = f"DigiWiki: Gehirn aktualisiert ({aktiv} aktive Dateien)"

    nachricht = "Der DigiWiki-Waechter hat seinen Rundgang beendet.\n\n"
    nachricht += "DATENBANK-STATUS:\n"
    nachricht += f"- Vorheriger Stand (wiki_stand): {gesamt_vorher} Dateien\n"
    nachricht += f"- Neuer Stand (wiki_stand): {gesamt_nachher} Dateien\n"
    nachricht += f"- Davon aktiv im Wiki (ohne CRM-Website-MD): {aktiv} Dateien\n"
    if crm_entfernt:
        nachricht += f"- CRM-Archiv in diesem Lauf entfernt: {crm_entfernt} Dateien\n"
    nachricht += "\n"

    nachricht += "AKTUELLE SCHICHT (Seit 22:30 Uhr):\n"
    nachricht += f"- Schicht-Zaehler (Index-Groesse): +{schicht_neu} Dateien\n\n"

    nachricht += "DETAILS ZU DIESEM LAUF:\n"
    nachricht += f"- Jetzt im Durchlauf gelernt: {len(erfolgreich)}\n"
    nachricht += f"- Veraltet / Entfernt: {geloescht}\n"
    nachricht += f"- Fehlerhaft: {len(fehler)}\n"
    nachricht += f"- Neue Quarantaene: {len(quarantaene_neu)}\n"

    if (
        len(erfolgreich) == 0
        and geloescht == 0
        and len(fehler) == 0
        and crm_entfernt == 0
    ):
        nachricht += "\nAlles auf dem neuesten Stand — kein Re-Indexing noetig.\n"

    if quarantaene_neu:
        nachricht += "NEU IN QUARANTAENE:\n"
        for d in quarantaene_neu:
            nachricht += f"  - {os.path.basename(d)}\n"

    bericht_pfad = _speichere_bericht_lokal(betreff, nachricht)
    print(f"📄 Bericht gespeichert: {bericht_pfad}")

    if not all([absender, passwort, empfaenger, smtp_host, port]):
        print("ℹ️ E-Mail uebersprungen (SMTP/EMAIL_* in .env nicht vollstaendig konfiguriert).")
        return

    msg = MIMEText(nachricht, "plain", "utf-8")
    msg["Subject"] = str(Header(betreff, "utf-8"))
    msg["From"] = absender
    msg["To"] = empfaenger

    try:
        _sende_smtp_mail(absender, passwort, empfaenger, msg)
        print(f"📧 Bericht per E-Mail an {empfaenger} gesendet.")
    except Exception as e:
        print(f"⚠️ E-Mail Fehler: {e}")
        print(f"   Bericht liegt lokal: {bericht_pfad}")
        if int(port or 0) == 465:
            print("   Tipp: Port 465 erwartet SSL — SMTP_USE_SSL=true setzen (jetzt automatisch bei 465).")
        elif int(port or 0) == 587:
            print("   Tipp: Port 587 nutzt STARTTLS — SMTP_USE_SSL=false, SMTP_SERVER/Port pruefen.")

def metadaten_aus_stat(stat):
    """mtime als int – sonst scheitert Vergleich mit wiki_manifest (int vs. float)."""
    return {"mtime": int(stat.st_mtime), "size": stat.st_size}


def metadaten_gleich(gespeichert, aktuell):
    if not gespeichert or not aktuell:
        return gespeichert == aktuell
    return (
        int(gespeichert.get("mtime", 0)) == int(aktuell.get("mtime", 0))
        and gespeichert.get("size") == aktuell.get("size")
    )


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
                        aktuelle_dateien[pfad] = metadaten_aus_stat(stat)
                    except FileNotFoundError:
                        continue
    return aktuelle_dateien


def loesche_vektor_eintrag(vektor_datenbank, pfad):
    """Entfernt alle Vektoren zu einer Quelldatei (robust gegen Chroma/Python-Varianten)."""
    collection = vektor_datenbank._collection
    pfad_varianten = {pfad, pfad.replace("\\", "/")}
    for quelle in pfad_varianten:
        try:
            ergebnis = collection.get(where={"source": quelle}, include=[])
            ids = ergebnis.get("ids") or []
            if ids:
                # Batchweise – sehr große MD-Dateien koennen hunderte Chunks haben
                batch = 500
                for i in range(0, len(ids), batch):
                    collection.delete(ids=ids[i : i + batch])
                return
        except Exception:
            continue
    try:
        vektor_datenbank.delete(where={"source": pfad})
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


def bereinige_crm_archiv_aus_index(vektor_datenbank, gespeicherter_status: dict) -> int:
    """Entfernt CRM-Website-MD aus Chroma und wiki_stand (Phase C)."""
    if not CHROMA_EXCLUDE_CRM_MD:
        return 0
    entfernt = 0
    for pfad in list(gespeicherter_status.keys()):
        if not ist_crm_archiv_datei(pfad):
            continue
        try:
            loesche_vektor_eintrag(vektor_datenbank, pfad)
            del gespeicherter_status[pfad]
            entfernt += 1
        except Exception:
            continue
    if entfernt:
        print(f"🧹 CRM-Archiv: {entfernt} Website-MD-Datei(en) aus dem Index entfernt")
    return entfernt


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
    print(f"📋 wiki_stand.json: {len(gespeicherter_status)} Dateien bereits im Index")
    
    print("🔍 Scanne beobachtete Ordner …")
    gespeicherter_manifest = lade_manifest()
    tatsaechliche_dateien = sammle_aktuelle_dateien(WATCH_ROOTS)
    print(f"   Gefunden: {len(tatsaechliche_dateien)} relevante Dateien")
    manifest_alt = not manifest_ist_aktuell(gespeicherter_manifest)

    if manifest_alt and gespeicherter_status:
        gespeicherter_manifest = {
            pfad: tatsaechliche_dateien.get(pfad)
            for pfad in gespeicherter_status.keys()
            if pfad in tatsaechliche_dateien
        }
        gespeicherter_manifest = {pfad: meta for pfad, meta in gespeicherter_manifest.items() if meta}

    gesamtstand_vorher = len(gespeicherter_status)
    crm_entfernt = 0

    quarantaene_liste = lade_json(QUARANTAENE_DATEI)

    print("🧠 Lade Chroma-Vektordatenbank und Embeddings (kann ~10 s dauern) …")
    print(f"   Chroma-Pfad: {DATENBANK_ORDNER}")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
    vektor_datenbank = Chroma(persist_directory=DATENBANK_ORDNER, embedding_function=embeddings)
    print(f"   Chroma bereit ({vektor_datenbank._collection.count()} Vektoren)")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    if CHROMA_EXCLUDE_CRM_MD:
        crm_entfernt = bereinige_crm_archiv_aus_index(vektor_datenbank, gespeicherter_status)
        if crm_entfernt:
            speichere_json(STATUS_DATEI, gespeicherter_status)

    alte_pfade = set(gespeicherter_status.keys())
    aktuelle_pfade = set(tatsaechliche_dateien.keys())
    
    geloescht = alte_pfade - aktuelle_pfade
    neu = aktuelle_pfade - alte_pfade
    veraendert = {
        pfad
        for pfad in (alte_pfade & aktuelle_pfade)
        if not metadaten_gleich(gespeicherter_manifest.get(pfad), tatsaechliche_dateien[pfad])
    }

    if manifest_alt:
        neu = aktuelle_pfade
        veraendert = set()
        geloescht = set()
    
    zu_verarbeiten = neu.union(veraendert)
    if CHROMA_EXCLUDE_CRM_MD:
        zu_verarbeiten = {p for p in zu_verarbeiten if not ist_crm_archiv_datei(p)}
    print(
        f"📊 Diff: neu={len(neu)}, geändert={len(veraendert)}, "
        f"gelöscht={len(geloescht)} → zu verarbeiten: {len(zu_verarbeiten)}"
    )
    
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
        zu_loeschen = geloescht.union(veraendert)
        print(f"🗑️ Entferne alte Vektoren für {len(zu_loeschen)} Datei(en) …")
        for idx, pfad in enumerate(zu_loeschen, start=1):
            try:
                loesche_vektor_eintrag(vektor_datenbank, pfad)
                if pfad in gespeicherter_status:
                    del gespeicherter_status[pfad]
                if pfad in gespeicherter_manifest:
                    del gespeicherter_manifest[pfad]
            except Exception as e:
                print(f"  ⚠️ Löschen übersprungen: {os.path.basename(pfad)} ({e})")
            if idx % 25 == 0 or idx == len(zu_loeschen):
                print(f"   … {idx}/{len(zu_loeschen)} bereinigt")
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
                    if CHROMA_EXCLUDE_CRM_MD and ist_crm_archiv_datei(pfad):
                        continue
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
    aktiv_nachher = sum(1 for p in gespeicherter_status if not ist_crm_archiv_datei(p))
    schicht_neu_anzahl = ermittle_schicht_neu_anzahl(gesamtstand_nachher)

    print("\n" + "="*50)
    print("📊 RUNDGANG BEENDET - STATUS-REPORT")
    print("="*50)
    print(f"Vorheriger Stand : {gesamtstand_vorher} Dateien")
    print(f"In diesem Lauf   : +{len(erfolgreich_gelernt)} gelernt, -{len(geloescht) + len(veraendert)} entfernt/ersetzt")
    if crm_entfernt:
        print(f"CRM-Archiv       : {crm_entfernt} Website-MDs aus Index entfernt")
    print(f"Neuer Datenstand : {gesamtstand_nachher} Dateien (wiki_stand)")
    print(f"Aktiv im Wiki    : {aktiv_nachher} Dateien (ohne CRM-Website-MD)")
    print("-" * 50)
    print(f"📈 Schicht-Zähler : +{schicht_neu_anzahl} Dateien (seit 22:30 Uhr)")
    print("="*50)

    # E-Mail Bericht senden
    anzahl_geloescht = len(geloescht) + len(veraendert)
    sende_bericht(
        erfolgreich_gelernt,
        fehler_dateien,
        anzahl_geloescht,
        quarantaene_neu,
        gesamtstand_vorher,
        gesamtstand_nachher,
        schicht_neu_anzahl,
        crm_entfernt=crm_entfernt,
        gespeicherter_status=gespeicherter_status,
    )

if __name__ == "__main__":
    aktualisiere_gehirn()