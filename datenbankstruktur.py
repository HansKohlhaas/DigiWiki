import pyodbc

def lese_tabellenstruktur(db_pfad, tabellen_name):
    conn_str = rf'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_pfad};'
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    # Struktur über cursor.columns dynamisch abfragen
    spalten = cursor.columns(table=tabellen_name).fetchall()
    
    print(f"--- Struktur der Tabelle '{tabellen_name}' ---")
    for spalte in spalten:
        print(f"Spalte: {spalte.column_name} | Typ: {spalte.type_name} | Größe: {spalte.column_size}")
        
    conn.close()

# Ausführung
pfad = r"C:\CodexProjekte\FirmenApp\Digibest_Master.accdb"
lese_tabellenstruktur(pfad, "Whitelist_Kontakte")