from _utils._util import *
from web.cachemanager import CacheManager
from .llm import *

class ItemMatcher:
    def __init__(self, target_attributes, attribute_weights=None):
        UTIL_LOGGER.info("Initializing ItemMatcher class.")
        self.target_attributes = target_attributes
        UTIL_LOGGER.debug(f"Target attributes: {list(self.target_attributes.keys())}")

        if attribute_weights is None:
            # Assign equal weights to attributes (excluding 'name')
            self.attribute_weights = {attr: 1 for attr in target_attributes if attr != 'name'}
            UTIL_LOGGER.info("No attribute weights provided. Assigned equal weights to attributes.")
        else:
            self.attribute_weights = attribute_weights
            UTIL_LOGGER.info("Attribute weights provided and assigned.")
            UTIL_LOGGER.debug(f"Attribute weights: {self.attribute_weights}")
        
        # Initialize CacheManager
        self.cache_manager = CacheManager()
        UTIL_LOGGER.info("Initialized CacheManager for embedding caching.")

        # Initialize LLM class
        self.llm = LLM()
        UTIL_LOGGER.info("Initialized LLM for embeddings.")

        self.attribute_phrase_embeddings = {}
        UTIL_LOGGER.debug("Attribute phrase embeddings initialized as empty dictionary.")

    async def get_phrase_embeddings(self, phrases):
        UTIL_LOGGER.debug("Fetching phrase embeddings.")
        embeddings = {}
        phrases_to_fetch = []
        cache_hits = 0
        cache_misses = 0

        # Normalize phrases to lowercase and strip whitespace, and remove duplicates
        normalized_phrases = set(phrase.lower().strip() for phrase in phrases)
        UTIL_LOGGER.debug(f"Normalized phrases to fetch: {len(normalized_phrases)} unique phrases.")

        for phrase in normalized_phrases:
            if not phrase:
                UTIL_LOGGER.warning("Encountered empty phrase after normalization. Skipping.")
                continue
            cached_embedding = self.cache_manager.get_cached_data('embedding_relevance', phrase)
            if cached_embedding is not None:
                try:
                    embeddings[phrase] = np.array(cached_embedding, dtype=np.float32)
                    cache_hits += 1
                except (ValueError, TypeError) as e:
                    UTIL_LOGGER.error(f"Error converting cached embedding for phrase '{phrase}': {e}. Fetching anew.")
                    phrases_to_fetch.append(phrase)
                    cache_misses += 1
            else:
                phrases_to_fetch.append(phrase)
                cache_misses += 1

        UTIL_LOGGER.debug(f"Cache hits: {cache_hits}, Cache misses: {cache_misses} out of {len(normalized_phrases)} unique phrases.")

        if phrases_to_fetch:
            UTIL_LOGGER.info(f"Fetching {len(phrases_to_fetch)} new embeddings from LLM.")
            try:
                new_embeddings = await self.llm.get_embeddings(phrases_to_fetch)
                for phrase, embedding in zip(phrases_to_fetch, new_embeddings):
                    embeddings[phrase] = np.array(embedding, dtype=np.float32)
                    # Save to cache as a list to ensure JSON serialization
                    self.cache_manager.set_cached_data(
                        'embedding_relevance',
                        phrase,
                        embedding.tolist()
                    )
                UTIL_LOGGER.info(f"Fetched and cached {len(phrases_to_fetch)} new embeddings.")
            except Exception as e:
                UTIL_LOGGER.error(f"Error fetching embeddings from LLM: {e}")
                raise e

        return embeddings

    async def precompute_attribute_embeddings(self):
        UTIL_LOGGER.info("Precomputing attribute phrase embeddings.")
        unique_phrases = set()
        for phrases in self.target_attributes.values():
            for phrase in phrases:
                normalized_phrase = phrase.lower().strip()
                if normalized_phrase:
                    unique_phrases.add(normalized_phrase)
                else:
                    UTIL_LOGGER.warning("Encountered empty phrase after normalization. Skipping.")
        UTIL_LOGGER.debug(f"Number of unique phrases to embed: {len(unique_phrases)}")

        try:
            self.attribute_phrase_embeddings = await self.get_phrase_embeddings(list(unique_phrases))
            UTIL_LOGGER.info("Precomputed and stored attribute phrase embeddings successfully.")
        except Exception as e:
            UTIL_LOGGER.error(f"Failed to precompute attribute embeddings: {e}")
            raise e
        
    def get_ngrams(self, text_list: List[str], max_n: int = 3) -> List[str]:
        UTIL_LOGGER.debug(f"Generating n-grams for a list of {len(text_list)} texts with max_n={max_n}.")
        ngrams = []
        for text in text_list:
            normalized_text = text.lower().strip()
            if not normalized_text:
                UTIL_LOGGER.warning("Encountered empty text after normalization. Skipping.")
                continue
            words = normalized_text.split()
            for n in range(1, max_n + 1):
                ngrams.extend([' '.join(words[i:i + n]) for i in range(len(words) - n + 1)])
        UTIL_LOGGER.debug(f"Generated {len(ngrams)} n-grams.")
        return ngrams

    def cosine_sim(self, vec1, vec2):
        try:
            similarity = cosine_similarity([vec1], [vec2])[0][0]
            return similarity
        except Exception as e:
            UTIL_LOGGER.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    async def calculate_attribute_similarity(self, scraped_item_ingredients):
        UTIL_LOGGER.debug("Calculating attribute similarity.")
        scraped_item_ngrams = self.get_ngrams(scraped_item_ingredients)
        UTIL_LOGGER.debug(f"Generated {len(scraped_item_ngrams)} n-grams from scraped item ingredients.")

        try:
            scraped_item_embeddings = await self.get_phrase_embeddings(scraped_item_ngrams)
            UTIL_LOGGER.debug("Obtained embeddings for scraped item n-grams.")
        except Exception as e:
            UTIL_LOGGER.error(f"Failed to get embeddings for scraped item: {e}")
            raise e

        attribute_similarity_scores = {}
        UTIL_LOGGER.debug(f"Calculating similarity scores for {len(self.target_attributes)} attributes.")

        for attribute, phrases in self.target_attributes.items():
            max_similarity = 0
            for phrase in phrases:
                phrase_lower = phrase.lower().strip()
                if not phrase_lower:
                    UTIL_LOGGER.warning("Encountered empty phrase after normalization. Skipping.")
                    continue
                phrase_embedding = self.attribute_phrase_embeddings.get(phrase_lower)
                if phrase_embedding is None:
                    UTIL_LOGGER.warning(f"Embedding for phrase '{phrase_lower}' not found.")
                    continue

                for ngram, ngram_embedding in scraped_item_embeddings.items():
                    similarity = self.cosine_sim(ngram_embedding, phrase_embedding)
                    if similarity > max_similarity:
                        max_similarity = similarity
            attribute_similarity_scores[attribute] = max_similarity
            UTIL_LOGGER.debug(f"Attribute '{attribute}' similarity score: {max_similarity:.4f}")

        UTIL_LOGGER.debug("Completed attribute similarity calculations.")
        return attribute_similarity_scores

    async def calculate_target_similarity(self, scraped_item_name):
        UTIL_LOGGER.debug("Calculating target similarity based on item name.")
        normalized_name = scraped_item_name.lower().strip()
        if not normalized_name:
            UTIL_LOGGER.warning("Scraped item name is empty after normalization. Returning similarity score 0.0.")
            return 0.0
        try:
            scraped_item_embedding = (await self.get_phrase_embeddings([normalized_name]))[normalized_name]
            UTIL_LOGGER.debug(f"Obtained embedding for scraped item name '{normalized_name}'.")
        except KeyError:
            UTIL_LOGGER.error(f"Embedding for scraped item name '{normalized_name}' not found.")
            return 0.0
        except Exception as e:
            UTIL_LOGGER.error(f"Failed to get embedding for scraped item name '{scraped_item_name}': {e}")
            raise e

        max_similarity = 0
        for name in self.target_attributes.get('name', []):
            name_lower = name.lower().strip()
            if not name_lower:
                UTIL_LOGGER.warning("Encountered empty name after normalization. Skipping.")
                continue
            name_embedding = self.attribute_phrase_embeddings.get(name_lower)
            if name_embedding is None:
                UTIL_LOGGER.warning(f"Embedding for target name '{name_lower}' not found.")
                continue
            similarity = self.cosine_sim(scraped_item_embedding, name_embedding)
            if similarity > max_similarity:
                max_similarity = similarity
        UTIL_LOGGER.debug(f"Target similarity score: {max_similarity:.4f}")
        return max_similarity

    async def hybrid_similarity(self, scraped_item_name, scraped_item_ingredients, attribute_threshold=0.0, name_similarity_weight=0.5):
        UTIL_LOGGER.info(f"Calculating hybrid similarity for item '{scraped_item_name}'.")
        try:
            attribute_similarity_scores = await self.calculate_attribute_similarity(scraped_item_ingredients)
            UTIL_LOGGER.debug(f"Attribute similarity scores: {attribute_similarity_scores}")
        except Exception as e:
            UTIL_LOGGER.error(f"Error calculating attribute similarity: {e}")
            raise e

        # Apply threshold
        passed_attributes = {attr: score if score >= attribute_threshold else 0 for attr, score in attribute_similarity_scores.items()}
        UTIL_LOGGER.debug(f"Passed attributes after applying threshold {attribute_threshold}: {passed_attributes}")

        # If no attributes pass and ingredients are provided, similarity is low
        if not any(passed_attributes.values()) and scraped_item_ingredients:
            UTIL_LOGGER.info(f"No attributes passed the threshold for item '{scraped_item_name}'. Returning similarity score 0.0.")
            return 0.0, attribute_similarity_scores

        # Weighted attribute score
        total_weight = sum(self.attribute_weights.values())
        if total_weight == 0:
            UTIL_LOGGER.error("Total attribute weight is zero. Cannot compute weighted attribute score.")
            raise ValueError("Total attribute weight must be greater than zero.")

        weighted_attribute_score = sum(
            self.attribute_weights[attr] * passed_attributes[attr] for attr in passed_attributes if attr != 'name'
        ) / total_weight
        UTIL_LOGGER.debug(f"Weighted attribute score: {weighted_attribute_score:.4f}")

        # Calculate target similarity
        try:
            target_similarity_score = await self.calculate_target_similarity(scraped_item_name)
            UTIL_LOGGER.debug(f"Target similarity score: {target_similarity_score:.4f}")
        except Exception as e:
            UTIL_LOGGER.error(f"Error calculating target similarity: {e}")
            raise e

        # Combine scores
        if scraped_item_ingredients:
            combined_score = (target_similarity_score * name_similarity_weight) + \
                             (weighted_attribute_score * (1 - name_similarity_weight))
            UTIL_LOGGER.debug(f"Combined similarity score with ingredients: {combined_score:.4f}")
        else:
            combined_score = target_similarity_score
            UTIL_LOGGER.debug(f"Combined similarity score without ingredients: {combined_score:.4f}")

        return combined_score, attribute_similarity_scores

    async def run_hybrid_similarity_tests(self, scraped_items):
        UTIL_LOGGER.info(f"Starting hybrid similarity tests for {len(scraped_items)} scraped items.")
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
                    UTIL_LOGGER.debug(f"Processed item '{item_name}' with combined score {combined_score:.4f}.")
                except Exception as e:
                    UTIL_LOGGER.error(f"Failed to process item '{item_name}': {e}")
        except Exception as e:
            UTIL_LOGGER.error(f"Error during hybrid similarity tests: {e}")
            raise e

        UTIL_LOGGER.info("Completed hybrid similarity tests.")
        return results
