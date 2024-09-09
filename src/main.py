from backend import back_main
from backend import local_storage
from backend import webscraper
from backend import webcrawler
from backend import llm
from bs4 import BeautifulSoup
import asyncio



# Usage
api_key = "***REMOVED***"

address = "Houston, Texas"
# restaurant_name = "Pappadeaux Seafood Kitchen"
# restaurant_name = "Whataburger"
# restaurant_name = "Starbucks"
restaurant_name = "Taco Bell"
radius = 5000

async def main():
    # Initialize local storage
    storage = local_storage.LocalStorage()
    scraper = webscraper.WebScraper(use_cache=True)
    crawler = webcrawler.WebCrawler(storage_dir="../data", use_cache=True, scraper=scraper)

    try:
        # Search for restaurant nearby (check cache first)
        restaurant_data = back_main.search_restaurants_nearby(api_key, address, restaurant_name, radius, db=storage)
        if restaurant_data and restaurant_data['results']:
            first_restaurant = restaurant_data['results'][0]
            place_id = first_restaurant['place_id']
            menu_link = back_main.get_menu(api_key, place_id)

            if menu_link:
                print(f"Menu link: {menu_link}")
                new_link = await scraper.source_menu_link(menu_link)

                if new_link:
                    tree = await crawler.start_crawling(new_link, d_limit=3)
                    print(f"Navigate to: {new_link}")
                else:
                    print("No menu link found.")
            else:
                print("No menu available.")
        else:
            print("Restaurant not found.")

        # if tree:
        #     tree = await scraper.dfs_recursive(tree)
        # else:
        #     print("No data to process.")
        
        # print(tree.menu_book)

    except Exception as e:
        print(f"Error: {e}")
        pass
    
    finally:
        # Close resources
        await scraper.close()
        await crawler.close()
        storage.close()
    
asyncio.run(main())


# def remove_entries(local_storage):
    
#     # Fetch all hash_key and idx pairs
#     local_storage.cursor.execute("SELECT hash_key, idx FROM place_id_map")
#     all_records = local_storage.cursor.fetchall()
    
#     # Iterate over each record and remove the ones containing 'whataburger'
#     for hash_key, idx in all_records:
#         if 'tacobell' in hash_key.lower():  # Case-insensitive check
#             print(f"Removing entry for: {hash_key}")
            
#             # Delete from place_id_map
#             local_storage.cursor.execute("DELETE FROM place_id_map WHERE hash_key = ?", (hash_key,))
            
#             # Delete corresponding data in data_dump
#             local_storage.cursor.execute("DELETE FROM data_dump WHERE id = ?", (idx,))
            
#             # Commit changes
#             local_storage.conn.commit()

#     print("Finished removing entries.")



# if __name__ == "__main__":
#     storage = local_storage.LocalStorage(storage_dir="../data", db_name="source_dest.db")
#     # Remove entries
#     remove_entries(storage)
#     # Close the database connection
#     storage.close()

#     storage = local_storage.LocalStorage(storage_dir="../data", db_name="url_to_html.db")
#     # Remove entries
#     remove_entries(storage)
#     # Close the database connection
#     storage.close()

#     storage = local_storage.LocalStorage(storage_dir="../data", db_name="url_to_menu.db")
#     # Remove entries
#     remove_entries(storage)
#     # Close the database connection
#     storage.close()
