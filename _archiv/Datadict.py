import pyodbc
import csv

# --- KONFIGURATION ---
DB_PFAD = r"C:\CodexProjekte\FirmenApp\Digibest_Master.accdb"
CONN_STR = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={DB_PFAD};"

# Die definierte Tabellen-Liste inkl. abdaartikel
RELEVANTE_TABELLEN = [
    "Connections",
    "crm_aktivitaeten",
    "crm_firmen_aktivitaeten",
    "crm_firmen_trigger_historie",
    "crm_personen",
    "Invitations_Normalized",
    "ref_funktionen",
    "stammdatenapo",
    "stammdatenindustrie",
    "Whitelist_Kontakte",
    "Datei_Index",
    "abdaartikel"
]

def erstelle_csv_dictionary():
    print("--- Generiere Semantisches Data Dictionary ---")
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Datenbankfehler: {e}")
        return

    # utf-8-sig sorgt dafür, dass Excel Umlaute direkt korrekt erkennt
    with open("data_dictionary.csv", "w", newline='', encoding="utf-8-sig") as f:
        # Semikolon ist der Standard-Trenner für deutsches Excel
        writer = csv.writer(f, delimiter=';') 
        
        # Kopfzeile
        writer.writerow(["Tabelle", "Spalte", "Datentyp", "Beschreibung_Inhalt", "Join_Foreign_Key"])
        
        for tabelle in RELEVANTE_TABELLEN:
            try:
                cursor.execute(f"SELECT TOP 1 * FROM [{tabelle}]")
                for row in cursor.description:
                    spalte = row[0]
                    typ = row[1].__name__ if hasattr(row[1], '__name__') else str(row[1])
                    
                    # Zeile schreiben mit Platzhaltern für dich
                    writer.writerow([tabelle, spalte, typ, "", ""])
            except Exception as e:
                print(f"Fehler bei Tabelle {tabelle}: {e}")

    conn.close()
    print("--- Export abgeschlossen ---")
    print("Bitte öffne 'data_dictionary.csv' in Excel und fülle die leeren Felder aus.")

if __name__ == "__main__":
    erstelle_csv_dictionary()