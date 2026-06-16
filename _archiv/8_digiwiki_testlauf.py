import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import os
from dotenv import load_dotenv

# 1. Lädt die geheimen Variablen aus der .env Datei in den Speicher
load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    print("FEHLER: Konnte den API-Key nicht finden. Bitte prüfe die .env Datei!")
    exit()

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma

# --- KONFIGURATION ---
DATENBANK_ORDNER = "./chroma_test_db"

# Das 'r' vor den Anführungszeichen löst das Windows-Pfad-Problem!
TEST_DATEI = r"C:\digibest_wiki\C_CodexProjekte_FirmenApp_Projekt_Ausgabedaten_MD_50000001_Hexal_AG.md"

def digiwiki_starten():
    print("1. Initialisiere das Gehirn (Gemini Modelle)...")
    
    # LangChain holt sich den Key dank load_dotenv() jetzt vollautomatisch!
    # Wir müssen nur das korrekte, neue Embedding-Modell angeben.
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

    print(f"2. Lese Dokument ein: {os.path.basename(TEST_DATEI)}...")
    loader = TextLoader(TEST_DATEI, encoding="utf-8")
    dokumente = loader.load()

    print("3. Zerschneide Dokument in verdauliche Häppchen...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    text_stuecke = text_splitter.split_documents(dokumente)

    print("4. Speichere Wissen in der Chroma Vektordatenbank...")
    vektor_datenbank = Chroma.from_documents(
        documents=text_stuecke, 
        embedding=embeddings, 
        persist_directory=DATENBANK_ORDNER
    )

    print("\n" + "="*50)
    print("🚀 DIGIWIKI IST BEREIT!")
    print("="*50 + "\n")

    # Die Interaktionsschleife (Der Chat)
    while True:
        frage = input("Deine Frage an das Wiki (oder 'exit' zum Beenden): ")
        if frage.lower() == 'exit':
            break

        print("\nSuche im Firmenwissen...")
        # Die Datenbank sucht die 6 passendsten Textabschnitte
        treffer = vektor_datenbank.similarity_search(frage, k=6)
        
        gefundener_kontext = "\n\n".join([t.page_content for t in treffer])
        
        prompt = f"""
        Du bist das interne DigiWiki-System. Beantworte die Frage ausschließlich basierend auf dem folgenden Kontext.
        Wenn die Information nicht im Kontext steht, sage 'Das weiß ich leider nicht.'
        
        Kontext:
        {gefundener_kontext}
        
        Frage: {frage}
        """
        
        antwort = llm.invoke(prompt)
        print("\n🤖 DigiWiki antwortet:")
        print(antwort.content)
        print("-" * 50)

if __name__ == "__main__":
    if not os.path.exists(TEST_DATEI):
        print(f"Fehler: Die Datei {TEST_DATEI} existiert nicht. Bitte Pfad prüfen!")
    else:
        digiwiki_starten()