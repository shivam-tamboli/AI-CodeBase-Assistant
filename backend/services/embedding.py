"""EmbeddingService — thin wrapper around the configured EmbeddingProvider.

Provider is selected via environment variable:
  EMBEDDING_PROVIDER=openai   (default; only supported option currently)
  EMBEDDING_MODEL=text-embedding-3-small

Switching provider in the future requires only .env changes.
"""
import os
from typing import List, Optional

from backend.services.providers.base import EmbeddingProvider
from backend.services.providers.factory import get_embedding_provider


class EmbeddingService:
    """Public API for generating embeddings — delegates to EmbeddingProvider."""

    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        self._provider = provider or get_embedding_provider()

    @property
    def dimensions(self) -> int:
        return self._provider.dimensions

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return await self._provider.embed_one(text)

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for an arbitrary number of texts.

        Batching and retry are handled by the underlying provider.
        """
        return await self._provider.embed_batch(texts)

    async def generate_embedding_with_dimensions(
        self, text: str, dimensions: int = 1536
    ) -> List[float]:
        """Generate embedding with custom dimensions (OpenAI provider only).

        Falls back to standard embedding if the provider does not support
        custom dimensions.
        """
        from backend.services.providers.openai_provider import OpenAIEmbeddingProvider
        if isinstance(self._provider, OpenAIEmbeddingProvider):
            import os
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
            response = await client.embeddings.create(
                model=model,
                input=text,
                dimensions=dimensions,
                encoding_format="float",
            )
            return response.data[0].embedding
        return await self._provider.embed_one(text)
