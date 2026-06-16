@st.cache_data(ttl=300)
def lade_whatsapp_kontakte():
    conn_str = fr'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};'
    try:
        conn = pyodbc.connect(conn_str)
        # Direktes und stabiles Mapping über die indpersonid der Whitelist
        query = """
            SELECT p.personid, p.anrede, p.vorname, p.nachname, w.Tel_Mobil, p.telefon, p.emailpers, p.privat_email, p.funktionsbezeichnung
            FROM crm_personen AS p INNER JOIN Whitelist_Kontakte AS w ON p.personid = w.indpersonid
            WHERE (((w.Tel_Mobil) Is Not Null));
        """
        df = pd.read_sql(query, conn)
        
        df = df.drop_duplicates(subset=['personid'])
        
        conn.close()
        return df
    except Exception as e:
        st.error(f"Datenbank-Fehler beim Laden der WhatsApp-Kontakte: {e}")
        return pd.DataFrame()