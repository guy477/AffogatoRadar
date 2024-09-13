# llmhandler.py

from _utils._util import *
from backend.llm import LLM
from _utils._util import PROMPT_HTML_EXTRACT  # Assuming this is defined

class LLMHandler:
    def __init__(self):
        self.llm = LLM()

    async def extract_menu_items(self, content, content_type='html'):
        if content_type == 'pdf':
            prompt = PROMPT_HTML_EXTRACT.format(content)  # Use appropriate prompt for PDFs
        else:
            prompt = PROMPT_HTML_EXTRACT.format(content)
        messages = [{"role": "user", "content": prompt}]
        responses = await self.llm.chat(messages, n=1)

        response = responses[-1] if responses else ""
        response = self.clean_response(response)
        menu_items = self.parse_menu_output(response)
        return menu_items

    def clean_response(self, response):
        response = response.replace('```output\n', '').replace('```output', '').replace('\n```', '').replace('```', '').strip()
        return response

    def parse_menu_output(self, llm_output: str) -> dict:
        pattern = r"(.+?):(.*)"
        menu_dict = {}
        for match in re.findall(pattern, llm_output):
            item = match[0].strip()
            ingredients = match[1].strip()
            if ingredients.lower() == 'n/a':
                ingredients_list = []
            else:
                ingredients_list = [ingredient.strip() for ingredient in ingredients.split("|")]
            menu_dict[item] = ingredients_list
        return menu_dict

    async def get_embeddings(self, text_list):
        embeddings = await self.llm.get_embeddings(text_list)
        return embeddings

    async def find_url_relevance(self, urls):
        if not urls:
            return []

        url_components = [segment for url in urls for segment in url.split("/") if segment]
        url_component_embeddings = await self.get_embeddings(url_components)
        keyword_embeddings = await self.get_embeddings(TARGET_URL_KEYWORDS)

        if url_component_embeddings is None or keyword_embeddings is None:
            return []

        similarities = cosine_similarity(url_component_embeddings, keyword_embeddings)
        idx = 0
        relevant_urls = []
        for url in urls:
            components = [segment for segment in url.split("/") if segment]
            num_components = len(components)

            if num_components == 0:
                relevant_urls.append((url, 0))
                continue

            url_similarities = similarities[idx:idx + num_components]
            idx += num_components

            if url_similarities.size == 0:
                relevant_urls.append((url, 0))
                continue

            max_per_component = np.max(url_similarities, axis=1)
            max_similarity = np.max(max_per_component) if max_per_component.size > 0 else 0
            relevant_urls.append((url, max_similarity))

        return relevant_urls