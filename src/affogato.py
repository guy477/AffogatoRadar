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

# Example async function for testing environment setup
class AffogatoFinder:
    def __init__(self):
        pass

    async def find_affogato(self, menu_book):
        """
        Checks if a restaurant's menu book contains ingredients to make affogato,
        and finds the most similar ingredients for "ice cream" and "espresso."
        """
        target_items = ["ice cream", "espresso"]
        menu_items = [x.lower() for x in list(menu_book.keys())]

        # Get embeddings for menu items and target items
        menu_embeddings = await llm.get_embeddings(menu_items)
        target_embeddings = await llm.get_embeddings(target_items)

        if menu_embeddings is None or target_embeddings is None:
            return False

        # Calculate cosine similarities between menu items and target items
        similarities = cosine_similarity(menu_embeddings, target_embeddings)

        # Find the most similar menu item for both "ice cream" and "espresso"
        ice_cream_sim = np.max(similarities[:, 0])
        espresso_sim = np.max(similarities[:, 1])

        ice_cream_idx = np.argmax(similarities[:, 0])  # Index of most similar to "ice cream"
        espresso_idx = np.argmax(similarities[:, 1])   # Index of most similar to "espresso"

        most_similar_ice_cream = menu_items[ice_cream_idx]
        most_similar_espresso = menu_items[espresso_idx]

        print(f'\nice_cream_sim: {ice_cream_sim} (Most similar ingredient: {most_similar_ice_cream})')
        print(f'espresso_sim: {espresso_sim} (Most similar ingredient: {most_similar_espresso})')

        return ice_cream_sim >= 0.90 and espresso_sim >= 0.90, most_similar_ice_cream, most_similar_espresso

    async def find_affogato_in_menus(self, node_list):
        results = []
        for node in node_list:
            menu_book = node['menu_book']
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
    print(tree_data['ChIJ8V1lbLUgQYYR67H1nckMgio']['menu_book'])
    # root_node = [tree_data['ChIJDb70R4zAQIYRPNqzh7SDJS4']]  # Use the root node for testing
    root_nodes = list(tree_data.values())
    affogato_results = await affogato_finder.find_affogato_in_menus(root_nodes)
    return affogato_results

# Run the test
asyncio.run(test_affogato())
