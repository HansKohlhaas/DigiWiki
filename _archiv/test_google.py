import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

print("1. Verbinde mit Google...")
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")

print("2. Sende Test-Frage an die API (Bitte Zeit stoppen)...")
try:
    vektor = embeddings.embed_query("Das ist ein Test für das DigiWiki.")
    print(f"3. ✅ ERFOLG! Google hat geantwortet. Vektorlänge: {len(vektor)}")
except Exception as e:
    print(f"3. ❌ FEHLER: {e}")