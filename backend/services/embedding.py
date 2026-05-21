import asyncio
import logging
from openai import AsyncOpenAI, RateLimitError, APIStatusError
from typing import List
import os

logger = logging.getLogger(__name__)

_BATCH_SIZE = 2000
_MAX_RETRIES = 3


class EmbeddingService:
    """Handles OpenAI embedding generation with batching and retry."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in .env")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.dimensions = 1536

    async def _embed_batch_with_retry(self, batch: List[str]) -> List[List[float]]:
        """Send one batch to the OpenAI API with exponential-backoff retry."""
        delay = 1.0
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    encoding_format="float",
                )
                return [item.embedding for item in response.data]
            except RateLimitError:
                if attempt == _MAX_RETRIES:
                    raise
                logger.warning(
                    "Embedding rate-limited (attempt %d/%d), retrying in %.1fs",
                    attempt, _MAX_RETRIES, delay,
                )
                await asyncio.sleep(delay)
                delay *= 2
            except APIStatusError as exc:
                if exc.status_code >= 500 and attempt < _MAX_RETRIES:
                    logger.warning(
                        "Embedding API error %d (attempt %d/%d), retrying in %.1fs",
                        exc.status_code, attempt, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    raise
        return []

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        results = await self._embed_batch_with_retry([text])
        return results[0]

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for an arbitrary number of texts.

        Splits input into batches of at most 2,000 (OpenAI API limit) and
        retries each batch independently on rate-limit or server errors.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i: i + _BATCH_SIZE]
            logger.debug(
                "Embedding batch %d-%d of %d texts",
                i + 1, i + len(batch), len(texts),
            )
            embeddings = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def generate_embedding_with_dimensions(
        self, text: str, dimensions: int = 1536
    ) -> List[float]:
        """Generate embedding with custom dimensions.

        text-embedding-3-small supports 256–3072 dimensions.
        """
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=dimensions,
            encoding_format="float",
        )
        return response.data[0].embedding
