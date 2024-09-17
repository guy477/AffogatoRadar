"""
########################################################################
########## HERE YOU CAN SET THE CONFIGURATION FOR THE SEARCH. ##########
########################################################################

SELECTED_ADDRESS = POI around which to based your search.
LOOKUP_RADIUS: (Guessing) Radius in feed around the SELECTED_ADDRESS to look for your `CURATED_PLACES`.

TARGET_URL_KEYWORDS: When crawling, the domain path is passed through an embedding model and compared against this list using CosineSimilarity. URLs with path components having a CosineSimilarity value greater than `SIMILARITY_THRESHOLD` will be explored.
MAX_CONCURRENCY: How many browser/page instances to use at once. Be reasonable.
WEBPAGE_TIMEOUT: How long to wait in milliseconds for a webpage to load before throwing timeout error.

USE_GET_CACHE: Will load from cache when True.
USE_SET_CACHE: Will save to cache when True.

PROMPT_HTML_EXTRACT: The `{{}}` sequence will be replaced with the scraped HTML of each traversed page. Currently returns an itemized list - should be easy to modify and adapt to differnet use cases.

TARGET_ATTRIBUTES: Descriptive attributes representing an item of interest. The fewer, more concrete, ingredients/examples the better. Use single-word exmaples for all but the `name`.
                    (Embedding models work based on semantic relationships, which are rarely qualitative. By decomposing an item to a list of qualities/attributes we get more semantic deminsions to work with)

TARGET_THRESHOLDS: Items of interest with similarity values above these values suggest varrying levels of alignment to the `TARGET_ATTRIBUTES`.

CURATED_PLACES: A list of places around which to base your search.

# NOTE: MORE SETTINGS TO COME...
"""

# <------------------------------------------------------------------------>
SELECTED_ADDRESS = "Houston, Texas"
LOOKUP_RADIUS = 500000

# Global Variables
SIMILARITY_THRESHOLD = 0.550  # Ignore any links with embedding cos-similarity less than this
MAX_CONCURRENCY = 4
WEBPAGE_TIMEOUT = 15000  # milliseconds

SEARCH_REQUEST = f"ukrainian food"
ESTABLISHMENT_TYPE = "food,restaurant,bar"

TARGET_ATTRIBUTES = { # The attributes of the dish you're interested in.
    "name": ["borscht", "borsh"],  # Full, common names of the menu item
    "ingredient_1": ["pork", "chicken", "beef"],  # Single word ingredients
    "ingredient_2": ["beet", "cabbage"],
    "ingredient_3": ["potato", "carrot", "onion"],
    # "ingredient_3": [],
}

# What are we looking for?
# TARGET_ATTRIBUTES = {
#     "name": ["chicken parmesan"],  # Full, common names of the menu item
#     "ingredient_1": ["chicken"],   # Single word ingredients
#     "ingredient_2": ["parmesan", "mozzarella"],
#     "ingredient_3": ["marinara", "tomato", "red"],
# }

# TARGET_ATTRIBUTES = {
#     "name": ["fish and chips"],       # Full, common names of the menu item
#     "ingredient_1": ["fish"],         # Single word ingredients
#     "ingredient_2": ["potatoes"],
#     "ingredient_3": [],
# }


# <------------------------------------------------------------------------>

USE_GET_CACHE = True
USE_SET_CACHE = True

TARGET_URL_KEYWORDS = [
                'menu', 'food', 'drink', 'bar', 'lunch', 'dinner', 'brunch', 'dessert', 'breakfast', 'nutrition', 'ingredients',
                'order', 'takeout', 'delivery', 'specials', 'catering', 'beverages', 'wine', 'cocktails', 'dish', 'restaurant',
                'happy-hour', 'reservation', 'meals', 'sides', 'entrees', 'appetizers', 'cuisine', 'dining', 'snack', 'side', 'starter',
                'buffet'
            ]

PROMPT_HTML_EXTRACT = f"""You're tasked with extracting structured menu items from a restaurant's unstructured webpage text. Please follow these steps carefully:

1. **Menu Item Formatting**: Each line represents one menu item. The format is:
    - Item name, followed by a colon (:).
    - Ingredients, separated by vertical bars (|). 
    - If no ingredients are listed, use 'N/A'.
  
2. **Text Cleaning**:
    - Omit any numbers, special characters, or punctuation.
    - Ignore prices, calories, or descriptions.
  
3. **Return Structure**:
    - If no items are found, return: `No menu items found`.
    - If only one item is found, format it as described.

4. **Examples**:
    ```output
    Item Name:Ingredient|Ingredient
    Item with No Ingredients:N/A
    ```

Please ensure that items are copied exactly as seen in the text, with special characters removed. Double-check your work for accuracy.
```
{{}}
```"""


PROMPT_PDF_EXTRACT = PROMPT_HTML_EXTRACT  # If you want to use a different prompt for PDF extraction, change this.

TARGET_THRESHOLDS = {
    "STRICT": 0.80,  # Very likely to be a chicken parmesan
    "LENIENT": 0.70,  # Same ingredients, but not exclusively Chicken Parmesans
    "EXPLORATIVE": 0.60,  # Very explorative
}

TARGET_THRESHOLD = TARGET_THRESHOLDS['EXPLORATIVE']

# <------------------------------------------------------------------------>