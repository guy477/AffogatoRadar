# traversalmanager.py
from _utils._util import *

# from .contentparser import ContentParser
# from .llmhandler import LLMHandler

        
class TraversalManager:
    def __init__(self, use_cache=True, similarity_threshold=0.6, max_concurrency=10, scraper=None, llm_handler=None, cache_manager=None, content_parser=None):
        self.use_cache = use_cache
        self.similarity_threshold = similarity_threshold
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.visited_urls = set()
        self.visited_lock = asyncio.Lock()
        self.node_lock = asyncio.Lock()

        self.scraper = scraper
        self.llm_handler = llm_handler
        self.cache_manager = cache_manager
        self.content_parser = content_parser

    async def mark_as_visited(self, url):
        async with self.visited_lock:
            self.visited_urls.add(url)

    async def is_visited(self, url):
        async with self.visited_lock:
            return url in self.visited_urls

    async def process_dfs_node(self, node, parent):
        assert self.use_cache, "Caching must be enabled for DFS processing."

        semaphored = 0
        async with self.node_lock:
            cached_menu_items = self.cache_manager.get_cached_data('url_to_menu', node.url)

        if cached_menu_items:
            node.menu_items = json.loads(cached_menu_items)
        else:
            async with self.semaphore:
                content_type = 'pdf' if self.scraper.web_fetcher.is_pdf_url(node.url) else 'html'
                final_url, content = await self.scraper.fetch_and_cache_content(node.url)

                if not content:
                    return

                filtered_content = self.content_parser.parse_content(content, content_type)
                menu_items = await self.llm_handler.extract_menu_items(filtered_content, content_type)
                node.menu_items = menu_items
                semaphored = 1

        tasks = []
        for child in node.children:
            if not await self.is_visited(child.url):
                await self.mark_as_visited(child.url)
                tasks.append(asyncio.create_task(self.process_dfs_node(child, node)))
        await asyncio.gather(*tasks)

        async with self.node_lock:
            for child in node.children:
                for item, ingredients in child.menu_book.items():
                    node.menu_book[item].update(ingredients)

            for item, ingredients in node.menu_items.items():
                node.menu_book[item].update(ingredients)

            if parent:
                for item, ingredients in node.menu_book.items():
                    parent.menu_book[item].update(ingredients)

            if semaphored:
                self.cache_manager.set_cached_data('url_to_menu', node.url, json.dumps(menu_items))
                print(f"Menu items for {node.url} cached.")

    async def dfs_recursive(self, root_node):
        await self.mark_as_visited(root_node.url)
        await self.process_dfs_node(root_node, None)

    async def start_dfs(self, root_node, openai_model='gpt-4o-mini', default_max_tokens=8192):
        self.visited_urls.clear()
        model_temp = self.llm_handler.llm.model_chat
        max_tokens_temp = self.llm_handler.llm.max_tokens
        self.llm_handler.llm.set_default_chat_model(openai_model)
        self.llm_handler.llm.set_default_max_tokens(default_max_tokens)

        await self.dfs_recursive(root_node)

        self.llm_handler.llm.set_default_chat_model(model_temp)
        self.llm_handler.llm.set_default_max_tokens(max_tokens_temp)
        return root_node