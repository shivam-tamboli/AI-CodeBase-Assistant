# Search Pipeline

The search system uses a three-stage hybrid pipeline to find the code chunks most relevant to a user's question: semantic search, keyword search, and re-ranking. Each stage compensates for the weaknesses of the others.

---

## Why Hybrid Search?

**Semantic search alone** works well for conceptual queries ("where is authentication handled?") but struggles with exact names ("find the `verify_token` function") because it operates on meaning, not text.

**Keyword search alone** works well for exact matches but fails on paraphrase or concept queries — it cannot retrieve "bcrypt password hashing" when the user asks "how are passwords secured?".

**Hybrid search** combines both: every query runs both methods in parallel and merges the results mathematically. The merger is then re-ranked by a more powerful model that reads query and chunk together.

---

## Stage 1: Semantic Search

**Implementation**: `backend/services/vector_store.py` → `semantic_search()`

At indexing time, every code chunk is converted to a 1536-dimensional vector using `text-embedding-3-small`. These vectors are stored in MongoDB alongside the source code.

At query time:
1. The user's question is embedded using the same model
2. The query vector is compared against all chunk vectors using cosine similarity
3. The most similar chunks (by angle, not by text) are returned

**Atlas $vectorSearch (HNSW)**: When the Atlas vector index is configured, this runs as an efficient approximate nearest-neighbor search on the server using the HNSW algorithm. `numCandidates` is set to `max(limit × 20, 100)` (capped at 1,000) to ensure the approximate index doesn't miss relevant results.

**In-memory fallback**: When Atlas vector search is not available (local MongoDB, or the index hasn't been created yet), all chunks for the repository are loaded and cosine similarity is computed in Python with NumPy. This is exact (not approximate) but O(n) in the number of chunks. It works well for development and small repositories.

---

## Stage 2: Keyword Search

**Implementation**: `backend/services/keyword_search.py` → `keyword_search()`

MongoDB's `$text` operator runs a full-text search against a compound text index on the `chunks` collection:

```python
await db.chunks.create_index(
    [("content", "text"), ("metadata.name", "text")],
    weights={"metadata.name": 5, "content": 1},
    default_language="english",
    name="content_name_text_index",
)
```

**Field weights**: Symbol names (`metadata.name`) are weighted 5× over body text (`content`). This means a query for `"authenticate"` will surface chunks named `authenticate` much higher than chunks that merely mention the word in a comment.

**Input sanitization**: The query is stripped to alphanumeric characters and basic punctuation before being passed to `$text`. This prevents injection-style queries that could manipulate the text search operator.

**Additional symbol lookup methods** (not via hybrid search, exposed as `GET /repositories/{id}/symbols`):
- `search_function_names(name, repo_id)` — exact match on `metadata.name` where `chunk_type=function`
- `search_class_names(name, repo_id)` — exact match on `metadata.name` where `chunk_type=class`
- `get_search_suggestions(prefix, repo_id)` — prefix match on `metadata.name` for autocomplete

---

## Stage 3: Reciprocal Rank Fusion

**Implementation**: `backend/services/hybrid_search.py` → `_reciprocal_rank_fusion()`

RRF merges two ranked lists into one without requiring score normalization. The formula:

```
score(d) = Σ  1 / (rank(d, list) + k)
```

where `k = 60` (a constant that prevents very high scores for top-ranked documents dominating the merge) and the sum is over both the semantic and keyword result lists.

**Why k=60?**  
The RRF constant `k` was empirically determined in the original 2009 paper. A value of 60 stabilizes the rankings — it means the difference between rank 1 and rank 2 is smaller than the difference between rank 1 and rank 61, so high-ranked documents are rewarded but not disproportionately.

**Deduplication**: Documents that appear in both lists (a good sign — both search methods agree) get contributions from both ranks and therefore score higher than documents appearing in only one list. Documents are identified by an MD5 hash of `file_path + start_line + end_line + first 100 chars of content`.

**Normalized score**: After fusion, scores are normalized to `(rrf_score × k) / 2`, so the maximum possible score (rank 1 in both lists) is approximately 1.0.

---

## Stage 4: Re-ranking

RRF gives a mathematically sound merge, but it only considers rank position — not the semantic relationship between the query and the chunk content. Re-ranking reads both together.

### Cohere Cross-Encoder (when configured)

**Implementation**: `backend/services/hybrid_search.py` → `_cohere_rerank()`

When `COHERE_API_KEY` is set, the merged RRF results are sent to Cohere's `rerank-english-v3.0` cross-encoder. Unlike bi-encoders (which embed query and document separately and compare vectors), a cross-encoder reads the query and the full document content together in a single forward pass. This produces much more accurate relevance scores at the cost of latency.

Cohere re-ranking is applied to the top `min(limit, len(results))` candidates from RRF. Cohere's free tier allows 1,000 requests/month.

### BM25 Fallback (no Cohere key)

**Implementation**: `backend/services/hybrid_search.py` → `_bm25_rerank()`

When Cohere is not configured, BM25Okapi from the `rank-bm25` library re-ranks the RRF results. BM25 (Best Match 25) is the standard probabilistic retrieval model — it's what search engines used before neural approaches became practical.

```python
corpus = []
for doc in results:
    meta = doc.get("metadata", {})
    name_tokens = meta.get("name", "").lower().split("_")
    content_tokens = doc.get("content", "").lower().split()
    corpus.append(name_tokens * 3 + content_tokens)
```

Symbol name tokens are repeated 3× in the corpus document to give them implicit higher weight — same idea as the text index field weights.

BM25 correctly normalises for document length and term frequency, making it substantially better than a simple term-count heuristic.

---

## Parallel Execution

Semantic and keyword searches run concurrently:

```python
semantic_results, keyword_results = await asyncio.gather(
    self.vector_store.semantic_search(query, repository_id, limit=20),
    self.keyword_service.keyword_search(query, repository_id, limit=20),
)
```

`asyncio.gather` schedules both coroutines on the event loop simultaneously. Since both operations are I/O-bound (MongoDB queries), they run in parallel without blocking each other, reducing total search latency roughly in half compared to sequential execution.

---

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `COHERE_API_KEY` | unset | Set to enable Cohere cross-encoder re-ranking |
| Atlas vector index | not created | Without it: in-memory cosine fallback (exact but O(n)) |
| `ENABLE_CHUNK_SUMMARIES` | `false` | When `true`, LLM-generated summaries are prepended to chunk content before embedding, improving retrieval for conceptual queries |

---

## Pipeline Summary

```
Query
  ├── embed(query) ──────────────► $vectorSearch HNSW (or in-memory cosine)  ─┐
  └── sanitize(query) ─────────► MongoDB $text compound index                  ├── RRF fusion → Cohere or BM25 rerank → Top-N chunks
                                                                                ┘
```

The full pipeline is exposed via `HybridSearchService.hybrid_search(query, repository_id, limit)`. Filtering by `chunk_type` or `file_path` is available via `search_with_filters()`.
