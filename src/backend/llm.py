from _utils._util import *

from openai import OpenAI

# SANATIZED KEY
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class LLM:
    def __init__(self, model_chat="gpt-4o-mini", model_embedding='text-embedding-3-large', max_tokens=265, temperature=0.7):
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
