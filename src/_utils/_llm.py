from _utils._util import *  # Assuming logging is imported from _utils._util

import tiktoken
from openai import OpenAI

# SANITIZED KEY
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class LLM:
    def __init__(self, model_chat="gpt-4o-mini", model_embedding='text-embedding-3-large', max_tokens=265, temperature=0.7):
        self.model_chat = model_chat
        self.model_embedding = model_embedding
        self.token_limit = 8191  # token limit for 'text-embedding-3-large'
        self.encoding = tiktoken.encoding_for_model(model_embedding)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(
            "LLM initialized with parameters: model_chat=%s, model_embedding=%s, max_tokens=%d, temperature=%.2f",
            self.model_chat, self.model_embedding, self.max_tokens, self.temperature
        )

    async def chat(self, messages, model=None, temperature=None, max_tokens=None, n=1):
        """
        Asynchronous chat-based API call to OpenAI.
        """
        model_to_use = model or self.model_chat
        temperature_to_use = temperature or self.temperature
        max_tokens_to_use = max_tokens or self.max_tokens

        self.logger.info(
            "Chat API called with model=%s, temperature=%.2f, max_tokens=%d, n=%d",
            model_to_use, temperature_to_use, max_tokens_to_use, n
        )

        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model_to_use,
                messages=messages,
                max_tokens=max_tokens_to_use,
                temperature=temperature_to_use,
                n=n
            )
            response_dict = response.to_dict()
            self.logger.debug("Chat API response received: %s", response_dict.keys())
            messages_content = [choice['message']['content'] for choice in response_dict.get('choices', [])]
            self.logger.info("Chat API call successful, number of choices returned: %d", len(messages_content))
            return messages_content
        except Exception as e:
            self.logger.error("Error during chat call: %s", str(e), exc_info=True)
            return None

    def _count_tokens(self, text):
        """Count the number of tokens in a text string."""
        token_count = len(self.encoding.encode(text))
        self.logger.debug("Token count for text: %d tokens", token_count)
        return token_count

    def _chunk_text(self, text):
        """Split text into chunks that fit within the token limit."""
        tokens = self.encoding.encode(text)
        chunks = [self.encoding.decode(tokens[i:i+self.token_limit]) for i in range(0, len(tokens), self.token_limit)]
        self.logger.info("Text chunked into %d chunks based on token limit %d", len(chunks), self.token_limit)
        return chunks

    async def get_embeddings(self, text_list):
        """
        Asynchronous generation of embeddings for a list of texts using OpenAI API.
        """
        self.logger.info("get_embeddings called with %d texts", len(text_list))
        try:
            all_embeddings = []

            for idx, text in enumerate(text_list):
                token_count = self._count_tokens(text)
                if token_count > self.token_limit:
                    self.logger.warning(
                        "Text at index %d exceeds token limit (%d > %d). Chunking required.",
                        idx, token_count, self.token_limit
                    )
                    text_chunks = self._chunk_text(text)
                else:
                    text_chunks = [text]
                    self.logger.debug("Text at index %d does not exceed token limit", idx)

                embeddings = []
                for chunk_idx, chunk in enumerate(text_chunks):
                    self.logger.debug(
                        "Generating embedding for chunk %d of text index %d",
                        chunk_idx, idx
                    )
                    embedding_response = await asyncio.to_thread(
                        client.embeddings.create,
                        model=self.model_embedding,
                        input=chunk
                    )
                    embedding_data = embedding_response.to_dict().get('data', [])
                    embeddings.extend([data['embedding'] for data in embedding_data])
                    self.logger.debug(
                        "Received %d embeddings for chunk %d of text index %d",
                        len(embedding_data), chunk_idx, idx
                    )

                if embeddings:
                    aggregated_embedding = np.mean(embeddings, axis=0)
                    all_embeddings.append(aggregated_embedding)
                    self.logger.info(
                        "Aggregated embedding for text index %d", idx
                    )
                else:
                    self.logger.warning(
                        "No embeddings received for text index %d", idx
                    )

            self.logger.info("get_embeddings completed successfully")
            return np.array(all_embeddings)
        except Exception as e:
            self.logger.error("Error during embedding call for texts: %s", str(e), exc_info=True)
            return None

    def set_default_chat_model(self, model):
        """Set the default model for all future calls."""
        old_model = self.model_chat
        self.model_chat = model
        self.logger.info("Default chat model changed from %s to %s", old_model, self.model_chat)

    def set_default_embedding_model(self, model):
        """Set the default model for all future calls."""
        old_model = self.model_embedding
        self.model_embedding = model
        self.logger.info("Default embedding model changed from %s to %s", old_model, self.model_embedding)

    def set_default_temperature(self, temperature):
        """Set the default temperature for all future calls."""
        old_temperature = self.temperature
        self.temperature = temperature
        self.logger.info("Default temperature changed from %.2f to %.2f", old_temperature, self.temperature)

    def set_default_max_tokens(self, max_tokens):
        """Set the default max_tokens for all future calls."""
        old_max_tokens = self.max_tokens
        self.max_tokens = max_tokens
        self.logger.info("Default max_tokens changed from %d to %d", old_max_tokens, self.max_tokens)

    def get_available_models(self):
        """Fetch the available models from OpenAI."""
        self.logger.info("Fetching available models from OpenAI")
        try:
            models = client.models.list()
            model_ids = [model.id for model in models.data]
            self.logger.info("Fetched %d models successfully", len(model_ids))
            return model_ids
        except Exception as e:
            self.logger.error("Error fetching models: %s", str(e), exc_info=True)
            return None
