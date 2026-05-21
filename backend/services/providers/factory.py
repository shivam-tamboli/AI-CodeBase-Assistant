"""Factory functions for constructing configured provider instances.

Environment variables:
  LLM_PROVIDER        openai (default) | anthropic
  LLM_MODEL           gpt-4o-mini (default) | claude-sonnet-4-6 | …
  EMBEDDING_PROVIDER  openai (default; only supported option currently)
  EMBEDDING_MODEL     text-embedding-3-small (default)
  OPENAI_API_KEY      required when LLM_PROVIDER=openai or EMBEDDING_PROVIDER=openai
  ANTHROPIC_API_KEY   required when LLM_PROVIDER=anthropic
"""
import os

from backend.services.providers.base import LLMProvider, EmbeddingProvider


def get_llm_provider() -> LLMProvider:
    """Return a configured LLMProvider based on LLM_PROVIDER env var."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set when LLM_PROVIDER=anthropic"
            )
        from backend.services.providers.anthropic_provider import AnthropicLLMProvider
        return AnthropicLLMProvider(api_key=api_key, model=model)

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY must be set when LLM_PROVIDER=openai"
            )
        from backend.services.providers.openai_provider import OpenAILLMProvider
        return OpenAILLMProvider(api_key=api_key, model=model)

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}. "
        "Supported values: openai, anthropic"
    )


def get_embedding_provider() -> EmbeddingProvider:
    """Return a configured EmbeddingProvider based on EMBEDDING_PROVIDER env var."""
    provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY must be set when EMBEDDING_PROVIDER=openai"
            )
        from backend.services.providers.openai_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(api_key=api_key, model=model)

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER={provider!r}. "
        "Supported values: openai"
    )
