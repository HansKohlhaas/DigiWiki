import os
import shutil

# --- KONFIGURATION ---
START_ORDNER = "C:\\" 
WIKI_ORDNER = "C:\\digibest_wiki"
ARCHIV_ORDNER = "Duplikate_Archiv" # Diesen Ordner ignorieren wir wieder

RELEVANTE_ENDUNGEN = ('.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf', '.txt', '.md', '.accdb')
IGNORIERTE_ORDNER = {'windows', 'program files', 'program files (x86)', 'appdata', '$recycle.bin', 'programdata', 'system volume information', 'digibest_wiki'}

def pfad_zu_dateiname(ursprungs_pfad):
    """Sichert den Kontext: Aus C:\Projekte\A\Rechnung.pdf wird C_Projekte_A_Rechnung.pdf"""
    bereinigt = str(ursprungs_pfad).replace(":\\", "_").replace("\\", "_").replace("/", "_")
    return bereinigt

def erstelle_wiki_sandbox(start, ziel):
    if not os.path.exists(ziel):
        os.makedirs(ziel)
        print(f"Wiki-Ordner erstellt: {ziel}")
        
    print(f"Kopiere Dateien sicher nach {ziel}...\nDas kann einen Moment dauern.")
    
    kopiert = 0
    fehler = 0
    
    for ordnerpfad, ordnernamen, dateinamen in os.walk(start):
        # Ignorierte Ordner aussortieren
        ordnernamen[:] = [d for d in ordnernamen if d.lower() not in IGNORIERTE_ORDNER and d != ARCHIV_ORDNER]
        
        for dateiname in dateinamen:
            if dateiname.lower().endswith(RELEVANTE_ENDUNGEN):
                quell_pfad = os.path.abspath(os.path.join(ordnerpfad, dateiname))
                
                # Neuen Namen mit Pfad-Kontext generieren
                neuer_name = pfad_zu_dateiname(quell_pfad)
                ziel_pfad = os.path.join(ziel, neuer_name)
                
                try:
                    # copy2 kopiert die Datei inklusive Metadaten (Zeitstempel)
                    shutil.copy2(quell_pfad, ziel_pfad) 
                    kopiert += 1
                except Exception as e:
                    fehler += 1
                    
    print("-" * 50)
    print(f"Sandbox bereit! {kopiert} Dateien wurden als sichere Kopie im Wiki-Ordner abgelegt.")
    if fehler > 0:
        print(f"Hinweis: {fehler} Dateien konnten wegen fehlender Rechte nicht kopiert werden.")

if __name__ == "__main__":
    erstelle_wiki_sandbox(START_ORDNER, WIKI_ORDNER)