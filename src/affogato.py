import json
import asyncio
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from backend.llm import LLM

# Load JSON data
file_path = '../data/_trees/trees.json'
with open(file_path, 'r') as file:
    tree_data = json.load(file)

# Initialize the LLM instance
llm = LLM()

class AffogatoFinder:
    def __init__(self):
        # Variants for ice cream and espresso
        self.ice_cream_variants = ["scoop of gelato", "scoop of ice cream", "ice cream", "vanilla ice cream", "vanilla gellato", "gellato"]
        self.espresso_variants = ["espresso", "double espresso", "shot of espresso", "coffee", "hot coffee"]
    
    async def average_embeddings(self, target_items):
        """
        Get the average embedding for a list of target items (i.e. variations of "ice cream" or "espresso").
        """
        target_embeddings = await llm.get_embeddings(target_items)
        if target_embeddings is None:
            return None
        return np.mean(target_embeddings, axis=0)  # Calculate the average embedding
    
    async def find_affogato(self, menu_book):
        """
        Checks if a restaurant's menu book contains ingredients to make affogato,
        and finds the most similar ingredients for "ice cream" and "espresso."
        Considers both menu item names and their descriptions.
        """
        menu_items = []
        menu_descriptions = []

        # Combine menu item names with their descriptions for embedding
        for key, value in menu_book.items():
            menu_items.append(key.lower())
            if isinstance(value, str):
                menu_descriptions.append(value.lower())  # Append descriptions
            else:
                menu_descriptions.append("")  # If no description available, use an empty string

        combined_menu_items = [f"{item} {desc}".strip() for item, desc in zip(menu_items, menu_descriptions)]

        # Get embeddings for combined menu items and average embeddings for target items
        menu_embeddings = await llm.get_embeddings(combined_menu_items)
        ice_cream_embedding = await self.average_embeddings(self.ice_cream_variants)
        espresso_embedding = await self.average_embeddings(self.espresso_variants)

        if menu_embeddings is None or ice_cream_embedding is None or espresso_embedding is None:
            return False

        # Calculate cosine similarities between menu items and target embeddings
        ice_cream_similarities = cosine_similarity(menu_embeddings, ice_cream_embedding.reshape(1, -1))
        espresso_similarities = cosine_similarity(menu_embeddings, espresso_embedding.reshape(1, -1))

        # Check for items where similarity to both ice cream and espresso is too close
        valid_items = []
        for i in range(len(combined_menu_items)):
            ice_cream_sim = ice_cream_similarities[i][0]
            espresso_sim = espresso_similarities[i][0]

            # Ignore items where the similarities are too close (i.e., difference < 0.1)
            # if abs(ice_cream_sim - espresso_sim) >= 0.1:
            valid_items.append((i, ice_cream_sim, espresso_sim))

        # If no valid items, return False
        if not valid_items:
            return False

        # Find the most similar valid menu item for both "ice cream" and "espresso"
        ice_cream_item = max(valid_items, key=lambda x: x[1])  # Max similarity to ice cream
        espresso_item = max(valid_items, key=lambda x: x[2])   # Max similarity to espresso

        ice_cream_idx, ice_cream_sim, _ = ice_cream_item
        espresso_idx, _, espresso_sim = espresso_item

        most_similar_ice_cream = combined_menu_items[ice_cream_idx]
        most_similar_espresso = combined_menu_items[espresso_idx]

        print(f'\nice_cream_sim: {ice_cream_sim} (Most similar ingredient: {most_similar_ice_cream})')
        print(f'espresso_sim: {espresso_sim} (Most similar ingredient: {most_similar_espresso})')

        return ice_cream_sim >= 0.7 and espresso_sim >= 0.7, most_similar_ice_cream, most_similar_espresso

    async def find_affogato_in_menus(self, node_list):
        """
        Loops through each node's menu book and checks if affogato ingredients are found.
        """
        results = []
        for node in node_list:
            menu_book = node.get('menu_book', None)
            if not menu_book:
                continue
            
            found_affogato, ice_cream_ingredient, espresso_ingredient = await self.find_affogato(menu_book)

            if found_affogato:
                results.append({
                    "url": node["url"],
                    "most_similar_ice_cream": ice_cream_ingredient,
                    "most_similar_espresso": espresso_ingredient
                })
                print(f'Affogato found at this menu: {node["url"]}')
                print(f'Most similar to ice cream: {ice_cream_ingredient}')
                print(f'Most similar to espresso: {espresso_ingredient}')
            else:
                print(f'No affogato found at this menu: {node["url"]}')
        return results


# Create instance of AffogatoFinder
affogato_finder = AffogatoFinder()

# Test on the tree data root node
async def test_affogato():
    # print(tree_data['ChIJ8V1lbLUgQYYR67H1nckMgio']['menu_book'])
    root_nodes = list(tree_data.values())  # Use the root nodes for testing
    affogato_results = await affogato_finder.find_affogato_in_menus(root_nodes)
    return affogato_results

# Run the test
asyncio.run(test_affogato())
