# webscraper.py
from urllib.parse import urljoin, urlparse

import asyncio
from playwright.async_api import async_playwright, Browser, Page

from bs4 import BeautifulSoup, Comment
from ._util import *
from .local_storage import *
from .llm import *
from collections import OrderedDict


class WebScraper:
    def __init__(self, storage_dir: str = "../data", use_cache=True):
        self.use_cache = use_cache
        self.llm = LLM()

        self.source_dest = LocalStorage(storage_dir, "source_dest.db")
        self.url_to_html = LocalStorage(storage_dir, "url_to_html.db")
        self.url_to_menu = LocalStorage(storage_dir, "url_to_menu.db")
        self.embedding_relevance = LocalStorage(storage_dir, "embedding_relevance.db")
        self.llm_relevance = LocalStorage(storage_dir, "llm_relevance.db")

        # Initialize the Playwright instance and browser to be reused
        self.playwright = None
        self.browser = None

    async def start_playwright(self):
        """Initialize Playwright and the browser instance."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.webkit.launch(headless=True)
    
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
            print(f"Returning cached page for {url}")
            return self.url_to_html.get_data_by_hash(cached_page)

        # Reuse browser page or open a new one
        page: Page = await self.browser.new_page()

        try:
            await page.goto(url)
            await page.wait_for_selector('body')
            final_url = page.url
            html_content = await page.content()

            # Cache the final page content
            if self.use_cache:
                self.source_dest.save_data(url, final_url)
                self.url_to_html.save_data(final_url, html_content)
                print(f"Landing page cached for {url}")
                
            return html_content

        except Exception as e:
            print(f"Error fetching page {url}: {e}")
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


    def find_subpage_links(self, url, html_content):
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
                print(f"Skipping external link: {full_url}")


        subpage_links = list(OrderedDict.fromkeys(subpage_links))

        subpage_links = self.satisfies_special_characteristics(subpage_links)

        return subpage_links
        
        

    async def dfs_recursive(self, node, parent=None):
        """Perform DFS traversal recursively starting from the root node and accumulate menu items upwards."""
        llm_ = LLM('gpt-4o-mini', max_tokens=512)

        print(f"Visiting: {node.url}")

        # Check if menu items for this URL are already cached
        cached_menu_items = self.url_to_menu.get_data_by_hash(node.url)
        if self.use_cache and cached_menu_items:
            print(f"Using cached menu items for {node.url}")
            node.menu_items = json.loads(cached_menu_items)
        else:
            # Fetch the webpage and extract menu items if not cached
            html = await self.fetch_webpage_with_js(node.url)
            filtered_html = self.filter_html_for_menu(html)
            
            # Extract the menu items using LLM
            menu_items = llm_.extract_menu_items(filtered_html)
            node.menu_items = menu_items

            # Save the extracted menu items in the cache
            if self.use_cache: 
                self.url_to_menu.save_data(node.url, json.dumps(menu_items))
                print(f"Menu items for {node.url} cached.")
            else:
                print("No body element found in the HTML.")
                node.menu_items = {}  # No menu found

        # Update node's menu_book with current menu_items
        for item, ingredients in node.menu_items.items():
            node.menu_book[item].extend(ingredients)

        # Set the node's description to the string of the current node's menu_items keys
        node.description = ', '.join(node.menu_items.keys())

        # Recursively process children nodes
        for child in node.children:
            await self.dfs_recursive(child, node)

        # Propagate the menu items upwards to the parent after processing all children
        if parent:
            for item, ingredients in node.menu_book.items():
                parent.menu_book[item].extend(ingredients)
                print(f"Propagated {item}: {ingredients} to parent {parent.url}")

        return node



    def filter_html_for_menu(self, html):
        """Aggressively remove HTML elements that are unlikely to contain menu items."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Define substrings that should be excluded (in tag names)
        exclude_substrings = ['script', 'style', 'footer', 'header', 'nav', 'aside', 'noscript', 'form', 'audio', 'video', 'img', 'image', 'path', 'iframe']
        
        # Remove tags that contain any of the excluded substrings in their name
        for tag in soup.find_all(True):  # True finds all tags
            if any(substring in tag.name for substring in exclude_substrings):
                tag.extract()  # Remove the tag entirely
        
        # Optionally, remove comments
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.extract()

        return str(soup.body) if soup.body else str(soup)


    def satisfies_special_words(self, path):
        special_words = ['menu', 'food', 'drink', 'lunch', 'dinner', 'breakfast', 'ingredient', 'dish', 'restaurant', 
                         'cuisine', 'recipe', 'meal', 'special', 'offer', 'chef', 'kitchen', 'reservation', 'order',
                            'table', 'dining', 'bar', 'cocktail', 'appetizer', 'entree', 'dessert', 'wine', 'beer', 'beverage',
                            'alcohol', 'non-alcoholic', 'drink', 'snack', 'side', 'starter', 'main', 'course', 'buffet', 'brunch']


        for special_word in special_words:
            if special_word in path:
                return True
    

    def satisfies_llm_criteria(self, path):
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
        
        
        if self.use_cache and self.llm_relevance.get_data_by_hash(path):
            print(f"Retrieving cached data for {path}")
            cached_data = json.loads(self.llm_relevance.get_data_by_hash(path))['yes_no']
            return cached_data[0] > cached_data[1]

        responses = self.llm.chat([prompt_gpt35], n = 5)

        N_YES = 0
        N_NO = 0

        for response in responses:
            if 'YES' in response:
                N_YES += 1
            if 'NO' in response:
                N_NO += 1
        if self.use_cache:
            self.llm_relevance.save_data(path, json.dumps({'yes_no': (N_YES, N_NO)}))
            print(f"Caching {path}")
        
        return N_YES > N_NO

    def satisfies_embedding_criteria(self, urls):
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
            hashed_data = [(url, self.embedding_relevance.get_data_by_hash(url)) for url in urls]
            hashed_data = [data for data in hashed_data if data[1] is not None]
            urls = [url for url in urls if self.embedding_relevance.get_data_by_hash(url) is None]
        else:
            urls = [url for url in urls]
            hashed_data = []

        
        
        print(f'Number of Hashed URLs: {len_before - len(urls)}... Percentage loads saved: {100*(len_before - len(urls))/len_before}%')
        
        # Find relevant URLs based on embedding criteria
        relevant_urls = self.llm.find_url_relevance(urls, target_keywords)

        for relevant_url in relevant_urls:
            if self.use_cache:
                print(f'Hashing URL: {relevant_url[0]}')
                self.embedding_relevance.save_data(relevant_url[0], relevant_url[1])
        
        for data in hashed_data:
            relevant_urls.append(data)
        # Return only relevant URLs with the base path excluded
        return [relevant_url[0] for relevant_url in relevant_urls if relevant_url[1]]
    

    def satisfies_special_characteristics(self, paths):
        if not paths:
            return []
        base_path = 'https://' + urlparse(paths[0]).netloc + '/'

        urls = [urlparse(url).path for url in paths]
        
        urls = self.satisfies_embedding_criteria(urls)

    
        urls = [path for path in urls if self.satisfies_special_words(path) or self.satisfies_llm_criteria(path)]
        
        paths = [urljoin(base_path, path) for path in urls]
        print(base_path)
        print(paths)
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