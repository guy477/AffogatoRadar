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
                prompt = PROMPT_HTML_EXTRACT.format("PDF content")  # Meta data instead of actual content
                util_logger.debug("Using PDF extraction prompt.")
            else:
                prompt = PROMPT_HTML_EXTRACT.format("HTML content")  # Meta data instead of actual content
                util_logger.debug("Using HTML extraction prompt.")
            
            messages = [{"role": "user", "content": "Formatted prompt for extraction."}]  # Meta data
            util_logger.debug("Prepared messages for LLM chat.")
            
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

            # Extract components after the base URL
            def extract_url_components(url):
                parsed_url = urlparse(url)
                path_components = parsed_url.path.split('/')[1:]  # Ignore the first empty component
                query_components = parsed_url.query.split('&') if parsed_url.query else []
                fragment_components = [parsed_url.fragment] if parsed_url.fragment else []
                components = path_components + query_components + fragment_components
                util_logger.debug(f"Extracted {len(components)} components from URL: {url}")
                return components

            # Extract and flatten URL components
            url_components = [
                component
                for url in urls
                for component in extract_url_components(url)
                if component
            ]
            util_logger.info(f"Total URL components extracted: {len(url_components)}.")

            # Further split components on '.', '_', and '-'
            url_components = [
                segment
                for component in url_components
                for segment in re.split(r'[._-]', component)
                if segment
            ]
            util_logger.info(f"Total URL segments after splitting: {len(url_components)}.")

            url_component_embeddings = await self.get_embeddings(url_components)
            keyword_embeddings = await self.get_embeddings(TARGET_URL_KEYWORDS)

            if url_component_embeddings is None or keyword_embeddings is None:
                util_logger.error("Embeddings retrieval failed for URL components or target keywords.")
                return []

            # Calculate similarities between all URL components and all keywords
            similarities = cosine_similarity(url_component_embeddings, keyword_embeddings)
            util_logger.info("Calculated cosine similarities between URL components and keywords.")

            relevant_urls = []
            idx = 0
            for url in urls:
                components = extract_url_components(url)
                num_components = sum(len(re.split(r'[._-]', component)) for component in components)
                util_logger.debug(f"URL '{url}' has {num_components} segments for similarity calculation.")

                if num_components == 0:
                    relevant_urls.append((url, 0))
                    util_logger.warning(f"No components found for URL: {url}. Assigning similarity 0.")
                    continue

                # Get similarities for this URL's components
                url_similarities = similarities[idx:idx + num_components]
                idx += num_components

                if url_similarities.size == 0:
                    relevant_urls.append((url, 0))
                    util_logger.warning(f"No similarities found for URL: {url}. Assigning similarity 0.")
                    continue

                # Find the maximum similarity for this URL
                max_similarity = np.max(url_similarities)
                relevant_urls.append((url, max_similarity))
                util_logger.debug(f"URL '{url}' has maximum similarity of {max_similarity}.")

            util_logger.info("Completed URL relevance calculation.")
            return relevant_urls
        except Exception as e:
            util_logger.error(f"Error in find_url_relevance: {e}")
            raise
