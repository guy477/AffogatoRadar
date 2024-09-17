# llmhandler.py

from _utils._util import *
from _utils._llm import LLM
from backend.cachemanager import CacheManager

class LLMHandler:
    def __init__(self):
        UTIL_LOGGER.info("Initializing LLMHandler.")
        try:
            self.llm = LLM()
            UTIL_LOGGER.info("LLM instance created successfully.")
        except Exception as e:
            UTIL_LOGGER.error(f"Failed to create LLM instance: {e}")
            raise
        # Initialize CacheManager
        self.cache_manager = CacheManager()
        UTIL_LOGGER.info("Initialized CacheManager for embedding caching.")

    async def extract_scraped_items(self, content, content_type='html'):
        UTIL_LOGGER.info(f"Starting extract_scraped_items with content_type: {content_type}.")
        try:
            if content_type == 'pdf':
                prompt = PROMPT_PDF_EXTRACT.format(content)  # Meta data instead of actual content
                UTIL_LOGGER.debug("Using PDF extraction prompt.")
            else:
                prompt = PROMPT_HTML_EXTRACT.format(content)  # Meta data instead of actual content
                UTIL_LOGGER.debug("Using HTML extraction prompt.")
            
            messages = [{"role": "user", "content": prompt}]  # Meta data
            UTIL_LOGGER.info(f"Prepared messages for LLM chat. {messages}")
            
            responses = await self.llm.chat(messages, n=1)
            responses = [response.lower() for response in responses]
            UTIL_LOGGER.info(f"Received {len(responses)} response(s) from LLM.")
            UTIL_LOGGER.debug(f"Responses: {responses}")
            
            # NOTE: You can increase `n` in `self.llm.chat(n=...)` if you want multiple samples
            response = responses[-1] if responses else ""
            if not responses:
                UTIL_LOGGER.warning("No responses received from LLM.")
            
            response = self.clean_llm_response(response)

            scraped_items = self.build_dict_from_llm_response(response)
            UTIL_LOGGER.info(f"Finished extracting scraped items. {scraped_items}")
            return scraped_items
        except Exception as e:
            UTIL_LOGGER.error(f"Error in extract_scraped_items: {e}")
            raise

    def clean_llm_response(self, response):
        UTIL_LOGGER.info("Cleaning response from LLM.")
        try:
            original_length = len(response)
            response = response.replace('```output\n', '').replace('```output', '').replace('\n```', '').replace('```', '').strip()
            cleaned_length = len(response)
            UTIL_LOGGER.debug(f"Cleaned response length: {cleaned_length} (original: {original_length}).")
            return response
        except Exception as e:
            UTIL_LOGGER.error(f"Error in clean_llm_response: {e}")
            raise

    def build_dict_from_llm_response(self, llm_output: str) -> dict:
        UTIL_LOGGER.info("Parsing menu output from LLM.")
        try:
            pattern = r"(.+?):(.*)"
            menu_dict = {}
            matches = re.findall(pattern, llm_output)
            UTIL_LOGGER.debug(f"Found {len(matches)} matches in LLM output.")
            
            for match in matches:
                item = match[0].strip()
                ingredients = match[1].strip()
                if ingredients == 'n/a':
                    ingredients_list = []
                    UTIL_LOGGER.debug(f"Item '{item}' marked as 'n/a'.")
                else:
                    ingredients_list = [ingredient.strip() for ingredient in ingredients.split("|")]
                    UTIL_LOGGER.debug(f"Parsed {len(ingredients_list)} Items for '{item}'.")
                menu_dict[item] = ingredients_list
            UTIL_LOGGER.info("Completed parsing menu output.")
            return menu_dict
        except Exception as e:
            UTIL_LOGGER.error(f"Error in build_dict_from_llm_response: {e}")
            raise

    async def find_url_relevance(self, urls: List[str]) -> List[Tuple[str, float]]:
        UTIL_LOGGER.info(f"Calculating URL relevance for {len(urls)} URLs.")
        try:
            if not urls:
                UTIL_LOGGER.warning("No URLs provided to find_url_relevance.")
                return []

            # Extract all unique segments from URLs
            unique_segments = self._extract_unique_segments(urls)
            UTIL_LOGGER.debug(f"Total unique segments to fetch embeddings for: {len(unique_segments)}")

            # Retrieve embeddings with caching
            segment_embeddings = await self._get_cached_embeddings(list(unique_segments))
            if not segment_embeddings:
                UTIL_LOGGER.error("Failed to retrieve embeddings for URL segments.")
                return []

            relevant_urls = []

            for url in tqdm(urls, desc="Processing URLs..."):
                UTIL_LOGGER.debug(f"Processing URL: {url}")
                segments = self._extract_segments(url)
                UTIL_LOGGER.debug(f"Extracted segments: {segments}")

                if not segments:
                    UTIL_LOGGER.warning(f"No valid segments found for URL: {url}. Assigning similarity 0.")
                    relevant_urls.append((url, 0.0))
                    continue

                # Retrieve embeddings for the current URL's segments
                current_embeddings = [
                    segment_embeddings.get(seg) for seg in segments if segment_embeddings.get(seg) is not None
                ]

                if not current_embeddings:
                    UTIL_LOGGER.warning(f"No embeddings found for segments of URL: {url}. Assigning similarity 0.")
                    relevant_urls.append((url, 0.0))
                    continue

                # Calculate cosine similarities with keyword embeddings
                similarities = cosine_similarity(current_embeddings, self.keyword_embeddings)
                max_similarity = similarities.max() if similarities.size > 0 else 0.0

                UTIL_LOGGER.debug(f"Max similarity for URL '{url}': {max_similarity}")

                # Apply similarity threshold
                if max_similarity >= SIMILARITY_THRESHOLD:
                    relevant_urls.append((url, max_similarity))
                    UTIL_LOGGER.info(f"URL '{url}' is relevant with similarity {max_similarity:.2f}.")
                else:
                    relevant_urls.append((url, max_similarity))
                    UTIL_LOGGER.info(f"URL '{url}' is not relevant. Similarity {max_similarity:.2f} is below threshold.")

            UTIL_LOGGER.info("Completed URL relevance calculation.")
            return relevant_urls

        except Exception as e:
            UTIL_LOGGER.error(f"Error in find_url_relevance: {e}")
            raise

    def _extract_unique_segments(self, urls: List[str]) -> set:
        """
        Extracts and returns a set of unique segments from a list of URLs.
        """
        UTIL_LOGGER.debug("Extracting unique segments from all URLs.")
        unique_segments = set()
        for url in urls:
            segments = self._extract_segments(url)
            unique_segments.update(segments)
        UTIL_LOGGER.debug(f"Extracted {len(unique_segments)} unique segments.")
        return unique_segments

    def _extract_segments(self, url: str) -> List[str]:
        """
        Extracts meaningful segments from a single URL.
        """
        parsed_url = urlparse(url)
        path_segments = [segment for segment in parsed_url.path.split('/') if segment]
        query_params = parsed_url.query.split('&') if parsed_url.query else []
        fragment = parsed_url.fragment.split('&') if parsed_url.fragment else []
        components = path_segments + query_params + fragment

        # Further split components on '.', '_', and '-'
        segments = []
        for component in components:
            split_segments = re.split(r'[._-]', component)
            segments.extend([seg.lower().strip() for seg in split_segments if seg])

        return segments

    async def _get_cached_embeddings(self, phrases: List[str]) -> dict:
        """
        Retrieves embeddings for a list of phrases using caching.
        Returns a dictionary mapping phrases to their embeddings.
        """
        UTIL_LOGGER.debug(f"Fetching embeddings for {len(phrases)} unique phrases with caching.")
        embeddings = {}
        phrases_to_fetch = []
        cache_hits = 0
        cache_misses = 0

        for phrase in phrases:
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

        UTIL_LOGGER.debug(f"Cache hits: {cache_hits}, Cache misses: {cache_misses} out of {len(phrases)} unique phrases.")

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

    async def get_embeddings(self, phrases: List[str]) -> dict:
        """
        Retrieves embeddings for a list of phrases using the LLM.
        Returns a dictionary mapping phrases to their embeddings.
        """
        UTIL_LOGGER.debug(f"Fetching embeddings for {len(phrases)} phrases.")
        try:
            new_embeddings = await self.llm.get_embeddings(phrases)
            return {phrase: embedding for phrase, embedding in zip(phrases, new_embeddings)}
        except Exception as e:
            UTIL_LOGGER.error(f"Error fetching embeddings: {e}")
            raise

    @property
    def keyword_embeddings(self):
        """
        Retrieves embeddings for target keywords used in similarity calculations.
        Assumes TARGET_URL_KEYWORDS is defined elsewhere in the class.
        """
        if not hasattr(self, '_keyword_embeddings'):
            embeddings = asyncio.run(self.get_embeddings(TARGET_URL_KEYWORDS))
            self._keyword_embeddings = embeddings if embeddings else {}
        return self._keyword_embeddings