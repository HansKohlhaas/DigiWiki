import os
import csv
import shutil

# --- KONFIGURATION ---
CSV_DATEI = "HighSpeed_Duplikate_Laufwerk_C.csv"
ARCHIV_ORDNER = "./Duplikate_Archiv"

def pfad_zu_dateiname(ursprungs_pfad):
    """Wandelt einen kompletten Dateipfad in einen flachen Dateinamen um."""
    bereinigt = str(ursprungs_pfad).replace(":\\", "_").replace("\\", "_").replace("/", "_")
    return bereinigt

def verarbeite_duplikate(csv_pfad, archiv_ziel):
    if not os.path.exists(archiv_ziel):
        os.makedirs(archiv_ziel)
        print(f"Archiv-Ordner erstellt: {os.path.abspath(archiv_ziel)}")

    print("Lese CSV-Datei und wende 'Same-Folder-Rule' an...\n" + "-"*50)
    
    aktuell_gruppe = None
    original_ordner = None # Speichert den Ordner des jeweiligen Originals
    
    anzahl_verschoben = 0
    anzahl_ignoriert = 0
    fehler_count = 0

    try:
        with open(csv_pfad, mode='r', encoding='utf-8-sig') as datei:
            reader = csv.reader(datei, delimiter=';')
            next(reader) # Kopfzeile überspringen

            for zeile in reader:
                if not zeile or len(zeile) < 3:
                    continue 
                
                gruppen_name = zeile[0]
                datei_pfad = zeile[2]
                
                # Finde heraus, in welchem Ordner diese spezielle Datei liegt
                aktueller_ordner = os.path.dirname(datei_pfad)

                # Wenn wir auf eine neue Gruppe stoßen
                if gruppen_name != aktuell_gruppe:
                    aktuell_gruppe = gruppen_name
                    # Die erste Datei einer neuen Gruppe ist unser Original. 
                    # Wir merken uns ihren Ordner!
                    original_ordner = aktueller_ordner
                    continue 
                
                # --- DIE NEUE REGEL ---
                # Ist das Duplikat im exakt gleichen Ordner wie das Original?
                if aktueller_ordner == original_ordner:
                    # Ja! Es ist eine absichtliche Variante (z.B. andere ID im Namen).
                    # Wir verschieben sie NICHT.
                    anzahl_ignoriert += 1
                    continue
                
                # Wenn wir hier ankommen, ist die Datei in einem anderen Ordner 
                # -> Echtes Duplikat -> Verschieben!
                neuer_name = pfad_zu_dateiname(datei_pfad)
                ziel_pfad = os.path.join(archiv_ziel, neuer_name)

                if not os.path.exists(datei_pfad):
                    continue

                try:
                    shutil.move(datei_pfad, ziel_pfad)
                    anzahl_verschoben += 1
                except Exception as e:
                    print(f"Fehler beim Verschieben von {datei_pfad}: {e}")
                    fehler_count += 1

        print("-" * 50)
        print(f"Aktion abgeschlossen!")
        print(f"-> {anzahl_verschoben} echte Duplikate (aus anderen Ordnern) verschoben.")
        print(f"-> {anzahl_ignoriert} absichtliche Kopien (im selben Ordner) behalten.")
        
        if fehler_count > 0:
            print(f"Hinweis: Bei {fehler_count} Dateien gab es Zugriffsprobleme.")

    except FileNotFoundError:
        print(f"Fehler: Die Datei {csv_pfad} wurde nicht gefunden.")

if __name__ == "__main__":
    verarbeite_duplikate(CSV_DATEI, ARCHIV_ORDNER)