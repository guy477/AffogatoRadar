from ._util import *

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

        # Create tables if they don't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS place_id_map (
                hash_key TEXT PRIMARY KEY,
                idx INTEGER
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_dump (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT UNIQUE  -- Ensure unique data entries
            )
        """)
        self.conn.commit()

    def get_last_index(self):
        """Get the last index in data_dump table."""
        self.cursor.execute("SELECT MAX(id) FROM data_dump")
        result = self.cursor.fetchone()
        return result[0] if result[0] is not None else 0

    def get_data_by_hash(self, hash_key):
        """Retrieve data from the cache using the hashed key."""
        self.cursor.execute("SELECT idx FROM place_id_map WHERE hash_key = ?", (hash_key,))
        result = self.cursor.fetchone()
        if result:
            idx = result[0]
            self.cursor.execute("SELECT data FROM data_dump WHERE id = ?", (idx,))
            fetched = self.cursor.fetchone()
            return fetched[0] if fetched else None  # Return JSON data as string
        return None

    def save_data(self, hash_key, data):
        """Save new API results to the cache."""
        # First, check if the data already exists in the data_dump table
        self.cursor.execute("SELECT id FROM data_dump WHERE data = ?", (data,))
        result = self.cursor.fetchone()
        
        if result:
            # Data already exists, reuse the existing id
            idx = result[0]
        else:
            # Data does not exist, insert new data and get the id
            self.cursor.execute("INSERT INTO data_dump (data) VALUES (?)", (data,))
            self.conn.commit()
            idx = self.cursor.lastrowid

        # Insert or replace hash -> index mapping
        self.cursor.execute("""
            INSERT OR REPLACE INTO place_id_map (hash_key, idx) VALUES (?, ?)
        """, (hash_key, idx))
        self.conn.commit()

    def close(self):
        self.conn.close()
