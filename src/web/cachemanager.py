# cachemanager.py
from backend.local_storage import LocalStorage

class CacheManager:
    def __init__(self, storage_dir: str = "../data"):
        self.source_dest = LocalStorage(storage_dir, "source_dest.db")
        self.url_to_html = LocalStorage(storage_dir, "url_to_html.db")
        self.url_to_menu = LocalStorage(storage_dir, "url_to_menu.db")
        self.embedding_relevance = LocalStorage(storage_dir, "embedding_relevance.db")
        self.llm_relevance = LocalStorage(storage_dir, "llm_relevance.db")

    def get_cached_data(self, storage_name, key):
        storage = getattr(self, storage_name)
        return storage.get_data_by_hash(key)

    def set_cached_data(self, storage_name, key, value):
        storage = getattr(self, storage_name)
        storage.save_data(key, value)

    def close(self):
        self.source_dest.close()
        self.url_to_html.close()
        self.url_to_menu.close()
        self.embedding_relevance.close()
        self.llm_relevance.close()