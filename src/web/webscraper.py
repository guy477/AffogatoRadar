# webscraper.py
from _utils._util import *

from .contentparser import ContentParser
from .webinterpreter import WebInterpreter

from backend.cachemanager import CacheManager
from backend.llmhandler import LLMHandler
from backend.webfetcher import WebFetcher

from urllib.robotparser import RobotFileParser
class RobotsTxtManager:
    def __init__(self, cache_manager: CacheManager, webpage_timeout: int):
        self.cache_manager = cache_manager
        self.webpage_timeout = webpage_timeout
        self.robots_parsers = {}

    async def is_allowed(self, url: str) -> bool:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path or '/'
        headers = get_anonymous_headers()

        robot_parser = await self._get_robot_parser(domain, headers)

        if robot_parser is None:
            UTIL_LOGGER.debug(f"No robots.txt parser for domain: {domain}. Assuming URL is allowed: {url}")
            return True

        if 'google.com' in url or '/maps.' in url:
            UTIL_LOGGER.debug(f"Google domain detected: {domain}. Assuming access is allowed VIA programmatic call: {url}")
            return True

        is_allowed = robot_parser.can_fetch(path, headers['User-Agent'])
        UTIL_LOGGER.debug(f"robots.txt compliance for URL {url}: {is_allowed}")
        return is_allowed

    async def _get_robot_parser(self, domain: str, headers: Dict[str, str]) -> Optional[RobotFileParser]:
        if domain in self.robots_parsers:
            UTIL_LOGGER.debug(f"robots.txt already fetched for domain: {domain}")
            return self.robots_parsers[domain]

        robots_url = f"https://{domain}/robots.txt"
        UTIL_LOGGER.info(f"Fetching robots.txt from: {robots_url}")

        robot_parser = RobotFileParser()
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(robots_url, timeout=self.webpage_timeout / 1000) as response:
                    if response.status == 200:
                        content = await response.text()
                        robot_parser.parse(content.splitlines())
                        UTIL_LOGGER.info(f"robots.txt fetched and parsed for domain: {domain}")
                    else:
                        UTIL_LOGGER.error(f"Failed to fetch robots.txt for domain: {domain}, response.status: {response.status}. Assuming all URLs are allowed.")
                        robot_parser = None
        except Exception as e:
            UTIL_LOGGER.error(f"Error fetching robots.txt for domain: {domain}. Error: {e}. Assuming all URLs are allowed.")
            robot_parser = None
            raise e

        self.robots_parsers[domain] = robot_parser
        return robot_parser


class LinkParser:
    @staticmethod
    def find_menu_link(html_content: str) -> Optional[str]:
        UTIL_LOGGER.debug("Parsing HTML content to find menu link.")
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            menu_element = soup.find('a', {'data-item-id': 'menu', 'data-tooltip': 'Open menu link'})
            if menu_element and menu_element.get('href'):
                UTIL_LOGGER.info("Menu link element found with href: %s", menu_element['href'])
                return menu_element['href']
            UTIL_LOGGER.info("Menu link element not found in HTML content.")

            menu_element = soup.find('a', {'data-item-id': 'authority', 'data-tooltip': 'Open website'})
            if menu_element and menu_element.get('href'):
                UTIL_LOGGER.info("Menu link element found with href: %s", menu_element['href'])
                return menu_element['href']
            UTIL_LOGGER.info("Website link element not found in HTML content.")

            return None
        except Exception as e:
            UTIL_LOGGER.error("Error parsing HTML content for menu link. Error: %s", str(e))
            return None

    @staticmethod
    async def extract_subpage_links(url: str, html_content: str, base_domain: str) -> List[str]:
        UTIL_LOGGER.info("Finding subpage links in URL: %s", url)
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            subpage_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                full_url = urljoin(url, href)
                parsed_url = urlparse(full_url)
                if parsed_url.netloc == base_domain and parsed_url.path and not full_url.startswith('#'):
                    subpage_links.append(full_url)

            unique_links = list(OrderedDict.fromkeys(subpage_links))
            UTIL_LOGGER.info("Found %d unique subpage links before filtering.", len(unique_links))

            if not unique_links:
                UTIL_LOGGER.warning("No subpage links found for URL: %s", url)
                return []

            return unique_links
        except Exception as e:
            UTIL_LOGGER.error("Error finding subpage links for URL: %s. Error: %s", url, str(e))
            return []


