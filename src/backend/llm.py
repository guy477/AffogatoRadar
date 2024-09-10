from ._util import *

from openai import OpenAI
import asyncio  # Add asyncio
import numpy as np
import re

# SANATIZED KEY
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set up OpenAI API key globally

class LLM:
    def __init__(self, model="gpt-3.5-turbo", max_tokens=265, temperature=0.7):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def chat(self, messages, model=None, temperature=None, max_tokens=None, n=1):
        """
        Asynchronous chat-based API call to OpenAI.
        """
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model or self.model,
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
                model="text-embedding-ada-002",
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
        if urls == []:
            return []

        url_embeddings = await self.get_embeddings(urls)
        keyword_embeddings = await self.get_embeddings(target_keywords)

        if url_embeddings is None or keyword_embeddings is None:
            return []

        similarities = np.dot(url_embeddings, keyword_embeddings.T)
        max_similarities = np.max(similarities, axis=1)
        relevant_urls = [(urls[i], sim) for i, sim in enumerate(max_similarities)]

        return relevant_urls


    async def extract_menu_items(self, html):
        """
        Asynchronous extraction of menu items from HTML using LLM.
        """
        prompt = f"""Given the HTML of a restaurant's webpage, extract the menu items in a structured format. List each menu item along with its ingredients. Present the itemized menu in the following format:

- Each line should represent one menu item
- The item name and ingredients should be separated by a colon (:)
- Ingredients should be separated by vertical bars (|)
- If there are no ingredients, use 'N/A' after the colon
- Do not use any numbers or bullet points
- Preserve the exact formatting shown in the examples below

Example output format:
```output
Example Drink:Ingredient|Ingredient|Ingredient
Example Food:Ingredient|Ingredient|Ingredient|Ingredient
Example Drink with No Ingredients:N/A
Example Food with No Ingredients:N/A
```

Important:
- Strictly adhere to the format above
- Do not add any explanatory text or additional information
- If no menu items are found, return only the exact phrase: "No menu items found."
- If only one menu item is found, return it in the format shown above

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

    def set_default_model(self, model):
        """Set the default model for all future calls."""
        self.model = model

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
