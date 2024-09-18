from _utils._util import *  # Assuming logging is imported from _utils._util

import tiktoken
from openai import OpenAI

# SANITIZED KEY
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class LLM:
    def __init__(self, model_chat: str = "gpt-4o-mini", model_embedding: str = 'text-embedding-3-large', max_tokens: int = 265, temperature: float = 0.7):
        self.model_chat = model_chat
        self.model_embedding = model_embedding
        self.token_limit = 4095  # token limit for 'text-embedding-3-large'
        self.encoding = tiktoken.encoding_for_model(model_embedding)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(
            "LLM initialized with parameters: model_chat=%s, model_embedding=%s, max_tokens=%d, temperature=%.2f",
            self.model_chat, self.model_embedding, self.max_tokens, self.temperature
        )

    async def chat(self, messages: List[dict], model: str = None, temperature: float = None, max_tokens: int = None, n: int = 1) -> List[str]:
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
            self.logger.error("Error during chat call: %s\nmessages: %s", str(e), messages, exc_info=True)
            return None

    def _count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        token_count = len(self.encoding.encode(text))
        self.logger.debug("Token count for text: %d tokens", token_count)
        return token_count

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks that fit within the token limit."""
        tokens = self.encoding.encode(text)
        chunks = [self.encoding.decode(tokens[i:i+self.token_limit]) for i in range(0, len(tokens), self.token_limit)]
        self.logger.info("Text chunked into %d chunks based on token limit %d", len(chunks), self.token_limit)
        return chunks

    async def get_embeddings(self, text_list: List[str]) -> np.ndarray:
        """
        Asynchronous generation of embeddings for a list of texts using OpenAI API.
        """
        self.logger.info("get_embeddings called with %d texts", len(text_list))
        try:
            batches = self._create_batches(text_list)
            all_embeddings = []

            for batch in batches:
                self.logger.debug("Generating embeddings for a batch of %d texts", len(batch))
                embedding_response = await asyncio.to_thread(
                    client.embeddings.create,
                    model=self.model_embedding,
                    input=batch
                )
                embedding_data = embedding_response.to_dict().get('data', [])
                batch_embeddings = [data['embedding'] for data in embedding_data]

                if batch_embeddings:
                    all_embeddings.extend(batch_embeddings)
                    self.logger.info("Aggregated embeddings for current batch")
                else:
                    self.logger.warning("No embeddings received for current batch")

            self.logger.info("get_embeddings completed successfully")
            return np.array(all_embeddings)
        except Exception as e:
            self.logger.error("Error during embedding call for texts: %s\ntext_list: %s", str(e), text_list, exc_info=True)
            return np.array([])

    def _create_batches(self, text_list: List[str]) -> List[List[str]]:
        """
        Create batches of texts where the total tokens per batch do not exceed the token limit.
        """
        batches = []
        current_batch = []
        current_tokens = 0

        for text in text_list:
            token_count = self._count_tokens(text)
            
            if token_count > self.token_limit:
                self.logger.warning(
                    "Text exceeds token limit (%d > %d). Chunking required.",
                    token_count, self.token_limit
                )
                text_chunks = self._chunk_text(text)
                for chunk in text_chunks:
                    chunk_tokens = self._count_tokens(chunk)
                    if current_tokens + chunk_tokens > self.token_limit:
                        if current_batch:
                            batches.append(current_batch)
                            self.logger.debug("Batch appended with %d texts/chunks", len(current_batch))
                            current_batch = []
                            current_tokens = 0
                    current_batch.append(chunk)
                    current_tokens += chunk_tokens
            else:
                if current_tokens + token_count > self.token_limit:
                    if current_batch:
                        batches.append(current_batch)
                        self.logger.debug("Batch appended with %d texts", len(current_batch))
                        current_batch = []
                        current_tokens = 0
                current_batch.append(text)
                current_tokens += token_count

        if current_batch:
            batches.append(current_batch)
            self.logger.debug("Final batch appended with %d texts", len(current_batch))

        self.logger.debug("Created %d batches for embedding generation", len(batches))
        return batches

    def set_default_chat_model(self, model: str) -> None:
        """Set the default model for all future calls."""
        old_model = self.model_chat
        self.model_chat = model
        self.logger.info("Default chat model changed from %s to %s", old_model, self.model_chat)

    def set_default_embedding_model(self, model: str) -> None:
        """Set the default model for all future calls."""
        old_model = self.model_embedding
        self.model_embedding = model
        self.logger.info("Default embedding model changed from %s to %s", old_model, self.model_embedding)

    def set_default_temperature(self, temperature: float) -> None:
        """Set the default temperature for all future calls."""
        old_temperature = self.temperature
        self.temperature = temperature
        self.logger.info("Default temperature changed from %.2f to %.2f", old_temperature, self.temperature)

    def set_default_max_tokens(self, max_tokens: int) -> None:
        """Set the default max_tokens for all future calls."""
        old_max_tokens = self.max_tokens
        self.max_tokens = max_tokens
        self.logger.info("Default max_tokens changed from %d to %d", old_max_tokens, self.max_tokens)

    def get_available_models(self) -> List[str]:
        """Fetch the available models from OpenAI."""
        self.logger.info("Fetching available models from OpenAI")
        try:
            models = client.models.list()
            model_ids = [model.id for model in models.data]
            self.logger.info("Fetched %d models successfully", len(model_ids))
            return model_ids
        except Exception as e:
            self.logger.error("Error fetching models: %s", str(e), exc_info=True)
            return []
