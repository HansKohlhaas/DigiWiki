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
    
    # Pandas-Warnung umgehen: Manuelles Mapping in DataFrame
    spalten = [column[0] for column in cursor.description]
    df = pd.DataFrame.from_records(rows, columns=spalten)
    conn.close()
    
    print(f"DEBUG: {len(df)} Kontakte aus Access geladen.")
    return df

def hole_relevante_emails(whitelist_df):
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    inbox = outlook.GetDefaultFolder(6)
    messages = inbox.Items
    messages.Sort("[ReceivedTime]", True)
    
    relevante_mails = []
    whitelist_emails = whitelist_df['Email_Gesch'].str.lower().tolist()
    
    print(f"DEBUG: Suche in Outlook nach diesen Adressen: {whitelist_emails}")

    for i in range(min(50, len(messages))):
        try:
            msg = messages[i]
            # Nur echte E-Mails verarbeiten (Class 43 = MailItem), keine Kalendereinträge
            if msg.Class != 43:
                continue
                
            sender = msg.SenderEmailAddress
            
            # Exchange-Adressen in echte SMTP-Adressen umwandeln
            if msg.SenderEmailType == "EX":
                exchange_user = msg.Sender.GetExchangeUser()
                if exchange_user is not None:
                    sender = exchange_user.PrimarySmtpAddress

            sender = sender.lower()
            
            if sender in whitelist_emails:
                kontakt_info = whitelist_df[whitelist_df['Email_Gesch'].str.lower() == sender].iloc[0]
                relevante_mails.append({
                    "Absender_Email": sender,
                    "Vorname": kontakt_info['Vorname'],
                    "Nachname": kontakt_info['Nachname'],
                    "Betreff": msg.Subject
                })
        except Exception as e:
            pass 
            
    return relevante_mails

# Ausführung
db_pfad = r"C:\CodexProjekte\FirmenApp\Digibest_Master.accdb"
whitelist = lade_whitelist(db_pfad)

if not whitelist.empty:
    gefilterte_mails = hole_relevante_emails(whitelist)
    print(f"\nERGEBNIS: {len(gefilterte_mails)} relevante Mails gefunden.")
    for mail in gefilterte_mails:
        print(f"- {mail['Vorname']} {mail['Nachname']} | Betreff: {mail['Betreff']}")
else:
    print("FEHLER: Whitelist ist leer. Bitte Access-Datenbank prüfen.")