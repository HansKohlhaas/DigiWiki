import os
import shutil
from datetime import datetime

# ==============================================================================
# KONFIGURATION
# ==============================================================================

QUELL_ORDNER_LISTE = [
    r"C:\Eigene Projekte",
    r"C:\Verwaltung",
    r"C:\CodexProjekte\FirmenApp\Projekt\Ausgabedaten\Bearbeitet"
]

EVAKUIERUNGS_ORDNER = r"C:\Digibest_Wiki_Projekt\wiki_cleanup_pool"

# Grenzwerte
MAX_SIZE_MB = 25  
ERLAUBTE_ENDUNGEN = {'.pdf', '.docx', '.xlsx', '.txt', '.md', '.csv'} # Habe .csv passend zum Wächter ergänzt

# NEU: Der Stichtag (Alles, was VOR diesem Datum zuletzt geändert wurde, fliegt raus)
STICHTAG = datetime(2024, 6, 30).timestamp()

# ⚠️ DER SICHERHEITSSCHALTER
# True  = Simulation (Es wird nur gezählt und gedruckt)
# False = Scharf geschaltet (Dateien werden physisch verschoben!)
TEST_MODUS = False

# ==============================================================================
# LOGIK
# ==============================================================================

def initialisiere_zielordner(ziel):
    if not TEST_MODUS and not os.path.exists(ziel):
        os.makedirs(ziel)
        print(f"📁 Evakuierungs-Verzeichnis erstellt: {ziel}")

def verschiebe_systembremsen():
    if TEST_MODUS:
        print("\n" + "🟡 " * 15)
        print(" ACHTUNG: TEST-MODUS IST AKTIV!")
        print(" Es werden noch keine Dateien echt verschoben.")
        print("🟡 " * 15 + "\n")
    else:
        print("\n🚀 SCHARFSTART: Starte Daten-Bereinigung in den Hauptverzeichnissen...\n")

    initialisiere_zielordner(EVAKUIERUNGS_ORDNER)
    
    verschoben_groesse_zaehler = 0
    verschoben_typ_zaehler = 0
    verschoben_alter_zaehler = 0 # NEU
    freigeraeumte_bytes = 0
    fehler_zaehler = 0
    
    print("-" * 70)

    for quell_ordner in QUELL_ORDNER_LISTE:
        if not os.path.exists(quell_ordner):
            print(f"⚠️ Warnung: Quellordner existiert nicht: {quell_ordner}")
            continue
            
        print(f"🔍 Scanne Verzeichnis: {quell_ordner}")
        
        for root, dirs, files in os.walk(quell_ordner):
            # Sicherheitsnetz: Ignoriere interne Systemordner
            if any(part in root for part in ['digibest_chroma_db', '.venv', '__pycache__', '.git', 'wiki_cleanup_pool']):
                continue
                
            for file in files:
                voller_pfad = os.path.join(root, file)
                dateiname, endung = os.path.splitext(file)
                endung = endung.lower()
                
                try:
                    grund = None
                    dateigroesse_bytes = os.path.getsize(voller_pfad)
                    dateigroesse_mb = dateigroesse_bytes / (1024 * 1024)
                    datei_alter = os.path.getmtime(voller_pfad)
                    
                    # 1. Kriterium: Falscher Dateityp
                    if endung not in ERLAUBTE_ENDUNGEN:
                        grund = f"Falscher Typ ({endung})"
                        verschoben_typ_zaehler += 1
                        
                    # 2. Kriterium: Zu groß
                    elif dateigroesse_mb > MAX_SIZE_MB:
                        grund = f"Zu groß ({dateigroesse_mb:.1f} MB)"
                        verschoben_groesse_zaehler += 1
                        
                    # 3. Kriterium: Zu alt (vor 30.06.2024)
                    elif datei_alter < STICHTAG:
                        grund = f"Zu alt (Vor dem 30.06.24)"
                        verschoben_alter_zaehler += 1
                    
                    # Wenn ein Kriterium zutrifft -> Datei evakuieren!
                    if grund:
                        relativer_pfad = os.path.relpath(root, quell_ordner)
                        
                        # Wir packen den Quellordner-Namen dazu, damit sich Dateien 
                        # aus "Eigene Projekte" und "Verwaltung" nicht im Pool überschneiden
                        quellordner_name = os.path.basename(quell_ordner)
                        ziel_unterordner = os.path.join(EVAKUIERUNGS_ORDNER, quellordner_name, relativer_pfad)
                        ziel_pfad = os.path.join(ziel_unterordner, file)
                        
                        if not TEST_MODUS:
                            if not os.path.exists(ziel_unterordner):
                                os.makedirs(ziel_unterordner)
                            
                            basis_ziel, ext_ziel = os.path.splitext(ziel_pfad)
                            counter = 1
                            while os.path.exists(ziel_pfad):
                                ziel_pfad = f"{basis_ziel}_{counter}{ext_ziel}"
                                counter += 1
                            
                            shutil.move(voller_pfad, ziel_pfad)
                            print(f"  📦 EVAKUIERT: {file} -> {grund}")
                        else:
                            print(f"  [SIMULATION] Würde evakuieren: {file} -> {grund}")
                            
                        freigeraeumte_bytes += dateigroesse_bytes
                        
                except Exception as e:
                    print(f"❌ Fehler bei Datei {file}: {str(e)}")
                    fehler_zaehler += 1

    # --- ABSCHLUSS-STATISTIK ---
    freigewordene_gb = freigeraeumte_bytes / (1024 * 1024 * 1024)
    
    print("-" * 70)
    print("📊 BEREINIGUNG BEENDET")
    print(f"⚠️ Zu groß (> {MAX_SIZE_MB}MB) : {verschoben_groesse_zaehler} Dateien")
    print(f"🚫 Falscher Typ         : {verschoben_typ_zaehler} Dateien")
    print(f"🕰️ Zu alt (< 30.06.24)  : {verschoben_alter_zaehler} Dateien")
    print(f"💾 Entlastung insgesamt : {freigewordene_gb:.2f} Gigabyte")
    
    if fehler_zaehler > 0:
        print(f"❌ Blockiert/Fehlerhaft: {fehler_zaehler} Dateien")
        
    if TEST_MODUS:
        print("\n💡 Um die Dateien ECHT zu verschieben, setze oben im Skript")
        print("   TEST_MODUS = False und starte es neu.")
    else:
        print("\n✅ Deine Hauptordner sind jetzt absolut sauber für den Wächter!")

if __name__ == "__main__":
    verschiebe_systembremsen()