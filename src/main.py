# main.py

from _utils._util import *
from backend import itemmatcher, placeslocator, webnode
from web import webscraper, webcrawler
import pandas as pd

async def load_old_trees(filepath='../data/_trees/trees.json'):
    """Load existing trees from a JSON file."""
    try:
        with open(filepath, 'r') as f:
            tree_data = json.load(f)
            old_trees = {key: webnode.WebNode.from_dict(value) for key, value in tree_data.items()}
            util_logger.info(f"Loaded {len(old_trees)} existing trees.")
            return old_trees
    except FileNotFoundError:
        util_logger.warning(f"No existing tree file found at {filepath}. Starting fresh.")
        return {}
    except json.JSONDecodeError as e:
        util_logger.error(f"JSON decode error: {e}. Starting with empty trees.")
        return {}
    except Exception as e:
        util_logger.error(f"Unexpected error while loading trees: {e}. Starting with empty trees.")
        return {}

async def save_trees(trees, filepath='../data/_trees/trees.json'):
    """Save trees to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump({k: v.to_dict() for k, v in trees.items()}, f, indent=4)
            util_logger.info(f"Saved {len(trees)} trees to {filepath}.")
    except Exception as e:
        util_logger.error(f"Failed to save trees to {filepath}: {e}")

async def build_and_parse_tree(keyword, address, establishment_type, lookup_radius, old_trees):
    """Build and parse trees."""
    # Initialize components
    PlaceLocator = placeslocator.PlaceLocator()
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
    await scraped_item_matcher.precompute_attribute_embeddings()

    trees = {}
    aggregated_results = []


    util_logger.debug(f"Processing keyword: {keyword}")
    try:
        # Search for establishments nearby
        search_results = PlaceLocator.search_establishments_nearby(address, keyword, establishment_type, lookup_radius)

        if search_results and search_results.get('results'):
            places_results = list(search_results['results'])
            good_local_trees = 0

            while places_results and good_local_trees < 2:
                first_establishment = places_results.pop(0)
                place_id = first_establishment['place_id']
                website_link = PlaceLocator.get_google_places_url(place_id)

                if website_link:
                    util_logger.info(f"Found establishment link for {first_establishment['name']}: {website_link}")
                    new_link = await scraper.source_establishment_url(website_link)

                    if new_link:
                        util_logger.info(f"Crawling and building tree from link: {new_link}")
                        tree = await crawler.start_crawling(new_link, d_limit=3)

                        util_logger.info("Parsing tree...")
                        tree = await scraper.traversal_manager.start_dfs(tree)

                        if tree and len(tree.menu_book) > 0:
                            util_logger.debug(f"Menu items found: {len(tree.menu_book)}")
                            results = await scraped_item_matcher.run_hybrid_similarity_tests(tree.menu_book)

                            for result in results:
                                aggregated_results.append({
                                    'keyword': (address, keyword, lookup_radius),
                                    'place_id': place_id,
                                    'scraped_item': result.get('scraped_item'),
                                    'ingredients': ', '.join(result.get('ingredients', [])),
                                    'combined_score': result.get('combined_score'),
                                    'attribute_scores': result.get('attribute_scores')
                                })

                            good_local_trees += 1

                        trees[place_id] = tree
                        util_logger.debug(f"Tree constructed and added with place_id: {place_id}")
                    else:
                        util_logger.warning("No forward link found after scraping.")
                else:
                    util_logger.warning("No source link available.")
        else:
            util_logger.warning(f"No establishment found for keyword: {keyword}.")
    except Exception as e:
        util_logger.error(f"Error processing keyword: {keyword}: {e}")

    # Update old trees with new ones
    old_trees.update(trees)
    util_logger.info(f"Total trees after update: {len(old_trees)}")

    # Create DataFrame and save to CSV
    if aggregated_results:
        df = pd.DataFrame(aggregated_results)
        df.sort_values(by='combined_score', ascending=False, inplace=True)
        try:
            df.to_csv('../results.csv', index=False)
            util_logger.info(f"Aggregated results saved to ../data/results.csv with {len(df)} records.")
        except Exception as e:
            util_logger.error(f"Failed to save aggregated results to CSV: {e}")

    return old_trees


async def main():
    """Main function to orchestrate tree building and parsing."""
    address = SELECTED_ADDRESS # NOTE: SEE _utils/_config.py
    keyword = SEARCH_REQUEST # NOTE: SEE _utils/_config.py
    establishment_type = ESTABLISHMENT_TYPE # NOTE: SEE _utils/_config.py

    # Load existing trees
    old_trees = await load_old_trees()

    # Build and parse trees
    updated_trees = await build_and_parse_tree(keyword, address, establishment_type, LOOKUP_RADIUS, old_trees)

    # Save updated trees
    await save_trees(updated_trees)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        util_logger.critical(f"Program terminated unexpectedly: {e}")
