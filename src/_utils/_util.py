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