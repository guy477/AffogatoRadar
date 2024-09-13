from ._util import *

from openai import OpenAI
import asyncio  # Add asyncio
import numpy as np
import re
from urllib.parse import urlparse
from sklearn.metrics.pairwise import cosine_similarity

# SANATIZED KEY
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set up OpenAI API key globally

class LLM:
    def __init__(self, model_chat="gpt-3.5-turbo", model_embedding='text-embedding-3-large', max_tokens=265, temperature=0.7):
        self.model_chat = model_chat
        self.model_embedding = model_embedding
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def chat(self, messages, model=None, temperature=None, max_tokens=None, n=1):
        """
        Asynchronous chat-based API call to OpenAI.
        """
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model or self.model_chat,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                n=n
            )
            response = response.to_dict()
            return [choice['message']['content'] for choice in response['choices']]
        except Exception as e:
            print(f"Error during chat call: {e}")
            return None

    async def get_embeddings(self, text_list):
        """
        Asynchronous generation of embeddings for a list of texts using OpenAI API.
        """
        try:
            embeddings = await asyncio.to_thread(
                client.embeddings.create,
                model=self.model_embedding,
                input=text_list
            )

            embeddings = embeddings.to_dict()
            embeddings = [data['embedding'] for data in embeddings['data']]
            return np.array(embeddings)
        except Exception as e:
            print(f"Error during embedding call: {e}")
            return None

    async def find_url_relevance(self, urls, target_keywords):
        """
        Asynchronous URL filtering based on similarity to target keywords.
        """
        if not urls:
            return []

        # Extract path components for each URL
        url_components = [segment for url in urls for segment in url.split("/") if segment]

        # Get embeddings for URL components and target keywords
        url_component_embeddings = await self.get_embeddings(url_components)
        keyword_embeddings = await self.get_embeddings(target_keywords)

        if url_component_embeddings is None or keyword_embeddings is None:
            return []

        # Compute cosine similarity between URL components and keywords
        similarities = cosine_similarity(url_component_embeddings, keyword_embeddings)

        # Calculate max similarity for each URL based on its components
        idx = 0
        relevant_urls = []
        for url in urls:
            components = [segment for segment in url.split("/") if segment]
            num_components = len(components)

            if num_components == 0:
                relevant_urls.append((url, 0))  # No components to compare, similarity is 0
                continue

            # Extract the relevant part of the similarity matrix for this URL
            url_similarities = similarities[idx:idx + num_components]
            idx += num_components

            if url_similarities.size == 0:
                relevant_urls.append((url, 0))  # No similarity values, similarity is 0
                continue
            
            # For each component, get the max similarity (highest value in the row)
            max_per_component = np.max(url_similarities, axis=1)
            
            # Get the max similarity for the entire URL
            max_similarity = np.max(max_per_component) if max_per_component.size > 0 else 0
            
            relevant_urls.append((url, max_similarity))

        return relevant_urls


    async def extract_menu_items(self, html):
        """
        Asynchronous extraction of menu items from HTML using LLM.
        """
        prompt = f"""Given the HTML content of a restaurant's webpage, extract the menu items in a structured format as follows:
- Each line should represent one menu item.
- Item name and ingredients should be separated by a colon (:).
- Ingredients should be separated by vertical bars (|).
- If there are no ingredients, use 'N/A' after the colon.
- Omit any numbers, special characters, or punctuation.
- Omit any prices, calories, descriptions.
- Maintain the exact formatting shown in the example.

Example format:
```output
Item Name:Ingredient|Ingredient
Item Name with No Ingredients:N/A
```

Important:
- Adhere strictly to the format.
- If no items are found, return only "No menu items found."
- If only one item is found, return it in the format shown.
- DO NOT HALLUCINATE OR MAKE UP ITEMS.

Now, extract the menu items from the following HTML:
```
{html}
```"""
        messages = [{"role": "user", "content": prompt}]
        responses = await self.chat(messages, n=1)

        # clean the response up
        for i, _ in enumerate(responses):
            while '```output\n' in responses[i]:
                responses[i] = responses[i].replace('```output\n', '').strip()
            while '```output' in responses[i]:
                response = responses[i].replace('```outupt', '').strip()
            while '\n```' in responses[i]:
                responses[i] = responses[i].replace('\n```', '').strip()
            while '```' in responses[i]:
                responses[i] = responses[i].replace('```', '').strip()

        responses = [self.parse_menu_output(response) for response in responses]
        responses = [response for response in responses if response]

        return responses[-1] if responses else {}

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

    def set_default_chat_model(self, model):
        """Set the default model for all future calls."""
        self.model_chat = model

    def set_default_embedding_model(self, model):
        """Set the default model for all future calls."""
        self.model_embedding = model

    def set_default_temperature(self, temperature):
        """Set the default temperature for all future calls."""
        self.temperature = temperature

    def set_default_max_tokens(self, max_tokens):
        """Set the default max_tokens for all future calls."""
        self.max_tokens = max_tokens

    def get_available_models(self):
        """Fetch the available models from OpenAI."""
        try:
            models = client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            print(f"Error fetching models: {e}")
            return None
