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

        util_logger.info(
            "TraversalManager initialized with use_cache=%s, similarity_threshold=%.2f, max_concurrency=%d",
            self.use_cache,
            self.similarity_threshold,
            max_concurrency
        )

    async def mark_as_visited(self, url):
        async with self.visited_lock:
            self.visited_urls.add(url)
            util_logger.info("URL marked as visited: %s", url)

    async def is_visited(self, url):
        async with self.visited_lock:
            visited = url in self.visited_urls
            util_logger.debug("Checked if URL is visited: %s -> %s", url, visited)
            return visited

    async def process_dfs_node(self, node, parent):
        util_logger.info("Processing DFS node: %s", node.url)
        assert self.use_cache, "Caching must be enabled for DFS processing."

        semaphored = 0
        async with self.node_lock:
            cached_scraped_items = self.cache_manager.get_cached_data('url_to_itemize', node.url)
            if cached_scraped_items:
                util_logger.debug("Cache hit for URL: %s", node.url)
            else:
                util_logger.debug("Cache miss for URL: %s", node.url)

        if cached_scraped_items:
            try:
                node.scraped_items = json.loads(cached_scraped_items)
                util_logger.debug("Loaded scraped items from cache for URL: %s", node.url)
            except json.JSONDecodeError as e:
                util_logger.error("Failed to decode cached data for URL: %s - %s", node.url, str(e))
                node.scraped_items = {}
        else:
            async with self.semaphore:
                try:
                    content_type = 'pdf' if self.scraper.web_fetcher.is_pdf_url(node.url) else 'html'
                    util_logger.info("Fetching content for URL: %s as %s", node.url, content_type)
                    final_url, content = await self.scraper.fetch_and_cache_content(node.url)
                    
                    if not content:
                        util_logger.warning("No content fetched for URL: %s", node.url)
                        return

                    util_logger.info("Content fetched for URL: %s, size: %d bytes", node.url, len(content))
                    
                    filtered_content = self.content_parser.parse_content(content, content_type)
                    util_logger.info("Content parsed for URL: %s", node.url)
                    
                    scraped_items = await self.llm_handler.extract_scraped_items(filtered_content, content_type)
                    node.scraped_items = scraped_items
                    semaphored = 1
                    util_logger.info("Extracted %d scraped items for URL: %s", len(scraped_items), node.url)
                except Exception as e:
                    util_logger.error("Error processing URL: %s - %s", node.url, str(e))
                    return

        tasks = []
        for child in node.children:
            if not await self.is_visited(child.url):
                await self.mark_as_visited(child.url)
                tasks.append(asyncio.create_task(self.process_dfs_node(child, node)))
            else:
                util_logger.debug("Skipping already visited URL: %s", child.url)
        
        if tasks:
            util_logger.info("Launching %d child tasks for URL: %s", len(tasks), node.url)
            await asyncio.gather(*tasks)
        else:
            util_logger.info("No new child URLs to process for URL: %s", node.url)

        async with self.node_lock:
            try:
                for child in node.children:
                    for item, ingredients in child.menu_book.items():
                        node.menu_book[item].update(ingredients)
                util_logger.debug("Aggregated menu books from children for URL: %s", node.url)

                for item, ingredients in node.scraped_items.items():
                    node.menu_book[item].update(ingredients)
                util_logger.debug("Updated menu book with scraped items for URL: %s", node.url)

                if parent:
                    for item, ingredients in node.menu_book.items():
                        parent.menu_book[item].update(ingredients)
                    util_logger.debug("Updated parent menu book with items from URL: %s", node.url)

                if semaphored:
                    self.cache_manager.set_cached_data('url_to_itemize', node.url, json.dumps(node.scraped_items))
                    util_logger.info("Cached scraped items for URL: %s", node.url)
            except Exception as e:
                util_logger.error("Error updating menu books for URL: %s - %s", node.url, str(e))

    async def dfs_recursive(self, root_node):
        util_logger.info("Starting DFS recursive traversal from root URL: %s", root_node.url)
        await self.mark_as_visited(root_node.url)
        try:
            await self.process_dfs_node(root_node, None)
            util_logger.info("Completed DFS recursive traversal from root URL: %s", root_node.url)
        except Exception as e:
            util_logger.error("DFS recursive traversal failed for root URL: %s - %s", root_node.url, str(e))

    async def start_dfs(self, root_node, openai_model='gpt-4o-mini', default_max_tokens=8192):
        util_logger.info("Starting DFS with root URL: %s", root_node.url)
        self.visited_urls.clear()
        util_logger.debug("Cleared visited URLs set")

        # Backup current LLM settings
        model_temp = self.llm_handler.llm.model_chat
        max_tokens_temp = self.llm_handler.llm.max_tokens
        util_logger.debug("Backup LLM settings: model=%s, max_tokens=%d", model_temp, max_tokens_temp)

        # Set new LLM settings
        self.llm_handler.llm.set_default_chat_model(openai_model)
        self.llm_handler.llm.set_default_max_tokens(default_max_tokens)
        util_logger.info("Set LLM to model=%s with max_tokens=%d", openai_model, default_max_tokens)

        try:
            await self.dfs_recursive(root_node)
            util_logger.info("DFS traversal completed for root URL: %s", root_node.url)
        except Exception as e:
            util_logger.error("DFS traversal encountered an error for root URL: %s - %s", root_node.url, str(e))
        finally:
            # Restore original LLM settings
            self.llm_handler.llm.set_default_chat_model(model_temp)
            self.llm_handler.llm.set_default_max_tokens(max_tokens_temp)
            util_logger.info("Restored LLM settings to model=%s with max_tokens=%d", model_temp, max_tokens_temp)

        return root_node
