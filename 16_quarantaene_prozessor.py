import os
import json
import time
from dotenv import load_dotenv
from config import CHROMA_DB_PATH, WATCH_QUARANTINE_PATH, WATCH_STATE_PATH, ist_beobachtete_datei

load_dotenv()

from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader, UnstructuredExcelLoader
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

DATENBANK_ORDNER = str(CHROMA_DB_PATH)
STATUS_DATEI = WATCH_STATE_PATH
QUARANTAENE_DATEI = WATCH_QUARANTINE_PATH

def verarbeite_schwere_datei(pfad):
    """Zwingt das System, diese eine Datei mit viel Geduld einzulesen."""
    print(f"\n⚙️ Starte Intensiv-Verarbeitung für: {os.path.basename(pfad)}")
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
    vektor_datenbank = Chroma(persist_directory=DATENBANK_ORDNER, embedding_function=embeddings)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    if pfad.lower().endswith('.pdf'): loader = PyPDFLoader(pfad)
    elif pfad.lower().endswith('.docx'): loader = Docx2txtLoader(pfad)
    elif pfad.lower().endswith('.xlsx'): loader = UnstructuredExcelLoader(pfad, mode="elements")
    elif pfad.lower().endswith('.csv'): loader = CSVLoader(file_path=pfad, encoding="utf-8", csv_args={'delimiter': ';'})
    else: loader = TextLoader(pfad, encoding="utf-8")
    
    try:
        try:
            dokumente = loader.load()
        except Exception:
            if pfad.lower().endswith('.csv'):
                loader = CSVLoader(file_path=pfad, encoding="cp1252", csv_args={'delimiter': ';'})
                dokumente = loader.load()
            else:
                raise

        text_stuecke = text_splitter.split_documents(dokumente)
        gesamt = len(text_stuecke)
        print(f"   -> Datei in {gesamt} Vektoren zerschnitten. Beginne Upload...")

        if gesamt > 0:
            for i in range(0, gesamt, 100):
                batch = text_stuecke[i:i + 100]
                erfolgreich = False
                versuche = 0
                while not erfolgreich and versuche < 5:
                    try:
                        vektor_datenbank.add_documents(batch)
                        erfolgreich = True
                        time.sleep(2) # Extra lange Pause für schwere Dateien
                        print(f"      Upload Fortschritt: {min(i+100, gesamt)}/{gesamt}")
                    except Exception as e:
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            print(f"      ⏳ API-Limit. Pause 60s...")
                            time.sleep(60)
                            versuche += 1
                        else:
                            raise e
            return True
    except Exception as e:
        print(f"❌ Fehler bei der Intensiv-Verarbeitung: {e}")
        return False

def manage_quarantaene():
    print("="*50)
    print("🏥 DIGIWIKI QUARANTÄNE-STATION")
    print("="*50)
    
    if not os.path.exists(QUARANTAENE_DATEI):
        print("Alles sauber! Keine Dateien in Quarantäne.")
        return
        
    with open(QUARANTAENE_DATEI, 'r', encoding='utf-8') as f:
        quarantaene_liste = json.load(f)
        
    if not quarantaene_liste:
        print("Alles sauber! Keine Dateien in Quarantäne.")
        return

    print(f"\nEs warten {len(quarantaene_liste)} große Dateien auf deine Entscheidung:\n")
    
    verbliebene_liste = quarantaene_liste.copy()
    
    for pfad, groesse in quarantaene_liste.items():
        print(f"📁 Datei:   {os.path.basename(pfad)}")
        print(f"📍 Ordner:  {os.path.dirname(pfad)}")
        print(f"⚖️ Größe:   {groesse}")
        
        aktion = input("Aktion wählen -> [e]inlesen, [i]gnorieren für immer, [s]überspringen für später: ").lower()
        
        if aktion == 'e':
            erfolg = verarbeite_schwere_datei(pfad)
            if erfolg:
                # Aus der Quarantäne löschen und ins "Gelernt"-Notizbuch eintragen
                del verbliebene_liste[pfad]
                with open(STATUS_DATEI, 'r', encoding='utf-8') as sf:
                    status = json.load(sf)
                status[pfad] = os.path.getmtime(pfad)
                with open(STATUS_DATEI, 'w', encoding='utf-8') as sf:
                    json.dump(status, sf, indent=4)
                print("✅ Erfolgreich verarbeitet und aus der Quarantäne entlassen!\n")
                
        elif aktion == 'i':
            print("🗑️ Datei bleibt in Quarantäne und wird vom Wächter ignoriert.\n")
            # Wir lassen sie in der Liste, damit der Wächter sie nie wieder anfasst
            
        else:
            print("⏭️ Übersprungen. Wir fragen beim nächsten Mal wieder.\n")

    # Aktualisierte Quarantäne speichern
    with open(QUARANTAENE_DATEI, 'w', encoding='utf-8') as f:
        json.dump(verbliebene_liste, f, indent=4)

if __name__ == "__main__":
    manage_quarantaene()