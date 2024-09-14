# test_webcrawler.py

import pytest
import pytest_asyncio
from web.webcrawler import WebCrawler
from web.webnode import WebNode
from web.llmhandler import LLMHandler  # Ensure correct import paths
from backend.local_storage import LocalStorage

@pytest_asyncio.fixture
async def setup_crawler():
    """Asynchronous fixture to initialize and clean up the WebCrawler."""
    # Initialize dependencies
    llm_handler = LLMHandler()
    cache = LocalStorage(storage_dir="../data/test", db_name="test_cache.db")
    
    # Initialize the WebCrawler with the scraper set to None or a mocked scraper if necessary
    crawler = WebCrawler(scraper=None, use_cache=True, max_concurrency=2)
    
    # Yield the crawler instance to the test
    yield crawler
    
    # Cleanup after the test
    await crawler.close()
@pytest_asyncio.fixture
async def setup_crawler():
    """Asynchronous fixture to initialize and clean up the WebCrawler."""
    SIMILARITY_THRESHOLD = .8
    crawler = WebCrawler(storage_dir="../data", use_cache=True, max_concurrency=4)
    crawler.scraper.similarity_threshold = SIMILARITY_THRESHOLD
    yield crawler
    await crawler.close()
    
@pytest.mark.asyncio
async def test_crawl_allowed_url(setup_crawler):
    """Test crawling an allowed URL with multiple child links using a robust website."""
    crawler = setup_crawler
    test_url = "https://www.python.org"
    
    # Start crawling with a depth limit of 1
    root_node = await crawler.start_crawling(test_url, d_limit=1)
    
    # Assert that children have been populated
    assert root_node.children is not None, "Root node should have a children list."
    assert len(root_node.children) > 0, "Root node should have at least one child."
    
    # Optionally, verify specific expected links
    expected_links = [
        "https://www.python.org/accounts/login",
        "https://www.python.org/psf/community-stories",
    ]
    crawled_links = [child.url for child in root_node.children]
    for link in expected_links:
        assert link in crawled_links, f"Expected link {link} not found in crawled children."

@pytest.mark.asyncio
async def test_crawl_disallowed_url(setup_crawler):
    """Test crawling a disallowed URL."""
    crawler = setup_crawler
    test_url = "https://robots-txt.com/"

    disallowed_links = [
        "https://robots-txt.com/admin/",
        "https://robots-txt.com/backups/",
        "https://robots-txt.com/data/",
        "https://robots-txt.com/plugins/",
        "https://robots-txt.com/data/uploads/"
    ]
    # Start crawling with a depth limit of 1
    root_node =await crawler.start_crawling(test_url, d_limit=2)
    


    crawled_links = [child.url for child in root_node.children]
    for link in crawled_links:
        assert link not in disallowed_links, f"Disallowed link {link} found in crawled children."
    # Assert that no children have been populated, assuming robots.txt disallows crawling
    # assert len(root_node.children) == 0, "Root node should have no children as URL is disallowed."