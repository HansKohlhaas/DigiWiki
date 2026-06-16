import pyodbc

# --- KONFIGURATION ---
DB_PFAD = r"C:\CodexProjekte\FirmenApp\Digibest_master.accdb"
CONN_STR = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={DB_PFAD};"

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

def exportiere_schema():
    print("--- Starte Schema-Export (v1.1) ---")
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Fehler bei der Datenbankverbindung: {e}")
        return

    with open("db_schema.txt", "w", encoding="utf-8") as f:
        f.write("Datenbankschema für DigiWiki\n")
        f.write("============================\n\n")

        for tabelle in RELEVANTE_TABELLEN:
            f.write(f"Tabelle: {tabelle}\n")
            f.write("-" * 30 + "\n")
            try:
                # Workaround: Dummy-Abfrage umgeht den UTF-16 Bug
                cursor.execute(f"SELECT TOP 1 * FROM [{tabelle}]")
                
                # cursor.description enthält (Spaltenname, Datentyp, ...)
                for row in cursor.description:
                    spalten_name = row[0]
                    # Hole den lesbaren Namen des Python-Datentyps
                    daten_typ = row[1].__name__ if hasattr(row[1], '__name__') else str(row[1])
                    f.write(f" - {spalten_name} ({daten_typ})\n")
            except Exception as e:
                f.write(f" Fehler beim Lesen der Tabelle '{tabelle}': {e}\n")
                print(f"Fehler bei Tabelle {tabelle}: {e}")
            f.write("\n")

    conn.close()
    print("--- Export abgeschlossen ---")
    print("Die Datei 'db_schema.txt' wurde im Projektverzeichnis erstellt.")

if __name__ == "__main__":
    exportiere_schema()
