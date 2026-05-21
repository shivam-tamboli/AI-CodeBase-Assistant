"""Anthropic Claude LLM provider.

Requires:  ANTHROPIC_API_KEY env var
           pip install anthropic>=0.27.0

The Anthropic messages API differs from OpenAI in two structural ways:
  1. The system prompt is a top-level `system` parameter, not a message.
  2. Response text lives at `response.content[0].text`.

Streaming uses the async context-manager style:
  async with client.messages.stream(...) as s:
      async for text in s.text_stream: ...

Note: Anthropic has no embedding API. Use OpenAI or Voyage for embeddings
when LLM_PROVIDER=anthropic.
"""
import logging
from typing import AsyncIterator, List

from backend.services.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicLLMProvider(LLMProvider):
    """Anthropic Claude provider (claude-sonnet-4-6, claude-haiku-4-5, …)."""

    def __init__(self, api_key: str, model: str):
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is required for LLM_PROVIDER=anthropic. "
                "Install it with: pip install anthropic>=0.27.0"
            ) from exc

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> str:
        import anthropic

        response = await self._client.messages.create(
            model=self._model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.content[0].text

    async def stream(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self._model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text
