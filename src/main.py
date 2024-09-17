# main.py

from _utils._util import *
from _utils import _webnode
from backend import itemmatcher, placeslocator
from web import webscraper, webcrawler
import pandas as pd

async def load_old_trees(filepath='../_trees/trees.json'):
    """Load existing trees from a JSON file."""
    try:
        with open(filepath, 'r') as f:
            tree_data = json.load(f)
            old_trees = {key: _webnode.WebNode.from_dict(value) for key, value in tree_data.items()}
            UTIL_LOGGER.info(f"Loaded {len(old_trees)} existing trees.")
            return old_trees
    except FileNotFoundError:
        UTIL_LOGGER.warning(f"No existing tree file found at {filepath}. Starting fresh.")
        return {}
    except json.JSONDecodeError as e:
        UTIL_LOGGER.error(f"JSON decode error: {e}. Starting with empty trees.")
        return {}
    except Exception as e:
        UTIL_LOGGER.error(f"Unexpected error while loading trees: {e}. Starting with empty trees.")
        return {}

async def save_trees(trees, filepath='../_trees/trees.json'):
    """Save trees to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump({k: v.to_dict() for k, v in trees.items()}, f, indent=4)
            UTIL_LOGGER.info(f"Saved {len(trees)} trees to {filepath}.")
    except Exception as e:
        UTIL_LOGGER.error(f"Failed to save trees to {filepath}: {e}")



def initialize_components() -> tuple:
    """Initialize and return all necessary components."""
    place_locator = placeslocator.PlaceLocator()
    scraper = webscraper.WebScraper(
        max_concurrency=MAX_CONCURRENCY,
        webpage_timeout=WEBPAGE_TIMEOUT,
        similarity_threshold=SIMILARITY_THRESHOLD
    )
    crawler = webcrawler.WebCrawler(
        scraper=scraper,
        max_concurrency=MAX_CONCURRENCY
    )
    scraped_item_matcher = itemmatcher.ItemMatcher(TARGET_ATTRIBUTES)
    return place_locator, scraper, crawler, scraped_item_matcher


async def search_establishments(
    place_locator: placeslocator.PlaceLocator,
    address: str,
    keyword: str,
    establishment_type: str,
    lookup_radius: int
) -> Dict[str, Any]:
    """Search for establishments nearby based on the provided parameters."""
    UTIL_LOGGER.debug(
        f"Searching establishments with keyword '{keyword}' around '{address}' within radius {lookup_radius}."
    )
    return place_locator.search_establishments_nearby(address, keyword, establishment_type, lookup_radius)


async def process_establishment(
    establishment: Dict[str, Any],
    place_locator: placeslocator.PlaceLocator,
    scraper: webscraper.WebScraper,
    crawler: webcrawler.WebCrawler,
    scraped_item_matcher: itemmatcher.ItemMatcher,
    trees: Dict[str, _webnode.WebNode],
    aggregated_results: list,
    address: str,
    keyword: str,
    establishment_type: str,
    lookup_radius: int,
    good_local_trees: int
) -> int:
    """Process a single establishment: fetch, crawl, parse, and aggregate results."""
    place_id = establishment['place_id']
    website_link = place_locator.get_google_places_url(place_id)

    if website_link:
        UTIL_LOGGER.info(
            f"Found establishment link for {establishment['name']}: {website_link}"
        )
        establishment_url = await scraper.source_establishment_url(website_link)

        if establishment_url:
            UTIL_LOGGER.info(f"Crawling and building tree from link: {establishment_url}")
            tree = await crawler.start_crawling(establishment_url, d_limit=3)

            UTIL_LOGGER.info("Parsing tree...")
            tree = await scraper.web_interpreter.start_dfs(tree)

            if tree and len(tree.menu_book) > 0:
                UTIL_LOGGER.debug(f"Menu items found: {len(tree.menu_book)}")
                results = await scraped_item_matcher.run_hybrid_similarity_tests(tree.menu_book)

                for result in results:
                    aggregated_results.append({
                        'google_url': f"'{website_link}'",
                        'establishment_url': f"'{establishment_url}'",
                        'scraped_item': result.get('scraped_item'),
                        'ingredients': ', '.join(result.get('ingredients', [])),
                        'combined_score': result.get('combined_score'),
                        'attribute_scores': result.get('attribute_scores')
                    })

                good_local_trees += 1

            trees[place_id] = tree
            UTIL_LOGGER.debug(f"Tree constructed and added with place_id: {place_id}")
        else:
            UTIL_LOGGER.warning("No forward link found after scraping.")
    else:
        UTIL_LOGGER.warning("No source link available.")

    return good_local_trees


async def save_aggregated_results(aggregated_results: list) -> None:
    """Save aggregated results to a CSV file."""
    if aggregated_results:
        df = pd.DataFrame(aggregated_results)
        df.sort_values(by='combined_score', ascending=False, inplace=True)
        try:
            df.to_csv('../results.csv', index=False)
            UTIL_LOGGER.info(
                f"Aggregated results saved to ../results.csv with {len(df)} records."
            )
        except Exception as e:
            UTIL_LOGGER.error(f"Failed to save aggregated results to CSV: {e}")


async def build_and_parse_tree(
    keyword: str,
    address: str,
    establishment_type: str,
    lookup_radius: int,
    old_trees: Dict[str, _webnode.WebNode]
) -> Dict[str, _webnode.WebNode]:
    """Build and parse trees."""
    # Initialize components
    place_locator, scraper, crawler, scraped_item_matcher = initialize_components()

    await scraped_item_matcher.precompute_attribute_embeddings()

    trees: Dict[str, _webnode.WebNode] = {}
    aggregated_results: list = []

    UTIL_LOGGER.debug(f"Processing keyword: {keyword}")
    try:
        # Search for establishments nearby
        search_results = await search_establishments(
            place_locator, address, keyword, establishment_type, lookup_radius
        )

        if search_results and search_results.get('results'):
            places_results = list(search_results['results'])
            good_local_trees = 0

            while places_results and good_local_trees < 2:
                establishment = places_results.pop(0)
                good_local_trees = await process_establishment(
                    establishment,
                    place_locator,
                    scraper,
                    crawler,
                    scraped_item_matcher,
                    trees,
                    aggregated_results,
                    address,
                    keyword,
                    establishment_type,
                    lookup_radius,
                    good_local_trees
                )
        else:
            UTIL_LOGGER.warning(f"No establishment found for keyword: {keyword}.")
    except Exception as e:
        UTIL_LOGGER.error(f"Error processing keyword: {keyword}: {e}")

    # Update old trees with new ones
    old_trees.update(trees)
    UTIL_LOGGER.info(f"Total trees after update: {len(old_trees)}")

    # Save aggregated results
    await save_aggregated_results(aggregated_results)

    return old_trees


async def main() -> None:
    """Main function to orchestrate tree building and parsing."""
    address: str = SELECTED_ADDRESS  # NOTE: SEE _utils/_config.py
    keyword: str = SEARCH_REQUEST    # NOTE: SEE _utils/_config.py
    establishment_type: str = ESTABLISHMENT_TYPE  # NOTE: SEE _utils/_config.py

    # Load existing trees
    old_trees = await load_old_trees()

    # Build and parse trees
    updated_trees = await build_and_parse_tree(
        keyword, address, establishment_type, LOOKUP_RADIUS, old_trees
    )

    # Save updated trees
    await save_trees(updated_trees)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        UTIL_LOGGER.critical(f"Program terminated unexpectedly: {e}")