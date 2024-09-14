import os
import re
import numpy as np
import asyncio  # Add asyncio
import aiohttp
import pandas as pd
import sqlite3, json
from tqdm import tqdm
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict, OrderedDict
from bs4 import BeautifulSoup, Comment

import logging
from logging.handlers import RotatingFileHandler

# --------------------- Logging Configuration ---------------------

# Create a logger for the utilities module
util_logger = logging.getLogger('log')
util_logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels

# Define log format
log_format = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# File handler for DEBUG and higher with rotation
file_handler = RotatingFileHandler(
    filename='../logging/log.log',
    mode='w',
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=3,
    encoding='utf-8',
    delay=0
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_format)

# Stream handler for DEBUG and higher (optional)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.WARNING)
stream_handler.setFormatter(log_format)

# Avoid adding multiple handlers if they already exist
if not util_logger.handlers:
    util_logger.addHandler(file_handler)
    util_logger.addHandler(stream_handler)

# Prevent logs from being propagated to the root logger
util_logger.propagate = False

# --------------------- End of Logging Configuration ---------------------

# <------------------------------------------------------------------------>

# Global Variables
SIMILARITY_THRESHOLD = 0.550  # Ignore any links with embedding cos-similarity less than this
MAX_CONCURRENCY = 4
USE_CACHE = True
WEBPAGE_TIMEOUT = 15000  # milliseconds
LOOKUP_RADIUS = 50000


TARGET_URL_KEYWORDS = [
                'menu', 'food', 'drink', 'bar', 'lunch', 'dinner', 'brunch', 'dessert', 'breakfast', 'nutrition', 'ingredients',
                'order', 'takeout', 'delivery', 'specials', 'catering', 'beverages', 'wine', 'cocktails', 'dish', 'restaurant',
                'happy-hour', 'reservation', 'meals', 'sides', 'entrees', 'appetizers', 'cuisine', 'dining', 'snack', 'side', 'starter',
                'buffet',
            ]


PROMPT_HTML_EXTRACT = f"""Given the HTML content of a restaurant's webpage, extract the menu items in a structured format as follows:
- Each line should represent one menu item.
- Item name and ingredients should be separated by a colon (:).
- Ingredients should be separated by vertical bars (|).
- If there are no ingredients, use 'N/A' after the colon.
- Omit any numbers, special characters, or punctuation.
- Omit any prices, calories, descriptions.
- Maintain the exact formatting shown in the example.

Example format:
```output
Item Name:Ingredient|Ingredient
Item Name with No Ingredients:N/A
```

Important:
- Adhere strictly to the format.
- If no items are found, return only "No menu items found."
- If only one item is found, return it in the format shown.
- DO NOT HALLUCINATE OR MAKE UP ITEMS.

Now, extract the menu items from the following HTML:
```
{{}}
```"""

# What are we looking for?
TARGET_ATTRIBUTES = {
    "name": ["chicken parmesan"],  # Full, common names of the menu item
    "ingredient_1": ["chicken"],
    "ingredient_2": ["parmesan", "mozzarella"],
    "ingredient_3": ["marinara", "tomato", "red"],
}
TARGET_THRESHOLDS = {
    "strict": 0.80,  # Very likely to be a chicken parmesan
    "lenient": 0.70,  # Same ingredients, but not exclusively Chicken Parmesans
    # "explorative": 0.60,  # Very explorative
}

# <------------------------------------------------------------------------>

# Restaurant Lists
RESTAURANT_NAMES_BASE = [
    "Pappadeaux Seafood Kitchen", "Dunkin Donuts", "McDonalds",
    "Whataburger", "Starbucks", "Taco Bell", "Chick-fil-A", "Cocohodo"
]

RESTAURANT_NAMES_COMMON = [
    "Denny's", "IHOP", "Buffalo Wild Wings", "The Capital Grille",
    "Texas Roadhouse", "Outback Steakhouse", "Fogo de Chão", "Steak 48",
    "Pappadeaux Seafood Kitchen", "The Cheesecake Factory", "Morton\'s The Steakhouse",
    "Chama Gaucha Brazilian Steakhouse", "Saltgrass Steakhouse", "Pappas Bros. Steakhouse",
    "Vic & Anthony's", "Brennan's of Houston", "Fleming's Prime Steakhouse",
    "Lucille's", "Cracker Barrel", "Kenny & Ziggy's", "Turner's",
    "Chili's", "Ruth's Chris Steak House", "BJ's Restaurant & Brewhouse",
    "The Melting Pot", "Nancy's Hustle", "Red Lobster",
    "Maggiano's Little Italy", "Olive Garden", "Yard House"
]

RESTAURANT_NAMES_COMMON_2 = [
    "Perry's Steakhouse & Grille", "The Palm", "Seasons 52", "Bonefish Grill",
    "Grimaldi's Pizzeria", "Black Walnut Cafe", "The Union Kitchen",
    "Gringo's Mexican Kitchen", "Eddie V's Prime Seafood", "Landry's Seafood House",
    "Razzoo's Cajun Cafe", "PF Chang's", "Mastro's Steakhouse",
    "Yia Yia Mary's Pappas Greek Kitchen", "Grotto Ristorante",
    "Truluck's Seafood Steak & Crab House", "Carrabba's Italian Grill",
    "Cyclone Anaya's Tex-Mex Cantina", "Del Frisco's Double Eagle Steakhouse",
    "LongHorn Steakhouse", "Papa John's Pizza", "Bubba Gump Shrimp Co.",
    "Rudy's “Country Store” and Bar-B-Q", "Chipotle Mexican Grill",
    "Topgolf", "Pappasito's Cantina", "Five Guys", "Ninfa's on Navigation",
    "Torchy's Tacos"
]

RESTAURANT_NAMES_NICHE = [
    "Lucille's", "Theodore Rex", "The Breakfast Klub", "Crawfish & Noodles",
    "POST Houston", "Kiran's", "B&B Butchers", "Squable", "The Blind Goat",
    "Feges BBQ", "Huynh Restaurant", "Pinkerton's Barbecue", "Kâu Ba",
    "Armando's", "Phat Eatery", "Le Jardinier", "Elro Pizza + Crudo",
    "State of Grace", "Nancy's Hustle", "Truth BBQ", "Bludorn", "Tris",
    "Rosalie Italian Soul", "Xochi", "Killen's Barbecue", "Backstreet Café",
    "Les Noodle", "Uchi"
]

# Select the restaurant list to use
SELECTED_RESTAURANTS = RESTAURANT_NAMES_COMMON_2  # You can modify this as needed

# <------------------------------------------------------------------------>