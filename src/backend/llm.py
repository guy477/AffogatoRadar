from _utils._util import *
import tiktoken
from openai import OpenAI

# SANATIZED KEY
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class LLM:
    def __init__(self, model_chat="gpt-4o-mini", model_embedding='text-embedding-3-large', max_tokens=265, temperature=0.7):
        self.model_chat = model_chat
        self.model_embedding = model_embedding
        self.token_limit = 8191  # token limit for text-embedding-ada-002
        self.encoding = tiktoken.encoding_for_model(model_embedding)
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

    def _count_tokens(self, text):
        """Count the number of tokens in a text string."""
        return len(self.encoding.encode(text))

    def _chunk_text(self, text):
        """Split text into chunks that fit within the token limit."""
        tokens = self.encoding.encode(text)
        # Split tokens into chunks that fit within the token limit
        return [self.encoding.decode(tokens[i:i+self.token_limit]) for i in range(0, len(tokens), self.token_limit)]

    async def get_embeddings(self, text_list):
        """
        Asynchronous generation of embeddings for a list of texts using OpenAI API.
        """
        try:
            all_embeddings = []

            for text in text_list:
                # Check token count for the current text
                token_count = self._count_tokens(text)
                if token_count > self.token_limit:
                    # If token count exceeds the limit, chunk the text
                    text_chunks = self._chunk_text(text)
                else:
                    # Otherwise, keep the text as a single chunk
                    text_chunks = [text]

                # Fetch embeddings for each chunk
                embeddings = []
                for chunk in text_chunks:
                    embedding_response = await asyncio.to_thread(
                        client.embeddings.create,
                        model=self.model_embedding,
                        input=chunk
                    )
                    embeddings.extend([data['embedding'] for data in embedding_response.to_dict()['data']])

                # Aggregate embeddings (optional: you may want to average them)
                all_embeddings.append(np.mean(embeddings, axis=0))

            return np.array(all_embeddings)
        except Exception as e:
            print(f"Error during embedding call: {text_list}: {e}")
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
