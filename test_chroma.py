import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()
DATENBANK_ORDNER = "./digibest_chroma_db"

print("1. Initialisiere Embeddings...")
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")

print("2. Verbinde mit lokaler ChromaDB...")
try:
    vektor_datenbank = Chroma(persist_directory=DATENBANK_ORDNER, embedding_function=embeddings)
    print("3. Starte lokale Suche in der Datenbank (Bitte Zeit stoppen)...")
    
    # Wir suchen nach einem Begriff, der auf jeden Fall in deinen Daten vorkommt
    treffer = vektor_datenbank.similarity_search("Hexal", k=2)
    
    print(f"4. ✅ ERFOLG! Dokumente in ChromaDB gefunden: {len(treffer)}")
    for i, t in enumerate(treffer):
        print(f"   📌 Treffer {i+1} aus Quelle: {t.metadata.get('source', 'Unbekannt')}")
        
except Exception as e:
    print(f"❌ FEHLER: {e}")