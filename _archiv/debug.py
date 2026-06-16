import os
from dotenv import load_dotenv

print("--- 0. Lade Umgebungsvariablen ---")
load_dotenv()

print("--- 1. Initialisiere Google Embeddings Objekt ---")
from langchain_google_genai import GoogleGenerativeAIEmbeddings
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")

print("--- 2. Ping an Google API (Netzwerk-Test) ---")
try:
    embeddings.embed_query("Hallo Welt")
    print("✅ Google API antwortet sofort.")
except Exception as e:
    print(f"❌ Fehler bei Google API: {e}")

print("--- 3. Verbinde mit ChromaDB Festplattendatei ---")
from langchain_chroma import Chroma
# Nutze hier exakt deinen Pfad aus der config
pfad = r"C:\Digibest_Wiki_Projekt\Chroma_DB" # oder F:\digibest_chroma_db, falls das aktuell ist
try:
    db = Chroma(persist_directory=pfad, embedding_function=embeddings)
    print("✅ ChromaDB erfolgreich geladen.")
except Exception as e:
    print(f"❌ Fehler bei ChromaDB: {e}")

print("--- Debugger beendet ---")