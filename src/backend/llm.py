from openai import OpenAI

client = OpenAI(api_key="***REMOVED***")
import numpy as np
import re

# Set up OpenAI API key globally

class LLM:
    def __init__(self, model="gpt-3.5-turbo", max_tokens=265, temperature=0.7):
        """
        Initialize the LLM object with OpenAI API key and default parameters.
        You can change the model, max_tokens, and temperature for each call.
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def chat(self, messages, model=None, temperature=None, max_tokens=None, n=1):
        """
        Make a chat-based API call to OpenAI, adjustable per request.

        Args:
            messages (list): A list of message dictionaries following OpenAI's chat format.
            model (str): Model to be used (default is gpt-4).
            temperature (float): Sampling temperature for response variation (default 0.7).
            max_tokens (int): Max number of tokens in the response.
            n (int): Number of completions to generate.

        Returns:
            list: A list of the generated responses (n responses).
        """
        try:
            response = client.chat.completions.create(model=model or self.model,
            messages=messages,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or self.temperature,
            n=n).to_dict()
            return [choice['message']['content'] for choice in response['choices']]
        except Exception as e:
            print(f"Error during chat call: {e}")
            return None

    def get_embeddings(self, text_list):
        """
        Generate embeddings for a list of texts using the text-embedding-ada-002 model.
        
        Args:
            text_list (list): List of strings to generate embeddings for.
            
        Returns:
            np.ndarray: A numpy array of embeddings.
        """
        try:
            # print(text_list)
            embeddings = client.embeddings.create(model="text-embedding-ada-002",
            input=text_list).to_dict()


            embeddings = [data['embedding'] for data in embeddings['data']]
            return np.array(embeddings)
        except Exception as e:
            print(f"Error during embedding call: {e}")
            return None

    def find_url_relevance(self, urls, target_keywords):
        """
        Filter URLs based on similarity to target keywords using embeddings.
        
        Args:
            urls (list): List of URLs to check.
            target_keywords (list): List of keywords to match URLs against (e.g., 'menu', 'food').
            
        Returns:
            list: Filtered list of URLs.
        """
        if urls == []:
            return []

        # Get embeddings for URLs and keywords
        url_embeddings = self.get_embeddings(urls)
        keyword_embeddings = self.get_embeddings(target_keywords)

        if url_embeddings is None or keyword_embeddings is None:
            return []

        # Calculate cosine similarity between URLs and target keywords
        similarities = np.dot(url_embeddings, keyword_embeddings.T)
        max_similarities = np.max(similarities, axis=1)

        # Filter URLs based on the similarity threshold
        relevant_urls = [(urls[i], sim) for i, sim in enumerate(max_similarities)]
        return relevant_urls


    def extract_menu_items(self, html):
        prompt = f"""Given the HTML of a restaurant's webpage, extract the menu items in a structured format. List each menu item along with its ingredients. Present the itemized menu in the following format (DO NOT USE ANY NUMBERS):
```output
Example Drink:Ingredient|Ingredient|Ingredient
Example Food:Ingredient|Ingredient|Ingredient|Ingredient
Example Drink:N/A
Example Food:N/A
```

If no menu items are found, return "No menu items found."
If only one menu item is found, return it in the format shown above.

```html
{html}
```"""
        messages = [{"role": "user", "content": prompt}]

        responses = self.chat(messages, n = 1)

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
        """
        Parse the menu output from the LLM and return a dictionary where each item is mapped to its ingredients.
        
        :param llm_output: The LLM output containing menu items in the specified format.
        :return: A dictionary with menu items as keys and a list of ingredients as values.
        """
        # Initialize the result dictionary
        menu_dict = {}

        # Regex to match the menu items and their ingredients
        pattern = r"(.+?):(.*)"

        # Iterate over all matches found
        for match in re.findall(pattern, llm_output):
            item = match[0].strip()  # Strip whitespace from the item name
            ingredients = match[1].strip()  # Strip whitespace from the ingredients
            if ingredients.lower() == 'n/a':
                ingredients_list = []  # If ingredients are "N/A", use an empty list
            else:
                # Split ingredients by pipe '|' and strip each ingredient
                ingredients_list = [ingredient.strip() for ingredient in ingredients.split("|")]
            
            # Map the item to its ingredients
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
