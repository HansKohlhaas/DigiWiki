import os
import hashlib
import csv

# Konfiguration: Hier trägst du den Pfad zu deinem Testordner ein
ORDNER_ZUM_DURCHSUCHEN = "./Test_Daten" 
AUSGABE_DATEI = "duplikate_bericht.csv"

def berechne_datei_hash(dateipfad):
    """Liest die Datei in kleinen Stücken und erstellt einen digitalen Fingerabdruck (Hash)."""
    hash_md5 = hashlib.md5()
    try:
        with open(dateipfad, "rb") as f:
            # Datei in Blöcken lesen, damit der Arbeitsspeicher bei großen Dateien nicht vollläuft
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"Fehler beim Lesen von {dateipfad}: {e}")
        return None

def finde_duplikate(start_ordner):
    print(f"Starte Suche in: {start_ordner}...")
    
    hash_zu_dateien = {} # Speichert den Fingerabdruck und die dazugehörigen Dateipfade
    
    # Geht durch alle Ordner und Unterordner
    for ordnerpfad, _, dateinamen in os.walk(start_ordner):
        for dateiname in dateinamen:
            dateipfad = os.path.join(ordnerpfad, dateiname)
            datei_hash = berechne_datei_hash(dateipfad)
            
            if datei_hash:
                # Wenn wir den Hash schon kennen, fügen wir die Datei der Liste hinzu
                if datei_hash in hash_zu_dateien:
                    hash_zu_dateien[datei_hash].append(dateipfad)
                # Wenn nicht, erstellen wir einen neuen Eintrag
                else:
                    hash_zu_dateien[datei_hash] = [dateipfad]
                    
    return hash_zu_dateien

def erstelle_bericht(hash_zu_dateien, ausgabe_csv):
    # Wir filtern alle Einträge heraus, die nur einmal vorkommen (keine Duplikate)
    duplikate = {h: pfad_liste for h, pfad_liste in hash_zu_dateien.items() if len(pfad_liste) > 1}
    
    if not duplikate:
        print("Keine exakten Duplikate gefunden!")
        return

    print(f"Es wurden {len(duplikate)} Gruppen von Duplikaten gefunden. Erstelle Bericht...")
    
    # CSV Bericht schreiben
    with open(ausgabe_csv, mode='w', newline='', encoding='utf-8') as csv_datei:
        writer = csv.writer(csv_datei, delimiter=';') # Semikolon für Excel
        writer.writerow(["Gruppe", "Anzahl Kopien", "Dateipfade"])
        
        gruppen_nummer = 1
        for _, pfad_liste in duplikate.items():
            for pfad in pfad_liste:
                writer.writerow([f"Duplikat-Gruppe {gruppen_nummer}", len(pfad_liste), pfad])
            gruppen_nummer += 1
            
    print(f"Bericht erfolgreich gespeichert unter: {ausgabe_csv}")

# --- Hauptprogramm ---
if __name__ == "__main__":
    gefundene_dateien = finde_duplikate(ORDNER_ZUM_DURCHSUCHEN)
    erstelle_bericht(gefundene_dateien, AUSGABE_DATEI)