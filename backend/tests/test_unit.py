"""
Unit tests for pure business logic (no DB, no HTTP calls).

Tests chunker, JWT utilities, and RRF scoring — all without any I/O.
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.auth.jwt import create_access_token, verify_token
from backend.services.chunker import CodeChunker


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

class TestJWT:
    def test_create_and_verify_roundtrip(self):
        token = create_access_token({"sub": "user123", "username": "alice"})
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["username"] == "alice"

    def test_expired_token_returns_none(self):
        from datetime import timedelta
        token = create_access_token({"sub": "x"}, expires_delta=timedelta(seconds=-1))
        assert verify_token(token) is None

    def test_tampered_token_returns_none(self):
        token = create_access_token({"sub": "user123"})
        tampered = token[:-4] + "XXXX"
        assert verify_token(tampered) is None

    def test_token_contains_exp_and_iat(self):
        token = create_access_token({"sub": "u1"})
        payload = verify_token(token)
        assert "exp" in payload
        assert "iat" in payload


# ---------------------------------------------------------------------------
# CodeChunker
# ---------------------------------------------------------------------------

SIMPLE_PYTHON = """\
import os
import sys


def greet(name: str) -> str:
    return f"Hello, {name}"


class Calculator:
    def add(self, a, b):
        return a + b
"""

EMPTY_PYTHON = ""
INVALID_PYTHON = "def broken_function(:\n    pass"


class TestCodeChunker:
    def setup_method(self):
        self.chunker = CodeChunker(max_tokens=1000, overlap=100)

    def test_chunks_simple_file(self):
        chunks = self.chunker.chunk_file(SIMPLE_PYTHON, file_path="test.py")
        assert len(chunks) > 0

    def test_chunk_types_present(self):
        chunks = self.chunker.chunk_file(SIMPLE_PYTHON, file_path="test.py")
        types = {c["chunk_type"] for c in chunks}
        assert "function" in types
        assert "class" in types

    def test_imports_chunk_has_correct_file_path(self):
        chunks = self.chunker.chunk_file(SIMPLE_PYTHON, file_path="mymodule/utils.py")
        imports = [c for c in chunks if c["chunk_type"] == "imports"]
        if imports:
            assert imports[0]["file_path"] == "mymodule/utils.py"

    def test_function_chunk_metadata(self):
        chunks = self.chunker.chunk_file(SIMPLE_PYTHON, file_path="test.py")
        func_chunks = [c for c in chunks if c["chunk_type"] == "function"]
        assert any(c["name"] == "greet" for c in func_chunks)

    def test_class_chunk_metadata(self):
        chunks = self.chunker.chunk_file(SIMPLE_PYTHON, file_path="test.py")
        class_chunks = [c for c in chunks if c["chunk_type"] == "class"]
        assert any(c["name"] == "Calculator" for c in class_chunks)

    def test_empty_source_returns_empty_list(self):
        assert self.chunker.chunk_file(EMPTY_PYTHON) == []

    def test_whitespace_only_returns_empty_list(self):
        assert self.chunker.chunk_file("   \n\n\t  ") == []

    def test_invalid_python_returns_empty_list(self):
        assert self.chunker.chunk_file(INVALID_PYTHON) == []

    def test_count_tokens_basic(self):
        assert self.chunker.count_tokens("hello world") > 0

    def test_count_tokens_empty(self):
        assert self.chunker.count_tokens("") == 0

    def test_all_chunks_have_required_fields(self):
        chunks = self.chunker.chunk_file(SIMPLE_PYTHON, file_path="test.py")
        # Chunker produces flat dicts; VectorStore adds the metadata sub-doc on save
        required = {"content", "chunk_type", "file_path", "name"}
        for chunk in chunks:
            assert required.issubset(chunk.keys()), f"Chunk missing fields: {chunk}"

    def test_chunks_have_line_numbers(self):
        chunks = self.chunker.chunk_file(SIMPLE_PYTHON, file_path="test.py")
        for chunk in chunks:
            if chunk["chunk_type"] in ("function", "class"):
                assert chunk.get("start_line", 0) > 0


# ---------------------------------------------------------------------------
# RRF scoring (HybridSearchService._reciprocal_rank_fusion)
# ---------------------------------------------------------------------------

def _make_doc(file_path: str, start: int = 1, end: int = 10) -> dict:
    """Minimal MongoDB chunk doc (post-storage format with metadata sub-dict)."""
    return {
        "content": f"def foo(): pass  # {file_path}:{start}",
        "metadata": {"file_path": file_path, "start_line": start, "end_line": end, "name": "foo"},
    }


@pytest.fixture
def rrf_service():
    """HybridSearchService with EmbeddingService patched (no OPENAI_API_KEY needed)."""
    with patch("backend.services.embedding.EmbeddingService.__init__", return_value=None):
        from backend.services.hybrid_search import HybridSearchService
        svc = HybridSearchService.__new__(HybridSearchService)
        svc.k = 60
        svc.max_results_per_search = 20
        svc.default_limit = 10
        svc.vector_store = MagicMock()
        svc.keyword_service = MagicMock()
        return svc


class TestRRF:
    @pytest.fixture(autouse=True)
    def _inject_service(self, rrf_service):
        self.service = rrf_service

    def test_item_in_both_lists_scores_higher(self):
        shared = _make_doc("shared.py", 1, 5)
        only_sem = _make_doc("sem_only.py", 1, 5)
        kw_only = _make_doc("kw_only.py", 1, 5)

        results = self.service._reciprocal_rank_fusion(
            [shared, only_sem], [shared, kw_only]
        )
        score_map = {r["metadata"]["file_path"]: r["hybrid_score"] for r in results}
        assert score_map["shared.py"] > score_map["sem_only.py"]
        assert score_map["shared.py"] > score_map["kw_only.py"]

    def test_earlier_rank_scores_higher(self):
        docs = [_make_doc(f"file{i}.py") for i in range(3)]
        results = self.service._reciprocal_rank_fusion(docs, [])
        scores = [r["hybrid_score"] for r in results]
        assert scores[0] >= scores[1] >= scores[2]

    def test_empty_inputs_return_empty(self):
        assert self.service._reciprocal_rank_fusion([], []) == []

    def test_output_sorted_descending(self):
        sem = [_make_doc("a.py"), _make_doc("b.py")]
        kw = [_make_doc("b.py"), _make_doc("c.py")]
        results = self.service._reciprocal_rank_fusion(sem, kw)
        scores = [r["hybrid_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_all_files_present_in_output(self):
        sem = [_make_doc("a.py"), _make_doc("b.py")]
        kw = [_make_doc("c.py"), _make_doc("d.py")]
        results = self.service._reciprocal_rank_fusion(sem, kw)
        paths = {r["metadata"]["file_path"] for r in results}
        assert paths == {"a.py", "b.py", "c.py", "d.py"}
