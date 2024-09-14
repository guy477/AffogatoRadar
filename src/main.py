# main.py

from _utils._util import *
from backend import restaurant_finder, item_matcher
from web import webnode, webscraper, webcrawler

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

async def build_and_parse_tree(restaurants, address, lookup_radius, old_trees):
    """Build and parse trees for the given restaurants."""
    # Initialize components
    restaurant_menu_loc = restaurant_finder.RestaurantMenuLocator()
    scraper = webscraper.WebScraper(
        use_cache=USE_CACHE,
        max_concurrency=MAX_CONCURRENCY,
        webpage_timeout=WEBPAGE_TIMEOUT,
        similarity_threshold=SIMILARITY_THRESHOLD
    )
    crawler = webcrawler.WebCrawler(
        storage_dir="../data",
        use_cache=USE_CACHE,
        scraper=scraper,
        max_concurrency=MAX_CONCURRENCY
    )
    scraped_item_matcher = item_matcher.ItemMatcher(TARGET_ATTRIBUTES)
    await scraped_item_matcher.precompute_attribute_embeddings()

    trees = {}

    for restaurant_name in restaurants:
        util_logger.debug(f"Processing restaurant: {restaurant_name}")
        try:
            # Search for restaurant nearby
            restaurant_data = restaurant_menu_loc.search_restaurants_nearby(address, restaurant_name, lookup_radius)
            if restaurant_data and restaurant_data.get('results'):
                restaurant_results = list(restaurant_data['results'])
                good_local_trees = 0

                while restaurant_results and good_local_trees < 2:
                    first_restaurant = restaurant_results.pop(0)
                    place_id = first_restaurant['place_id']
                    menu_link = restaurant_menu_loc.get_menu(place_id)

                    if menu_link:
                        util_logger.info(f"Found menu link for {restaurant_name}: {menu_link}")
                        new_link = await scraper.source_menu_link(menu_link)

                        if new_link:
                            util_logger.info(f"Crawling and building tree from link: {new_link}")
                            tree = await crawler.start_crawling(new_link, d_limit=3)

                            util_logger.info("Parsing tree...")
                            tree = await scraper.traversal_manager.start_dfs(tree)

                            if tree and len(tree.menu_book) > 0:
                                util_logger.debug(f"Menu items found: {len(tree.menu_book)}")
                                results = await scraped_item_matcher.run_hybrid_similarity_tests(tree.menu_book)
                                for result in results:
                                    if result['combined_score'] > TARGET_THRESHOLDS['strict'] or 'Chicken Parmesan Pizza' in result['scraped_item']:
                                        util_logger.info(f"Menu Item: {result['scraped_item']}")
                                        util_logger.info(f"Ingredients: {', '.join(result['ingredients'])}")
                                        util_logger.info(f"Combined Similarity Score: {result['combined_score']:.4f}")
                                        util_logger.info(f"Attribute Similarity Scores: {result['attribute_scores']}\n")
                                good_local_trees += 1

                            trees[place_id] = tree
                            util_logger.debug(f"Tree constructed and added with place_id: {place_id}")
                        else:
                            util_logger.warning("No forward link found after scraping.")
                    else:
                        util_logger.warning("No source link available for this restaurant.")
            else:
                util_logger.warning(f"No restaurant data found for {restaurant_name}.")

        except Exception as e:
            util_logger.error(f"Error processing restaurant '{restaurant_name}': {e}")

    # Update old trees with new ones
    old_trees.update(trees)
    util_logger.info(f"Total trees after update: {len(old_trees)}")
    return old_trees


async def main():
    """Main function to orchestrate tree building and parsing."""
    
    address = SELECTED_ADDRESS # NOTE: SEE _utils/_config.py
    restaurants = CURATED_PLACES # NOTE: SEE _utils/_config.py

    # Load existing trees
    old_trees = await load_old_trees()

    # Build and parse trees
    updated_trees = await build_and_parse_tree(restaurants, address, LOOKUP_RADIUS, old_trees)

    # Save updated trees
    await save_trees(updated_trees)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        util_logger.critical(f"Program terminated unexpectedly: {e}")
