import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain

# 1. WICHTIG: ChromaDB Telemetrie hart abschalten (verhindert Netzwerk-Hänger)
os.environ["ANONYMIZED_TELEMETRY"] = "False"

load_dotenv()

DATENBANK_ORDNER = r"F:\digibest_chroma_db"

# --- DER NEUE C-LEVEL SYSTEM-PROMPT ---
SYSTEM_PROMPT = """Du bist die exklusive, hochprofessionelle KI-Assistenz für den Geschäftsführer von DigiBest.
Deine Aufgabe ist es, Fragen basierend auf dem bereitgestellten Kontext messerscharf, präzise und geschäftstauglich zu beantworten.

REGELN FÜR DEINE ANTWORT:
1. Antworte immer auf Deutsch, in einem professionellen, kompetenten und direkten Ton (C-Level-Niveau). Keine Floskeln.
2. Nutze AUSSCHLIESSLICH die Informationen aus dem bereitgestellten Kontext. Rate niemals.
3. Wenn die Antwort nicht im Kontext steht, sage glasklar: "Dazu liegen mir in der Datenbank aktuell keine Informationen vor."
4. Strukturiere deine Antwort gut lesbar (nutze Tabellen, Aufzählungen oder Fettungen für wichtige Werte).
5. Berücksichtige bei deiner Antwort auch den "Bisherigen Gesprächsverlauf", falls der Nutzer sich auf etwas bezieht, das ihr gerade besprochen habt.

KONTEXT AUS DER DATENBANK:
{context}

BISHERIGER GESPRÄCHSVERLAUF:
{chat_historie}
"""

def frage_das_wiki(aktuelle_frage, historie_text=""):
    """
    Fragt die Datenbank ab. Akzeptiert optional den bisherigen Gesprächsverlauf.
    """
    try:
        # 2. Datenbank und KI laden
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
        vektor_datenbank = Chroma(persist_directory=DATENBANK_ORDNER, embedding_function=embeddings)
        retriever = vektor_datenbank.as_retriever(search_kwargs={"k": 5}) # Holt die 5 besten Treffer
        
        # 3. Timeout und Retries einbauen, um Endlos-Warten zu verhindern
        llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.1, timeout=15, max_retries=1)
        
        # 4. Den neuen Prompt zusammenbauen
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{input}")
        ])
        
        # 5. Die Kette (Chain) erstellen
        frage_antwort_kette = create_stuff_documents_chain(llm, prompt)
        rag_kette = create_retrieval_chain(retriever, frage_antwort_kette)
        
        # 6. Die Abfrage mit Historie starten
        antwort_objekt = rag_kette.invoke({
            "input": aktuelle_frage,
            "chat_historie": historie_text
        })
        
        # 7. Quellen sauber extrahieren
        gefundene_dokumente = antwort_objekt.get("context", [])
        quellen_set = set()
        for doc in gefundene_dokumente:
            quelle = doc.metadata.get("source", "Unbekannt")
            dateiname = os.path.basename(quelle)
            quellen_set.add(dateiname)
            
        return {
            "antwort": antwort_objekt["answer"],
            "quellen": list(quellen_set)
        }
        
    except Exception as e:
        print(f"Fehler im Orakel: {e}")
        # 8. Echte Fehlermeldung direkt in die UI durchreichen
        return {
            "antwort": f"❌ **Technischer Fehler:** {str(e)}",
            "quellen": []
        }