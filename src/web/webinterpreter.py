# WebInterpreter.py
from _utils._util import *


class WebInterpreter:
    def __init__(self, similarity_threshold=0.6, max_concurrency=10, scraper=None, llm_handler=None, cache_manager=None, content_parser=None):
        self.similarity_threshold = similarity_threshold
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.visited_urls = set()
        self.visited_lock = asyncio.Lock()
        self.node_lock = asyncio.Lock()

        self.scraper = scraper
        self.llm_handler = llm_handler
        self.cache_manager = cache_manager
        self.content_parser = content_parser

        UTIL_LOGGER.info(
            "WebInterpreter initialized with similarity_threshold=%.2f, max_concurrency=%d",
            self.similarity_threshold,
            max_concurrency
        )

    async def mark_as_visited(self, url):
        async with self.visited_lock:
            self.visited_urls.add(url)
            UTIL_LOGGER.info("URL marked as visited: %s", url)

    async def is_visited(self, url):
        async with self.visited_lock:
            visited = url in self.visited_urls
            UTIL_LOGGER.debug("Checked if URL is visited: %s -> %s", url, visited)
            return visited

    async def process_dfs_node(self, node, parent):
        UTIL_LOGGER.info("Processing DFS node: %s", node.url)
        
        filtered_content = None

        semaphored = 0
        async with self.node_lock:
            cached_scraped_items = self.cache_manager.get_cached_data('url_to_itemize', node.url)
            if cached_scraped_items:
                UTIL_LOGGER.debug("Cache hit for URL: %s", node.url)
            else:
                UTIL_LOGGER.debug("Cache miss for URL: %s", node.url)

        if cached_scraped_items:
            try:
                node.scraped_items = json.loads(cached_scraped_items)
                UTIL_LOGGER.debug("Loaded scraped items from cache for URL: %s", node.url)
            except json.JSONDecodeError as e:
                UTIL_LOGGER.error("Failed to decode cached data for URL: %s - %s", node.url, str(e))
                node.scraped_items = {}
        else:
            async with self.semaphore:
                try:
                    content_type = 'pdf' if self.scraper.web_fetcher.is_pdf_url(node.url) else 'html'
                    
                    UTIL_LOGGER.info("Fetching content for URL: %s as %s", node.url, content_type)
                    final_url, html_content, pdf_content = await self.scraper.fetch_and_cache_content(node.url)
                    
                    if not html_content and not pdf_content:
                        UTIL_LOGGER.warning("No content fetched for URL: %s", node.url)
                        return

                    if content_type == 'html':
                        # Try loading html content first
                        filtered_content = self.content_parser.parse_content(html_content, 'html')
                        scraped_items = await self.llm_handler.extract_scraped_items(filtered_content, content_type)
                    
                    if content_type == 'pdf' or not scraped_items:
                        # If no scraped items from html, try loading pdf content (or if pdf is the only content type)
                        filtered_content = self.content_parser.parse_content(pdf_content, 'pdf')
                        scraped_items = await self.llm_handler.extract_scraped_items(filtered_content, content_type)
                    
                    node.scraped_items = scraped_items
                    
                    # If the llm call returns None, there was an error: do not cache. Otherwise, cache.
                    semaphored = 1 if scraped_items is not None else 0
                    UTIL_LOGGER.info("Extracted %d scraped items for URL: %s", len(scraped_items), node.url)
                except Exception as e:
                    UTIL_LOGGER.error("Error processing URL: %s - %s", node.url, str(e))
                    return

        tasks = []
        for child in node.children:
            if not await self.is_visited(child.url):
                await self.mark_as_visited(child.url)
                tasks.append(asyncio.create_task(self.process_dfs_node(child, node)))
            else:
                UTIL_LOGGER.debug("Skipping already visited URL: %s", child.url)
        
        if tasks:
            UTIL_LOGGER.info("Launching %d child tasks for URL: %s", len(tasks), node.url)
            await asyncio.gather(*tasks)
        else:
            UTIL_LOGGER.info("No new child URLs to process for URL: %s", node.url)

        async with self.node_lock:
            try:
                for child in node.children:
                    for item, ingredients in child.menu_book.items():
                        node.menu_book[item].update(ingredients)
                UTIL_LOGGER.debug("Aggregated menu books from children for URL: %s", node.url)

                for item, ingredients in node.scraped_items.items():
                    node.menu_book[item].update(ingredients)
                UTIL_LOGGER.debug("Updated menu book with scraped items for URL: %s", node.url)

                if parent:
                    for item, ingredients in node.menu_book.items():
                        parent.menu_book[item].update(ingredients)
                    UTIL_LOGGER.debug("Updated parent menu book with items from URL: %s", node.url)

                if semaphored:
                    self.cache_manager.set_cached_data('url_to_itemize', node.url, json.dumps(node.scraped_items))
                    UTIL_LOGGER.info("Cached scraped items for URL: %s", node.url)
            except Exception as e:
                UTIL_LOGGER.error("Error updating menu books for URL: %s - %s", node.url, str(e))

    async def dfs_recursive(self, root_node):
        UTIL_LOGGER.info("Starting DFS recursive traversal from root URL: %s", root_node.url)
        await self.mark_as_visited(root_node.url)
        try:
            await self.process_dfs_node(root_node, None)
            UTIL_LOGGER.info("Completed DFS recursive traversal from root URL: %s", root_node.url)
        except Exception as e:
            UTIL_LOGGER.error("DFS recursive traversal failed for root URL: %s - %s", root_node.url, str(e))

    async def start_dfs(self, root_node, openai_model='gpt-4o-mini', default_max_tokens=8192):
        UTIL_LOGGER.info("Starting DFS with root URL: %s", root_node.url)
        self.visited_urls.clear()
        UTIL_LOGGER.debug("Cleared visited URLs set")

        # Backup current LLM settings
        model_temp = self.llm_handler.llm.model_chat
        max_tokens_temp = self.llm_handler.llm.max_tokens
        UTIL_LOGGER.debug("Backup LLM settings: model=%s, max_tokens=%d", model_temp, max_tokens_temp)

        # Set new LLM settings
        self.llm_handler.llm.set_default_chat_model(openai_model)
        self.llm_handler.llm.set_default_max_tokens(default_max_tokens)
        UTIL_LOGGER.info("Set LLM to model=%s with max_tokens=%d", openai_model, default_max_tokens)

        try:
            await self.dfs_recursive(root_node)
            UTIL_LOGGER.info("DFS traversal completed for root URL: %s", root_node.url)
        except Exception as e:
            UTIL_LOGGER.error("DFS traversal encountered an error for root URL: %s - %s", root_node.url, str(e))
        finally:
            # Restore original LLM settings
            self.llm_handler.llm.set_default_chat_model(model_temp)
            self.llm_handler.llm.set_default_max_tokens(max_tokens_temp)
            UTIL_LOGGER.info("Restored LLM settings to model=%s with max_tokens=%d", model_temp, max_tokens_temp)

        return root_node
