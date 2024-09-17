# llmhandler.py

from _utils._util import *
from backend.llm import LLM

class LLMHandler:
    def __init__(self):
        util_logger.info("Initializing LLMHandler.")
        try:
            self.llm = LLM()
            util_logger.info("LLM instance created successfully.")
        except Exception as e:
            util_logger.error(f"Failed to create LLM instance: {e}")
            raise

    async def extract_scraped_items(self, content, content_type='html'):
        util_logger.info(f"Starting extract_scraped_items with content_type: {content_type}.")
        try:
            if content_type == 'pdf':
                prompt = PROMPT_HTML_EXTRACT.format(content)  # Meta data instead of actual content
                util_logger.debug("Using PDF extraction prompt.")
            else:
                prompt = PROMPT_HTML_EXTRACT.format(content)  # Meta data instead of actual content
                util_logger.debug("Using HTML extraction prompt.")
            
            messages = [{"role": "user", "content": prompt}]  # Meta data
            util_logger.info(f"Prepared messages for LLM chat. {messages}")
            
            responses = await self.llm.chat(messages, n=1)
            util_logger.info(f"Received {len(responses)} response(s) from LLM.")
            
            response = responses[-1] if responses else ""
            if not responses:
                util_logger.warning("No responses received from LLM.")
            
            response = self.clean_response(response)

            scraped_items = self.parse_menu_output(response)
            util_logger.info("Finished extracting scraped items.")
            return scraped_items
        except Exception as e:
            util_logger.error(f"Error in extract_scraped_items: {e}")
            raise

    def clean_response(self, response):
        util_logger.info("Cleaning response from LLM.")
        try:
            original_length = len(response)
            response = response.replace('```output\n', '').replace('```output', '').replace('\n```', '').replace('```', '').strip()
            cleaned_length = len(response)
            util_logger.debug(f"Cleaned response length: {cleaned_length} (original: {original_length}).")
            return response
        except Exception as e:
            util_logger.error(f"Error in clean_response: {e}")
            raise

    def parse_menu_output(self, llm_output: str) -> dict:
        util_logger.info("Parsing menu output from LLM.")
        try:
            pattern = r"(.+?):(.*)"
            menu_dict = {}
            matches = re.findall(pattern, llm_output)
            util_logger.debug(f"Found {len(matches)} matches in LLM output.")
            
            for match in matches:
                item = match[0].strip()
                ingredients = match[1].strip()
                if ingredients.lower() == 'n/a':
                    ingredients_list = []
                    util_logger.debug(f"Ingredients for '{item}' marked as 'n/a'.")
                else:
                    ingredients_list = [ingredient.strip() for ingredient in ingredients.split("|")]
                    util_logger.debug(f"Parsed {len(ingredients_list)} ingredients for '{item}'.")
                menu_dict[item] = ingredients_list
            util_logger.info("Completed parsing menu output.")
            return menu_dict
        except Exception as e:
            util_logger.error(f"Error in parse_menu_output: {e}")
            raise

    async def get_embeddings(self, text_list):
        util_logger.info(f"Getting embeddings for a list of {len(text_list)} text items.")
        try:
            embeddings = await self.llm.get_embeddings(text_list)
            if embeddings is not None:
                util_logger.info("Successfully retrieved embeddings.")
            else:
                util_logger.warning("Received None for embeddings.")
            return embeddings
        except Exception as e:
            util_logger.error(f"Error in get_embeddings: {e}")
            raise

    async def find_url_relevance(self, urls):
        util_logger.info(f"Calculating URL relevance for {len(urls)} URLs.")
        try:
            if not urls:
                util_logger.warning("No URLs provided to find_url_relevance.")
                return []

            relevant_urls = []

            # Get embeddings for target keywords once
            keyword_embeddings = await self.get_embeddings(TARGET_URL_KEYWORDS)
            if keyword_embeddings is None:
                util_logger.error("Failed to retrieve embeddings for target keywords.")
                return []
            
            async for url in tqdm(urls, desc="Fetching URL segment embeddings (This may take a while [OPTIMIZE])...."):
                util_logger.debug(f"Processing URL: {url}")

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

                util_logger.debug(f"Extracted segments from URL '{url}': {segments}")

                if not segments:
                    util_logger.warning(f"No valid segments found for URL: {url}. Assigning similarity 0.")
                    relevant_urls.append((url, 0))
                    continue
                
                # Get embeddings for URL segments
                segment_embeddings = await self.get_embeddings(segments)
                if segment_embeddings is None:
                    util_logger.error(f"Failed to retrieve embeddings for URL segments of {url}. Assigning similarity 0.")
                    relevant_urls.append((url, 0))
                    continue

                # Calculate cosine similarities between segment embeddings and keyword embeddings
                similarities = cosine_similarity(segment_embeddings, keyword_embeddings)
                max_similarity = similarities.max() if similarities.size > 0 else 0

                util_logger.debug(f"Max similarity for URL '{url}': {max_similarity}")

                # Apply similarity threshold
                if max_similarity >= SIMILARITY_THRESHOLD:
                    relevant_urls.append((url, max_similarity))
                    util_logger.info(f"URL '{url}' is relevant with similarity {max_similarity:.2f}.")
                else:
                    relevant_urls.append((url, max_similarity))
                    util_logger.info(f"URL '{url}' is not relevant. Similarity {max_similarity:.2f} is below threshold.")

            util_logger.info("Completed URL relevance calculation.")
            return relevant_urls
        except Exception as e:
            util_logger.error(f"Error in find_url_relevance: {e}")
            raise
