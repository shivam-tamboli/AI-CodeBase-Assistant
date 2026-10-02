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


# ---------------------------------------------------------------------------
# Chunk overlap is bounded in tokens (regression: it used to be 100 *lines*)
# ---------------------------------------------------------------------------

def _big_class(n_methods=60):
    body = "\n".join(
        f"    def method_{i}(self, value):\n"
        f"        \"\"\"Docstring for method {i} explaining what it does.\"\"\"\n"
        f"        result = value * {i} + self.offset\n"
        f"        return result\n"
        for i in range(n_methods)
    )
    return f"class Big:\n    offset = 1\n\n{body}\n"


class TestChunkOverlap:
    def setup_method(self):
        self.chunker = CodeChunker(max_tokens=1000, overlap=100)

    def test_large_class_is_not_split_into_near_duplicates(self):
        src = _big_class()
        total_tokens = self.chunker.count_tokens(src)
        pieces = [c for c in self.chunker.chunk_file(src, "big.py") if c["name"] == "Big"]
        # With ~100 tokens of overlap, each piece adds ~900 new tokens.
        assert 1 < len(pieces) <= total_tokens // 900 + 2

    def test_consecutive_pieces_overlap_by_at_most_overlap_tokens(self):
        pieces = [c for c in self.chunker.chunk_file(_big_class(), "big.py") if c["name"] == "Big"]
        for prev, nxt in zip(pieces, pieces[1:]):
            shared_lines = prev["end_line"] - nxt["start_line"] + 1
            assert shared_lines >= 0
            shared_text = "\n".join(prev["content"].split("\n")[-shared_lines:]) if shared_lines else ""
            assert self.chunker.count_tokens(shared_text) <= 100 + 20  # +slack for the joining newline
            assert nxt["start_line"] > prev["start_line"] + 10  # actually moves forward


# ---------------------------------------------------------------------------
# Retrieval drops overlapping windows of the same code
# ---------------------------------------------------------------------------

def _hit(path, start, end, name="x", chunk_type="class"):
    return {"content": f"{path}:{start}", "metadata": {"file_path": path, "start_line": start, "end_line": end, "name": name, "chunk_type": chunk_type}}


class TestDropOverlapping:
    def setup_method(self):
        from backend.services.hybrid_search import HybridSearchService
        self.drop = HybridSearchService._drop_overlapping

    def test_near_identical_windows_collapse_to_best_ranked(self):
        ranked = [_hit("s.py", 40, 128), _hit("s.py", 40, 129), _hit("s.py", 40, 130), _hit("t.py", 1, 50), _hit("s.py", 40, 131)]
        out = self.drop(ranked, limit=5)
        assert [(h["metadata"]["file_path"], h["metadata"]["end_line"]) for h in out] == [("s.py", 128), ("t.py", 50)]

    def test_adjacent_or_slightly_overlapping_chunks_are_kept(self):
        ranked = [_hit("s.py", 1, 100), _hit("s.py", 95, 200), _hit("s.py", 201, 300)]
        assert len(self.drop(ranked, limit=5)) == 3

    def test_same_lines_in_different_files_are_kept(self):
        ranked = [_hit("a.py", 1, 50), _hit("b.py", 1, 50)]
        assert len(self.drop(ranked, limit=5)) == 2

    def test_respects_limit_after_dropping(self):
        ranked = [_hit("s.py", 1, 100), _hit("s.py", 1, 101)] + [_hit(f"f{i}.py", 1, 10) for i in range(10)]
        out = self.drop(ranked, limit=5)
        assert len(out) == 5 and out[0]["metadata"]["file_path"] == "s.py" and out[1]["metadata"]["file_path"] == "f0.py"

    def test_different_symbols_with_overlapping_ranges_are_kept(self):
        # The imports chunk is synthesized with a fixed 1-50 range, so it
        # "overlaps" any function near the top of the file.
        ranked = [_hit("m.py", 24, 45, name="escape", chunk_type="function"),
                  _hit("m.py", 1, 50, name="__init__", chunk_type="imports")]
        assert len(self.drop(ranked, limit=5)) == 2


# ---------------------------------------------------------------------------
# Fallback rerank keeps the semantic ranking in play
# ---------------------------------------------------------------------------

class TestBm25FallbackFusion:
    def setup_method(self):
        from backend.services.hybrid_search import HybridSearchService
        self.svc = HybridSearchService.__new__(HybridSearchService)
        self.svc.k = 60

    def test_top_semantic_hit_without_shared_words_survives(self):
        # Ranked #1 by RRF (semantic), shares no words with the question.
        semantic_best = {"content": "if age > max_age: raise SignatureExpired(...)", "metadata": {"name": "unsign"}}
        wordy = [{"content": "signature token verification signature token " * (i + 1), "metadata": {"name": f"w{i}"}} for i in range(10)]
        out = self.svc._bm25_rerank([semantic_best] + wordy, "how does signature verification work when a token has expired")
        assert semantic_best in out[:5]

    def test_lexical_match_can_still_move_up(self):
        docs = [{"content": f"unrelated text {i}", "metadata": {"name": f"u{i}"}} for i in range(5)]
        target = {"content": "escape characters html escape", "metadata": {"name": "escape"}}
        out = self.svc._bm25_rerank(docs + [target], "escape html characters")
        assert out.index(target) < 5  # started last (index 5), BM25 lifts it


class TestCohereClientSelection:
    async def _rerank_with(self, fake_module):
        import sys
        from unittest.mock import AsyncMock, MagicMock
        from backend.services.hybrid_search import HybridSearchService
        svc = HybridSearchService.__new__(HybridSearchService)
        client = MagicMock()
        client.rerank = AsyncMock(return_value=MagicMock(results=[MagicMock(index=1, relevance_score=0.9)]))
        fake_module.return_value_client = client
        with patch.dict(sys.modules, {"cohere": fake_module}), patch.dict("os.environ", {"COHERE_API_KEY": "k"}):
            return await svc._cohere_rerank([{"content": "a"}, {"content": "b"}], "q", 5)

    @pytest.mark.asyncio
    async def test_uses_v2_client_when_available(self):
        import types
        mod = types.SimpleNamespace()
        mod.AsyncClientV2 = lambda key: mod.return_value_client
        mod.AsyncClient = lambda key: (_ for _ in ()).throw(AssertionError("v1 used"))
        out = await self._rerank_with(mod)
        assert out[0]["content"] == "b" and out[0]["rerank_score"] == 0.9

    @pytest.mark.asyncio
    async def test_falls_back_to_v1_client_on_older_sdk(self):
        import types
        mod = types.SimpleNamespace()
        mod.AsyncClient = lambda key: mod.return_value_client  # no AsyncClientV2 attribute
        out = await self._rerank_with(mod)
        assert out[0]["content"] == "b"
