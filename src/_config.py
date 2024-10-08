""" SEE `_configs/` FOR EXAMPLES.

####################################################################################################
########################### Configuration for Search Functionality #################################
####################################################################################################

This configuration file allows you to set and adjust various parameters that control the behavior of the search process. 

Sections:
1. **Global Settings**: Controls overall concurrency and caching behaviors.
2. **Location Settings**: Defines the geographical focus of the search.
3. **Similarity and Timeout Settings**: Determines how URLs are evaluated and sets load time limits.
4. **Search Parameters**: Specifies the search query and types of establishments to target.
5. **Targeting Attributes**: Defines the descriptive attributes for items of interest.
6. **URL Keywords**: Lists keywords used to filter and explore URLs during crawling.
7. **Prompt Settings**: Contains prompts used for extracting information from HTML and PDF content.
8. **Similarity Thresholds**: Sets thresholds for aligning items with target attributes.

# NOTE: MORE SETTINGS TO COME...
"""

# <-----------------------Global Settings--------------------------------->
MAX_CONCURRENCY = 4  # Maximum number of browser/page instances to use concurrently.
USE_GET_CACHE = False  # Enable loading from cache when set to True.
USE_SET_CACHE = False  # Enable saving to cache when set to True.

# <-----------------------Location Settings--------------------------------->
SELECTED_ADDRESS = "Houston, Texas"  # Point of Interest (POI) around which to base your search.
LOOKUP_RADIUS = 16093  # Radius in meters around the SELECTED_ADDRESS to look for CURATED_PLACES.

# <-----------------------Similarity and Timeout Settings-------------------->
SIMILARITY_THRESHOLD = 0.550  # Ignore any links with embedding cosine similarity less than this (see `TARGET_URL_KEYWORDS`).
WEBPAGE_TIMEOUT = 10000  # Time in milliseconds to wait for a webpage to load before throwing a timeout error.
DEPTH_LIMIT = 3  # Depth limit for the crawler.

# <-----------------------Search Parameters--------------------------------->
SEARCH_REQUEST = "ukrainian"  # Search query term.
ESTABLISHMENT_TYPES = ["food", "restaurant", "bar"]  # Types of establishments to search for.

# <-----------------------Targeting Attributes--------------------------------->
TARGET_ATTRIBUTES = {  # Attributes of the dish of interest.
    "name": ["borscht", "borsh", "ukrainian borsh"],  # Full, common names of the menu item.
    "ingredient_1": ["pork", "chicken", "beef"],  # Primary ingredients.
    "ingredient_2": ["beet", "cabbage"],  # Secondary ingredients.
    "ingredient_3": ["potato", "carrot", "onion"],  # Tertiary ingredients.
    # "ingredient_4": [],  # Example of an empty ingredient list. Add as many ingredients as you deem necessary.
}

# <-----------------------Alternative Target Attributes Examples-------------------->
# What are we looking for?
# TARGET_ATTRIBUTES = {
#     "name": ["chicken parmesan"],  # Full, common names of the menu item.
#     "ingredient_1": ["chicken"],  # Primary ingredient.
#     "ingredient_2": ["parmesan", "mozzarella"],  # Secondary ingredients.
#     "ingredient_3": ["marinara", "tomato", "red"],  # Tertiary ingredients.
# }

# TARGET_ATTRIBUTES = {
#     "name": ["fish and chips"],  # Full, common names of the menu item.
#     "ingredient_1": ["fish"],  # Primary ingredient.
#     "ingredient_2": ["potatoes"],  # Secondary ingredient.
#     "ingredient_3": [],  # No tertiary ingredients.
# }

# <-----------------------URL Keywords--------------------------------->
TARGET_URL_KEYWORDS = [
    'menu', 'food', 'drink', 'bar', 'lunch', 'dinner', 'brunch', 'dessert', 'breakfast',
    'nutrition', 'ingredients', 'order', 'takeout', 'delivery', 'specials', 'catering',
    'beverages', 'wine', 'cocktails', 'dish', 'restaurant', 'happy-hour', 'reservation',
    'meals', 'sides', 'entrees', 'appetizers', 'cuisine', 'dining', 'snack', 'side',
    'starter', 'buffet'
]

# <-----------------------Prompt Settings--------------------------------->
PROMPT_HTML_EXTRACT = """You're tasked with extracting structured menu items from a restaurant's unstructured webpage text. Please follow these steps carefully:

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
{}
```"""

PROMPT_PDF_EXTRACT = PROMPT_HTML_EXTRACT  # Use the same prompt for PDF extraction. Modify if a different prompt is required.

# <------------------------------------------------------------------------>