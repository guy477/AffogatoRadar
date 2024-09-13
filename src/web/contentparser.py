# contentparser.py
from _utils._util import *
import re
from io import BytesIO
import pdfplumber

class ContentParser:
    def __init__(self):
        pass

    def parse_content(self, content, content_type='html'):
        if content_type == 'html':
            return self.parse_html(content)
        elif content_type == 'pdf':
            return self.parse_pdf_content(content)
        else:
            return None

    def parse_html(self, html_content):
        """Filter and parse HTML content."""
        return self.filter_html_for_menu(html_content)

    def parse_pdf_content(self, pdf_bytes):
        """Parse PDF content."""
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text()
        return text

    def filter_html_for_menu(self, html):
        """Aggressively remove HTML elements that are unlikely to contain menu items."""
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.body or soup

        if body:
            remove_tags = ['script', 'style']
            for tag in body(remove_tags):
                tag.decompose()

            for comment in body.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            for element in body.find_all(True):
                element.attrs = {}

            return str(body)
        else:
            return "No <body> tag found in the HTML"