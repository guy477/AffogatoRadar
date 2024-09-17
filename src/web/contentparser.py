# contentparser.py
from _utils._util import *
import re
from io import BytesIO
import pdfplumber

class ContentParser:
    def __init__(self):
        util_logger.info("ContentParser initialized.")

    def parse_content(self, content, content_type='html'):
        util_logger.info(f"Parsing content of type: {content_type}")
        if content_type == 'html':
            try:
                result = self.parse_html(content)
                util_logger.info("HTML content parsed successfully.")
                return result
            except Exception as e:
                util_logger.error(f"Failed to parse HTML content: {e}")
                return None
        elif content_type == 'pdf':
            try:
                result = self.parse_pdf_content(content)
                util_logger.info("PDF content parsed successfully.")
                return result
            except Exception as e:
                util_logger.error(f"Failed to parse PDF content: {e}")
                return None
        else:
            util_logger.warning(f"Unsupported content type received: {content_type}")
            return None

    def parse_html(self, html_content):
        """Filter and parse HTML content."""
        util_logger.debug("Starting HTML parsing.")
        filtered_content = self.filter_html_for_menu(html_content)
        util_logger.debug("HTML content filtered for menu.")
        return filtered_content

    def parse_pdf_content(self, pdf_bytes):
        """Parse PDF content."""
        util_logger.debug("Starting PDF parsing.")
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                num_pages = len(pdf.pages)
                util_logger.info(f"Number of pages in PDF: {num_pages}")
                text = ''
                for i, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text
                        util_logger.debug(f"Extracted text from page {i}.")
                    else:
                        util_logger.warning(f"No text found on page {i}.")
            util_logger.info("Completed PDF parsing.")
            return text
        except Exception as e:
            util_logger.error(f"Error while parsing PDF: {e}")
            raise

    def filter_html_for_menu(self, html):
        """Filter HTML content to extract text for menu items."""
        util_logger.debug("Starting HTML filtering for menu items.")
        try:
            soup = BeautifulSoup(html, 'html.parser')
            body = soup.body or soup
            if body:
                # Extract text content while preserving the text between tags
                filtered_text = body.get_text(separator=' ', strip=True)
                util_logger.info("HTML content filtered successfully.")
                return filtered_text
            else:
                util_logger.warning("No <body> tag found in the HTML.")
                return "No <body> tag found in the HTML"
        except Exception as e:
            util_logger.error(f"Error while filtering HTML: {e}")
            raise
