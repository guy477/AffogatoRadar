# webcrawler.py
from _utils._util import *
from .webscraper import WebScraper
from .webnode import WebNode

from collections import deque
from rich.console import Console


class WebCrawler:
    def __init__(self, storage_dir: str = "../data", use_cache=True, scraper=None, max_concurrency=8):
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

        html = None
        final_url = None
        subpage_links = []
        
        err_count = 0
        correct_timeout = self.scraper.webpage_timeout*2//1000 # 2 calls, convert milliseconds to seconds

        # Fetch the page content asynchronously, limiting concurrency with semaphore
        async with self.semaphore:
            try:
                while not html and err_count < 3:
                    err_count += 1
                    final_url, html = await asyncio.wait_for(self.scraper.fetch_and_cache_content(normalized_url), timeout=correct_timeout)
                if err_count == 3:
                    print(f"Failed to fetch page {node.url} after 3 attempts.")
                    return
            except asyncio.TimeoutError:
                print(f"Timeout while fetching {normalized_url}")
                return
            except Exception as e:
                print(f"Failed to fetch page content for {normalized_url}: {e}")
                return

            if not html:
                print(f"Failed to fetch page content for {normalized_url}")
                return

            if not self.scraper.web_fetcher.is_pdf_url(final_url):
                # Find subpage links and create child WebNode objects
                subpage_links = await self.scraper.find_subpage_links(normalized_url, html)

        for link in subpage_links:
            normalized_link = self.normalize_url(link, base_url=normalized_url)
            # verify our depth is still valid (since we do the visit check here):
            # If we do it too early, we never load the page.
            if depth >= d_limit:
                continue

            # If the subpage link has already been visited, skip it
            if await self.is_visited(normalized_link):
                continue

            # Mark the link as visited and enqueue the child node
            await self.mark_as_visited(normalized_link)
            

            child_node = WebNode(url=normalized_link, descriptor=f"{normalized_link}")
            async with self.node_lock:
                node.add_child(child_node)
                queue.append((child_node, depth + 1))

    async def crawl(self, root_node, d_limit):
        """Iteratively crawl subpages starting from the given root node using BFS."""
        queue = deque([(root_node, 0)])  # Each entry is a tuple (node, depth)
        normalized_url = self.normalize_url(root_node.url)

        # Mark the root node as visited
        await self.mark_as_visited(normalized_url)

        tasks = set([])

        # While there are nodes to process in the queue or tasks are still running
        while queue or tasks:
            # Schedule new tasks as long as we have nodes in the queue
            while queue and len(tasks) < self.semaphore._value:
                node, depth = queue.popleft()
                task = asyncio.create_task(self.process_node(node, depth, d_limit, queue))
                tasks.add(task)

            if tasks:
                # Wait for one or more tasks to complete
                done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                
                for task in done:
                    try:
                        task.result()  # Propagate exceptions
                    except Exception as e:
                        print(f"Task failed with exception: {e}")

    async def start_crawling(self, start_url, d_limit=2):
        """Start the crawling process from the root node asynchronously."""
        # Clear the visitation set and create the root node
        self.visited_urls.clear()
        self.root_node = WebNode(url=self.normalize_url(start_url), descriptor=start_url)

        # Begin crawling webpage
        await self.crawl(self.root_node, d_limit)

        # Visualize the website structure after crawling
        tree = self.root_node.visualize()
        self.console.print(tree)

        return self.root_node
    
    async def close(self):
        """Close the WebScraper."""
        if self.scraper:
            await self.scraper.close()
