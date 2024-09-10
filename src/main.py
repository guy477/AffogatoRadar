from backend import back_main
from backend import webnode
from backend import webscraper
from backend import webcrawler
from _deleter import __DELETER_

import asyncio, json



# __DELETER_('source_dest.db', 'clover')
# __DELETER_('llm_relevance.db', 'clover')
# __DELETER_('url_to_html.db', 'clover')
# __DELETER_('url_to_menu.db', 'clover')
# __DELETER_('embedding_relevance.db', 'clover')
# exit(1)

# Global Variables (TODO: Move to _util.py)
max_concurrency = 4
use_cache = True

# Load old trees
try:
    with open('../data/_trees/trees.json', 'r') as f:
        tree_data = json.load(f)
        # old_trees = tree_data
        old_trees = {_: webnode.WebNode.from_dict(tree_dict) for _, tree_dict in tree_data.items()}
except Exception as e:
    print(f"Error: {e}")
    old_trees = {}


async def build_and_parse_tree(restaurants: list, address: str, lookup_radius: int):
    # Initialize local storage
    scraper = webscraper.WebScraper(use_cache=use_cache, max_concurrency=max_concurrency, webpage_timeout=webpage_timeout)
    crawler = webcrawler.WebCrawler(storage_dir="../data", use_cache=use_cache, scraper=scraper, max_concurrency=max_concurrency)
    trees = {}
    
    try:
        for restaurant_name in restaurants:
            try:
                # Search for restaurant nearby (check cache first)
                restaurant_data = back_main.search_restaurants_nearby(address, restaurant_name, lookup_radius)
                # print(restaurant_data)
                if restaurant_data and restaurant_data['results']:
                    restaurant_data = list(restaurant_data['results'])

                    good_local_trees = 0
                    
                    while restaurant_data and good_local_trees < 2:
                        first_restaurant = restaurant_data.pop(0)
                        place_id = first_restaurant['place_id']
                        menu_link = back_main.get_menu(place_id)

                        if menu_link:
                            print(f"Menu link: {menu_link}")
                            new_link = await scraper.source_menu_link(menu_link)

                            if new_link:
                                print("Crawling Links & Building Tree...")
                                tree = await crawler.start_crawling(new_link, d_limit=3)
                                
                                print("Parsing tree...")
                                tree = await scraper.start_dfs(tree)
                                
                                if tree:
                                    if len(tree.children) > 0:
                                        good_local_trees += 1
                                trees[place_id] = tree
                                print(f"Tree constructed and added to trees: (KEY)=`{place_id}`")
                            else:
                                print("No forward link found.")
                        else:
                            print("No source link available.")

                if not restaurant_data and not tree:
                    print(f"No restaurants available not found. {restaurant_data}")
            
            except Exception as e:
                print(f"Error With Restaurant ({restaurant_name}): {e}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    
    finally:
        # Close resources
        await scraper.close()
        await crawler.close()

    print(trees)
    old_trees.update(trees)

# Define search parameters
address = "Houston, Texas"
restaurant_names = ["Pappadeaux Seafood Kitchen", "Dunkin Donuts", "McDonalds", "Whataburger", "Starbucks", "Taco Bell", "Chick-fil-A", "Cocohodo"]
# restaurant_names = ["Cocohodo"]
webpage_timeout = 12500 # milliseconds
radius = 50000

# Run the main function
asyncio.run(build_and_parse_tree(restaurants=restaurant_names, address=address, lookup_radius=radius))

# After constructing the trees
with open('../data/_trees/trees.json', 'w') as f:
    json.dump({k: v.to_dict() for k, v in old_trees.items()}, f, indent=4) 
