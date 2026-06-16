import os
import csv
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

# --- KONFIGURATION ---
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise SystemExit("GOOGLE_API_KEY fehlt. Bitte in .env setzen.")
START_ORDNER = "C:\\" 
ARCHIV_ORDNER = "Duplikate_Archiv" 
AUSGABE_CSV = "Wiki_Struktur_Vorschlag.csv"

RELEVANTE_ENDUNGEN = ('.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf', '.txt', '.md', '.accdb')
IGNORIERTE_ORDNER = {'windows', 'program files', 'program files (x86)', 'appdata', '$recycle.bin', 'programdata', 'system volume information'}

def sammle_dateien(start_ordner):
    print("Sammle alle verbliebenen Dateien...")
    datei_liste = []
    for ordnerpfad, ordnernamen, dateinamen in os.walk(start_ordner):
        ordnernamen[:] = [d for d in ordnernamen if d.lower() not in IGNORIERTE_ORDNER and d != ARCHIV_ORDNER]
        for dateiname in dateinamen:
            if dateiname.lower().endswith(RELEVANTE_ENDUNGEN):
                datei_liste.append(os.path.abspath(os.path.join(ordnerpfad, dateiname)))
    return datei_liste

def ki_kategorisierung_in_batches(datei_liste):
    # Die NEUE Art, die Google API aufzurufen
    client = genai.Client(api_key=API_KEY)
    
    BATCH_GROESSE = 300 # So viele Dateien schicken wir pro Durchgang
    total_batches = (len(datei_liste) // BATCH_GROESSE) + 1
    
    print(f"Starte KI-Analyse für {len(datei_liste)} Dateien in {total_batches} Etappen.")
    print("Die Tabelle wird live mitgeschrieben. Du kannst das Skript also jederzeit abbrechen.\n" + "-"*50)

    # Wir öffnen die CSV-Datei im "Append"-Modus ('a' statt 'w'), um Daten anzuhängen
    with open(AUSGABE_CSV, mode="w", encoding="utf-8-sig") as f:
        f.write("Ursprungspfad;Vorgeschlagener_Wiki_Ordner\n") # Kopfzeile

    with open(AUSGABE_CSV, mode="a", encoding="utf-8-sig") as f:
        for i in range(0, len(datei_liste), BATCH_GROESSE):
            chunk = datei_liste[i:i + BATCH_GROESSE]
            batch_num = (i // BATCH_GROESSE) + 1
            print(f"Verarbeite Paket {batch_num} von {total_batches}...")
            
            dateien_text = "\n".join(chunk)
            prompt = f"""
            Du bist ein Experte für Wissensmanagement.
            Ordne diese Dateipfade einer sauberen, flachen Ordnerstruktur für ein Unternehmens-Wiki zu (z.B. 'HR', 'IT', 'Rechnungen', 'Projekte', etc.).
            
            Gib AUSSCHLIESSLICH eine CSV-Tabelle (getrennt durch Semikolon) aus. Keine Einleitung, kein Markdown (```).
            Format:
            Ursprungspfad;Vorgeschlagener_Wiki_Ordner
            
            Dateien:
            {dateien_text}
            """

            try:
                # Der NEUE Aufruf für das Modell
                response = client.models.generate_content(
                    model='gemini-2.5-flash', # Wir nutzen das aktuellste Flash-Modell
                    contents=prompt
                )
                
                # Text bereinigen
                sauberer_text = response.text.replace("```csv", "").replace("```", "").strip()
                zeilen = sauberer_text.split('\n')
                
                # Falls die KI eine eigene Kopfzeile geschrieben hat, entfernen wir sie
                if zeilen and "Ursprungspfad" in zeilen[0]:
                    zeilen = zeilen[1:]
                    
                # Ins Dokument schreiben
                for zeile in zeilen:
                    if zeile.strip():
                        f.write(zeile.strip() + "\n")
                        
            except Exception as e:
                print(f"Fehler in Paket {batch_num}: {e}")

            # Pause, um das kostenlose API-Limit (meist 15 Aufrufe pro Minute) nicht zu sprengen
            if batch_num < total_batches:
                print("-> Pausiere für 10 Sekunden (Rate-Limit-Schutz)...")
                time.sleep(10)
                
    print("-" * 50)
    print(f"Komplette Analyse abgeschlossen! Tabelle gespeichert unter: {AUSGABE_CSV}")

if __name__ == "__main__":
    gefundene_dateien = sammle_dateien(START_ORDNER)
    if len(gefundene_dateien) > 0:
        ki_kategorisierung_in_batches(gefundene_dateien)
    else:
        print("Keine Dateien gefunden.")