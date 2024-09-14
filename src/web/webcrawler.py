# webcrawler.py
from _utils._util import *
from .webscraper import WebScraper
from .webnode import WebNode

from collections import deque
from rich.console import Console
from urllib.parse import urljoin, urlparse
import asyncio


class WebCrawler:
    def __init__(self, storage_dir: str = "../data", use_cache=True, scraper=None, max_concurrency=8, webpage_timeout=10000):
        self.scraper = WebScraper(storage_dir, use_cache, webpage_timeout=webpage_timeout) if not scraper else scraper
        self.visited_urls = set()
        self.console = Console()
        self.visited_lock = asyncio.Lock()  # Lock to ensure exclusive access to visited_urls
        self.node_lock = asyncio.Lock()     # Lock to ensure exclusive node handling
        self.semaphore = asyncio.Semaphore(max_concurrency)  # Limit concurrent fetches
        self.root_normalized_url = None     # To store the normalized root URL

        util_logger.info(f"WebCrawler initialized with storage_dir='{storage_dir}', use_cache={use_cache}, "
                     f"max_concurrency={max_concurrency}")

    def normalize_url(self, url, base_url=None):
        """Normalize the URL by joining it with the base and stripping any trailing slashes, queries, and fragments."""
        original_url = url
        url_ = url.strip()
        if base_url:
            url_ = urljoin(base_url, url_)
        parsed = urlparse(url_)
        normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        normalized_url = normalized_url.rstrip('/')

        util_logger.debug(f"Normalized URL from '{original_url}' to '{normalized_url}'")
        return normalized_url

    async def mark_as_visited(self, url):
        """Mark a URL as visited with locking to prevent race conditions."""
        async with self.visited_lock:
            self.visited_urls.add(url)
            util_logger.info(f"Marked URL as visited: {url}")

    async def is_visited(self, url):
        """Check if a URL has been visited with locking."""
        async with self.visited_lock:
            visited = url in self.visited_urls
            util_logger.debug(f"Checked if URL is visited: {url} -> {visited}")
            return visited
        

    async def process_node(self, node, depth, d_limit, queue):
        """Process a single node, fetch its content, and enqueue child nodes."""        
        normalized_url = self.normalize_url(node.url)
        util_logger.info(f"Processing node: {normalized_url} at depth {depth}")

        html = None
        final_url = None
        subpage_links = []
        
        err_count = 0
        
        # Calculate correct timeout
        correct_timeout = self.scraper.webpage_timeout * 3 / 1000  # Convert milliseconds to seconds

        # Fetch the page content asynchronously, limiting concurrency with semaphore
        async with self.semaphore:
            try:
                while not html and err_count < 3:
                    err_count += 1
                    util_logger.debug(f"Attempt {err_count} to fetch content for URL: {normalized_url}")
                    try:
                        final_url, html = await asyncio.wait_for(
                            self.scraper.fetch_and_cache_content(normalized_url),
                            timeout=correct_timeout
                        )
                        util_logger.debug(f"Successfully fetched content for URL: {normalized_url}")
                    except asyncio.TimeoutError:
                        util_logger.warning(f"Timeout while fetching URL: {normalized_url} (Attempt {err_count})")
                    except Exception as e:
                        util_logger.error(f"Error fetching URL: {normalized_url} (Attempt {err_count}): {e}")
                
                if err_count == 3 and not html:
                    util_logger.error(f"Failed to fetch page {node.url} after 3 attempts.")
                    return
            except Exception as e:
                util_logger.error(f"Unexpected error while fetching {normalized_url}: {e}")
                return

            if not html:
                util_logger.error(f"No HTML content fetched for URL: {normalized_url}")
                return

            # Normalize final_url after redirection and mark it as visited
            if final_url:
                normalized_final_url = self.normalize_url(final_url)
                await self.mark_as_visited(normalized_final_url)
                # If the final URL is in the root URL, skip
                if normalized_final_url == self.root_normalized_url and depth > 0:
                    util_logger.debug(f"Final URL {normalized_final_url} is the root URL and depth > 0. Skipping.")
                    return

            if not self.scraper.web_fetcher.is_pdf_url(final_url):
                try:
                    subpage_links = await self.scraper.find_subpage_links(normalized_url, html)
                    util_logger.debug(f"Found {len(subpage_links)} subpage links in URL: {normalized_url}")
                except Exception as e:
                    util_logger.error(f"Error finding subpage links in URL: {normalized_url}: {e}")
                    return

        for link in subpage_links:
            normalized_link = self.normalize_url(link, base_url=normalized_url)

            if depth >= d_limit:
                util_logger.debug(f"Depth limit reached for URL: {normalized_link}")
                continue

            if await self.is_visited(normalized_link):
                util_logger.debug(f"URL already visited: {normalized_link}")
                continue

            await self.mark_as_visited(normalized_link)

            if self.root_normalized_url and normalized_link == self.root_normalized_url:
                util_logger.warning(f"Detected potential cycle for link: {link} in URL: {normalized_url}")
                continue

            child_node = WebNode(url=normalized_link, descriptor=f"{normalized_link}")
            async with self.node_lock:
                node.add_child(child_node)
            await queue.put((child_node, depth + 1))
            util_logger.info(f"Enqueued child URL: {normalized_link} at depth {depth + 1}")

    async def crawl(self, root_node, d_limit):
        """Iteratively crawl subpages starting from the given root node using BFS."""
        queue = asyncio.Queue()
        normalized_url = self.normalize_url(root_node.url)

        # Store the root normalized URL for reference
        self.root_normalized_url = normalized_url
        util_logger.info(f"Starting crawl with root URL: {normalized_url} and depth limit: {d_limit}")

        # Mark the root node as visited and enqueue it
        await self.mark_as_visited(normalized_url)
        await queue.put((root_node, 0))

        workers = []
        for _ in range(self.semaphore._value):
            worker = asyncio.create_task(self.worker(queue, d_limit))
            workers.append(worker)
            util_logger.debug(f"Worker {_+1} started.")

        await queue.join()

        for worker in workers:
            worker.cancel()
        
        # Ensure all workers are properly cancelled
        await asyncio.gather(*workers, return_exceptions=True)

        util_logger.info("Crawling completed.")

    async def worker(self, queue, d_limit):
        """Worker task to process nodes from the queue."""
        while True:
            try:
                node, depth = await queue.get()
                await self.process_node(node, depth, d_limit, queue)
                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                util_logger.error(f"Unexpected error in worker: {e}")
                queue.task_done()

    async def start_crawling(self, start_url, d_limit=2):
        """Start the crawling process from the root node asynchronously."""
        util_logger.info(f"Starting crawling process for URL: {start_url} with depth limit: {d_limit}")
        
        # Clear the visitation set and create the root node
        self.visited_urls.clear()
        normalized_start_url = self.normalize_url(start_url)
        self.root_node = WebNode(url=normalized_start_url, descriptor=start_url)

        # Store the root normalized URL
        self.root_normalized_url = normalized_start_url

        # Mark the root node as visited before enqueueing
        await self.mark_as_visited(normalized_start_url)

        # Begin crawling
        await self.crawl(self.root_node, d_limit)

        # Visualize the website structure after crawling
        tree = self.root_node.visualize()
        self.console.print(tree)
        util_logger.info("Crawling process finished and website structure visualized.")

        return self.root_node
    


    async def close(self):
        """Close the WebScraper."""
        if self.scraper:
            await self.scraper.close()
            util_logger.info("WebScraper closed successfully.")
        else:
            util_logger.warning("WebScraper was not initialized; nothing to close.")
