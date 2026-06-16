@st.cache_data(ttl=60)
def suche_telefonnummer(such_name):
    """Sucht strikt (AND) in CRM und Whitelist - absolut unabhängig."""
    if not such_name: 
        return pd.DataFrame()
        
    conn_str = fr'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};'
    try:
        conn = pyodbc.connect(conn_str)
        
        # 1. Namensteile vorbereiten
        teile = [t.strip() for t in str(such_name).split() if len(t.strip()) > 2]
        if not teile: teile = [str(such_name).strip()]

        # 2. CRM-Suche (Strikte AND-Logik)
        crm_where = " AND ".join([f"(nachname LIKE '%{t.replace("'", "''")}%' OR vorname LIKE '%{t.replace("'", "''")}%')" for t in teile])
        query_crm = f"SELECT vorname, nachname, mobil, telefon, 'CRM' as quelle FROM crm_personen WHERE {crm_where}"
        df_crm = pd.read_sql(query_crm, conn)
        
        # 3. Whitelist-Suche (Strikte AND-Logik)
        # Hier suchen wir nur im Feld [Name] – falls du andere Felder brauchst, sag Bescheid.
        wl_where = " AND ".join([f"([Name] LIKE '%{t.replace("'", "''")}%')" for t in teile])
        
        query_wl = f"""
            SELECT 'WL' as vorname, [Name] as nachname, [Tel_Mobil] as mobil, [Tel_Gesch] as telefon, 'WL' as quelle 
            FROM Whitelist_Kontakte 
            WHERE {wl_where}
        """
        df_wl = pd.read_sql(query_wl, conn)
        
        # 4. Ergebnisse im Speicher vereinen (kein JOIN auf DB-Ebene!)
        df = pd.concat([df_crm, df_wl], ignore_index=True)
        
        # 5. Scoring & Bereinigung
        if not df.empty:
            df['mobil'] = df['mobil'].fillna('').astype(str)
            df['telefon'] = df['telefon'].fillna('').astype(str)
            df['num_score'] = df['mobil'].str.len() + df['telefon'].str.len()
            df = df.sort_values('num_score', ascending=False)
            df = df.drop_duplicates(subset=['vorname', 'nachname']).head(5)
            
        return df
        
    except Exception as e:
        return pd.DataFrame()