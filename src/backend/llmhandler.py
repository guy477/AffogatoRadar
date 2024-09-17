# llmhandler.py

from _utils._util import *
from backend.llm import LLM

class LLMHandler:
    def __init__(self):
        UTIL_LOGGER.info("Initializing LLMHandler.")
        try:
            self.llm = LLM()
            UTIL_LOGGER.info("LLM instance created successfully.")
        except Exception as e:
            UTIL_LOGGER.error(f"Failed to create LLM instance: {e}")
            raise

    async def extract_scraped_items(self, content, content_type='html'):
        UTIL_LOGGER.info(f"Starting extract_scraped_items with content_type: {content_type}.")
        try:
            if content_type == 'pdf':
                prompt = PROMPT_HTML_EXTRACT.format(content)  # Meta data instead of actual content
                UTIL_LOGGER.debug("Using PDF extraction prompt.")
            else:
                prompt = PROMPT_HTML_EXTRACT.format(content)  # Meta data instead of actual content
                UTIL_LOGGER.debug("Using HTML extraction prompt.")
            
            messages = [{"role": "user", "content": prompt}]  # Meta data
            UTIL_LOGGER.info(f"Prepared messages for LLM chat. {messages}")
            
            responses = await self.llm.chat(messages, n=1)
            UTIL_LOGGER.info(f"Received {len(responses)} response(s) from LLM.")
            
            response = responses[-1] if responses else ""
            if not responses:
                UTIL_LOGGER.warning("No responses received from LLM.")
            
            response = self.clean_response(response)

            scraped_items = self.parse_menu_output(response)
            UTIL_LOGGER.info("Finished extracting scraped items.")
            return scraped_items
        except Exception as e:
            UTIL_LOGGER.error(f"Error in extract_scraped_items: {e}")
            raise

    def clean_response(self, response):
        UTIL_LOGGER.info("Cleaning response from LLM.")
        try:
            original_length = len(response)
            response = response.replace('```output\n', '').replace('```output', '').replace('\n```', '').replace('```', '').strip()
            cleaned_length = len(response)
            UTIL_LOGGER.debug(f"Cleaned response length: {cleaned_length} (original: {original_length}).")
            return response
        except Exception as e:
            UTIL_LOGGER.error(f"Error in clean_response: {e}")
            raise

    def parse_menu_output(self, llm_output: str) -> dict:
        UTIL_LOGGER.info("Parsing menu output from LLM.")
        try:
            pattern = r"(.+?):(.*)"
            menu_dict = {}
            matches = re.findall(pattern, llm_output)
            UTIL_LOGGER.debug(f"Found {len(matches)} matches in LLM output.")
            
            for match in matches:
                item = match[0].strip()
                ingredients = match[1].strip()
                if ingredients.lower() == 'n/a':
                    ingredients_list = []
                    UTIL_LOGGER.debug(f"Ingredients for '{item}' marked as 'n/a'.")
                else:
                    ingredients_list = [ingredient.strip() for ingredient in ingredients.split("|")]
                    UTIL_LOGGER.debug(f"Parsed {len(ingredients_list)} ingredients for '{item}'.")
                menu_dict[item] = ingredients_list
            UTIL_LOGGER.info("Completed parsing menu output.")
            return menu_dict
        except Exception as e:
            UTIL_LOGGER.error(f"Error in parse_menu_output: {e}")
            raise

    async def get_embeddings(self, text_list):
        UTIL_LOGGER.info(f"Getting embeddings for a list of {len(text_list)} text items.")
        try:
            embeddings = await self.llm.get_embeddings(text_list)
            if embeddings is not None:
                UTIL_LOGGER.info("Successfully retrieved embeddings.")
            else:
                UTIL_LOGGER.warning("Received None for embeddings.")
            return embeddings
        except Exception as e:
            UTIL_LOGGER.error(f"Error in get_embeddings: {e}")
            raise

    async def find_url_relevance(self, urls):
        UTIL_LOGGER.info(f"Calculating URL relevance for {len(urls)} URLs.")
        try:
            if not urls:
                UTIL_LOGGER.warning("No URLs provided to find_url_relevance.")
                return []

            relevant_urls = []

            # Get embeddings for target keywords once
            keyword_embeddings = await self.get_embeddings(TARGET_URL_KEYWORDS)
            if keyword_embeddings is None:
                UTIL_LOGGER.error("Failed to retrieve embeddings for target keywords.")
                return []
            
            async for url in tqdm(urls, desc="Fetching URL segment embeddings (This may take a while [OPTIMIZE])...."):
                UTIL_LOGGER.debug(f"Processing URL: {url}")

                # Extract meaningful segments from the URL
                parsed_url = urlparse(url)
                path_segments = [segment for segment in parsed_url.path.split('/') if segment]
                query_params = parsed_url.query.split('&') if parsed_url.query else []
                fragment = parsed_url.fragment.split('&') if parsed_url.fragment else []
                components = path_segments + query_params + fragment

                # Further split components on '.', '_', and '-'
                segments = []
                for component in components:
                    split_segments = re.split(r'[._-]', component)
                    segments.extend([seg for seg in split_segments if seg])

                UTIL_LOGGER.debug(f"Extracted segments from URL '{url}': {segments}")

                if not segments:
                    UTIL_LOGGER.warning(f"No valid segments found for URL: {url}. Assigning similarity 0.")
                    relevant_urls.append((url, 0))
                    continue
                
                # Get embeddings for URL segments
                segment_embeddings = await self.get_embeddings(segments)
                if segment_embeddings is None:
                    UTIL_LOGGER.error(f"Failed to retrieve embeddings for URL segments of {url}. Assigning similarity 0.")
                    relevant_urls.append((url, 0))
                    continue

                # Calculate cosine similarities between segment embeddings and keyword embeddings
                similarities = cosine_similarity(segment_embeddings, keyword_embeddings)
                max_similarity = similarities.max() if similarities.size > 0 else 0

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
