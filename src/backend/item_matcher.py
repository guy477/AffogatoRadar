import os
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from .local_storage import *
from .llm import *
import asyncio

class MenuItemMatcher:
    def __init__(self, target_attributes, attribute_weights=None):
        self.target_attributes = target_attributes
        if attribute_weights is None:
            # Assign equal weights to attributes (excluding 'name')
            self.attribute_weights = {attr: 1 for attr in target_attributes if attr != 'name'}
        else:
            self.attribute_weights = attribute_weights
        
        # Initialize your LocalStorage caching logic
        self.embedding_cache = LocalStorage(db_name='embedding_target_menu.db')

        # Initialize your LLM class
        self.llm = LLM()

        self.attribute_phrase_embeddings = {}

        # self.precompute_attribute_embeddings()

    async def get_phrase_embeddings(self, phrases):
        embeddings = {}
        phrases_to_fetch = []
        for phrase in phrases:
            phrase_lower = phrase.lower()
            cached_embedding = self.embedding_cache.get_data_by_hash(phrase_lower)
            if cached_embedding is not None:
                embeddings[phrase_lower] = np.frombuffer(cached_embedding, dtype=np.float32)
            else:
                phrases_to_fetch.append(phrase_lower)
        if phrases_to_fetch:
            # Get embeddings using your LLM class
            new_embeddings = await self.llm.get_embeddings(phrases_to_fetch)
            for i, phrase in enumerate(phrases_to_fetch):
                embedding = new_embeddings[i]
                embeddings[phrase] = embedding
                # Save to cache
                self.embedding_cache.save_data(
                    phrase,
                    np.array(embedding, dtype=np.float32).tobytes()
                )
        return embeddings

    async def precompute_attribute_embeddings(self):
        unique_phrases = set()
        for phrases in self.target_attributes.values():
            unique_phrases.update([phrase.lower() for phrase in phrases])
        self.attribute_phrase_embeddings = await self.get_phrase_embeddings(list(unique_phrases))

    def get_ngrams(self, text_list, max_n=3):
        ngrams = []
        for text in text_list:
            words = text.lower().split()
            for n in range(1, max_n + 1):
                ngrams.extend([' '.join(words[i:i + n]) for i in range(len(words) - n + 1)])
        return ngrams

    def cosine_sim(self, vec1, vec2):
        return cosine_similarity([vec1], [vec2])[0][0]

    async def calculate_attribute_similarity(self, menu_item_ingredients):
        # Generate n-grams from the list of ingredients
        menu_item_ngrams = self.get_ngrams(menu_item_ingredients)
        menu_item_embeddings = await self.get_phrase_embeddings(menu_item_ngrams)
        attribute_similarity_scores = {}

        
        for attribute, phrases in self.target_attributes.items():
            max_similarity = 0
            for phrase in phrases:
                phrase_lower = phrase.lower()
                phrase_embedding = self.attribute_phrase_embeddings[phrase_lower]
                
                for ngram, ngram_embedding in menu_item_embeddings.items():
                    similarity = self.cosine_sim(ngram_embedding, phrase_embedding)
                    max_similarity = max(max_similarity, similarity)
            attribute_similarity_scores[attribute] = max_similarity

        
        return attribute_similarity_scores

    async def calculate_target_similarity(self, menu_item_name):
        menu_item_embedding = (await self.get_phrase_embeddings([menu_item_name.lower()]))[menu_item_name.lower()]
        max_similarity = 0
        for name in self.target_attributes['name']:
            name_lower = name.lower()
            name_embedding = self.attribute_phrase_embeddings[name_lower]
            similarity = self.cosine_sim(menu_item_embedding, name_embedding)
            max_similarity = max(max_similarity, similarity)
        return max_similarity

    async def hybrid_similarity(self, menu_item_name, menu_item_ingredients, attribute_threshold=0.0, name_similarity_weight=0.5):
        # Calculate attribute similarity

        attribute_similarity_scores = await self.calculate_attribute_similarity(menu_item_ingredients) #if menu_item_ingredients else {}
        # Apply threshold
        passed_attributes = {attr: score if score >= attribute_threshold else 0 for attr, score in attribute_similarity_scores.items()}
        # If no attributes pass and ingredients are provided, similarity is low
        if not any(passed_attributes.values()) and menu_item_ingredients:
            return 0.0, attribute_similarity_scores

        # Weighted attribute score
        total_weight = sum(self.attribute_weights.values())

        
        weighted_attribute_score = sum(
            self.attribute_weights[attr] * passed_attributes[attr] for attr in passed_attributes if attr != 'name'
        ) / total_weight
        
        
        # Calculate target similarity
        target_similarity_score = await self.calculate_target_similarity(menu_item_name)
        
        # Combine scores
        # we have ingredients to consider!
        if menu_item_ingredients:
            combined_score = (target_similarity_score * name_similarity_weight) + \
                                (weighted_attribute_score * (1 - name_similarity_weight))
        else:
            # there are no ingredients to consider -> weighting has no effect
            combined_score = target_similarity_score
        
        return combined_score, attribute_similarity_scores

    async def run_hybrid_similarity_tests(self, menu_items):
        results = []
        for item_name, item_ingredients in menu_items.items():
            combined_score, attribute_scores = await self.hybrid_similarity(item_name, item_ingredients)
            results.append({
                'menu_item': item_name,
                'ingredients': item_ingredients,
                'combined_score': combined_score,
                'attribute_scores': attribute_scores
            })
        return results


