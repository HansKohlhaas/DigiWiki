import os
import hashlib
import shutil

# --- KONFIGURATION ---
# Welcher Ordner soll aufgeräumt werden? (Dein Testordner von gestern)
QUELL_ORDNER = "./Test_Daten"

# Wohin sollen die Duplikate verschoben werden?
ZIEL_ORDNER = "./Duplikate_Archiv"


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

def sicheres_verschieben(quell_pfad, ziel_verzeichnis):
    """Verschiebt eine Datei und verhindert, dass bestehende Dateien überschrieben werden."""
    # Falls der Archiv-Ordner noch nicht existiert, erstellen wir ihn
    if not os.path.exists(ziel_verzeichnis):
        os.makedirs(ziel_verzeichnis)
        
    dateiname = os.path.basename(quell_pfad)
    name, extension = os.path.splitext(dateiname)
    
    # Standard-Zielpfad
    ziel_pfad = os.path.join(ziel_verzeichnis, dateiname)
    
    # Falls die Datei im Zielordner schon existiert, hängen wir eine Nummer an
    zähler = 1
    while os.path.exists(ziel_pfad):
        neuer_dateiname = f"{name}_{zähler}{extension}"
        ziel_pfad = os.path.join(ziel_verzeichnis, neuer_dateiname)
        zähler += 1
        
    # Jetzt sicher verschieben
    try:
        shutil.move(quell_pfad, ziel_pfad)
        print(f"-> VERSCHOBEN: {os.path.basename(quell_pfad)} nach {os.path.basename(ziel_pfad)}")
    except Exception as e:
        print(f"Fehler beim Verschieben von {quell_pfad}: {e}")

def duplikate_aufräumen(start_ordner, archiv_ordner):
    print(f"Starte Bereinigung im Ordner: {start_ordner}...")
    print(f"Duplikate werden gesammelt in: {archiv_ordner}\n" + "-"*50)
    
    bekannte_hashes = set()
    anzahl_verschoben = 0
    
    # Wir gehen durch alle Ordner und Unterordner
    for ordnerpfad, _, dateinamen in os.walk(start_ordner):
        # Wichtig: Wir wollen nicht den Archiv-Ordner selbst durchsuchen, falls er im selben Verzeichnis liegt!
        if os.path.abspath(archiv_ordner) in os.path.abspath(ordnerpfad):
            continue
            
        for dateiname in dateinamen:
            dateipfad = os.path.join(ordnerpfad, dateiname)
            datei_hash = berechne_datei_hash(dateipfad)
            
            if datei_hash:
                # Haben wir diesen Datei-Inhalt schon einmal gesehen?
                if datei_hash in bekannte_hashes:
                    # JA -> Es ist ein Duplikat. Verschieben!
                    sicheres_verschieben(dateipfad, archiv_ordner)
                    anzahl_verschoben += 1
                else:
                    # NEIN -> Das ist unser "Original". Wir merken uns den Inhalt und lassen die Datei liegen.
                    bekannte_hashes.add(datei_hash)
                    
    print("-"*50)
    print(f"Bereinigung abgeschlossen! {anzahl_verschoben} Duplikate wurden ins Archiv verschoben.")

# --- Hauptprogramm ---
if __name__ == "__main__":
    duplikate_aufräumen(QUELL_ORDNER, ZIEL_ORDNER)