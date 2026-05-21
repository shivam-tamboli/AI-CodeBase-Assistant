"""OpenAI concrete providers for LLM completions and embeddings."""
import asyncio
import logging
from typing import AsyncIterator, List

from openai import AsyncOpenAI, RateLimitError, APIStatusError

from backend.services.providers.base import LLMProvider, EmbeddingProvider

logger = logging.getLogger(__name__)

_EMBED_BATCH_SIZE = 2000
_MAX_RETRIES = 3


class OpenAILLMProvider(LLMProvider):
    """OpenAI chat-completions provider (gpt-4o-mini, gpt-4o, gpt-4, …)."""

    def __init__(self, api_key: str, model: str):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    def _build_messages(self, system: str, messages: List[dict]) -> List[dict]:
        return [{"role": "system", "content": system}, *messages]

    async def complete(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_messages(system, messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def stream(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=self._build_messages(system, messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings provider (text-embedding-3-small, text-embedding-3-large, …)."""

    def __init__(self, api_key: str, model: str, dims: int = 1536):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._dimensions = dims

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def _batch_with_retry(self, batch: List[str]) -> List[List[float]]:
        delay = 1.0
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.embeddings.create(
                    model=self._model,
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
                        "Embedding API %d error (attempt %d/%d), retrying in %.1fs",
                        exc.status_code, attempt, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    raise
        return []

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        result: List[List[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[i: i + _EMBED_BATCH_SIZE]
            result.extend(await self._batch_with_retry(batch))
        return result
