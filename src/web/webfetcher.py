# webfetcher.py
from _utils._util import *

from playwright.async_api import async_playwright, Page


class WebFetcher:
    def __init__(self, webpage_timeout=1000):
        self.webpage_timeout = webpage_timeout
        self.playwright = None
        self.browser = None

    async def start_playwright(self):
        """Initialize Playwright and the browser instance."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            
            # NOTE: We're using firefox because it's more universal. Install plugins to optimize
            self.browser = await self.playwright.firefox.launch(headless=False)

        if not self.browser.is_connected():
            self.browser = await self.playwright.firefox.launch(headless=False)

    async def stop_playwright(self):
        """Stop the Playwright instance and close the browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def is_pdf_url(self, url):
        """Check if a URL is a PDF."""
        return url.lower().endswith('.pdf') if url else False

    async def fetch_content(self, url):
        """Fetch content from a URL, handling HTML and PDF."""
        if self.is_pdf_url(url):
            return await self.fetch_pdf(url)
        else:
            return await self.fetch_html(url)

    async def fetch_html(self, url):
        """Fetch HTML content using Playwright with pause for debugging."""
        # Start Playwright if it's not already running
        await self.start_playwright()

        # Open a new page
        page: Page = await self.browser.new_page()

        try:
            # Attempt to navigate to the URL
            await page.goto(url, wait_until='networkidle', timeout=self.webpage_timeout)
        except Exception as e:
            # Handle navigation errors and retry once
            print(f"Initial navigation failed for {url}: {e}")
            await page.close()
            page = await self.browser.new_page()
            try:
                await page.goto(url, wait_until='networkidle', timeout=self.webpage_timeout)
            except Exception as e:
                print(f"Retry navigation failed for {url}: {e}")
                await page.close()
                return None, None  # Early exit if both attempts fail

        try:
            # Additional wait to ensure content is fully loaded
            await page.wait_for_load_state('networkidle', timeout=self.webpage_timeout / 4)
            
            # Pause execution and open Playwright Inspector
            # await page.pause()
            
            # After resuming, retrieve the page content
            html_content = await page.content()
            final_url = page.url

            # Optionally, capture a screenshot for verification
            # await page.screenshot(path="screenshot.png")
        except Exception as e:
            print(f"Error retrieving content for {url}: {e}")
            html_content = None
            final_url = page.url if page else None
        finally:
            # Ensure the page is closed to free resources
            if not page.is_closed():
                await page.close()

        return final_url, html_content

    async def fetch_pdf(self, url):
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
                        print(f"Successfully downloaded PDF from {url}")
                        print(f"PDF size: {len(pdf_data)} bytes")
                        return url, pdf_data
                    else:
                        print(f"Failed to fetch PDF: {response.status} {response.reason}")
                        return None, None
            except Exception as e:
                print(f"An error occurred while fetching the PDF: {str(e)}")
                return None, None