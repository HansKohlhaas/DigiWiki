import os
import hashlib
import csv
from datetime import datetime

# --- KONFIGURATION ---
# Welcher Hauptordner soll durchsucht werden? (Alle Unterordner werden automatisch mitgenommen)
# Du kannst hier später z.B. "C:/Users/DeinName/Documents" eintragen.
START_ORDNER = "./Test_Daten"

# Die Ausgabedatei
AUSGABE_CSV = "Master_Duplikate_Inventur.csv"

# Welche Dateitypen interessieren uns? (Alles klein geschrieben eintragen)
RELEVANTE_ENDUNGEN = (
    '.doc', '.docx',  # Word
    '.xls', '.xlsx',  # Excel
    '.ppt', '.pptx',  # PowerPoint
    '.pdf',           # PDF
    '.txt', '.md',    # Text & Markdown
    '.accdb', '.mdb'  # Access
)

def berechne_datei_hash(dateipfad):
    """Erstellt den digitalen Fingerabdruck der Datei."""
    hash_md5 = hashlib.md5()
    try:
        with open(dateipfad, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"Fehler beim Lesen von {dateipfad}: {e}")
        return None

def hole_datei_infos(pfad):
    """Liest Größe und letztes Änderungsdatum der Datei aus."""
    stat = os.stat(pfad)
    groesse_kb = round(stat.st_size / 1024, 2)
    datum = datetime.fromtimestamp(stat.st_mtime).strftime('%d.%m.%Y %H:%M')
    return groesse_kb, datum

def inventur_durchfuehren(start_ordner):
    print(f"Starte intelligente Inventur in: {os.path.abspath(start_ordner)}...")
    print(f"Suche nach Dateitypen: {', '.join(RELEVANTE_ENDUNGEN)}\n" + "-"*50)
    
    # Speichert Hash -> Liste von Datei-Informationen (Pfad, Größe, Datum)
    datei_datenbank = {} 
    durchsuchte_dateien = 0
    
    for ordnerpfad, _, dateinamen in os.walk(start_ordner):
        for dateiname in dateinamen:
            # Prüfen, ob die Datei eine unserer gesuchten Endungen hat
            if not dateiname.lower().endswith(RELEVANTE_ENDUNGEN):
                continue
                
            dateipfad = os.path.abspath(os.path.join(ordnerpfad, dateiname))
            datei_hash = berechne_datei_hash(dateipfad)
            durchsuchte_dateien += 1
            
            if datei_hash:
                groesse, datum = hole_datei_infos(dateipfad)
                datei_info = {
                    'name': dateiname,
                    'ordner': ordnerpfad,
                    'pfad': dateipfad,
                    'groesse_kb': groesse,
                    'datum': datum
                }
                
                if datei_hash in datei_datenbank:
                    datei_datenbank[datei_hash].append(datei_info)
                else:
                    datei_datenbank[datei_hash] = [datei_info]
                    
    return datei_datenbank, durchsuchte_dateien

def erstelle_inventur_bericht(datei_datenbank, ausgabe_csv):
    # Nur Gruppen behalten, die mehr als eine Datei haben (Duplikate)
    duplikate = {h: infos for h, infos in datei_datenbank.items() if len(infos) > 1}
    
    if not duplikate:
        print("Es wurden keine Duplikate bei den angegebenen Dateitypen gefunden.")
        return

    print(f"Gefunden: {len(duplikate)} Gruppen von Duplikaten. Schreibe Bericht...")
    
    with open(ausgabe_csv, mode='w', newline='', encoding='utf-8-sig') as csv_datei:
        # utf-8-sig sorgt dafür, dass Excel Umlaute richtig anzeigt
        writer = csv.writer(csv_datei, delimiter=';') 
        writer.writerow(["Gruppe", "Dateiname", "Zuletzt geändert", "Größe (KB)", "Ordnerpfad", "Kompletter Pfad"])
        
        gruppen_nummer = 1
        for _, infos in duplikate.items():
            for datei in infos:
                writer.writerow([
                    f"Duplikat-Gruppe {gruppen_nummer}", 
                    datei['name'], 
                    datei['datum'], 
                    datei['groesse_kb'], 
                    datei['ordner'],
                    datei['pfad']
                ])
            # Eine leere Zeile zur besseren Lesbarkeit zwischen den Gruppen in Excel
            writer.writerow([]) 
            gruppen_nummer += 1
            
    print(f"Fertig! Bericht gespeichert unter: {os.path.abspath(ausgabe_csv)}")

# --- Hauptprogramm ---
if __name__ == "__main__":
    datenbank, anzahl = inventur_durchfuehren(START_ORDNER)
    print(f"Insgesamt wurden {anzahl} relevante Dateien analysiert.")
    erstelle_inventur_bericht(datenbank, AUSGABE_CSV)