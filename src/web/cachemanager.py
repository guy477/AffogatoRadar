# cachemanager.py
from backend.localstorage import LocalStorage
from _utils._util import *  # Assuming logging is imported through _utils

class CacheManager:
    def __init__(self):
        util_logger.info("Initializing CacheManager")
        self.storages = {}
        util_logger.info("CacheManager initialized successfully.")

    def _get_storage(self, storage_name):
        if not USE_CACHE:
            return None
        try:
            if storage_name not in self.storages:
                util_logger.debug(f"Initializing new LocalStorage for '{storage_name}'")
                self.storages[storage_name] = LocalStorage(storage_name)
            return self.storages[storage_name]
        except Exception as e:
            util_logger.error(f"Failed to initialize LocalStorage for '{storage_name}': {e}", exc_info=True)
            raise

    def get_cached_data(self, storage_name, key):
        util_logger.debug(f"Attempting to retrieve data from '{storage_name}' with key: {key}")

        try:
            storage = self._get_storage(storage_name)
            if storage is None:
                return None
            data = storage.get_data_by_hash(key)
            if data is None:
                util_logger.debug(f"No data found in '{storage_name}' for key: {key}")
            else:
                util_logger.debug(f"Data retrieved successfully from '{storage_name}' for key: {key}")
            return data
        except AttributeError:
            util_logger.error(f"Storage '{storage_name}' does not exist in CacheManager.", exc_info=True)
            raise
        except Exception as e:
            util_logger.error(f"Error retrieving data from '{storage_name}' for key '{key}': {e}", exc_info=True)
            raise

    def set_cached_data(self, storage_name, key, value):
        util_logger.info(f"Attempting to set data in '{storage_name}' with key: {key}")
        try:
            storage = self._get_storage(storage_name)
            if storage is None:
                return
            storage.save_data(key, value)
            util_logger.info(f"Data set successfully in '{storage_name}' for key: {key}")
        except AttributeError:
            util_logger.error(f"Storage '{storage_name}' does not exist in CacheManager.", exc_info=True)
            raise
        except Exception as e:
            util_logger.error(f"Error setting data in '{storage_name}' for key '{key}': {e}", exc_info=True)
            raise

    def close(self):
        util_logger.info("Closing all LocalStorage instances.")
        for name, storage in self.storages.items():
            try:
                storage.close()
                util_logger.info(f"Closed storage '{name}'.")
            except Exception as e:
                util_logger.error(f"Error closing storage '{name}': {e}", exc_info=True)
        util_logger.info("All LocalStorage instances have been closed.")