class URLRelevanceEvaluator:
    def __init__(self, llm_handler: LLMHandler, cache_manager: CacheManager, similarity_threshold: float):
        self.llm_handler = llm_handler
        self.cache_manager = cache_manager
        self.similarity_threshold = similarity_threshold

    async def filter_relevant_urls(self, urls: List[str]) -> List[str]:
        UTIL_LOGGER.info("Evaluating embedding relevance for %d URLs.", len(urls))
        relevant_urls = []
        normalized_urls = [normalize_url(url) for url in urls]
        try:
            UTIL_LOGGER.debug("Checking cache for embedding relevance.")
            cached_data = {
                url: self.cache_manager.get_cached_data('embedding_relevance', url)
                for url in normalized_urls
            }

            cached_urls = [(url, relevance) for url, relevance in cached_data.items() if relevance is not None]
            uncached_urls = [url for url, relevance in cached_data.items() if relevance is None]

            UTIL_LOGGER.info(
                "Cache hit for %d URLs, remaining URLs to evaluate: %d",
                len(cached_urls),
                len(uncached_urls)
            )
            relevant_urls.extend(cached_urls)

            if uncached_urls:
                UTIL_LOGGER.info("Evaluating relevance for %d uncached URLs.", len(uncached_urls))
                new_relevant_urls = await self.llm_handler.find_url_relevance(uncached_urls)
                for final_url, relevance in new_relevant_urls:
                    if relevance is not None:
                        self.cache_manager.set_cached_data('embedding_relevance', final_url, relevance)
                        UTIL_LOGGER.info("Cached embedding relevance for URL: %s", final_url)
                        relevant_urls.append((final_url, relevance))

            filtered_urls = [
                url for url, relevance in relevant_urls
                if relevance is not None and float(relevance) > self.similarity_threshold
            ]
            UTIL_LOGGER.info(
                "Filtered %d URLs based on similarity threshold of %.2f.",
                len(filtered_urls),
                self.similarity_threshold
            )

            return filtered_urls
        except Exception as e:
            UTIL_LOGGER.error("Error evaluating URL embedding relevance. Error: %s", str(e))
            return []


