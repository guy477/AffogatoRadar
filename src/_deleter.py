from backend import local_storage


def __DELETER_(db_name, base_url_or_like):
    # def remove_entries(local_storage):
    storage = local_storage.LocalStorage(storage_dir="../data", db_name=db_name)
    
    try:
        # Fetch all hash_key and idx pairs
        storage.cursor.execute("SELECT hash_key, idx FROM place_id_map")
        all_records = storage.cursor.fetchall()
        
        # Iterate over each record and remove the ones containing 'whataburger'
        for hash_key, idx in all_records:
            if base_url_or_like in hash_key.lower():  # Case-insensitive check
                print(f"Removing entry for: {hash_key}")
                
                # Delete from place_id_map
                storage.cursor.execute("DELETE FROM place_id_map WHERE hash_key = ?", (hash_key,))
                
                # Delete corresponding data in data_dump
                storage.cursor.execute("DELETE FROM data_dump WHERE id = ?", (idx,))
                
                # Commit changes
                storage.conn.commit()
    except Exception as e:
        print(f"Error: {e}")

    storage.close()
    print("Finished removing entries.")
