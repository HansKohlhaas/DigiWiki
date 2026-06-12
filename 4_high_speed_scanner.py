import os
import hashlib
import csv
from collections import defaultdict

# --- KONFIGURATION ---
# Das gesamte Laufwerk C:
START_ORDNER = "C:\\" 
AUSGABE_CSV = "HighSpeed_Duplikate_Laufwerk_C.csv"

RELEVANTE_ENDUNGEN = ('.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf', '.txt', '.md', '.accdb')

# Ordner, die wir ignorieren, um System-Müll und Abstürze zu vermeiden
IGNORIERTE_ORDNER = {'windows', 'program files', 'program files (x86)', 'appdata', '$recycle.bin', 'programdata', 'system volume information'}

def get_hash(dateipfad, first_chunk_only=False):
    hash_md5 = hashlib.md5()
    try:
        with open(dateipfad, "rb") as f:
            if first_chunk_only:
                hash_md5.update(f.read(4096))
            else:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None

def high_speed_scan(start_ordner):
    print(f"Stufe 1: Sammle Dateigrößen auf {start_ordner} (Blitzsuche)...")
    print("Systemordner werden automatisch übersprungen.")
    
    groessen_dict = defaultdict(list)
    
    for ordnerpfad, ordnernamen, dateinamen in os.walk(start_ordner):
        # Systemordner aus der Suche ausschließen (beschleunigt den Prozess massiv)
        ordnernamen[:] = [d for d in ordnernamen if d.lower() not in IGNORIERTE_ORDNER]
        
        for dateiname in dateinamen:
            if dateiname.lower().endswith(RELEVANTE_ENDUNGEN):
                pfad = os.path.abspath(os.path.join(ordnerpfad, dateiname))
                try:
                    groesse = os.path.getsize(pfad)
                    groessen_dict[groesse].append(pfad)
                except Exception:
                    # Falls eine Datei vom System gesperrt ist, überspringen wir sie lautlos
                    pass

    potenzielle_duplikate = [pfade for pfade in groessen_dict.values() if len(pfade) > 1]
    print(f"Stufe 1 abgeschlossen: {len(potenzielle_duplikate)} Gruppen mit identischer Dateigröße gefunden.")

    print("Stufe 2 & 3: Berechne Hashes für die verbleibenden Kandidaten...")
    echte_duplikate = defaultdict(list)
    
    for pfade in potenzielle_duplikate:
        for pfad in pfade:
            schnell_hash = get_hash(pfad, first_chunk_only=True)
            if not schnell_hash: continue
            
            voll_hash = get_hash(pfad, first_chunk_only=False)
            if not voll_hash: continue
                
            eindeutiger_key = f"{schnell_hash}_{voll_hash}"
            echte_duplikate[eindeutiger_key].append(pfad)

    finale_duplikate = {k: v for k, v in echte_duplikate.items() if len(v) > 1}
    return finale_duplikate

def schreibe_csv(duplikate_dict, ausgabe_csv):
    print("Schreibe Ergebnisse in CSV-Tabelle...")
    with open(ausgabe_csv, mode='w', newline='', encoding='utf-8-sig') as csv_datei:
        writer = csv.writer(csv_datei, delimiter=';')
        writer.writerow(["Gruppe", "Dateiname", "Kompletter Pfad (Ursprung)"])
        
        gruppen_nummer = 1
        for pfade in duplikate_dict.values():
            for pfad in pfade:
                writer.writerow([f"Gruppe {gruppen_nummer}", os.path.basename(pfad), pfad])
            writer.writerow([]) 
            gruppen_nummer += 1
            
    print(f"Fertig! Tabelle gespeichert unter: {os.path.abspath(ausgabe_csv)}")

if __name__ == "__main__":
    gefundene_duplikate = high_speed_scan(START_ORDNER)
    schreibe_csv(gefundene_duplikate, AUSGABE_CSV)