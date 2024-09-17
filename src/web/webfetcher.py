# webfetcher.py
from _utils._util import *

from playwright.async_api import async_playwright, Page, TimeoutError

class WebFetcher:
    def __init__(self, webpage_timeout=1000):
        self.webpage_timeout = webpage_timeout
        self.playwright = None
        self.browser = None
        self.context = None
        UTIL_LOGGER.info("WebFetcher initialized with webpage_timeout=%d ms", self.webpage_timeout)

    async def start_playwright(self):
        """Initialize Playwright and the browser instance."""
        if not self.playwright:
            UTIL_LOGGER.info("Starting Playwright and launching Firefox browser.")
            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.firefox.launch(headless=False)
                UTIL_LOGGER.info("Playwright started and Firefox browser launched.")
                await self.start_context()
            except Exception as e:
                UTIL_LOGGER.error("Failed to start Playwright or launch browser: %s", e)
                raise

        if not self.browser.is_connected():
            UTIL_LOGGER.warning("Browser is not connected. Reconnecting...")
            try:
                self.browser = await self.playwright.firefox.launch(headless=False)
                UTIL_LOGGER.info("Browser reconnected successfully.")
                await self.start_context()
            except Exception as e:
                UTIL_LOGGER.error("Failed to reconnect the browser: %s", e)
                raise
        

    async def start_context(self):
        """Initialize Playwright and the browser instance."""
        if not self.context:
            UTIL_LOGGER.info("Starting Playwright and launching Firefox browser.")
            try:
                self.context = await self.browser.new_context(
                    ignore_https_errors=True,
                    viewport={"width": 800, "height": 600}, 
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/115.0.0.0 Safari/537.36"
                    )  # Modern Chrome on Windows 10
                )
            except Exception as e:
                UTIL_LOGGER.error("Failed to start context: %s", e)
        
    async def stop_playwright(self):
        """Stop the Playwright instance and close the browser."""
        if self.browser:
            UTIL_LOGGER.info("Closing the browser.")
            try:
                await self.browser.close()
                UTIL_LOGGER.info("Browser closed successfully.")
            except Exception as e:
                UTIL_LOGGER.error("Error while closing the browser: %s", e)

        if self.playwright:
            UTIL_LOGGER.info("Stopping Playwright.")
            try:
                await self.playwright.stop()
                UTIL_LOGGER.info("Playwright stopped successfully.")
            except Exception as e:
                UTIL_LOGGER.error("Error while stopping Playwright: %s", e)

    def is_pdf_url(self, url):
        """Check if a URL is a PDF."""
        is_pdf = url.lower().endswith('.pdf') if url else False
        UTIL_LOGGER.debug("URL %s is a PDF: %s", url, is_pdf)
        return is_pdf

    async def fetch_content(self, url):
        """Fetch content from a URL, handling HTML and PDF."""
        UTIL_LOGGER.info("Fetching content for URL: %s", url)
        if self.is_pdf_url(url):
            return await self.fetch_pdf(url)
        else:
            return await self.fetch_html(url)

    async def fetch_html(self, url):
        """Fetch HTML content using Playwright with improved timeout handling."""
        UTIL_LOGGER.info("Fetching HTML content for URL: %s", url)
        await self.start_playwright()

        try:
            page: Page = await self.context.new_page()
            UTIL_LOGGER.info("New page opened for URL: %s", url)
        except Exception as e:
            UTIL_LOGGER.error("Failed to open a new page for URL: %s. Error: %s", url, e)
            return None, None

        try:
            UTIL_LOGGER.info("Navigating to URL: %s", url)
            await page.goto(url, wait_until='networkidle', timeout=self.webpage_timeout)
            UTIL_LOGGER.info("Navigation to URL %s successful.", url)
        except TimeoutError:
            UTIL_LOGGER.warning("Navigation to URL %s timed out after %d ms.", url, self.webpage_timeout)
        except Exception as e:
            UTIL_LOGGER.error("Failed to navigate to URL: %s. Error: %s", url, e)
            await page.close()
            return None, None

        try:
            # Scroll down until all content is loaded
            previous_height = await page.evaluate("document.body.scrollHeight")
            while True:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)  # Give the page time to load more data
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == previous_height:
                    break
                previous_height = new_height
        except Exception as e:
            UTIL_LOGGER.error("Error during wait for load state for URL: %s. Error: %s", url, e)
            await page.close()
            return None, None

        try:
            html_content = await page.content()
            final_url = page.url
            UTIL_LOGGER.info("Successfully retrieved HTML content for URL: %s", final_url)
        except Exception as e:
            UTIL_LOGGER.error("Error retrieving content for URL: %s. Error: %s", url, e)
            html_content = None
            final_url = page.url if page else None
        finally:
            if not page.is_closed():
                await page.close()
                UTIL_LOGGER.info("Page closed for URL: %s", url)

        return final_url, html_content

    async def fetch_pdf(self, url):
        """Fetch PDF content from a URL."""
        UTIL_LOGGER.info("Fetching PDF content for URL: %s", url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/113.0.0.0 Safari/537.36"
            ),
            "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        pdf_data = await response.read()
                        UTIL_LOGGER.info("Successfully downloaded PDF from URL: %s", url)
                        UTIL_LOGGER.info("PDF size for URL %s: %d bytes", url, len(pdf_data))
                        return url, pdf_data
                    else:
                        UTIL_LOGGER.warning(
                            "Failed to fetch PDF from URL: %s. Status: %d, Reason: %s",
                            url,
                            response.status,
                            response.reason
                        )
                        return None, None
            except Exception as e:
                UTIL_LOGGER.error("An error occurred while fetching the PDF from URL: %s. Error: %s", url, e)
                return None, None
