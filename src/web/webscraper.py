# webscraper.py
from _utils._util import *

from .webfetcher import WebFetcher
from .contentparser import ContentParser
from .llmhandler import LLMHandler
from .cachemanager import CacheManager
from .traversalmanager import TraversalManager


class WebScraper:
    def __init__(self, storage_dir: str = "../data", use_cache=True, max_concurrency=10, webpage_timeout=1000, similarity_threshold=0.6):
        self.use_cache = use_cache
        self.webpage_timeout = webpage_timeout
        self.similarity_threshold = similarity_threshold
        self.max_concurrency = max_concurrency

        self.web_fetcher = WebFetcher(webpage_timeout=self.webpage_timeout)
        self.content_parser = ContentParser()
        self.cache_manager = CacheManager(storage_dir)
        self.llm_handler = LLMHandler()
        self.traversal_manager = TraversalManager(
            use_cache=self.use_cache,
            similarity_threshold=self.similarity_threshold,
            max_concurrency=self.max_concurrency,
            scraper=self,
            llm_handler=self.llm_handler,
            cache_manager=self.cache_manager,
            content_parser=self.content_parser
        )

    async def fetch_and_cache_content(self, url):
        # Check cache first
        redirect_url = self.cache_manager.get_cached_data('source_dest', url)
        if self.use_cache and redirect_url:
            content = self.cache_manager.get_cached_data('url_to_html', redirect_url)
            return redirect_url, content

        # Fetch content
        final_url, content = await self.web_fetcher.fetch_content(url)
        if not content:
            return None, None

        # Cache the final page content
        self.cache_manager.set_cached_data('source_dest', url, final_url)
        self.cache_manager.set_cached_data('url_to_html', final_url, content)
        print(f"Content cached for {url}")

        return final_url, content

    async def source_menu_link(self, google_maps_url):
        _, html_content = await self.fetch_and_cache_content(google_maps_url)
        if not html_content:
            return None

        menu_link = self.find_menu_link_html(html_content)
        if menu_link:
            print(f"Menu link found: {menu_link}")
            return menu_link
        else:
            print("Menu link not found.")
            return None

    def find_menu_link_html(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        menu_element = soup.find('a', {'data-item-id': 'menu', 'data-tooltip': 'Open menu link'})
        if menu_element and menu_element.get('href'):
            return menu_element['href']
        return None

    async def find_subpage_links(self, url, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        parsed_base_url = urlparse(url)
        base_domain = parsed_base_url.netloc

        subpage_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(url, href)
            parsed_url = urlparse(full_url)
            if parsed_url.netloc == base_domain and parsed_url.path:
                subpage_links.append(full_url)

        subpage_links = list(OrderedDict.fromkeys(subpage_links))
        subpage_links = await self.satisfies_special_characteristics(subpage_links)

        return subpage_links

    def satisfies_special_words(self, full_url):
        path = urlparse(full_url).path
        special_words = SPECIAL_WORDS  # Assume SPECIAL_WORDS is imported
        for special_word in special_words:
            if special_word in path:
                return True
        return False

    async def url_embedding_relevance(self, full_urls):
        if self.use_cache:
            hashed_data = [(url, self.cache_manager.get_cached_data('embedding_relevance', url)) for url in full_urls]
            hashed_data = [data for data in hashed_data if data[1] is not None]
            full_urls = [url for url in full_urls if self.cache_manager.get_cached_data('embedding_relevance', url) is None]
        else:
            hashed_data = []

        relevant_urls = await self.llm_handler.find_url_relevance(full_urls)

        for relevant_url in relevant_urls:
            if not self.cache_manager.get_cached_data('embedding_relevance', relevant_url[0]):
                print(f'Caching Embedding Relevance For {relevant_url[0]}')
                self.cache_manager.set_cached_data('embedding_relevance', relevant_url[0], relevant_url[1])

        for data in hashed_data:
            relevant_urls.append(data)

        return [relevant_url[0] for relevant_url in relevant_urls if relevant_url[1] and float(relevant_url[1]) > self.similarity_threshold]

    async def satisfies_special_characteristics(self, full_urls):
        if not full_urls:
            return []

        relevant_urls = [url for url in full_urls if self.satisfies_special_words(url)]
        full_urls = relevant_urls
        full_urls = await self.url_embedding_relevance(full_urls)

        return full_urls

    async def close(self):
        await self.web_fetcher.stop_playwright()
        self.cache_manager.close()