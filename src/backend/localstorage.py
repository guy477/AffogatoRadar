from _utils._util import *
from _utils._cust_db_manager import CustomDBManager
import pickle

class LocalStorage:
    def __init__(self, db_name: str = "local_storage"):
        self.db_name = db_name
        util_logger.info("Initializing LocalStorage with db_name='%s'", db_name)

        # Initialize cm_db_manager connection
        try:
            self.db_manager = CustomDBManager(
                system='***REMOVED***',  # Replace with your system address
                uid='***REMOVED***',           # Replace with your username
                pwd='***REMOVED***',           # Replace with your password
                library='Affogato',        # Replace with your library/schema
                table_name=db_name,
                logg=util_logger
            )
            util_logger.info("Connected to subnet database '%s' in library '%s'", db_name, 'your_library')
        except Exception as e:
            util_logger.error("Failed to connect to subnet database '%s': %s", db_name, str(e))
            raise


    def get_data_by_hash(self, hash_key):
        """Retrieve data from the cache using the hashed key."""
        util_logger.debug("Retrieving data for hash_key='%s'", hash_key)
        blob_data = self.db_manager.pull_blob_from_db(hash_key)
        if blob_data:
            util_logger.debug("Data found for hash_key='%s'", hash_key)
            try:
                return pickle.loads(blob_data)  # Adjust decoding as necessary
            except UnicodeDecodeError as e:
                util_logger.error("Decoding error for hash_key='%s': %s", hash_key, str(e))
                return None
        else:
            util_logger.info("No data found for hash_key='%s'", hash_key)
            return None

    def save_data(self, hash_key, data):
        """Save new API results to the cache, overwrite if data already exists."""
        util_logger.info("Saving data for hash_key='%s'", hash_key)
        try:
            # Serialize data to bytes using pickle for reversible storage
            blob = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            self.db_manager.push_blob_to_db(self.db_name, blob, hash_key)
            util_logger.info("Saved data for hash_key='%s'", hash_key)
            return {"status": "Inserted or Updated"}
        except Exception as e:
            util_logger.error("Error while saving data for hash_key='%s': %s", hash_key, str(e))
            return {"error": str(e)}

    def close(self):
        """Close the database connection."""
        self.db_manager.close()

