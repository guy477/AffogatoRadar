# webcrawler.py

import asyncio
from collections import deque
from .webscraper import WebScraper
from .webnode import WebNode
from rich.console import Console
from urllib.parse import urlparse, urljoin

class WebCrawler:
    def __init__(self, storage_dir: str = "../data", use_cache=True, scraper=None, max_concurrency=10):
        self.scraper = WebScraper(storage_dir, use_cache) if not scraper else scraper
        self.visited_urls = set()
        self.console = Console()
        self.visited_lock = asyncio.Lock()  # Lock to ensure exclusive access to visited_urls
        self.node_lock = asyncio.Lock()  # Lock to ensure exclusive node handling
        self.semaphore = asyncio.Semaphore(max_concurrency)  # Limit concurrent fetches

    def normalize_url(self, url, base_url=None):
        """Normalize the URL by joining it with the base and stripping any trailing slashes."""
        url_ = url.strip()
        if base_url:
            url_ = urljoin(base_url, url_)
        parsed = urlparse(url_)
        normalized_url = parsed.scheme + "://" + parsed.netloc + parsed.path
        return normalized_url.rstrip('/')

    async def mark_as_visited(self, url):
        """Mark a URL as visited with locking to prevent race conditions."""
        async with self.visited_lock:
            self.visited_urls.add(url)

    async def is_visited(self, url):
        """Check if a URL has been visited with locking."""
        async with self.visited_lock:
            return url in self.visited_urls

    async def process_node(self, node, depth, d_limit, queue):
        """Process a single node, fetch its content, and enqueue child nodes."""
        normalized_url = self.normalize_url(node.url)

        # Max depth check
        if depth >= d_limit:
            print(f"Max depth reached for {normalized_url}")
            return

        # Fetch the page content asynchronously, limiting concurrency with semaphore
        async with self.semaphore:
            html_content = await self.scraper.fetch_webpage_with_js(normalized_url)

        if not html_content:
            print(f"Failed to fetch page content for {normalized_url}")
            return

        # Find subpage links and create child WebNode objects
        subpage_links = self.scraper.find_subpage_links(normalized_url, html_content)

        for link in subpage_links:
            normalized_link = self.normalize_url(link, base_url=normalized_url)

            # If the subpage link has already been visited, skip it
            if await self.is_visited(normalized_link):
                print(f"Skipping already visited child: {normalized_link}")
                continue

            # Mark the link as visited and enqueue the child node
            await self.mark_as_visited(normalized_link)

            child_node = WebNode(url=normalized_link, descriptor=f"{normalized_link}")
            async with self.node_lock:
                node.add_child(child_node)

            # Enqueue the child node for further crawling
            queue.append((child_node, depth + 1))

    async def crawl(self, root_node, d_limit):
        """Iteratively crawl subpages starting from the given root node using BFS."""
        queue = deque([(root_node, 0)])  # Each entry is a tuple (node, depth)
        normalized_url = self.normalize_url(root_node.url)

        # Mark the root node as visited
        await self.mark_as_visited(normalized_url)

        # While there are nodes to process in the queue
        while queue:
            node, depth = queue.popleft()

            # Process the node (this is done concurrently)
            await self.process_node(node, depth, d_limit, queue)

    async def start_crawling(self, start_url, d_limit=2):
        """Start the crawling process from the root node asynchronously."""
        self.root_node = WebNode(url=self.normalize_url(start_url), descriptor=start_url)
        await self.crawl(self.root_node, d_limit)

        # Visualize the website structure after crawling
        tree = self.root_node.visualize()
        self.console.print(tree)
        return self.root_node

    async def close(self):
        """Close the WebScraper."""
        if self.scraper:
            await self.scraper.close()
