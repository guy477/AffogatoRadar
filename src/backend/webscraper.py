# webscraper.py
from urllib.parse import urljoin, urlparse

import asyncio
from playwright.async_api import async_playwright, Browser, Page

from bs4 import BeautifulSoup, Comment
from ._util import *
from .local_storage import *
from .llm import *
from collections import OrderedDict, deque


class WebScraper:
    def __init__(self, storage_dir: str = "../data", use_cache=True, max_concurrency=10, webpage_timeout = 1000):
        self.use_cache = use_cache
        self.webpage_timeout = webpage_timeout
        self.llm = LLM()
        self.source_dest = LocalStorage(storage_dir, "source_dest.db")
        self.url_to_html = LocalStorage(storage_dir, "url_to_html.db")
        self.url_to_menu = LocalStorage(storage_dir, "url_to_menu.db")
        self.embedding_relevance = LocalStorage(storage_dir, "embedding_relevance.db")
        self.llm_relevance = LocalStorage(storage_dir, "llm_relevance.db")
        self.visited_urls = set()

        # Add a semaphore to control max concurrent tasks
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.visited_lock = asyncio.Lock()  # Lock to ensure exclusive access to visited_urls
        self.node_lock = asyncio.Lock()

        # Initialize Playwright
        self.playwright = None
        self.browser = None

    async def start_playwright(self):
        """Initialize Playwright and the browser instance."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.firefox.launch(headless=False)
    
    async def stop_playwright(self):
        """Stop the Playwright instance and close the browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def fetch_webpage_with_js(self, url):
        """Fetch the webpage with JavaScript execution using a persistent Playwright instance."""
        # Start Playwright if it's not already running
        await self.start_playwright()

        # Check the cache first
        cached_page = self.source_dest.get_data_by_hash(url)
        if self.use_cache and cached_page:
            # print(f"Returning cached page for {url}")
            return self.url_to_html.get_data_by_hash(cached_page)

        # Reuse browser page or open a new one
        page: Page = await self.browser.new_page()

        try:
            # load dynamic content
            try:
                await page.goto(url, wait_until='networkidle', timeout=self.webpage_timeout)
            except Exception as e:
                # close original page 
                await page.close()

                # and try again
                page: Page = await self.browser.new_page()
                print(f"Error/Timeout 1: {url}") 

            # re-execute
            await page.goto(url, wait_until='networkidle', timeout=self.webpage_timeout)

            # Wait for any dynamic content to load
            await asyncio.sleep(1)  
            # Ensure the page is fully loaded (pointless i'd argue)
            await page.wait_for_selector('body')

            final_url = page.url
            html_content = await page.content()

            # Cache the final page content
        
            self.source_dest.save_data(url, final_url)
            self.url_to_html.save_data(final_url, html_content)
            print(f"HTML cached for {url}")
                
            return html_content

        except Exception as e:
            print(f"Error/Timeout 2 {url} (No Data Fetched):\n{e}")
            return None

        finally:
            await page.close()

    def find_menu_link_html(self, html_content):
        """Extract the menu link from the HTML content."""
        soup = BeautifulSoup(html_content, 'html.parser')
        menu_element = soup.find('a', {'data-item-id': 'menu', 'data-tooltip': 'Open menu link'})
        if menu_element and menu_element.get('href'):
            return menu_element['href']
        return None

    async def source_menu_link(self, google_maps_url):
        """Scrape the Google Maps URL, execute JavaScript, and find the menu link."""
        html_content = await self.fetch_webpage_with_js(google_maps_url)
        menu_link = self.find_menu_link_html(html_content)
        if menu_link:
            print(f"Menu link found: {menu_link}")
            return menu_link
        else:
            print("Menu link not found.")
            return None


    async def find_subpage_links(self, url, html_content):
        """Extract subpage links (e.g., categories, further menus) from a menu page."""
        soup = BeautifulSoup(html_content, 'html.parser')
        parsed_base_url = urlparse(url)
        base_domain = parsed_base_url.netloc

        subpage_links = []

        # source all links from current webpage that are from the same domain
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(url, href)  # Handle relative URLs
            parsed_url = urlparse(full_url)
            # Check if the link is from the same domain and is not just an anchor
            if parsed_url.netloc == base_domain and parsed_url.path:
                # Check if the new path is a subpage of the base path
                subpage_links.append(full_url)
            else:
                # print(f"Skipping external link: {full_url}")
                pass


        subpage_links = list(OrderedDict.fromkeys(subpage_links))

        subpage_links = await self.satisfies_special_characteristics(subpage_links)

        return subpage_links
        

    async def mark_as_visited(self, url):
        """Mark a URL as visited with locking to prevent race conditions."""
        async with self.visited_lock:
            self.visited_urls.add(url)

    async def is_visited(self, url):
        """Check if a URL has been visited with locking."""
        async with self.visited_lock:
            return url in self.visited_urls
        

    async def process_dfs_node(self, node, parent):
        """
        Recursive DFS helper function to process nodes and propagate menu items upwards.
        """
        html = None
        err_count = 0
        async with self.node_lock:
            # Check if menu items for this URL are already cached
            cached_menu_items = self.url_to_menu.get_data_by_hash(node.url)

        if self.use_cache and cached_menu_items is not None:
            # print(f"Using cached menu items for {node.url}")
            node.menu_items = json.loads(cached_menu_items)
        else:
            async with self.semaphore:
                # Fetch the webpage and extract menu items if not cached
                while not html and err_count < 3:
                    err_count += 1
                    html = await self.fetch_webpage_with_js(node.url)
                if err_count == 3:
                    print(f"Failed to fetch page {node.url} after 3 attempts.")
                    return
                filtered_html = self.filter_html_for_menu(html)
                
                # Extract the menu items using LLM
                menu_items = await self.llm.extract_menu_items(filtered_html)
                node.menu_items = menu_items

                async with self.node_lock:
                    # Save the extracted menu items in the cache using the node lock
                    self.url_to_menu.save_data(node.url, json.dumps(menu_items))
                    print(f"Menu items for {node.url} cached.")
    
        # Recursively process all child nodes first
        # Create a list of tasks by filtering unvisited children
        tasks = []
        for child in node.children:
            if not await self.is_visited(child.url):  # This needs to be awaited outside the comprehension
                await self.mark_as_visited(child.url)  # Mark the node as visited
                tasks.append(asyncio.create_task(self.process_dfs_node(child, node)))  # Add the task to the list

        # Now gather the tasks and await their completion
        await asyncio.gather(*tasks)

        # After processing all children, propagate the menu items to the parent
        async with self.node_lock:
            for item, ingredients in node.menu_items.items():
                node.menu_book[item].union(ingredients)

            if parent:
                for item, ingredients in node.menu_book.items():
                    # print(f"Propagated {item}: {ingredients} to parent {parent.url}")
                    parent.menu_book[item].union(ingredients)
                    

    async def dfs_recursive(self, root_node):
        """
        Perform recursive DFS traversal asynchronously.
        """
        # Mark the root node as visited and start processing recursively
        await self.mark_as_visited(root_node.url)
        await self.process_dfs_node(root_node, None)

    async def start_dfs(self, root_node, openai_model = 'gpt-4o-mini', default_max_tokens = 2048):
        """
        Kicks off the DFS recursive traversal.
        Assumes tree is a zero-cycle, directed graph.
        """

        # set llm model to provided model
        model_temp = self.llm.model
        max_tokens_temp = self.llm.max_tokens
        self.llm.set_default_model(openai_model)
        self.llm.set_default_max_tokens(default_max_tokens)

        await self.dfs_recursive(root_node)

        # reset llm model to default
        self.llm.set_default_model(model_temp)
        self.llm.set_default_max_tokens(max_tokens_temp)
        return root_node


    def filter_html_for_menu(self, html):
        """Aggressively remove HTML elements that are unlikely to contain menu items but preserve potential menu-related tags."""
        soup = BeautifulSoup(html, 'html.parser')

        plain_text = soup.body.get_text(separator='\n', strip=True)

        return plain_text




    def satisfies_special_words(self, path):
        special_words = ['menu', 'food', 'drink', 'lunch', 'dinner', 'breakfast', 'ingredient', 'dish', 'restaurant', 
                         'cuisine', 'recipe', 'meal', 'special', 'offer', 'chef', 'kitchen', 'reservation', 'order',
                            'table', 'dining', 'bar', 'cocktail', 'appetizer', 'entree', 'dessert', 'wine', 'beer', 'beverage',
                            'alcohol', 'non-alcoholic', 'drink', 'snack', 'side', 'starter', 'main', 'course', 'buffet', 'brunch']


        for special_word in special_words:
            if special_word in path:
                return True
    

    async def satisfies_llm_criteria(self, path):
        prompt_gpt4 = f"""
You are an advanced web scraper assistant. You need to navigate restaurant websites and look for URLs that suggest food-related content such as menus. Your job is to help identify relevant URLs by analyzing their content and returning only those that suggest the page contains a menu or food items.

Example URL patterns to look for: 
- Contains the word 'menu'
- Contains the word 'food' or 'drink'
- Refers to specific meals like 'lunch', 'dinner', 'desert', or 'breakfast'
- Any page that might list ingredients or dishes

Analyze this URL: 
```
{path}
```

Respond with "YES" if the URL is relevant, or "NO" if it is not. 
"""
        prompt_gpt35 = {"role": "user", "content": f"""
You are tasked with identifying relevant URLs from a restaurant website that suggest food-related content. Focus on links that point to pages related to 'menus', 'food items', 'meals', or similar content. Look for URL patterns that contain:
- The word 'menu'
- Keywords like 'breakfast', 'lunch', 'dinner', 'desert', 'food', or 'drink'

Given this URL: {path}

Respond with "YES" if the URL is relevant, or "NO" if it is not.
"""}
        
        async with self.node_lock:
            if self.use_cache and self.llm_relevance.get_data_by_hash(path):
                # print(f"Retrieving cached data for {path}")
                cached_data = json.loads(self.llm_relevance.get_data_by_hash(path))['yes_no']
                return cached_data[0] > cached_data[1]

        responses = await self.llm.chat([prompt_gpt35], n = 5)

        N_YES = 0
        N_NO = 0

        for response in responses:
            if 'YES' in response:
                N_YES += 1
            if 'NO' in response:
                N_NO += 1
    
        async with self.node_lock:
            self.llm_relevance.save_data(path, json.dumps({'yes_no': (N_YES, N_NO)}))
            print(f"Caching LLM Relevance For {path}")
    
        return N_YES > N_NO

    async def satisfies_embedding_criteria(self, urls):
        """
        Filters URLs based on their relevance to target keywords and excludes the base path.
        
        Args:
            paths (list): A list of full URLs.
            
        Returns:
            list: URLs that match the target keywords, with the base path excluded.
        """
        target_keywords = ['menu', 'food', 'drink', 'lunch', 'dinner', 'desert', 'breakfast']

        len_before = len(urls)

        if self.use_cache:
            async with self.node_lock:
                hashed_data = [(url, self.embedding_relevance.get_data_by_hash(url)) for url in urls]
                hashed_data = [data for data in hashed_data if data[1] is not None]
                urls = [url for url in urls if self.embedding_relevance.get_data_by_hash(url) is None]
        else:
            urls = [url for url in urls]
            hashed_data = []
        
        
        # print(f'Number of Hashed URLs: {len_before - len(urls)}... Percentage loads saved: {100*(len_before - len(urls))/len_before}%')
        
        # Find relevant URLs based on embedding criteria
        relevant_urls = await self.llm.find_url_relevance(urls, target_keywords)
        
        for relevant_url in relevant_urls:
            async with self.node_lock:
                if not self.embedding_relevance.get_data_by_hash(relevant_url[0]):
                    print(f'Caching Embedding Relevance For {relevant_url[0]}')
                    self.embedding_relevance.save_data(relevant_url[0], relevant_url[1])
        
        for data in hashed_data:
            relevant_urls.append(data)
        # Return only relevant URLs with the base path excluded
        return [relevant_url[0] for relevant_url in relevant_urls if relevant_url[1] and float(relevant_url[1])]
    

    async def satisfies_special_characteristics(self, paths):
        if not paths:
            return []
        base_path = 'https://' + urlparse(paths[0]).netloc + '/'

        urls = [urlparse(url).path for url in paths]
        
        urls = await self.satisfies_embedding_criteria(urls)

    
        urls = [path for path in urls if self.satisfies_special_words(path) or await self.satisfies_llm_criteria(path)]
        
        paths = [urljoin(base_path, path) for path in urls]

        return paths

    async def find_menu_items(self, menu_url):
        """Scrape the menu URL and extract the menu items."""
        html_content = await self.fetch_webpage_with_js(menu_url)
        # Implement menu item extraction here
        return html_content

    async def close(self):
        """Close the Playwright instance and the database connections."""
        await self.stop_playwright()  # Ensure Playwright is properly closed
        self.source_dest.close()
        self.url_to_html.close()
        self.url_to_menu.close()