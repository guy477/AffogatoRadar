# webscraper.py
from urllib.parse import urljoin, urlparse

import asyncio
from playwright.async_api import async_playwright, Browser, Page

from bs4 import BeautifulSoup, Comment, Tag
from ._util import *
from .local_storage import *
from .llm import *
from collections import OrderedDict, deque


class WebScraper:
    def __init__(self, storage_dir: str = "../data", use_cache=True, max_concurrency=10, webpage_timeout = 1000, similarity_threshold = 0.6):
        self.use_cache = use_cache
        self.webpage_timeout = webpage_timeout
        self.similarity_threshold = similarity_threshold

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
        redirect_url = self.source_dest.get_data_by_hash(url)
        if self.use_cache and redirect_url:
            # print(f"Returning cached page for {url}")
            return self.url_to_html.get_data_by_hash(redirect_url)

        # Reuse browser page or open a new one
        page: Page = await self.browser.new_page()

        try:
            
            try:
                # load dynamic content (likely) until timeout
                await page.goto(url, wait_until='networkidle', timeout=self.webpage_timeout)
            except Exception as e:
                # close original page - content cached
                if not page.is_closed():
                    await page.close()

                # make a new page
                page: Page = await self.browser.new_page()
                print(f"Error/Timeout 1: {url}") 

            # re-execute - load from cache (i think...)
            await page.goto(url, wait_until='networkidle', timeout=self.webpage_timeout)

            # Wait for any dynamic content to load...
            await asyncio.sleep(1)
            
            # Ensure the page is fully loaded (pointless i'd argue)
            # await page.wait_for_selector('body')

            # Get the final URL and the HTML content
            final_url = page.url
            html_content = await page.content()

            # Cache the final page content
            self.source_dest.save_data(url, final_url)
            self.url_to_html.save_data(final_url, html_content)
            print(f"HTML cached for {url}")
                
            return html_content

        except Exception as e:
            print(f"Error/Timeout 2 {url} (No Data Fetched)")
            return None

        finally:
            if not page.is_closed():
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
        assert self.use_cache, "Caching must be enabled for DFS processing."

        html = None
        semaphored = 0
        async with self.node_lock:
            # Check if menu items for this URL are already cached
            cached_menu_items = self.url_to_menu.get_data_by_hash(node.url)

        if cached_menu_items:
            # print(f"Using cached menu items for {node.url}")
            node.menu_items = json.loads(cached_menu_items)
        else:
            async with self.semaphore:
                # Fetch the webpage (cached) and extract menu items if not cached
                html = await self.fetch_webpage_with_js(node.url)

                filtered_html = self.filter_html_for_menu(html)
                
                # Extract the menu items using LLM
                menu_items = await self.llm.extract_menu_items(filtered_html)
                node.menu_items = menu_items
                semaphored = 1


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

            if semaphored:
                # Save the extracted menu items in the cache using the node lock
                self.url_to_menu.save_data(node.url, json.dumps(menu_items))
                print(f"Menu items for {node.url} cached.")

    async def dfs_recursive(self, root_node):
        """
        Perform recursive DFS traversal asynchronously.
        """
        # Mark the root node as visited and start processing recursively
        await self.mark_as_visited(root_node.url)
        await self.process_dfs_node(root_node, None)

    async def start_dfs(self, root_node, openai_model = 'gpt-4o-mini', default_max_tokens = 8192):
        """
        Kicks off the DFS recursive traversal.
        Assumes tree is a zero-cycle, directed graph.
        """
        # reset the visitation set.
        self.visited_urls.clear()

        # set llm model to provided model
        model_temp = self.llm.model
        max_tokens_temp = self.llm.max_tokens
        self.llm.set_default_model(openai_model)
        self.llm.set_default_max_tokens(default_max_tokens)

        # start the dfs from the root_node
        await self.dfs_recursive(root_node)

        # reset llm model to default
        self.llm.set_default_model(model_temp)
        self.llm.set_default_max_tokens(max_tokens_temp)
        return root_node


    def filter_html_for_menu(self, html):
        """Aggressively remove HTML elements that are unlikely to contain menu items but preserve potential menu-related tags and structure."""
        soup = BeautifulSoup(html, 'html.parser')

        # Find the body tag
        # if no body tag, return the entire HTML
        body = soup.body or soup

        if body:
            # Define tags that you want to remove (e.g., script, style)
            remove_tags = ['script', 'style']
            
            # Remove unwanted tags from the body
            for tag in body(remove_tags):
                tag.decompose()

            # Remove all comments from the body
            for comment in body.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()  # Remove comment

            # Iterate over all elements in the body and remove attributes while preserving tags and text
            for element in body.find_all(True):  # True finds all tags
                element.attrs = {}  # Remove all attributes but keep the tags and their text content

            # Return the modified HTML structure of the body as a string
            return str(body)
        else:
            return "No <body> tag found in the HTML"


    def satisfies_special_words(self, full_url):
        """
        Checks if the URL path contains any of the special words.
        """
        # Parse out the path from the full URL
        path = urlparse(full_url).path
        special_words = ['menu', 'food', 'drink', 'lunch', 'dinner', 'breakfast', 'ingredient', 'dish', 'restaurant', 
                         'cuisine', 'recipe', 'meal', 'special', 'offer', 'chef', 'kitchen', 'reservation', 'order',
                         'table', 'dining', 'bar', 'cocktail', 'appetizer', 'entree', 'dessert', 'wine', 'beer', 'beverage',
                         'alcohol', 'non-alcoholic', 'drink', 'snack', 'side', 'starter', 'main', 'course', 'buffet', 'brunch']
        
        # Check if any of the special words exist in the path
        for special_word in special_words:
            if special_word in path:
                return True
        return False

    async def satisfies_llm_criteria(self, full_url):
        """
        Sends the full URL to the LLM for analysis and determines if it satisfies the criteria.
        """
        # Parse the path from the full URL
        path = urlparse(full_url).path

        prompt_gpt35 = {"role": "user", "content": f"""
You are tasked with identifying relevant URLs from a restaurant website that suggest food-related content. Focus on links that point to pages related to 'menus', 'food items', 'meals', or similar content. Look for URL patterns that contain:
- The word 'menu'
- Keywords like 'breakfast', 'lunch', 'dinner', 'desert', 'food', or 'drink'

Given this URL Path: {path}

Respond with "YES" if the URL is relevant, or "NO" if it is not.
"""}
        
        async with self.node_lock:
            if self.use_cache and self.llm_relevance.get_data_by_hash(full_url):
                cached_data = json.loads(self.llm_relevance.get_data_by_hash(full_url))['yes_no']
                return cached_data[0] > cached_data[1]

        responses = await self.llm.chat([prompt_gpt35], n=5)

        N_YES = 0
        N_NO = 0

        for response in responses:
            if 'YES' in response:
                N_YES += 1
            if 'NO' in response:
                N_NO += 1
    
        async with self.node_lock:
            self.llm_relevance.save_data(full_url, json.dumps({'yes_no': (N_YES, N_NO)}))
            print(f"Caching LLM Relevance For {full_url}")
    
        return N_YES > N_NO


    async def satisfies_embedding_criteria(self, full_urls):
        """
        Filters URLs based on their relevance to target keywords and excludes the base path.
        
        Args:
            full_urls (list): A list of full URLs.
            
        Returns:
            list: URLs that match the target keywords, with the base path excluded.
        """
        target_keywords = ['menu', 'menus', '...menu...', '...menus...', 'food', '...food...', 'drink', '...drink...', 'lunch', '...lunch...', 'dinner', '...dinner...', 'desert', '...desert...', 'breakfast', '...breakfast...', 'nutrition', '...nutrition', 'ingredients', '...ingredients...']

        if self.use_cache:
            async with self.node_lock:
                hashed_data = [(url, self.embedding_relevance.get_data_by_hash(url)) for url in full_urls]
                hashed_data = [data for data in hashed_data if data[1] is not None]
                full_urls = [url for url in full_urls if self.embedding_relevance.get_data_by_hash(url) is None]
        else:
            full_urls = [url for url in full_urls]
            hashed_data = []
        
        relevant_urls = await self.llm.find_url_relevance(full_urls, target_keywords)
        
        for relevant_url in relevant_urls:
            async with self.node_lock:
                if not self.embedding_relevance.get_data_by_hash(relevant_url[0]):
                    print(f'Caching Embedding Relevance For {relevant_url[0]}')
                    self.embedding_relevance.save_data(relevant_url[0], relevant_url[1])
        
        for data in hashed_data:
            relevant_urls.append(data)
        # Return only relevant URLs (similarity > {similarity_threshold})
        return [relevant_url[0] for relevant_url in relevant_urls if relevant_url[1] and float(relevant_url[1]) > self.similarity_threshold]
    

    async def satisfies_special_characteristics(self, full_urls):
        if not full_urls:
            return []

        # Process URLs based on full URLs - only embedding
        full_urls = await self.satisfies_embedding_criteria(full_urls)

        # full_urls = [url for url in full_urls if self.satisfies_special_words(url) or await self.satisfies_llm_criteria(url)]

        return full_urls

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