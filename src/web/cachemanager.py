# cachemanager.py
from backend.localstorage import LocalStorage
from _utils._util import *  # Assuming logging is imported through _utils

class CacheManager:
    def __init__(self):
        UTIL_LOGGER.info("Initializing CacheManager")
        self.storages = {}
        UTIL_LOGGER.info("CacheManager initialized successfully.")

    def _get_storage(self, storage_name):
        if not USE_CACHE:
            return None
        try:
            if storage_name not in self.storages:
                UTIL_LOGGER.debug(f"Initializing new LocalStorage for '{storage_name}'")
                self.storages[storage_name] = LocalStorage(storage_name)
            return self.storages[storage_name]
        except Exception as e:
            UTIL_LOGGER.error(f"Failed to initialize LocalStorage for '{storage_name}': {e}", exc_info=True)
            raise

    def get_cached_data(self, storage_name, key):
        UTIL_LOGGER.debug(f"Attempting to retrieve data from '{storage_name}' with key: {key}")

        try:
            storage = self._get_storage(storage_name)
            if storage is None:
                return None
            data = storage.get_data_by_hash(key)
            if data is None:
                UTIL_LOGGER.debug(f"No data found in '{storage_name}' for key: {key}")
            else:
                UTIL_LOGGER.debug(f"Data retrieved successfully from '{storage_name}' for key: {key}")
            return data
        except AttributeError:
            UTIL_LOGGER.error(f"Storage '{storage_name}' does not exist in CacheManager.", exc_info=True)
            raise
        except Exception as e:
            UTIL_LOGGER.error(f"Error retrieving data from '{storage_name}' for key '{key}': {e}", exc_info=True)
            raise

    def set_cached_data(self, storage_name, key, value):
        UTIL_LOGGER.info(f"Attempting to set data in '{storage_name}' with key: {key}")
        try:
            storage = self._get_storage(storage_name)
            if storage is None:
                return
            storage.save_data(key, value)
            UTIL_LOGGER.info(f"Data set successfully in '{storage_name}' for key: {key}")
        except AttributeError:
            UTIL_LOGGER.error(f"Storage '{storage_name}' does not exist in CacheManager.", exc_info=True)
            raise
        except Exception as e:
            UTIL_LOGGER.error(f"Error setting data in '{storage_name}' for key '{key}': {e}", exc_info=True)
            raise

    def close(self):
        UTIL_LOGGER.info("Closing all LocalStorage instances.")
        for name, storage in self.storages.items():
            try:
                storage.close()
                UTIL_LOGGER.info(f"Closed storage '{name}'.")
            except Exception as e:
                UTIL_LOGGER.error(f"Error closing storage '{name}': {e}", exc_info=True)
        UTIL_LOGGER.info("All LocalStorage instances have been closed.")
