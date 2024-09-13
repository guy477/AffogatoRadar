from backend import back_main
from backend import webnode
from backend import webscraper
from backend import webcrawler
from backend import item_matcher

import asyncio, json


# what are we looking for?
target_attributes = {
    "name": ["chicken parmesan"],  # Full, common names of the menu item
    "ingredient_1": ["chicken"],
    "ingredient_2": ["parmesan", "mozzarella"],
    "ingredient_3": ["marinara", "tomato", "red"],
}
target_threshold = .75 # strict
target_threshold = .7  # sounds good!
# target_thxreshold = .6 # very... explorative:)


# Global Variables (TODO: Move to _util.py)
similarity_threshold = 0.550 # Ignore any linkes with embedding cos-similarity less than this
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
    scraper = webscraper.WebScraper(use_cache=use_cache, max_concurrency=max_concurrency, webpage_timeout=webpage_timeout, similarity_threshold=similarity_threshold)
    crawler = webcrawler.WebCrawler(storage_dir="../data", use_cache=use_cache, scraper=scraper, max_concurrency=max_concurrency)
    menu_item_matcher = item_matcher.MenuItemMatcher(target_attributes)
    await menu_item_matcher.precompute_attribute_embeddings()
    
    tree = None
    trees = {}    
    # try:
    for restaurant_name in restaurants:
            # try:
                # Search for restaurant nearby (check cache first)
            restaurant_data = back_main.search_restaurants_nearby(address, restaurant_name, lookup_radius)
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
                                # a tree was returned...
                                if len(tree.menu_book) > 0:
                                    # ... with accumulated menu items
                                    # Lets see if we can find our item!
                                    results = await menu_item_matcher.run_hybrid_similarity_tests(tree.menu_book)
                                    for result in results:
                                        if result['combined_score'] > target_threshold or 'Chicken Parmesan Pizza' in result['menu_item']:
                                            print(f"Menu Item: {result['menu_item']}")
                                            print(f"Ingredients: {', '.join(result['ingredients'])}")
                                            print(f"Combined Similarity Score: {result['combined_score']:.4f}")
                                            print(f"Attribute Similarity Scores: {result['attribute_scores']}\n")
                                    good_local_trees += 1
                                    
                            trees[place_id] = tree
                            print(f"Tree constructed and added to trees: (KEY)=`{place_id}`")
                        else:
                            print("No forward link found.")
                    else:
                        print("No source link available.")

            if not restaurant_data and not tree:
                print(f"No restaurants available not found. {restaurant_data}")
        
    #         except Exception as e:
    #             print(f"Error With Restaurant ({restaurant_name}): {e}")

    # except Exception as e:
    #     print(f"CRITICAL ERROR: {e}")
    
    # finally:
    #     # Close resources
    #     await scraper.close()
    #     await crawler.close()

    print(trees)
    old_trees.update(trees)

# Define search parameters
address = "Houston, Texas"
restaurant_names_base = ["Pappadeaux Seafood Kitchen", "Dunkin Donuts", "McDonalds", "Whataburger", "Starbucks", "Taco Bell", "Chick-fil-A", "Cocohodo"]
restaurant_names_common = ['Denny\'s', 'IHOP', 'Buffalo Wild Wings', 'The Capital Grille', 'Texas Roadhouse', 'Outback Steakhouse', 'Fogo de Chão', 'Steak 48', 'Pappadeaux Seafood Kitchen', 'The Cheesecake Factory', 'Morton\'s The Steakhouse', 'Chama Gaucha Brazilian Steakhouse', 'Saltgrass Steakhouse', 'Pappas Bros. Steakhouse', 'Vic & Anthony\'s', 'Brennan\'s of Houston', 'Fleming\'s Prime Steakhouse', 'Lucille\'s', 'Cracker Barrel', 'Kenny & Ziggy\'s', 'Turner\'s', 'Chili\'s', 'Ruth\'s Chris Steak House', 'BJ\'s Restaurant & Brewhouse', 'The Melting Pot', 'Nancy\'s Hustle', 'Red Lobster', 'Maggiano\'s Little Italy', 'Olive Garden', 'Yard House']
restaurant_names_common_2 = ['Perry\'s Steakhouse & Grille', 'The Palm', 'Seasons 52', 'Bonefish Grill', 'Grimaldi\'s Pizzeria', 'Black Walnut Cafe', 'The Union Kitchen', 'Gringo\'s Mexican Kitchen', 'Eddie V\'s Prime Seafood', 'Landry\'s Seafood House', 'Razzoo\'s Cajun Cafe', 'PF Chang\'s', 'Mastro\'s Steakhouse', 'Yia Yia Mary\'s Pappas Greek Kitchen', 'Grotto Ristorante', 'Truluck\'s Seafood Steak & Crab House', 'Carrabba\'s Italian Grill', 'Cyclone Anaya\'s Tex-Mex Cantina', 'Del Frisco\'s Double Eagle Steakhouse', 'LongHorn Steakhouse', 'Papa John\'s Pizza', 'Bubba Gump Shrimp Co.', 'Rudy\'s “Country Store” and Bar-B-Q', 'Chipotle Mexican Grill', 'Topgolf', 'Pappasito\'s Cantina', 'Saltgrass Steakhouse', 'Five Guys', 'Ninfa\'s on Navigation', 'Torchy\'s Tacos']
restaurant_names_niche = ['Theodore Rex', 'Lucille\'s', 'The Breakfast Klub', 'Crawfish & Noodles', 'POST Houston', 'Kiran\'s', 'B&B Butchers', 'Squable', 'The Blind Goat', 'Feges BBQ', 'Huynh Restaurant', 'Pinkerton\'s Barbecue', 'Kâu Ba', 'Armando\'s', 'Phat Eatery', 'Le Jardinier', 'Elro Pizza + Crudo', 'State of Grace', 'Nancy\'s Hustle', 'Pappadeaux Seafood Kitchen', 'Truth BBQ', 'Bludorn', 'Kenny & Ziggy\'s', 'Tris', 'Rosalie Italian Soul', 'Xochi', 'Killen\'s Barbecue', 'Backstreet Café', 'Les Noodle', 'Uchi']
restaurant_names = restaurant_names_niche + restaurant_names_base + restaurant_names_common + restaurant_names_common_2

webpage_timeout = 15000 # milliseconds
radius = 50000

# Run the main function
asyncio.run(build_and_parse_tree(restaurants=restaurant_names, address=address, lookup_radius=radius))

# After constructing the trees
with open('../data/_trees/trees.json', 'w') as f:
    json.dump({k: v.to_dict() for k, v in old_trees.items()}, f, indent=4) 
