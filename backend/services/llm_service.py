import logging
import os
from typing import AsyncIterator, Dict, Any, List, Optional

from dotenv import load_dotenv
from openai import RateLimitError, APIError

from backend.services.providers.base import LLMProvider
from backend.services.providers.factory import get_llm_provider

load_dotenv()

logger = logging.getLogger(__name__)


class LLMService:
    """Generates LLM answers for retrieved code context.

    Delegates to a pluggable LLMProvider so that switching between
    OpenAI and Anthropic Claude requires only .env changes:

      LLM_PROVIDER=anthropic
      LLM_MODEL=claude-sonnet-4-6
      ANTHROPIC_API_KEY=sk-ant-...
    """

    MAX_HISTORY_TOKENS = 2000

    _SYSTEM_PROMPT = (
        "You are an expert code analyst specialising in understanding and "
        "explaining software codebases.\n\n"
        "When answering questions:\n"
        "1. Cite specific file paths and line numbers for every claim\n"
        "2. Include relevant code snippets from the provided context\n"
        "3. If the answer is not in the context, clearly say so\n"
        "4. Provide clear, actionable explanations\n"
        "5. Use markdown formatting for readability\n"
        "6. Focus on explaining HOW the code works, not just WHAT it does"
    )

    def __init__(self, provider: Optional[LLMProvider] = None):
        self._provider = provider or get_llm_provider()
        self.temperature = 0.2
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2000"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _format_context(self, chunks: List[Dict[str, Any]]) -> str:
        parts = []
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.get("metadata", {})
            header = (
                f"Source {i}: {meta.get('file_path', 'unknown')}"
                f":{meta.get('start_line', 0)}-{meta.get('end_line', 0)}"
            )
            name = meta.get("name", "")
            if name:
                header += f" ({meta.get('chunk_type', 'code')}: {name})"
            parts.append(f"--- {header} ---\n{chunk.get('content', '')}\n")
        return "\n".join(parts)

    def _truncate_history(
        self, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return the most recent history entries within MAX_HISTORY_TOKENS."""
        if not history:
            return []

        import tiktoken
        try:
            enc = tiktoken.encoding_for_model("gpt-4o-mini")
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")

        def token_count(msgs: List[Dict]) -> int:
            return sum(len(enc.encode(m.get("content", ""))) for m in msgs)

        truncated = list(history)
        while truncated and token_count(truncated) > self.MAX_HISTORY_TOKENS:
            truncated = truncated[2:] if len(truncated) >= 2 else truncated[1:]
        return truncated

    def _build_messages(
        self,
        query: str,
        context: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, str]]:
        """Build the conversation messages array (without system prompt).

        History is passed as native alternating user/assistant turns.
        The final user turn contains the retrieved context and the query.
        """
        messages: List[Dict[str, str]] = []

        for msg in self._truncate_history(chat_history or []):
            role = msg.get("role", "user")
            if role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": msg.get("content", "")})

        user_content = (
            "Based on the following code context from the uploaded repository, "
            "answer the question.\n\n"
            f"Context:\n---\n{context}\n---\n\n"
            f"Question: {query}\n\n"
            "Cite sources in the format [filename:lines]. If the context does "
            "not contain enough information to fully answer, acknowledge what "
            "you can explain from the available context."
        )
        messages.append({"role": "user", "content": user_content})
        return messages

    def _validate_citations(
        self,
        answer: str,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check that file paths cited in the answer appear in retrieved chunks."""
        import re

        _INDEXED_EXTENSIONS = r'\.(?:py|js|ts|jsx|tsx|go|java|rs|rb)'
        cited_files = set(re.findall(r'[\w/._-]+' + _INDEXED_EXTENSIONS, answer))

        source_paths = {
            chunk.get("metadata", {}).get("file_path", "")
            for chunk in retrieved_chunks
        }
        source_basenames = {fp.split("/")[-1] for fp in source_paths if fp}

        hallucinated = [
            f for f in cited_files
            if f not in source_paths and f.split("/")[-1] not in source_basenames
        ]
        return {
            "cited_files": sorted(cited_files),
            "hallucinated_files": hallucinated,
            "citation_valid": len(hallucinated) == 0,
        }

    def _build_sources(
        self, retrieved_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        sources = []
        for chunk in retrieved_chunks:
            meta = chunk.get("metadata", {})
            sources.append({
                "file_path": meta.get("file_path", ""),
                "start_line": meta.get("start_line", 0),
                "end_line": meta.get("end_line", 0),
                "chunk_type": meta.get("chunk_type", "code"),
                "name": meta.get("name", ""),
                "score": chunk.get("final_score", chunk.get("hybrid_score", 0)),
            })
        return sources

    def _append_citation_warning(
        self, answer: str, citation_check: Dict[str, Any]
    ) -> str:
        if citation_check["hallucinated_files"]:
            unverified = ", ".join(
                f"`{f}`" for f in citation_check["hallucinated_files"]
            )
            answer += (
                f"\n\n> **Note**: The following file references could not be "
                f"verified against the indexed source: {unverified}"
            )
        return answer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_answer(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate a complete answer from retrieved context."""
        if not retrieved_chunks:
            return {
                "answer": (
                    "No relevant code found for your question. "
                    "Try rephrasing or asking about a different aspect of the codebase."
                ),
                "sources": [],
            }

        try:
            context = self._format_context(retrieved_chunks)
            messages = self._build_messages(query, context, chat_history)

            answer = await self._provider.complete(
                system=self._SYSTEM_PROMPT,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            citation_check = self._validate_citations(answer, retrieved_chunks)
            answer = self._append_citation_warning(answer, citation_check)

            return {
                "answer": answer,
                "sources": self._build_sources(retrieved_chunks),
                "chunks_used": len(retrieved_chunks),
                "citation_valid": citation_check["citation_valid"],
                "citation_warnings": citation_check["hallucinated_files"],
            }

        except RateLimitError:
            return {
                "answer": "Rate limit reached. Please wait a moment and try again.",
                "sources": [],
                "error": "rate_limit",
            }
        except APIError as e:
            return {
                "answer": f"API error occurred: {e}",
                "sources": [],
                "error": "api_error",
            }
        except Exception as e:
            logger.error("LLM generation error: %s", e)
            return {
                "answer": f"Error generating answer: {e}",
                "sources": [],
                "error": "unknown",
            }

    async def generate_streaming_answer(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Generate an answer with streaming token events."""
        if not retrieved_chunks:
            yield {
                "type": "done",
                "answer": "No relevant code found for your question.",
                "sources": [],
            }
            return

        try:
            context = self._format_context(retrieved_chunks)
            messages = self._build_messages(query, context, chat_history)
            sources = self._build_sources(retrieved_chunks)

            full_answer = ""
            async for token in self._provider.stream(
                system=self._SYSTEM_PROMPT,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            ):
                full_answer += token
                yield {"type": "token", "token": token, "answer": full_answer}

            citation_check = self._validate_citations(full_answer, retrieved_chunks)
            full_answer = self._append_citation_warning(full_answer, citation_check)

            yield {
                "type": "done",
                "answer": full_answer,
                "sources": sources,
                "chunks_used": len(retrieved_chunks),
                "citation_valid": citation_check["citation_valid"],
                "citation_warnings": citation_check["hallucinated_files"],
            }

        except RateLimitError:
            yield {
                "type": "error",
                "answer": "Rate limit reached. Please wait a moment and try again.",
                "error": "rate_limit",
            }
        except APIError as e:
            yield {
                "type": "error",
                "answer": f"API error occurred: {e}",
                "error": "api_error",
            }
        except Exception as e:
            logger.error("Streaming LLM error: %s", e)
            yield {
                "type": "error",
                "answer": f"Error: {e}",
                "error": "unknown",
            }

    async def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("text-embedding-3-small")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    async def estimate_response_tokens(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """Estimate token usage before making an API call."""
        context = self._format_context(retrieved_chunks)
        system_tokens = await self.count_tokens(self._SYSTEM_PROMPT)
        context_tokens = await self.count_tokens(context)
        query_tokens = await self.count_tokens(query)
        total_input = system_tokens + context_tokens + query_tokens
        return {
            "system_tokens": system_tokens,
            "context_tokens": context_tokens,
            "query_tokens": query_tokens,
            "total_input_tokens": total_input,
            "max_response_tokens": self.max_tokens,
            "total_tokens": total_input + self.max_tokens,
            "within_limit": total_input < (128_000 - self.max_tokens),
        }
