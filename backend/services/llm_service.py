from openai import AsyncOpenAI, RateLimitError, APIError
from typing import List, Dict, Any, AsyncIterator, Optional
import os
from dotenv import load_dotenv

load_dotenv()


class LLMService:
    """Handles LLM interactions for answer generation"""

    MAX_HISTORY_TOKENS = 2000

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment variables")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.temperature = 0.2
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2000"))

    def _format_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved code chunks for LLM context"""
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get("metadata", {})
            file_path = metadata.get("file_path", "unknown")
            start_line = metadata.get("start_line", 0)
            end_line = metadata.get("end_line", 0)
            chunk_type = metadata.get("chunk_type", "code")
            name = metadata.get("name", "")

            header = f"Source {i}: {file_path}:{start_line}-{end_line}"
            if name:
                header += f" ({chunk_type}: {name})"

            context_parts.append(
                f"--- {header} ---\n{chunk.get('content', '')}\n"
            )

        return "\n".join(context_parts)

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """Format chat history for inclusion in prompt"""
        if not history:
            return ""

        history_parts = []
        for msg in history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            history_parts.append(f"{role.upper()}: {content}")

        return "\n\n".join(history_parts)

    def _build_prompt(
        self,
        query: str,
        context: str,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, str]]:
        """Build prompt with system and user messages"""

        system_prompt = """You are an expert code analyst specializing in understanding and explaining software codebases.

When answering questions:
1. Cite specific file paths and line numbers for every claim
2. Include relevant code snippets from the provided context
3. If the answer isn't in the context, clearly state that
4. Provide clear, actionable explanations
5. Use markdown formatting for readability
6. Focus on explaining HOW the code works, not just WHAT it does
7. Use conversation history to maintain context in multi-turn conversations"""

        history_text = self._format_history(chat_history) if chat_history else ""

        history_section = f"""
Previous conversation:
---
{history_text}
---

""" if history_text else ""

        user_prompt = f"""Based on the following code context from the uploaded repository, answer the user's question.

{history_section}Context:
---
{context}
---

Question: {query}

Provide your answer with source citations in the format [filename:lines]. If the context doesn't contain enough information to fully answer the question, acknowledge what you can explain from the available context."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _validate_citations(
        self,
        answer: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate that file paths cited in the answer exist in retrieved chunks.

        Extracts all .py paths from the answer text and checks each against
        the file_path metadata of the chunks that were actually retrieved.
        Returns a dict with citation_valid flag and list of unverified paths.
        """
        import re

        cited_files = set(re.findall(r'[\w/._-]+\.py', answer))

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
            "citation_valid": len(hallucinated) == 0
        }

    async def generate_answer(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Generate answer from retrieved context"""

        if not retrieved_chunks:
            return {
                "answer": "No relevant code found for your question. Try rephrasing or asking about a different aspect of the codebase.",
                "sources": []
            }

        try:
            context = self._format_context(retrieved_chunks)
            messages = self._build_prompt(query, context, chat_history)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            answer = response.choices[0].message.content

            citation_check = self._validate_citations(answer, retrieved_chunks)
            if citation_check["hallucinated_files"]:
                unverified = ", ".join(f"`{f}`" for f in citation_check["hallucinated_files"])
                answer += (
                    f"\n\n> **Note**: The following file references could not be "
                    f"verified against the indexed source: {unverified}"
                )

            sources = []
            for chunk in retrieved_chunks:
                metadata = chunk.get("metadata", {})
                sources.append({
                    "file_path": metadata.get("file_path", ""),
                    "start_line": metadata.get("start_line", 0),
                    "end_line": metadata.get("end_line", 0),
                    "chunk_type": metadata.get("chunk_type", "code"),
                    "name": metadata.get("name", ""),
                    "score": chunk.get("final_score", chunk.get("hybrid_score", 0))
                })

            return {
                "answer": answer,
                "sources": sources,
                "chunks_used": len(retrieved_chunks),
                "citation_valid": citation_check["citation_valid"],
                "citation_warnings": citation_check["hallucinated_files"]
            }

        except RateLimitError:
            return {
                "answer": "Rate limit reached. Please wait a moment and try again.",
                "sources": [],
                "error": "rate_limit"
            }
        except APIError as e:
            return {
                "answer": f"API error occurred: {str(e)}",
                "sources": [],
                "error": "api_error"
            }
        except Exception as e:
            return {
                "answer": f"Error generating answer: {str(e)}",
                "sources": [],
                "error": "unknown"
            }

    async def generate_streaming_answer(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Generate answer with streaming responses"""

        if not retrieved_chunks:
            yield {
                "type": "done",
                "answer": "No relevant code found for your question.",
                "sources": []
            }
            return

        try:
            context = self._format_context(retrieved_chunks)
            messages = self._build_prompt(query, context, chat_history)

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )

            sources = []
            for chunk in retrieved_chunks:
                metadata = chunk.get("metadata", {})
                sources.append({
                    "file_path": metadata.get("file_path", ""),
                    "start_line": metadata.get("start_line", 0),
                    "end_line": metadata.get("end_line", 0),
                    "chunk_type": metadata.get("chunk_type", "code"),
                    "name": metadata.get("name", ""),
                    "score": chunk.get("final_score", chunk.get("hybrid_score", 0))
                })

            full_answer = ""

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_answer += token
                    yield {
                        "type": "token",
                        "token": token,
                        "answer": full_answer
                    }

            yield {
                "type": "done",
                "answer": full_answer,
                "sources": sources,
                "chunks_used": len(retrieved_chunks)
            }

        except RateLimitError:
            yield {
                "type": "error",
                "answer": "Rate limit reached. Please wait a moment and try again.",
                "error": "rate_limit"
            }
        except APIError as e:
            yield {
                "type": "error",
                "answer": f"API error occurred: {str(e)}",
                "error": "api_error"
            }
        except Exception as e:
            yield {
                "type": "error",
                "answer": f"Error: {str(e)}",
                "error": "unknown"
            }

    async def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("text-embedding-3-small")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    async def estimate_response_tokens(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Estimate token usage before making API call"""

        context = self._format_context(retrieved_chunks)

        system_prompt = """You are an expert code analyst..."""
        system_tokens = await self.count_tokens(system_prompt)
        context_tokens = await self.count_tokens(context)
        query_tokens = await self.count_tokens(query)

        total_input_tokens = system_tokens + context_tokens + query_tokens
        estimated_response_tokens = self.max_tokens

        return {
            "system_tokens": system_tokens,
            "context_tokens": context_tokens,
            "query_tokens": query_tokens,
            "total_input_tokens": total_input_tokens,
            "max_response_tokens": estimated_response_tokens,
            "total_tokens": total_input_tokens + estimated_response_tokens,
            "within_limit": total_input_tokens < (8000 - estimated_response_tokens)
        }
