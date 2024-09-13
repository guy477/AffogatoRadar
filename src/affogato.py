import json
import asyncio
import numpy as np
from tqdm import tqdm
from sklearn.metrics.pairwise import cosine_similarity
from backend.llm import LLM

# Load JSON data
file_path = '../data/_trees/trees.json'
cache_file_path = '../data/_trees/affogato_cache.json'

with open(file_path, 'r') as file:
    tree_data = json.load(file)

# Initialize the LLM instance
llm = LLM()

class AffogatoFinder:
    def __init__(self, cache_file):
        self.cache_file = cache_file

        self.affogato_variants = ["affogato", "espresso over ice cream", "coffee float", "gelato affogato", "affogato al caffe", "coffee sundae", 'special affogato']
        self.ice_cream_variants = ["scoop of gelato", "scoop of ice cream", "ice cream", "vanilla ice cream", "vanilla gellato", "gellato"]
        self.espresso_variants = ["espresso", "double espresso", "shot of espresso", "coffee", "hot coffee"]
        self.affogato_cache = self.load_cache()

    def load_cache(self):
        """
        Loads affogato results cache from a JSON file.
        """
        try:
            with open(self.cache_file, 'r') as cache_file:
                return json.load(cache_file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_cache(self):
        """
        Saves affogato results cache to a JSON file.
        """
        with open(self.cache_file, 'w') as cache_file:
            json.dump(self.affogato_cache, cache_file, indent=4)

    async def calculate_similarities_with_labels(self, menu_embeddings, variant_embeddings, variant_labels):
        """
        Calculates the cosine similarity between menu items and variant items and includes the variant labels.
        Returns a list of dictionaries with the similarity and label for each menu item.
        """
        similarities = cosine_similarity(menu_embeddings, variant_embeddings)
        similarity_with_labels = []

        for i in range(similarities.shape[0]):  # Loop over each menu item
            item_similarities = {}
            for j in range(similarities.shape[1]):  # Loop over each variant
                item_similarities[variant_labels[j]] = similarities[i][j]
            similarity_with_labels.append(item_similarities)

        return similarity_with_labels

    async def search_affogato_variants(self, combined_menu_items, menu_embeddings):
        """
        Searches for the highest matching affogato variant in the menu.
        Returns True and the matched item if found, along with cosine similarities.
        """
        affogato_embeddings = await llm.get_embeddings(self.affogato_variants)

        if affogato_embeddings is None or menu_embeddings is None:
            return False, None, None

        affogato_similarities = await self.calculate_similarities_with_labels(menu_embeddings, affogato_embeddings, self.affogato_variants)

        max_similarity = 0
        best_match = None

        # Find the best match by the highest similarity score
        for i in range(len(combined_menu_items)):
            for label, similarity in affogato_similarities[i].items():
                if similarity > max_similarity:
                    max_similarity = similarity
                    best_match = combined_menu_items[i]

        # Return the best match if it exceeds a certain threshold (e.g., 0.75)
        if max_similarity >= 0.75:
            return True, best_match, affogato_similarities

        return False, None, affogato_similarities

    async def search_ice_cream_and_espresso(self, combined_menu_items, menu_embeddings):
        """
        Searches for ice cream and espresso ingredients in the menu.
        Returns True if both ice cream and espresso are found with high similarity scores, and their respective similarities.
        """
        ice_cream_embeddings = await llm.get_embeddings(self.ice_cream_variants)
        espresso_embeddings = await llm.get_embeddings(self.espresso_variants)

        if menu_embeddings is None or ice_cream_embeddings is None or espresso_embeddings is None:
            return False, None, None, None, None

        ice_cream_similarities = await self.calculate_similarities_with_labels(menu_embeddings, ice_cream_embeddings, self.ice_cream_variants)
        espresso_similarities = await self.calculate_similarities_with_labels(menu_embeddings, espresso_embeddings, self.espresso_variants)

        # Find the best matches for both ice cream and espresso
        best_ice_cream_item = None
        best_espresso_item = None
        max_ice_cream_similarity = 0
        max_espresso_similarity = 0

        for i in range(len(combined_menu_items)):
            # Find the highest similarity score for ice cream
            for label, similarity in ice_cream_similarities[i].items():
                if similarity > max_ice_cream_similarity:
                    max_ice_cream_similarity = similarity
                    best_ice_cream_item = combined_menu_items[i]

            # Find the highest similarity score for espresso
            for label, similarity in espresso_similarities[i].items():
                if similarity > max_espresso_similarity:
                    max_espresso_similarity = similarity
                    best_espresso_item = combined_menu_items[i]

        # Return true if both ice cream and espresso have high similarity scores
        if max_ice_cream_similarity >= 0.7 and max_espresso_similarity >= 0.7:
            return True, best_ice_cream_item, best_espresso_item, ice_cream_similarities, espresso_similarities

        return False, None, None, ice_cream_similarities, espresso_similarities

    async def find_affogato(self, menu_book, recalculate=False):
        """
        Checks if a restaurant's menu contains a direct affogato variant or the ingredients to make affogato.
        Stores similarity scores with labels for each menu item and the affogato/ice cream/espresso variants.
        """
        menu_items, menu_descriptions = [], []
        for key, value in menu_book.items():
            menu_items.append(key.lower())
            menu_descriptions.append(value.lower() if isinstance(value, str) else "")

        combined_menu_items = [f"{item} {desc}".strip() for item, desc in zip(menu_items, menu_descriptions)]
        menu_embeddings = await llm.get_embeddings(combined_menu_items)

        # Step 1: Check for direct affogato variants
        found_affogato, affogato_item, affogato_similarities = await self.search_affogato_variants(combined_menu_items, menu_embeddings)
        if found_affogato:
            return True, affogato_item, None, None, affogato_similarities, None

        # Step 2: If no affogato match, check for individual ingredients
        found_ingredients, ice_cream_item, espresso_item, ice_cream_similarities, espresso_similarities = await self.search_ice_cream_and_espresso(combined_menu_items, menu_embeddings)
        
        return found_ingredients, ice_cream_item, espresso_item, ice_cream_similarities, affogato_similarities, espresso_similarities

    async def find_affogato_in_menus(self, tree_data, recalculate=False):
        """
        Iterates through each node in tree_data and checks for affogato ingredients in the menu.
        Caches results to avoid redundant computations. Can recalculate based on a parameter.
        """
        results = []
        for node_key, node in tqdm(tree_data.items()):
            if node_key in self.affogato_cache and not recalculate:
                results.append(self.affogato_cache[node_key])
                continue

            menu_book = node.get('menu_book', None)
            if not menu_book:
                self.affogato_cache[node_key] = {"failure": "No menu_book found"}
                results.append(self.affogato_cache[node_key])
                continue
            
            found_affogato, ice_cream, espresso, ice_cream_similarities, affogato_similarities, espresso_similarities = await self.find_affogato(menu_book, recalculate=recalculate)

            # Cache the results, including the similarity scores for each menu item and the variants
            result = {
                "url": node["url"],
                "found_affogato": found_affogato,
                "most_similar_ice_cream": ice_cream,
                "most_similar_espresso": espresso,
                "menu_items": []
            }

            # Store the similarity scores for each menu item in the dictionary structure
            for i, menu_item in enumerate(menu_book.keys()):
                result["menu_items"].append({
                    "menu_item": menu_item,
                    "affogato_similarities": affogato_similarities[i],
                    "ice_cream_similarities": ice_cream_similarities[i] if ice_cream_similarities else None,
                    "espresso_similarities": espresso_similarities[i] if espresso_similarities else None
                })

            if not found_affogato and not ice_cream and not espresso:
                result["failure"] = "No affogato or ingredients found"

            self.affogato_cache[node_key] = result
            results.append(result)

        # Save the updated cache to disk after processing
        self.save_cache()
        return results

# Create instance of AffogatoFinder
affogato_finder = AffogatoFinder(cache_file_path)

# Test on the tree data root node
async def test_affogato():
    test_tree = {key: tree_data[key] for key in list(tree_data.keys())[:5]} # random n
    affogato_results = await affogato_finder.find_affogato_in_menus(tree_data, recalculate=True)
    return affogato_results

# Run the test
asyncio.run(test_affogato())
