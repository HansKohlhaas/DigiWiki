import os
import re

# --- KONFIGURATION ---
MD_ORDNER = r"C:\Eigene Projekte\MD" # Hier den echten Pfad eintragen

# Sucht nach der ersten durchgehenden Zahlenfolge im Dateinamen (Standard-Annahme)
KDNR_MUSTER = r"(\d+)"

def entferne_md_duplikate(ordner_pfad):
    print(f"--- Starte Bereinigung im Ordner: {ordner_pfad} ---")
    
    if not os.path.exists(ordner_pfad):
        print("Fehler: Der angegebene Ordner wurde nicht gefunden.")
        return

    dateien_nach_kdnr = {}
    
    # 1. Alle MD-Dateien erfassen und nach Kundennummer gruppieren
    for dateiname in os.listdir(ordner_pfad):
        if dateiname.lower().endswith(".md"):
            pfad = os.path.join(ordner_pfad, dateiname)
            
            # Kundennummer aus dem Dateinamen extrahieren
            treffer = re.search(KDNR_MUSTER, dateiname)
            
            if treffer:
                kdnr = treffer.group(1)
                dateigroesse = os.path.getsize(pfad)
                
                if kdnr not in dateien_nach_kdnr:
                    dateien_nach_kdnr[kdnr] = []
                
                dateien_nach_kdnr[kdnr].append({
                    "pfad": pfad, 
                    "groesse": dateigroesse, 
                    "name": dateiname
                })

    # 2. Duplikate finden und löschen
    geloescht_count = 0
    freigegeben_bytes = 0

    for kdnr, dateien in dateien_nach_kdnr.items():
        if len(dateien) > 1:
            # Nach Dateigröße absteigend sortieren (größte Datei auf Index 0)
            dateien.sort(key=lambda x: x["groesse"], reverse=True)
            
            behalten = dateien[0]
            zu_loeschen = dateien[1:]
            
            print(f"\nKundennummer {kdnr}:")
            print(f"  [BEHALTE] '{behalten['name']}' ({behalten['groesse']} Bytes)")
            
            for datei in zu_loeschen:
                try:
                    os.remove(datei["pfad"])
                    geloescht_count += 1
                    freigegeben_bytes += datei["groesse"]
                    print(f"  [GELÖSCHT] '{datei['name']}' ({datei['groesse']} Bytes)")
                except Exception as e:
                    print(f"  [FEHLER] Konnte '{datei['name']}' nicht löschen: {e}")

    # 3. Abschlussbericht
    print("\n--- Zusammenfassung ---")
    print(f"Gelöschte Duplikate: {geloescht_count}")
    print(f"Freigegebener Speicher: {freigegeben_bytes / 1024:.2f} KB")

if __name__ == "__main__":
    entferne_md_duplikate(MD_ORDNER)