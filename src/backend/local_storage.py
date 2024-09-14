from _utils._util import *
class LocalStorage:
    def __init__(self, storage_dir: str = "../data", db_name: str = "local_storage.db"):
        self.storage_dir = storage_dir
        self.db_path = os.path.join(storage_dir, db_name)
        util_logger.info("Initializing LocalStorage with storage_dir='%s' and db_name='%s'", storage_dir, db_name)

        try:
            if not os.path.exists(storage_dir):
                os.makedirs(storage_dir)
                util_logger.info("Created storage directory at '%s'", storage_dir)
            else:
                util_logger.info("Storage directory '%s' already exists", storage_dir)
        except Exception as e:
            util_logger.error("Failed to create storage directory '%s': %s", storage_dir, str(e))
            raise

        try:
            self._init_db()
            util_logger.info("Database initialized at '%s'", self.db_path)
        except Exception as e:
            util_logger.error("Failed to initialize database at '%s': %s", self.db_path, str(e))
            raise

    def _init_db(self):
        """Initialize the database if it doesn't exist."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            util_logger.debug("Connected to SQLite database at '%s'", self.db_path)

            # Create table if it doesn't exist
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_dump (
                    hash_key TEXT PRIMARY KEY,
                    data TEXT
                )
            """)
            self.conn.commit()
            util_logger.info("Ensured that table 'data_dump' exists in the database")
        except sqlite3.Error as e:
            util_logger.error("SQLite error during database initialization: %s", str(e))
            raise

    def get_data_by_hash(self, hash_key):
        """Retrieve data from the cache using the hashed key."""
        util_logger.debug("Retrieving data for hash_key='%s'", hash_key)
        try:
            self.cursor.execute("SELECT data FROM data_dump WHERE hash_key = ?", (hash_key,))
            fetched = self.cursor.fetchone()
            if fetched:
                util_logger.debug("Data found for hash_key='%s'", hash_key)
                return fetched[0]  # Return JSON data as string
            else:
                util_logger.warning("No data found for hash_key='%s'", hash_key)
                return None
        except sqlite3.Error as e:
            util_logger.error("SQLite error while retrieving data for hash_key='%s': %s", hash_key, str(e))
            return None

    def save_data(self, hash_key, data):
        """Save new API results to the cache, overwrite if data already exists."""
        util_logger.info("Saving data for hash_key='%s'", hash_key)
        try:
            # First, check if the hash_key already exists
            old_data = self.get_data_by_hash(hash_key)

            if old_data is not None:
                # Data already exists, we need to overwrite it
                self.cursor.execute("REPLACE INTO data_dump (hash_key, data) VALUES (?, ?)", (hash_key, data))
                self.conn.commit()
                util_logger.warning("Overwritten existing data for hash_key='%s'", hash_key)

                # Return the old and new data for comparison (metadata only)
                return {"old_data": "Exists", "new_data": "Updated"}
            else:
                # Data does not exist, insert new data
                self.cursor.execute("INSERT INTO data_dump (hash_key, data) VALUES (?, ?)", (hash_key, data))
                self.conn.commit()
                util_logger.info("Inserted new data for hash_key='%s'", hash_key)

                # Return the new data for logging purposes (metadata only)
                return {"new_data": "Inserted"}
        except sqlite3.Error as e:
            util_logger.error("SQLite error while saving data for hash_key='%s': %s", hash_key, str(e))
            return {"error": str(e)}

    def close(self):
        """Close the database connection."""
        try:
            self.conn.close()
            util_logger.info("Closed database connection to '%s'", self.db_path)
        except sqlite3.Error as e:
            util_logger.error("Error closing database connection: %s", str(e))
