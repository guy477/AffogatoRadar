# webscraper.py
from _utils._util import *

from .webfetcher import WebFetcher
from .contentparser import ContentParser
from backend.llmhandler import LLMHandler
from web.cachemanager import CacheManager
from .traversalmanager import TraversalManager

from urllib.robotparser import RobotFileParser

class WebScraper:
    def __init__(self, max_concurrency=10, webpage_timeout=1000, similarity_threshold=0.6):
        util_logger.info("Initializing WebScraper with parameters: max_concurrency=%d, webpage_timeout=%d, similarity_threshold=%.2f",
                    max_concurrency, webpage_timeout, similarity_threshold)

        self.webpage_timeout = webpage_timeout
        self.similarity_threshold = similarity_threshold
        self.max_concurrency = max_concurrency

        # Initialize robots.txt parsers cache
        self.robots_parsers = {}  # Dictionary to store RobotFileParser instances per domain

        self.web_fetcher = WebFetcher(webpage_timeout=self.webpage_timeout)
        self.content_parser = ContentParser()
        self.cache_manager = CacheManager()
        self.llm_handler = LLMHandler()
        self.traversal_manager = TraversalManager(
            similarity_threshold=self.similarity_threshold,
            max_concurrency=self.max_concurrency,
            scraper=self,
            llm_handler=self.llm_handler,
            cache_manager=self.cache_manager,
            content_parser=self.content_parser
        )
        
        util_logger.info("WebScraper initialized successfully.")

    async def fetch_and_cache_content(self, url):
        util_logger.info("Fetching and caching contents for URL: %s", url)

        # Check robots.txt compliance
        if not await self.is_compliant(url):
            util_logger.info(f"URL disallowed by robots.txt: {url}. Skipping.")
            return None, None
        
        # Check cache first
        redirect_url = self.cache_manager.get_cached_data('source_dest', url)
        if redirect_url:
            util_logger.debug("Cache hit for URL: %s, redirecting to: %s", url, redirect_url)
            content = self.cache_manager.get_cached_data('url_to_page_data', redirect_url)
            if content:
                util_logger.debug("Content retrieved from cache for URL: %s", redirect_url)
                return redirect_url, content
            else:
                util_logger.warning("Redirect URL found in cache but no content cached for: %s", redirect_url)
        
        # Fetch content
        util_logger.debug("Cache miss for URL: %s. Fetching content.", url)
        try:
            final_url, content = await self.web_fetcher.fetch_content(url)
            if not content:
                util_logger.error("Failed to fetch content for URL: %s", url)
                return None, None
            util_logger.debug("Content fetched successfully for URL: %s", final_url)
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

    async def source_establishment_url(self, google_maps_url):
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
            util_logger.warning("Menu/website link not found for URL: %s", final_url)
            return None

    def find_menu_link_html(self, html_content):
        util_logger.debug("Parsing HTML content to find menu link.")
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            menu_element = soup.find('a', {'data-item-id': 'menu', 'data-tooltip': 'Open menu link'})
            if menu_element and menu_element.get('href'):
                util_logger.info("Menu link element found with href: %s", menu_element['href'])
                return menu_element['href']
            util_logger.info("Menu link element not found in HTML content.")


            menu_element = soup.find('a', {'data-item-id': 'authority', 'data-tooltip': 'Open website'})
            if menu_element and menu_element.get('href'):
                util_logger.info("Menu link element found with href: %s", menu_element['href'])
                return menu_element['href']
            util_logger.info("Website link element not found in HTML content.")

            return None
        except Exception as e:
            util_logger.error("Error parsing HTML content for menu link. Error: %s", str(e))
            return None

    async def is_compliant(self, url: str, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0") -> bool:
        """ 

        Check if the URL is allowed to be crawled based on robots.txt.
        
        Args:
            url (str): The URL to check.
            user_agent (str): The user agent to check permissions against.
        
        Returns:
            bool: True if allowed, False otherwise.
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path or '/'
        
        robot_parser = await self.fetch_robots_txt(domain, user_agent)
        
        if robot_parser is None:
            # No robots.txt found or failed to fetch; assume allowed
            util_logger.debug(f"No robots.txt parser for domain: {domain}. Assuming URL is allowed: {url}")
            return True
        
        if 'google.com' in url or '/maps.' in url:
            util_logger.debug(f"Google domain detected: {domain}. Assuming access is allowed VIA programmatic call: {url}")
            return True
        
        is_allowed = robot_parser.can_fetch(user_agent, path)
        util_logger.debug(f"robots.txt compliance for URL {url}: {is_allowed}")
        return is_allowed
    
    async def fetch_robots_txt(self, domain: str, user_agent: str = '*') -> RobotFileParser:
        """
        Fetch and parse the robots.txt file for the given domain.
        
        Args:
            domain (str): The domain to fetch robots.txt for.
            user_agent (str): The user agent to check permissions against.
        
        Returns:
            RobotFileParser: Parsed robots.txt rules for the domain.
        """
        if domain in self.robots_parsers:
            util_logger.debug(f"robots.txt already fetched for domain: {domain}")
            return self.robots_parsers[domain]
        
        robots_url = f"https://{domain}/robots.txt"
        util_logger.info(f"Fetching robots.txt from: {robots_url}")
        
        robot_parser = RobotFileParser()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url, timeout=self.webpage_timeout / 1000) as response:
                    if response.status == 200:
                        content = await response.text()
                        robot_parser.parse(content.splitlines())
                        util_logger.info(f"robots.txt fetched and parsed for domain: {domain}")
                    else:
                        util_logger.error(f"Failed to fetch robots.txt for domain: {domain}, status: {response.status}. Assuming all URLs are allowed.")
                        robot_parser = None  # No robots.txt available, allow all
        except Exception as e:
            util_logger.error(f"Error fetching robots.txt for domain: {domain}. Error: {e}. Assuming all URLs are allowed.")
            robot_parser = None  # On error, allow all
        
        self.robots_parsers[domain] = robot_parser
        return robot_parser

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
                # Ensure the link is from the same base domain and has a valid path
                if parsed_url.netloc == base_domain and parsed_url.path and not full_url.startswith('#'):
                    subpage_links.append(full_url)

            subpage_links = list(OrderedDict.fromkeys(subpage_links))
            util_logger.info("Found %d unique subpage links before filtering.", len(subpage_links))

            # Check if the subpage links are valid and not empty
            if not subpage_links:
                util_logger.warning("No subpage links found for URL: %s", url)
                return []

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
            util_logger.debug("Checking cache for embedding relevance.")
            # Retrieve cached relevance
            cached_data = {
                url: self.cache_manager.get_cached_data('embedding_relevance', url)
                for url in full_urls
            }
            # Separate cached and uncached URLs
            cached_urls = [(url, relevance) for url, relevance in cached_data.items() if relevance is not None]
            uncached_urls = [url for url, relevance in cached_data.items() if relevance is None]

            util_logger.info(
                "Cache hit for %d URLs, remaining URLs to evaluate: %d",
                len(cached_urls),
                len(uncached_urls)
            )
            relevant_urls.extend(cached_urls)

            if uncached_urls:
                util_logger.info("Evaluating relevance for %d uncached URLs.", len(uncached_urls))
                new_relevant_urls = await self.llm_handler.find_url_relevance(uncached_urls)
                for final_url, relevance in new_relevant_urls:
                    if relevance is not None:
                        self.cache_manager.set_cached_data('embedding_relevance', final_url, relevance)
                        util_logger.info("Cached embedding relevance for URL: %s", final_url)
                        relevant_urls.append((final_url, relevance))

            # Filter URLs based on similarity threshold
            filtered_urls = [
                url for url, relevance in relevant_urls
                if relevance is not None and float(relevance) > self.similarity_threshold
            ]
            util_logger.info(
                "Filtered %d URLs based on similarity threshold of %.2f.",
                len(filtered_urls),
                self.similarity_threshold
            )

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
