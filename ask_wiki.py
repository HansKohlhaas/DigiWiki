import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain
from config import chroma_db_path_str, ist_gueltiger_wissensbereich, liste_wissensbereiche
from brandvoice import (
    BRANDVOICE_PROFILE,
    _finde_brandvoice_dateien,
    erkenne_brandvoice_wiki_frage,
    lade_brandvoice_kontext_fuer_frage,
)

# 1. WICHTIG: ChromaDB Telemetrie hart abschalten (verhindert Netzwerk-Hänger)
os.environ["ANONYMIZED_TELEMETRY"] = "False"

load_dotenv()

DATENBANK_ORDNER = chroma_db_path_str()

KEINE_INFO_TEXT = "Dazu liegen mir in der Datenbank aktuell keine Informationen vor."

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

BRANDVOICE_SYSTEM_PROMPT = """Du beantwortest Fragen zu Brandvoice-Dokumenten (Tonalitaet, Stil, Formulierungen).
Nutze AUSSCHLIESSLICH den bereitgestellten Dokumenttext. Rate nichts dazu.
Wenn das Thema im Text nicht vorkommt, sage klar: "Dazu liegen mir in der Datenbank aktuell keine Informationen vor."
Nenne am Ende in Klammern die Quelldatei(en), aus denen du zitiert hast.

BRANDVOICE-DOKUMENTE ({profil_name}):
{context}

BISHERIGER GESPRÄCHSVERLAUF:
{chat_historie}
"""


def baue_retriever(vektor_datenbank, bereich=None, max_treffer=5):
    if bereich and bereich != "vollzugriff":
        if not ist_gueltiger_wissensbereich(bereich):
            raise ValueError(f"Unbekannter Wissensbereich: {bereich}. Verfuegbar: {', '.join(liste_wissensbereiche())}")
        return vektor_datenbank.as_retriever(search_kwargs={"k": max_treffer, "filter": {"bereich": bereich}})
    return vektor_datenbank.as_retriever(search_kwargs={"k": max_treffer})


def _antwort_ohne_treffer(antwort: str) -> bool:
    return KEINE_INFO_TEXT in (antwort or "")


def frage_brandvoice_dokument(aktuelle_frage, historie_text="", stimme="hans"):
    """Direkter Pfad: Brandvoice-.docx lesen statt Vektor-Suche im CRM-Meer."""
    dateien = _finde_brandvoice_dateien(stimme)
    kontext, quellen = lade_brandvoice_kontext_fuer_frage(stimme, aktuelle_frage)
    profil_name = BRANDVOICE_PROFILE[stimme]["name"]
    if not kontext:
        if dateien:
            hinweis = (
                f"(Brandvoice-Dateien gefunden ({len(dateien)}), aber .docx-Text konnte nicht "
                f"gelesen werden. In der venv ausfuehren: python -m pip install docx2txt)"
            )
        else:
            hinweis = f"(Keine Brandvoice-Dateien fuer {profil_name} gefunden.)"
        return {
            "antwort": f"{KEINE_INFO_TEXT}\n\n{hinweis}",
            "quellen": [],
        }
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1, timeout=60, max_retries=1)
    prompt = ChatPromptTemplate.from_messages([
        ("system", BRANDVOICE_SYSTEM_PROMPT),
        ("human", "{input}"),
    ])
    kette = prompt | llm
    antwort = kette.invoke({
        "input": aktuelle_frage,
        "context": kontext,
        "chat_historie": historie_text or "(keiner)",
        "profil_name": profil_name,
    }).content
    if _antwort_ohne_treffer(antwort):
        return {"antwort": antwort, "quellen": []}
    return {"antwort": antwort, "quellen": quellen}


def frage_das_wiki(aktuelle_frage, historie_text="", bereich=None, max_treffer=5):
    """
    Fragt die Datenbank ab. Akzeptiert optional den bisherigen Gesprächsverlauf.
    """
    brandvoice_stimme = erkenne_brandvoice_wiki_frage(aktuelle_frage)
    if brandvoice_stimme:
        return frage_brandvoice_dokument(
            aktuelle_frage, historie_text=historie_text, stimme=brandvoice_stimme
        )

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
        vektor_datenbank = Chroma(persist_directory=DATENBANK_ORDNER, embedding_function=embeddings)
        retriever = baue_retriever(vektor_datenbank, bereich=bereich, max_treffer=max_treffer)

        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1, timeout=30, max_retries=1)

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{input}")
        ])

        frage_antwort_kette = create_stuff_documents_chain(llm, prompt)
        rag_kette = create_retrieval_chain(retriever, frage_antwort_kette)

        antwort_objekt = rag_kette.invoke({
            "input": aktuelle_frage,
            "chat_historie": historie_text
        })

        antwort = antwort_objekt["answer"]
        quellen_set = set()
        if not _antwort_ohne_treffer(antwort):
            for doc in antwort_objekt.get("context", []):
                quelle = doc.metadata.get("source", "Unbekannt")
                quellen_set.add(os.path.basename(quelle))

        return {
            "antwort": antwort,
            "quellen": list(quellen_set)
        }

    except Exception as e:
        print(f"Fehler im Orakel: {e}")
        return {
            "antwort": f"❌ **Technischer Fehler:** {str(e)}",
            "quellen": []
        }