class WebScraper:
    def __init__(self, max_concurrency: int = 10, webpage_timeout: int = 1000, similarity_threshold: float = 0.6):
        UTIL_LOGGER.info(
            "Initializing WebScraper with parameters: max_concurrency=%d, webpage_timeout=%d, similarity_threshold=%.2f",
            max_concurrency, webpage_timeout, similarity_threshold
        )

        self.webpage_timeout = webpage_timeout
        self.similarity_threshold = similarity_threshold
        self.max_concurrency = max_concurrency

        self.web_fetcher = WebFetcher(webpage_timeout=self.webpage_timeout)
        self.content_parser = ContentParser()
        self.cache_manager = CacheManager()
        self.llm_handler = LLMHandler()
        self.web_interpreter = WebInterpreter(
            similarity_threshold=self.similarity_threshold,
            max_concurrency=self.max_concurrency,
            scraper=self,
            llm_handler=self.llm_handler,
            cache_manager=self.cache_manager,
            content_parser=self.content_parser
        )
        self.robots_manager = RobotsTxtManager(self.cache_manager, self.webpage_timeout)
        self.link_parser = LinkParser()
        self.url_relevance_evaluator = URLRelevanceEvaluator(self.llm_handler, self.cache_manager, self.similarity_threshold)

        UTIL_LOGGER.info("WebScraper initialized successfully.")

    async def fetch_and_cache_content(self, url: str) -> Optional[Tuple[str, Optional[str], Optional[bytes]]]:
        UTIL_LOGGER.info("Fetching and caching contents for URL: %s", url)

        normalized_url = normalize_url(url)

        cached_final_url = self.cache_manager.get_cached_data('source_dest', normalized_url)
        if cached_final_url:
            UTIL_LOGGER.debug("Cache hit for URL: %s, redirecting to: %s", normalized_url, cached_final_url)
            html_content = self.cache_manager.get_cached_data('url_to_html_data', cached_final_url)
            pdf_content = self.cache_manager.get_cached_data('url_to_pdf_data', cached_final_url)
            if html_content or pdf_content:
                UTIL_LOGGER.debug("Content retrieved from cache for URL: %s", cached_final_url)
                return cached_final_url, html_content, pdf_content
            UTIL_LOGGER.warning("Redirect URL found in cache but no content cached for: %s", cached_final_url)

        if not await self.robots_manager.is_allowed(normalized_url):
            UTIL_LOGGER.info(f"URL disallowed by robots.txt: {normalized_url}. Skipping.")
            return None, None, None

        UTIL_LOGGER.debug("Cache miss for URL: %s. Fetching content.", normalized_url)
        try:
            final_url, html_content, pdf_content = await self.web_fetcher.fetch_content(url)
            if not html_content and not pdf_content:
                UTIL_LOGGER.error("Failed to fetch content for URL: %s", normalized_url)
                return None, None, None
            UTIL_LOGGER.debug("Content fetched successfully for URL: %s", final_url)
        except Exception as e:
            UTIL_LOGGER.error("Exception occurred while fetching content for URL: %s. Error: %s", normalized_url, str(e))
            return None, None, None

        normalized_final_url = normalize_url(final_url)

        try:
            self.cache_manager.set_cached_data('source_dest', normalized_url, normalized_final_url)
            if html_content:
                self.cache_manager.set_cached_data('url_to_html_data', normalized_final_url, html_content)
            if pdf_content:
                self.cache_manager.set_cached_data('url_to_pdf_data', normalized_final_url, pdf_content)
            UTIL_LOGGER.info("Content cached for URL: %s", normalized_final_url)
        except Exception as e:
            UTIL_LOGGER.error("Failed to cache content for URL: %s. Error: %s", normalized_final_url, str(e))

        return final_url, html_content, pdf_content

    async def source_establishment_url(self, google_maps_url: str) -> Optional[str]:
        UTIL_LOGGER.info("Retrieving menu link from Google Maps URL: %s", google_maps_url)

        final_url, html_content, _ = await self.fetch_and_cache_content(google_maps_url)
        if not html_content:
            UTIL_LOGGER.warning("No HTML content found for Google Maps URL: %s", google_maps_url)
            return None

        menu_link = self.link_parser.find_menu_link(html_content)
        if menu_link:
            UTIL_LOGGER.info("Menu link found: %s for URL: %s", menu_link, final_url)
            return menu_link
        UTIL_LOGGER.warning("Menu/website link not found for URL: %s", final_url)
        return None

    async def find_subpage_links(self, url: str, html_content: str) -> List[str]:
        parsed_base_url = urlparse(url)
        base_domain = parsed_base_url.netloc
        subpage_links = await LinkParser.extract_subpage_links(url, html_content, base_domain)
        if not subpage_links:
            return []

        filtered_links = await self.url_relevance_evaluator.filter_relevant_urls(subpage_links)
        UTIL_LOGGER.info("Number of subpage links after filtering: %d", len(filtered_links))
        return filtered_links

    async def close(self):
        UTIL_LOGGER.info("Closing WebScraper and releasing resources.")
        try:
            await self.web_fetcher.stop_playwright()
            UTIL_LOGGER.debug("WebFetcher Playwright stopped.")
        except Exception as e:
            UTIL_LOGGER.error("Error stopping WebFetcher Playwright. Error: %s", str(e))

        try:
            self.cache_manager.close()
            UTIL_LOGGER.debug("CacheManager closed.")
        except Exception as e:
            UTIL_LOGGER.error("Error closing CacheManager. Error: %s", str(e))

        UTIL_LOGGER.info("WebScraper closed successfully.")
