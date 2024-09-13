from _utils._util import *

class LocalStorage:
    def __init__(self, storage_dir: str = "../data", db_name: str = "local_storage.db"):
        self.storage_dir = storage_dir
        self.db_path = os.path.join(storage_dir, db_name)

        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        self._init_db()

    def _init_db(self):
        """Initialize the database if it doesn't exist."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        # Create table if it doesn't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_dump (
                hash_key TEXT PRIMARY KEY,
                data TEXT
            )
        """)
        self.conn.commit()

    def get_data_by_hash(self, hash_key):
        """Retrieve data from the cache using the hashed key."""
        self.cursor.execute("SELECT data FROM data_dump WHERE hash_key = ?", (hash_key,))
        fetched = self.cursor.fetchone()
        return fetched[0] if fetched else None  # Return JSON data as string

    def save_data(self, hash_key, data):
        """Save new API results to the cache, overwrite if data already exists."""
        # First, check if the hash_key already exists
        old_data = self.get_data_by_hash(hash_key)

        if old_data is not None:
            # Data already exists, we need to overwrite it
            self.cursor.execute("REPLACE INTO data_dump (hash_key, data) VALUES (?, ?)", (hash_key, data))
            self.conn.commit()

            # Return the old and new data for comparison
            return {"old_data": old_data, "new_data": data}
        else:
            # Data does not exist, insert new data
            self.cursor.execute("INSERT INTO data_dump (hash_key, data) VALUES (?, ?)", (hash_key, data))
            self.conn.commit()

            # Return the new data for logging purposes
            return {"new_data": data}

    def close(self):
        self.conn.close()
