from _utils._util import *
from .local_storage import *
from .llm import *

from tqdm.asyncio import tqdm

class ItemMatcher:
    def __init__(self, target_attributes, attribute_weights=None):
        util_logger.info("Initializing ItemMatcher class.")
        self.target_attributes = target_attributes
        util_logger.debug(f"Target attributes: {list(self.target_attributes.keys())}")

        if attribute_weights is None:
            # Assign equal weights to attributes (excluding 'name')
            self.attribute_weights = {attr: 1 for attr in target_attributes if attr != 'name'}
            util_logger.info("No attribute weights provided. Assigned equal weights to attributes.")
        else:
            self.attribute_weights = attribute_weights
            util_logger.info("Attribute weights provided and assigned.")
            util_logger.debug(f"Attribute weights: {self.attribute_weights}")
        
        # Initialize LocalStorage caching logic
        self.embedding_cache = LocalStorage(db_name='embedding_target_menu.db')
        util_logger.info("Initialized LocalStorage for embedding caching.")

        # Initialize LLM class
        self.llm = LLM()
        util_logger.info("Initialized LLM for embeddings.")

        self.attribute_phrase_embeddings = {}
        util_logger.debug("Attribute phrase embeddings initialized as empty dictionary.")

        # Uncomment if precomputing embeddings at initialization
        # self.precompute_attribute_embeddings()

    async def get_phrase_embeddings(self, phrases):
        util_logger.info("Fetching phrase embeddings.")
        embeddings = {}
        phrases_to_fetch = []
        cache_hits = 0
        cache_misses = 0

        for phrase in phrases:
            phrase_lower = phrase.lower()
            cached_embedding = self.embedding_cache.get_data_by_hash(phrase_lower)
            if cached_embedding is not None:
                embeddings[phrase_lower] = np.frombuffer(cached_embedding, dtype=np.float32)
                cache_hits += 1
            else:
                phrases_to_fetch.append(phrase_lower)
                cache_misses += 1

        util_logger.debug(f"Cache hits: {cache_hits}, Cache misses: {cache_misses} out of {len(phrases)} phrases.")

        if phrases_to_fetch:
            util_logger.info(f"Fetching {len(phrases_to_fetch)} new embeddings from LLM.")
            try:
                new_embeddings = await self.llm.get_embeddings(phrases_to_fetch)
                for i, phrase in enumerate(phrases_to_fetch):
                    embedding = new_embeddings[i]
                    embeddings[phrase] = embedding
                    # Save to cache
                    self.embedding_cache.save_data(
                        phrase,
                        np.array(embedding, dtype=np.float32).tobytes()
                    )
                util_logger.info(f"Fetched and cached {len(phrases_to_fetch)} new embeddings.")
            except Exception as e:
                util_logger.error(f"Error fetching embeddings from LLM: {e}")
                raise e

        return embeddings

    async def precompute_attribute_embeddings(self):
        util_logger.info("Precomputing attribute phrase embeddings.")
        unique_phrases = set()
        for phrases in self.target_attributes.values():
            unique_phrases.update([phrase.lower() for phrase in phrases])
        util_logger.debug(f"Number of unique phrases to embed: {len(unique_phrases)}")

        try:
            self.attribute_phrase_embeddings = await self.get_phrase_embeddings(list(unique_phrases))
            util_logger.info("Precomputed and stored attribute phrase embeddings successfully.")
        except Exception as e:
            util_logger.error(f"Failed to precompute attribute embeddings: {e}")
            raise e

    def get_ngrams(self, text_list, max_n=3):
        util_logger.debug(f"Generating n-grams for a list of {len(text_list)} texts with max_n={max_n}.")
        ngrams = []
        for text in text_list:
            words = text.lower().split()
            for n in range(1, max_n + 1):
                ngrams.extend([' '.join(words[i:i + n]) for i in range(len(words) - n + 1)])
        util_logger.debug(f"Generated {len(ngrams)} n-grams.")
        return ngrams

    def cosine_sim(self, vec1, vec2):
        try:
            similarity = cosine_similarity([vec1], [vec2])[0][0]
            return similarity
        except Exception as e:
            util_logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    async def calculate_attribute_similarity(self, scraped_item_ingredients):
        util_logger.info("Calculating attribute similarity.")
        scraped_item_ngrams = self.get_ngrams(scraped_item_ingredients)
        util_logger.debug(f"Generated {len(scraped_item_ngrams)} n-grams from scraped item ingredients.")

        try:
            scraped_item_embeddings = await self.get_phrase_embeddings(scraped_item_ngrams)
            util_logger.debug("Obtained embeddings for scraped item n-grams.")
        except Exception as e:
            util_logger.error(f"Failed to get embeddings for scraped item: {e}")
            raise e

        attribute_similarity_scores = {}
        util_logger.info(f"Calculating similarity scores for {len(self.target_attributes)} attributes.")

        for attribute, phrases in self.target_attributes.items():
            max_similarity = 0
            for phrase in phrases:
                phrase_lower = phrase.lower()
                phrase_embedding = self.attribute_phrase_embeddings.get(phrase_lower)
                if phrase_embedding is None:
                    util_logger.warning(f"Embedding for phrase '{phrase_lower}' not found.")
                    continue
                
                for ngram, ngram_embedding in scraped_item_embeddings.items():
                    similarity = self.cosine_sim(ngram_embedding, phrase_embedding)
                    if similarity > max_similarity:
                        max_similarity = similarity
            attribute_similarity_scores[attribute] = max_similarity
            util_logger.debug(f"Attribute '{attribute}' similarity score: {max_similarity:.4f}")

        util_logger.info("Completed attribute similarity calculations.")
        return attribute_similarity_scores

    async def calculate_target_similarity(self, scraped_item_name):
        util_logger.info("Calculating target similarity based on item name.")
        try:
            scraped_item_embedding = (await self.get_phrase_embeddings([scraped_item_name.lower()]))[scraped_item_name.lower()]
            util_logger.debug(f"Obtained embedding for scraped item name '{scraped_item_name.lower()}'.")
        except Exception as e:
            util_logger.error(f"Failed to get embedding for scraped item name '{scraped_item_name}': {e}")
            raise e

        max_similarity = 0
        for name in self.target_attributes.get('name', []):
            name_lower = name.lower()
            name_embedding = self.attribute_phrase_embeddings.get(name_lower)
            if name_embedding is None:
                util_logger.warning(f"Embedding for target name '{name_lower}' not found.")
                continue
            similarity = self.cosine_sim(scraped_item_embedding, name_embedding)
            if similarity > max_similarity:
                max_similarity = similarity
        util_logger.debug(f"Target similarity score: {max_similarity:.4f}")
        return max_similarity

    async def hybrid_similarity(self, scraped_item_name, scraped_item_ingredients, attribute_threshold=0.0, name_similarity_weight=0.5):
        util_logger.info(f"Calculating hybrid similarity for item '{scraped_item_name}'.")
        try:
            attribute_similarity_scores = await self.calculate_attribute_similarity(scraped_item_ingredients)
            util_logger.debug(f"Attribute similarity scores: {attribute_similarity_scores}")
        except Exception as e:
            util_logger.error(f"Error calculating attribute similarity: {e}")
            raise e

        # Apply threshold
        passed_attributes = {attr: score if score >= attribute_threshold else 0 for attr, score in attribute_similarity_scores.items()}
        util_logger.debug(f"Passed attributes after applying threshold {attribute_threshold}: {passed_attributes}")

        # If no attributes pass and ingredients are provided, similarity is low
        if not any(passed_attributes.values()) and scraped_item_ingredients:
            util_logger.info(f"No attributes passed the threshold for item '{scraped_item_name}'. Returning similarity score 0.0.")
            return 0.0, attribute_similarity_scores

        # Weighted attribute score
        total_weight = sum(self.attribute_weights.values())
        if total_weight == 0:
            util_logger.error("Total attribute weight is zero. Cannot compute weighted attribute score.")
            raise ValueError("Total attribute weight must be greater than zero.")

        weighted_attribute_score = sum(
            self.attribute_weights[attr] * passed_attributes[attr] for attr in passed_attributes if attr != 'name'
        ) / total_weight
        util_logger.debug(f"Weighted attribute score: {weighted_attribute_score:.4f}")

        # Calculate target similarity
        try:
            target_similarity_score = await self.calculate_target_similarity(scraped_item_name)
            util_logger.debug(f"Target similarity score: {target_similarity_score:.4f}")
        except Exception as e:
            util_logger.error(f"Error calculating target similarity: {e}")
            raise e

        # Combine scores
        if scraped_item_ingredients:
            combined_score = (target_similarity_score * name_similarity_weight) + \
                             (weighted_attribute_score * (1 - name_similarity_weight))
            util_logger.debug(f"Combined similarity score with ingredients: {combined_score:.4f}")
        else:
            combined_score = target_similarity_score
            util_logger.debug(f"Combined similarity score without ingredients: {combined_score:.4f}")

        return combined_score, attribute_similarity_scores

    async def run_hybrid_similarity_tests(self, scraped_items):
        util_logger.info(f"Starting hybrid similarity tests for {len(scraped_items)} scraped items.")
        results = []
        try:
            async for item in tqdm(scraped_items.items(), desc='Calculating scraped_item Embeddings (this can take a while)....'):
                item_name, item_ingredients = item
                try:
                    combined_score, attribute_scores = await self.hybrid_similarity(item_name, item_ingredients)
                    results.append({
                        'scraped_item': item_name,
                        'ingredients': item_ingredients,
                        'combined_score': combined_score,
                        'attribute_scores': attribute_scores
                    })
                    util_logger.debug(f"Processed item '{item_name}' with combined score {combined_score:.4f}.")
                except Exception as e:
                    util_logger.error(f"Failed to process item '{item_name}': {e}")
        except Exception as e:
            util_logger.error(f"Error during hybrid similarity tests: {e}")
            raise e

        util_logger.info("Completed hybrid similarity tests.")
        return results


if __name__ == "__main__":
    # Configure logging level (can be adjusted as needed)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    # Example target attributes (e.g., chicken Parmesan)
    target_attributes = {
        "name": ["chicken parmesan"],  # Full, common names of the menu item
        "ingredient_1": ["chicken"],
        "ingredient_2": ["parmesan", "mozzarella"],
        "ingredient_3": ["marinara", "tomato", "red"],
    }

    # Example menu items with ingredients
    scraped_items = {
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

    matcher = ItemMatcher(target_attributes)

    # Optionally precompute embeddings at startup
    # asyncio.run(matcher.precompute_attribute_embeddings())

    try:
        results = asyncio.run(matcher.run_hybrid_similarity_tests(scraped_items))
        util_logger.info("Hybrid similarity testing completed. Displaying results:")
        for result in results:
            print(f"Menu Item: {result['scraped_item']}")
            print(f"Ingredients: {', '.join(result['ingredients'])}")
            print(f"Combined Similarity Score: {result['combined_score']:.4f}")
            print(f"Attribute Similarity Scores: {result['attribute_scores']}\n")
        ### NOTE: .75 threshold works for the above set. 
    except Exception as e:
        util_logger.error(f"An error occurred during the matching process: {e}")
