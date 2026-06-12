import os
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# HIER DEINEN KEY DIREKT ALS STRING EINTRAGEN (KEINE ANFÜHRUNGSZEICHEN ZU VIEL!)
MEIN_API_KEY = "REDACTED_GOOGLE_API_KEY" 

print("--- START INTEGRITÄTS-TEST ---")

try:
    print("Lade Embeddings-Modell mit direktem Key...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2", 
        google_api_key=MEIN_API_KEY
    )
    
    print("Versuche, ChromaDB zu öffnen...")
    db_pfad = r"F:\digibest_chroma_db"
    db = Chroma(persist_directory=db_pfad, embedding_function=embeddings)
    
    count = db._collection.count()
    print(f"ERFOLG! VDB geladen. Anzahl Dokumente: {count}")
    
except Exception as e:
    print(f"--- KRITISCHER FEHLER ---")
    print(f"{str(e)}")