if __name__ == "__main__":
    # Example target attributes (e.g., chicken Parmesan)
    target_attributes = {
        "name": ["chicken parmesan"],  # Full, common names of the menu item
        "ingredient_1": ["chicken"],
        "ingredient_2": ["parmesan", "mozzarella"],
        "ingredient_3": ["marinara", "tomato", "red"],
    }

    # Example menu items with ingredients
    menu_items = {
        "classic chicken Parmesan": ["chicken", "parmesan", "tomato sauce"],
        "spaghetti with chicken Parmesan": ["spaghetti", "chicken", "parmesan"],
        "grilled chicken with mozzarella and marinara": ["chicken", "mozzarella", "marinara sauce"],
        "Parmesan-crusted chicken with tomato sauce": ["chicken", "parmesan", "tomato sauce"],
        "baked chicken Parmesan with marinara": ["chicken", "parmesan", "marinara sauce"],
        "fried chicken with mozzarella cheese": ["chicken", "mozzarella"],
        "chicken with tomato and mozzarella": ["chicken", "tomato", "mozzarella"],
        "breaded chicken with red pepper sauce": ["chicken", "breaded", "red pepper sauce"],
        "chicken parm pizza": ["chicken", "parmesan", "pizza dough", "tomato sauce"],

        # Similar ingredients but different dishes
        "eggplant Parmesan": ["eggplant", "parmesan", "tomato sauce"],
        "mozzarella-stuffed chicken": ["chicken", "mozzarella"],
        "chicken Alfredo with Parmesan cheese": ["chicken", "parmesan", "alfredo sauce"],
        "cheesy chicken lasagna": ["chicken", "mozzarella", "lasagna noodles", "tomato sauce"],
        "spaghetti and marinara sauce with mozzarella": ["spaghetti", "mozzarella", "marinara sauce"],
        "grilled chicken with Parmesan cream sauce": ["chicken", "parmesan", "cream sauce"],
        "chicken sandwich with red sauce": ["chicken", "bread", "tomato sauce"],
        "baked ziti with mozzarella and marinara": ["ziti", "mozzarella", "marinara sauce"],
        "rotisserie chicken with Parmesan garnish": ["rotisserie chicken", "parmesan"],
        "pasta with marinara and meatballs": ["pasta", "marinara sauce", "meatballs"],
        
        # Least similar, possibly some shared ingredients
        "chicken piccata": ["chicken", "lemon", "capers", "butter"],
        "grilled chicken with roasted tomatoes": ["chicken", "tomatoes"],
        "tomato and mozzarella salad": ["tomato", "mozzarella", "salad greens"],
        "mozzarella sticks with marinara sauce": ["mozzarella", "breadcrumbs", "marinara sauce"],
        "buffalo chicken dip with cheese": ["chicken", "buffalo sauce", "cheese"],
        "BBQ chicken with cheese": ["chicken", "bbq sauce", "cheddar cheese"]
    }


    matcher = MenuItemMatcher(target_attributes)
    results = asyncio.run(matcher.run_hybrid_similarity_tests(menu_items))
    for result in results:
        print(f"Menu Item: {result['menu_item']}")
        print(f"Ingredients: {', '.join(result['ingredients'])}")
        print(f"Combined Similarity Score: {result['combined_score']:.4f}")
        print(f"Attribute Similarity Scores: {result['attribute_scores']}\n")
    ### NOTE: .75 threshold works for the above set. 