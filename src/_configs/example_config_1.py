"""
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
USE_GET_CACHE = True  # Enable loading from cache when set to True.
USE_SET_CACHE = True  # Enable saving to cache when set to True.

# <-----------------------Location Settings--------------------------------->
SELECTED_ADDRESS = "Houston, Texas"  # Point of Interest (POI) around which to base your search.
LOOKUP_RADIUS = 500000  # Radius in feet around the SELECTED_ADDRESS to look for CURATED_PLACES.

# <-----------------------Similarity and Timeout Settings-------------------->
SIMILARITY_THRESHOLD = 0.550  # Ignore any links with embedding cosine similarity less than this (see `TARGET_URL_KEYWORDS`).
WEBPAGE_TIMEOUT = 10000  # Time in milliseconds to wait for a webpage to load before throwing a timeout error.

# <-----------------------Search Parameters--------------------------------->
SEARCH_REQUEST = "electronics gadgets"  # Search query term.
ESTABLISHMENT_TYPE = "electronics,store,shop"  # Types of establishments to search for.

# <-----------------------Targeting Attributes--------------------------------->
TARGET_ATTRIBUTES = {  # Attributes of the product of interest.
    "name": ["smartphone", "laptop", "tablet"],  # Full, common names of the product.
    "feature_1": ["battery life", "screen size", "processor"],  # Primary features.
    "feature_2": ["ram", "storage", "camera"],  # Secondary features.
    "feature_3": ["color", "weight", "brand"],  # Tertiary features.
    # "feature_4": [],  # Example of an empty feature list. Add as many features as you deem necessary.
}

# <-----------------------Alternative Target Attributes Examples-------------------->
# What are we looking for?
# TARGET_ATTRIBUTES = {
#     "name": ["gaming console"],  # Full, common names of the product.
#     "feature_1": ["graphics", "storage"],  # Primary features.
#     "feature_2": ["resolution", "connectivity"],  # Secondary features.
#     "feature_3": ["color", "weight"],  # Tertiary features.
# }

# TARGET_ATTRIBUTES = {
#     "name": ["wireless headphones"],  # Full, common names of the product.
#     "feature_1": ["battery life"],  # Primary feature.
#     "feature_2": ["noise cancellation"],  # Secondary feature.
#     "feature_3": [],  # No tertiary features.
# }

# <-----------------------URL Keywords--------------------------------->
TARGET_URL_KEYWORDS = [
    'product', 'electronics', 'gadgets', 'buy', 'shop', 'store', 'price', 'features',
    'specs', 'reviews', 'discount', 'sale', 'new arrivals', 'best sellers', 'offers',
    'deals', 'cart', 'checkout', 'warranty', 'support', 'accessories', 'brands',
    'technology', 'innovation', 'latest', 'trending', 'top rated', 'customer service',
    'shipping', 'returns', 'exchange', 'inventory', 'stock', 'availability'
]

# <-----------------------Prompt Settings--------------------------------->
PROMPT_HTML_EXTRACT = """You're tasked with extracting structured product items from an online store's unstructured webpage text. Please follow these steps carefully:

1. **Product Item Formatting**: Each line represents one product item. The format is:
    - Product name, followed by a colon (:).
    - Features, separated by vertical bars (|). 
    - If no features are listed, use 'N/A'.
  
2. **Text Cleaning**:
    - Omit any numbers, special characters, or punctuation.
    - Ignore prices, ratings, or descriptions.
  
3. **Return Structure**:
    - If no items are found, return: `No product items found`.
    - If only one item is found, format it as described.

4. **Examples**:
    ```output
    Product Name:Feature|Feature
    Product with No Features:N/A
    ```
  
Please ensure that products are copied exactly as seen in the text, with special characters removed. Double-check your work for accuracy.
```
{}
```"""

PROMPT_PDF_EXTRACT = PROMPT_HTML_EXTRACT  # Use the same prompt for PDF extraction. Modify if a different prompt is required.

# <------------------------------------------------------------------------>