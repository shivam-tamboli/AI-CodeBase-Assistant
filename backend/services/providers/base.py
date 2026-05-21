"""Abstract base classes for LLM and embedding providers.

All provider implementations must satisfy these interfaces. The canonical
message format is provider-neutral:

  system: str          — system / instruction prompt
  messages: list[dict] — alternating {"role": "user"|"assistant", "content": "..."}

Concrete providers translate to their SDK's native format internally.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List


class LLMProvider(ABC):
    """Abstract LLM completion provider."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> str:
        """Return a complete response string for the given conversation."""
        ...

    @abstractmethod
    async def stream(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        """Yield response text tokens incrementally."""
        ...


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Dimensionality of the embedding vectors produced."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Return one embedding vector per input text, in the same order."""
        ...

    async def embed_one(self, text: str) -> List[float]:
        """Convenience wrapper — embed a single text."""
        results = await self.embed_batch([text])
        return results[0]
