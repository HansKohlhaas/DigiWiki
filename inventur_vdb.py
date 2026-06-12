import chromadb

def inventur_vdb():
    # ChromaDB-Client anbinden
    client = chromadb.PersistentClient(path=r"F:\digibest_chroma_db")
    
    # Alle Collections auflisten
    collections = client.list_collections()
    
    print(f"Gefundene Collections: {[c.name for c in collections]}")
    
    for coll in collections:
        # Hole eine Stichprobe der Dokumente (z.B. 100)
        results = coll.get(limit=100)
        metadaten = results['metadatas']
        
        # Sammle alle eindeutigen Keys
        alle_keys = set()
        for meta in metadaten:
            if meta:
                alle_keys.update(meta.keys())
        
        print(f"\n--- Keys in Collection '{coll.name}' ---")
        print(f"Gefundene Attribute: {alle_keys}")

if __name__ == "__main__":
    inventur_vdb()