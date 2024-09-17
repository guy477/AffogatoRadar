# contentparser.py
from _utils._util import *

from io import BytesIO
import pdfplumber

class ContentParser:
    def __init__(self):
        UTIL_LOGGER.info("ContentParser initialized.")

    def parse_content(self, content, content_type='html'):
        UTIL_LOGGER.info(f"Parsing content of type: {content_type}")
        if content_type == 'html':
            try:
                result = self.parse_html(content)
                UTIL_LOGGER.info("HTML content parsed successfully.")
                return result
            except Exception as e:
                UTIL_LOGGER.error(f"Failed to parse HTML content: {e}")
                return None
        elif content_type == 'pdf':
            try:
                result = self.parse_pdf_content(content)
                UTIL_LOGGER.info("PDF content parsed successfully.")
                return result
            except Exception as e:
                UTIL_LOGGER.error(f"Failed to parse PDF content: {e}")
                return None
        else:
            UTIL_LOGGER.warning(f"Unsupported content type received: {content_type}")
            return None

    def parse_html(self, html_content):
        """Filter and parse HTML content."""
        UTIL_LOGGER.debug("Starting HTML parsing.")
        filtered_content = self.filter_html_for_menu(html_content)
        UTIL_LOGGER.debug("HTML content filtered for menu.")
        return filtered_content

    def parse_pdf_content(self, pdf_bytes):
        """Parse PDF content."""
        UTIL_LOGGER.debug("Starting PDF parsing.")
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                num_pages = len(pdf.pages)
                UTIL_LOGGER.info(f"Number of pages in PDF: {num_pages}")
                text = ''
                for i, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text
                        UTIL_LOGGER.debug(f"Extracted text from page {i}.")
                    else:
                        UTIL_LOGGER.warning(f"No text found on page {i}.")
            UTIL_LOGGER.info("Completed PDF parsing.")
            return text
        except Exception as e:
            UTIL_LOGGER.error(f"Error while parsing PDF: {e};\n{pdf_bytes[:1000]}")
            raise

    def filter_html_for_menu(self, html):
        """Filter HTML content to extract text for menu items."""
        UTIL_LOGGER.debug("Starting HTML filtering for menu items.")
        try:
            soup = BeautifulSoup(html, 'html.parser')
            if soup:
                # Extract text content while preserving the text between tags
                filtered_text = soup.get_text(separator=' ', strip=True)
                UTIL_LOGGER.info("HTML content filtered successfully.")
                return filtered_text
            else:
                UTIL_LOGGER.warning("No <body> tag found in the HTML.")
                return "No <body> tag found in the HTML"
        except Exception as e:
            UTIL_LOGGER.error(f"Error while filtering HTML: {e}")
            raise
