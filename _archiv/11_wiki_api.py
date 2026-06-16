import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from config import API_HOST, API_PORT, ist_gueltiger_wissensbereich, liste_wissensbereiche

# Hier importieren wir einfach deine fertige Logik aus ask_wiki.py.
from ask_wiki import frage_das_wiki 

load_dotenv()

# Wir initialisieren die API
app = FastAPI(title="DigiWiki API", version="1.0")

# CORS-Einstellungen (Damit dein CRM von digibest.eu zugreifen darf)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Für die Produktion später auf ["http://digibest.eu:8181"] ändern!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dieses Datenmodell erwartet die API vom CRM
class WikiAnfrage(BaseModel):
    frage: str
    passwort: str # Ein kleiner Basisschutz für den Start
    bereich: str | None = None

# Der eigentliche Endpunkt, den das CRM aufruft
@app.post("/ask")
async def ask_endpoint(anfrage: WikiAnfrage):
    # Simpler Passwort-Schutz, damit nicht jeder das Wiki abfragen kann
    if anfrage.passwort != "DigiBest2026!": 
        raise HTTPException(status_code=401, detail="Zugriff verweigert")
    
    print(f"\n📡 Anfrage vom CRM empfangen: {anfrage.frage}")
    
    try:
        # Hier rufen wir einfach deine bereits geschriebene Funktion auf
        if anfrage.bereich and not ist_gueltiger_wissensbereich(anfrage.bereich):
            raise HTTPException(status_code=400, detail=f"Unbekannter Wissensbereich. Verfuegbar: {', '.join(liste_wissensbereiche())}")

        ergebnis = frage_das_wiki(anfrage.frage, bereich=anfrage.bereich)
        return ergebnis
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/areas")
async def get_areas():
    return {"areas": liste_wissensbereiche()}

if __name__ == "__main__":
    import uvicorn
    # Startet den lokalen Server auf Port 8000
    print("🚀 Starte DigiWiki API-Server...")
    uvicorn.run(app, host=API_HOST, port=API_PORT)