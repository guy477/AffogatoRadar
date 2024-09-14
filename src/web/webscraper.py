# webscraper.py
from _utils._util import *

from .webfetcher import WebFetcher
from .contentparser import ContentParser
from .llmhandler import LLMHandler
from .cachemanager import CacheManager
from .traversalmanager import TraversalManager


class WebScraper:
    def __init__(self, storage_dir: str = "../data", use_cache=True, max_concurrency=10, webpage_timeout=1000, similarity_threshold=0.6):
        util_logger.info("Initializing WebScraper with parameters: storage_dir=%s, use_cache=%s, max_concurrency=%d, webpage_timeout=%d, similarity_threshold=%.2f",
                     storage_dir, use_cache, max_concurrency, webpage_timeout, similarity_threshold)
        
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
        
        util_logger.info("WebScraper initialized successfully.")

    async def fetch_and_cache_content(self, url):
        util_logger.info("Fetching content for URL: %s", url)
        
        # Check cache first
        redirect_url = self.cache_manager.get_cached_data('source_dest', url)
        if self.use_cache and redirect_url:
            util_logger.debug("Cache hit for URL: %s, redirecting to: %s", url, redirect_url)
            content = self.cache_manager.get_cached_data('url_to_page_data', redirect_url)
            if content:
                util_logger.info("Content retrieved from cache for URL: %s", redirect_url)
                return redirect_url, content
            else:
                util_logger.warning("Redirect URL found in cache but no content cached for: %s", redirect_url)
        
        # Fetch content
        util_logger.info("Cache miss for URL: %s. Fetching content.", url)
        try:
            final_url, content = await self.web_fetcher.fetch_content(url)
            if not content:
                util_logger.error("Failed to fetch content for URL: %s", url)
                return None, None
            util_logger.info("Content fetched successfully for URL: %s", final_url)
        except Exception as e:
            util_logger.error("Exception occurred while fetching content for URL: %s. Error: %s", url, str(e))
            return None, None

        # Cache the final page content
        try:
            self.cache_manager.set_cached_data('source_dest', url, final_url)
            self.cache_manager.set_cached_data('url_to_page_data', final_url, content)
            util_logger.info("Content cached for URL: %s", url)
        except Exception as e:
            util_logger.error("Failed to cache content for URL: %s. Error: %s", url, str(e))

        return final_url, content

    async def source_menu_link(self, google_maps_url):
        util_logger.info("Retrieving menu link from Google Maps URL: %s", google_maps_url)
        
        final_url, html_content = await self.fetch_and_cache_content(google_maps_url)
        if not html_content:
            util_logger.warning("No HTML content found for Google Maps URL: %s", google_maps_url)
            return None
        
        menu_link = self.find_menu_link_html(html_content)
        if menu_link:
            util_logger.info("Menu link found: %s for URL: %s", menu_link, final_url)
            return menu_link
        else:
            util_logger.warning("Menu link not found for URL: %s", final_url)
            return None

    def find_menu_link_html(self, html_content):
        util_logger.debug("Parsing HTML content to find menu link.")
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            menu_element = soup.find('a', {'data-item-id': 'menu', 'data-tooltip': 'Open menu link'})
            if menu_element and menu_element.get('href'):
                util_logger.info("Menu link element found with href: %s", menu_element['href'])
                return menu_element['href']
            util_logger.debug("Menu link element not found in HTML content.")
            return None
        except Exception as e:
            util_logger.error("Error parsing HTML content for menu link. Error: %s", str(e))
            return None

    async def find_subpage_links(self, url, html_content):
        util_logger.info("Finding subpage links in URL: %s", url)
        try:
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
            util_logger.info("Found %d unique subpage links before filtering.", len(subpage_links))

            subpage_links = await self.satisfies_special_characteristics(subpage_links)
            util_logger.info("Number of subpage links after filtering: %d", len(subpage_links))

            return subpage_links
        except Exception as e:
            util_logger.error("Error finding subpage links for URL: %s. Error: %s", url, str(e))
            return []

    async def url_embedding_relevance(self, full_urls):
        util_logger.info("Evaluating embedding relevance for %d URLs.", len(full_urls))
        relevant_urls = []
        try:
            if self.use_cache:
                util_logger.debug("Checking cache for embedding relevance.")
                hashed_data = [(url, self.cache_manager.get_cached_data('embedding_relevance', url)) for url in full_urls]
                cached_urls = [data for data in hashed_data if data[1] is not None]
                relevant_urls.extend(cached_urls)
                full_urls = [url for url in full_urls if self.cache_manager.get_cached_data('embedding_relevance', url) is None]
                util_logger.info("Cache hit for %d URLs, remaining URLs to evaluate: %d", len(cached_urls), len(full_urls))
            else:
                hashed_data = []
                util_logger.debug("Cache usage disabled. Proceeding without cache.")

            if full_urls:
                util_logger.info("Evaluating relevance for %d uncached URLs.", len(full_urls))
                new_relevant_urls = await self.llm_handler.find_url_relevance(full_urls)
                for relevant_url in new_relevant_urls:
                    url, relevance = relevant_url
                    if not self.cache_manager.get_cached_data('embedding_relevance', url):
                        self.cache_manager.set_cached_data('embedding_relevance', url, relevance)
                        util_logger.info("Cached embedding relevance for URL: %s", url)
                relevant_urls.extend(new_relevant_urls)

            # Combine cached and newly evaluated relevant URLs
            for data in hashed_data:
                relevant_urls.append(data)

            # Filter URLs based on similarity threshold
            filtered_urls = [url for url, relevance in relevant_urls if relevance and float(relevance) > self.similarity_threshold]
            util_logger.info("Filtered %d URLs based on similarity threshold of %.2f.", len(filtered_urls), self.similarity_threshold)

            return filtered_urls
        except Exception as e:
            util_logger.error("Error evaluating URL embedding relevance. Error: %s", str(e))
            return []

    async def satisfies_special_characteristics(self, full_urls):
        util_logger.info("Applying special characteristics filtering to %d URLs.", len(full_urls))
        if not full_urls:
            util_logger.warning("No URLs provided for special characteristics filtering.")
            return []
        
        try:
            filtered_urls = await self.url_embedding_relevance(full_urls)
            util_logger.info("After embedding relevance, %d URLs satisfy special characteristics.", len(filtered_urls))
            # Additional filtering logic can be added here
            return filtered_urls
        except Exception as e:
            util_logger.error("Error applying special characteristics filtering. Error: %s", str(e))
            return []

    async def close(self):
        util_logger.info("Closing WebScraper and releasing resources.")
        try:
            await self.web_fetcher.stop_playwright()
            util_logger.debug("WebFetcher Playwright stopped.")
        except Exception as e:
            util_logger.error("Error stopping WebFetcher Playwright. Error: %s", str(e))
        
        try:
            self.cache_manager.close()
            util_logger.debug("CacheManager closed.")
        except Exception as e:
            util_logger.error("Error closing CacheManager. Error: %s", str(e))
        
        util_logger.info("WebScraper closed successfully.")
