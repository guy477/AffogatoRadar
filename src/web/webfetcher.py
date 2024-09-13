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
        """Fetch HTML content using Playwright."""
        # Start Playwright if it's not already running
        await self.start_playwright()

        # Open a new page
        page: Page = await self.browser.new_page()

        
        try:
            # Load dynamic content until timeout
            await page.goto(url, wait_until='networkidle', timeout=self.webpage_timeout)
        except Exception:
            # Close original page and retry
            if not page.is_closed():
                await page.close()
            page: Page = await self.browser.new_page()
            print(f"Error/Timeout 1: {url}")

        try:
            # Re-execute loading
            await page.goto(url, wait_until='networkidle', timeout=self.webpage_timeout)
        except Exception:
            print(f"Error/Timeout 2 {url}")

        # Get the final URL and HTML content
        final_url = page.url
        html_content = await page.content()

        if not page.is_closed():
            await page.close()

        return final_url, html_content




    async def fetch_pdf(self, url):
        """Fetch and parse PDF content."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    pdf_bytes = await response.read()
                    return url, pdf_bytes
                else:
                    print(f"Failed to fetch PDF: {url}")
                    return None, None
