import pyodbc
import pandas as pd
import win32com.client

def lade_whitelist(db_pfad):
    conn_str = rf'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_pfad};'
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    query = "SELECT Email_Gesch, Vorname, Nachname, Ansprache FROM Whitelist_Kontakte WHERE Email_Gesch IS NOT NULL"
    cursor.execute(query)
    rows = cursor.fetchall()
    
    spalten = [column[0] for column in cursor.description]
    df = pd.DataFrame.from_records(rows, columns=spalten)
    conn.close()
    
    print(f"DEBUG: {len(df)} Kontakte aus Access geladen.")
    return df

def hole_relevante_emails(whitelist_df):
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    
    print("\n--- DEBUG: VERFÜGBARE OUTLOOK-KONTEN ---")
    for s in outlook.Stores:
        print(f"Gefunden: '{s.DisplayName}'")
    print("----------------------------------------\n")

    relevante_mails = []
    if whitelist_df.empty:
        return relevante_mails
        
    whitelist_emails = whitelist_df['Email_Gesch'].str.lower().tolist()

    for store in outlook.Stores:
        try:
            inbox = store.GetDefaultFolder(6) # 6 = Posteingang
            messages = inbox.Items
            messages.Sort("[ReceivedTime]", True)
            
            print(f"Scanne Konto: '{store.DisplayName}'...")
            
            for i in range(min(100, len(messages))):
                msg = messages[i]
                if msg.Class != 43:
                    continue
                    
                sender = msg.SenderEmailAddress
                
                if msg.SenderEmailType == "EX":
                    exchange_user = msg.Sender.GetExchangeUser()
                    if exchange_user is not None:
                        sender = exchange_user.PrimarySmtpAddress

                sender = sender.lower()
                
                if sender in whitelist_emails:
                    kontakt_info = whitelist_df[whitelist_df['Email_Gesch'].str.lower() == sender].iloc[0]
                    relevante_mails.append({
                        "Konto": store.DisplayName,
                        "Absender_Email": sender,
                        "Vorname": kontakt_info['Vorname'],
                        "Nachname": kontakt_info['Nachname'],
                        "Betreff": msg.Subject
                    })
        except Exception as e:
            # Ordner existiert nicht oder Zugriff verweigert (z.B. bei reinen Datendateien)
            pass
            
    return relevante_mails

# Ausführung
db_pfad = r"C:\CodexProjekte\FirmenApp\Digibest_Master.accdb"
whitelist = lade_whitelist(db_pfad)

gefilterte_mails = hole_relevante_emails(whitelist)

print(f"\nERGEBNIS: {len(gefilterte_mails)} relevante Mails gefunden.")
for mail in gefilterte_mails:
    print(f"- [{mail['Konto']}] {mail['Vorname']} {mail['Nachname']} | Betreff: {mail['Betreff']}")