"""Provider abstraction layer for LLM and embedding services.

Switching providers requires only environment-variable changes:
  LLM_PROVIDER=openai|anthropic
  EMBEDDING_PROVIDER=openai
  LLM_MODEL=gpt-4o-mini|claude-sonnet-4-6
  EMBEDDING_MODEL=text-embedding-3-small
"""
from backend.services.providers.base import LLMProvider, EmbeddingProvider
from backend.services.providers.factory import get_llm_provider, get_embedding_provider

__all__ = [
    "LLMProvider",
    "EmbeddingProvider",
    "get_llm_provider",
    "get_embedding_provider",
]
