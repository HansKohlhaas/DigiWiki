import os

# --- KONFIGURATION ---
ORDNER = r"C:\Eigene Projekte\MD"
TESTLAUF = False  # Auf False setzen, um wirklich umzubenennen!

def bereinige_wasserdicht():
    print(f"📂 Prüfe Ordner: {ORDNER}\n")
    
    if not os.path.exists(ORDNER):
        print("❌ Fehler: Der Ordner existiert nicht.")
        return

    treffer_anzahl = 0

    for dateiname in os.listdir(ORDNER):
        pfad_alt = os.path.join(ORDNER, dateiname)
        
        if os.path.isfile(pfad_alt):
            # 1. Trenne die Zahlen am Anfang vom Rest des Dateinamens
            ziffern_block = ""
            for zeichen in dateiname:
                if zeichen.isdigit():
                    ziffern_block += zeichen
                else:
                    break # Stoppt beim ersten Nicht-Zahlen-Zeichen (z.B. _, Leerzeichen)
            
            rest_des_namens = dateiname[len(ziffern_block):]
            
            # 2. Die knallharte, mathematische Prüfung:
            # - Ist der Block am Anfang EXACT 9 Zeichen lang?
            # - Ist das 5. Zeichen (Index 4) eine '0'?
            if len(ziffern_block) == 9 and ziffern_block[4] == '0':
                treffer_anzahl += 1
                
                # Wir schneiden die '0' in der Mitte heraus (Nimm die ersten 4, lass eins aus, nimm den Rest)
                neuer_ziffern_block = ziffern_block[:4] + ziffern_block[5:]
                neuer_name = neuer_ziffern_block + rest_des_namens
                pfad_neu = os.path.join(ORDNER, neuer_name)
                
                if TESTLAUF:
                    print(f"🔍 [TESTLAUF] Erkannt als 9-stellig (0 in der Mitte):")
                    print(f"   ALT: {dateiname}")
                    print(f"   NEU: {neuer_name}\n")
                else:
                    try:
                        os.rename(pfad_alt, pfad_neu)
                        print(f"✅ Umbenannt: {neuer_name}")
                    except Exception as e:
                        print(f"❌ Fehler bei {dateiname}: {e}")

    print("-" * 50)
    if TESTLAUF:
        print(f"🏁 Testlauf beendet! Es würden {treffer_anzahl} Dateien geändert.")
        print("👉 Prüfe die Liste. Keine 8-stelligen Nummern mehr dabei?")
    else:
        print(f"🏁 Fertig! {treffer_anzahl} Dateien wurden erfolgreich bereinigt.")

if __name__ == "__main__":
    bereinige_wasserdicht()