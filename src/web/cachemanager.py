# cachemanager.py
from backend.local_storage import LocalStorage
from _utils._util import *  # Assuming logging is imported through _utils

class CacheManager:
    def __init__(self, storage_dir: str = "../data"):
        self.storage_dir = storage_dir
        util_logger.info(f"Initializing CacheManager with storage directory: {self.storage_dir}")
        try:
            self.source_dest = LocalStorage(storage_dir, "source_dest.db")
            self.url_to_page_data = LocalStorage(storage_dir, "url_to_page_data.db")
            self.url_to_itemize = LocalStorage(storage_dir, "url_to_itemize.db")
            self.embedding_relevance = LocalStorage(storage_dir, "embedding_relevance.db")
            self.llm_relevance = LocalStorage(storage_dir, "llm_relevance.db")
            util_logger.info("All LocalStorage instances initialized successfully.")
        except Exception as e:
            util_logger.error(f"Failed to initialize LocalStorage instances: {e}", exc_info=True)
            raise

    def get_cached_data(self, storage_name, key):
        util_logger.debug(f"Attempting to retrieve data from '{storage_name}' with key: {key}")
        try:
            storage = getattr(self, storage_name)
            data = storage.get_data_by_hash(key)
            if data is None:
                util_logger.warning(f"No data found in '{storage_name}' for key: {key}")
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
            storage = getattr(self, storage_name)
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
        storages = [
            ('source_dest', self.source_dest),
            ('url_to_page_data', self.url_to_page_data),
            ('url_to_itemize', self.url_to_itemize),
            ('embedding_relevance', self.embedding_relevance),
            ('llm_relevance', self.llm_relevance)
        ]
        for name, storage in storages:
            try:
                storage.close()
                util_logger.info(f"Closed storage '{name}'.")
            except Exception as e:
                util_logger.error(f"Error closing storage '{name}': {e}", exc_info=True)
        util_logger.info("All LocalStorage instances have been closed.")
