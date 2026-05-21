"""Chunk summary generation service.

Generates a one-sentence natural-language summary for each code chunk using
the configured LLM provider. Summaries are prepended to the chunk content
before embedding, improving semantic retrieval for conceptual queries.

Controlled by the ENABLE_CHUNK_SUMMARIES environment variable (default: false).
"""
import asyncio
import logging
from typing import Dict, List, Optional

from backend.services.providers.factory import get_llm_provider
from backend.services.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a code search indexing assistant. "
    "Summarize the provided code in exactly one sentence. "
    "State what the code does — its purpose — not implementation details. "
    "Output only the sentence, no preamble."
)


class SummaryService:
    """Generates one-sentence summaries for code chunks using the LLM provider."""

    def __init__(self, provider: Optional[LLMProvider] = None, concurrency: int = 10):
        self._provider = provider or get_llm_provider()
        self._semaphore = asyncio.Semaphore(concurrency)

    async def summarize_chunk(self, content: str, chunk_type: str = "", name: str = "") -> str:
        """Return a one-sentence summary for a single chunk, or '' on failure."""
        if not content or not content.strip():
            return ""

        label = f"{chunk_type}: {name}" if name else chunk_type
        user_message = f"Code chunk ({label}):\n\n{content}" if label else content

        async with self._semaphore:
            try:
                return await self._provider.complete(
                    _SYSTEM_PROMPT,
                    [{"role": "user", "content": user_message}],
                    max_tokens=100,
                    temperature=0.0,
                )
            except Exception as exc:
                logger.warning("Summary generation failed for chunk '%s': %s", name, exc)
                return ""

    async def summarize_chunks(self, chunks: List[Dict]) -> List[str]:
        """Return one summary per chunk, in the same order. Failures return ''."""
        tasks = [
            self.summarize_chunk(
                chunk.get("content", ""),
                chunk.get("chunk_type", ""),
                chunk.get("name", ""),
            )
            for chunk in chunks
        ]
        return await asyncio.gather(*tasks)
