# AI Codebase Assistant

A full-stack Retrieval Augmented Generation (RAG) system for querying code repositories in natural language. Upload a project as a ZIP or import directly from GitHub, ask questions in plain English, and receive answers with exact file path and line number citations — streamed token-by-token to the browser.

**Stack**: Python 3.12 · FastAPI · MongoDB Atlas · OpenAI API · React 19 · Vite  
**Deploy**: Render (backend) · Vercel (frontend)

---

## What It Does

```
Upload ZIP or paste GitHub URL
         ↓
Scan → AST/tree-sitter parse → chunk → embed → store in MongoDB
         ↓
Ask a question in plain English
         ↓
Hybrid search: semantic ($vectorSearch) + keyword ($text) → RRF fusion
         ↓
Cohere cross-encoder re-ranking (optional)
         ↓
GPT-4o-mini generates an answer with file:line citations
         ↓
Citation validator checks every cited file path against retrieved chunks
         ↓
Answer streams token-by-token to the browser via SSE
```

---

## Architecture

```
Browser (React SPA — Vercel)
  │  HTTP/JSON + Bearer token
  │  SSE for streaming answers
  ▼
FastAPI (Python — Render)
  ├── Middleware: CORS · Rate Limiting (SlowAPI) · Error Handlers
  ├── Auth:        POST /auth/register, /auth/login  (JWT + bcrypt)
  ├── /repositories  CRUD · /upload · /import · /reindex · /symbols · /stats
  └── /chat          sessions CRUD · /query · /query/stream (SSE)
         │
         ├── RepositoryProcessor
         │     scan_directory → (ast_parser | treesitter_parser) → CodeChunker
         │     → EmbeddingService (batch) → VectorStore.add_chunks
         │     Incremental: MD5 diff — only re-embeds changed files
         │
         ├── HybridSearchService
         │     VectorStore._atlas_vector_search  ($vectorSearch HNSW)
         │       └── fallback: _in_memory_search (cosine, numpy)
         │     KeywordSearchService              ($text compound index)
         │     _reciprocal_rank_fusion (k=60)
         │     _cohere_rerank (cross-encoder)
         │       └── fallback: _rerank (keyword-bonus heuristic)
         │
         └── LLMService
               _build_prompt (system + history + context)
               generate_answer / generate_streaming_answer (stream=True)
               _validate_citations (verifies file paths in answer)

MongoDB Atlas (ragdb)
  ├── users          — accounts (username unique index)
  ├── repositories   — repo metadata
  ├── chunks         — code + 1536-dim embeddings + file_hash + metadata
  │     Indexes: repository_id_1
  │              content_name_text_index (compound $text)
  │              vector_search_index     (HNSW — Atlas UI, manual setup)
  └── chat_sessions  — conversation history
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI 0.104, Uvicorn |
| Database | MongoDB Atlas (motor async driver) |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim, batch) |
| LLM | OpenAI `gpt-4o-mini` (default) — configurable via `LLM_MODEL` |
| Vector Search | MongoDB Atlas `$vectorSearch` (HNSW) with in-memory cosine fallback |
| Keyword Search | MongoDB `$text` compound index on `content` + `metadata.name` |
| Re-ranking | Cohere `rerank-english-v3.0` cross-encoder (optional, heuristic fallback) |
| Auth | JWT (python-jose, HS256, 24h expiry) + bcrypt (passlib) |
| Rate Limiting | SlowAPI — per-IP on all endpoints |
| Multi-language | Python (`ast`), JS/TS/Go/Java/Rust/Ruby (tree-sitter), line-based fallback |
| Frontend | React 19, Vite, Axios, react-markdown |
| Streaming | Server-Sent Events (backend) + Fetch `ReadableStream` (frontend) |
| Deployment | Vercel (frontend) + Render (backend) |
| Testing | pytest 7.4, pytest-asyncio, httpx (41 tests) |

---

## Features

### Repository Ingestion
- **ZIP upload** — multipart file upload, extracted and indexed server-side
- **GitHub URL import** — `git clone --depth 1` from any public repository URL
- **Incremental re-indexing** — `POST /repositories/{id}/reindex` computes MD5 hashes per file, deletes stale chunks, re-embeds only changed or new files; unchanged files produce zero API calls

### Multi-language Parsing
| Language | Parser | Extracts |
|---|---|---|
| Python | `ast` (stdlib) | functions, async functions, classes, imports with exact line numbers |
| JavaScript / JSX | tree-sitter | function declarations, arrow functions, methods, classes |
| TypeScript / TSX | tree-sitter | same as JS + interface declarations |
| Go | tree-sitter | function declarations, method declarations, type declarations |
| Java | tree-sitter | method declarations, constructors, class/interface/enum declarations |
| Rust | tree-sitter | function items, struct/enum/trait/impl items |
| Ruby | tree-sitter | methods, singleton methods, classes, modules |
| Others (PHP, C#, etc.) | line-based | sliding-window chunks with 100-token overlap |

### Search Pipeline
1. **Semantic search** — query embedding (1536-dim) → `$vectorSearch` HNSW on Atlas; falls back to in-memory cosine similarity if the Atlas index is not configured
2. **Keyword search** — MongoDB `$text` on `content` + `metadata.name`, TF-IDF scored
3. **RRF fusion** — `score = Σ 1/(rank + 60)` merges both result sets
4. **Cohere re-ranking** (optional) — `rerank-english-v3.0` cross-encoder reads query + chunk content together; falls back to keyword-bonus heuristic when `COHERE_API_KEY` is absent

### Answer Generation
- System prompt + up to 10 messages of conversation history + retrieved code context
- **Citation enforcement** — regex-extracts `.py` (and other) file paths from the answer, validates each against `retrieved_chunks` metadata; appends a blockquote warning for unverified references; response includes `citation_valid` flag and `citation_warnings` list
- **Streaming** — `POST /chat/query/stream` returns `text/event-stream`; tokens appear in the browser incrementally via `ReadableStream`

### Authentication
- Register / login with username + password
- Passwords hashed with bcrypt (passlib)
- JWT tokens (HS256, 24-hour expiry, stored in `localStorage`)
- All data scoped to the authenticated user
- Rate limiting on every endpoint via SlowAPI

### Conversation Sessions
- Create multiple named conversations per repository
- Full message history stored in MongoDB (role, content, timestamp)
- Continue previous conversations — LLM receives last 10 messages as context
- Session sidebar: switch, create, delete conversations

### API Utilities
- `GET /repositories/{id}/symbols?name=foo&type=function|class` — exact symbol lookup by name
- `GET /repositories/{id}/stats` — chunk count and indexed status
- `GET /health` — database connectivity check

---

## External Services and API Keys

### Required

#### OpenAI
**Used for**: generating 1536-dim embeddings (`text-embedding-3-small`) and LLM answers (`gpt-4o-mini`)  
**Where to get it**: [platform.openai.com](https://platform.openai.com) → API Keys → Create new secret key  
**Free tier**: $5 credit on new accounts (enough for substantial development)  
**Cost at scale**: ~$0.02 per 1M embedding tokens; $0.15 per 1M input tokens (gpt-4o-mini)  
**Environment variable**: `OPENAI_API_KEY`

#### MongoDB Atlas
**Used for**: storing users, repositories, code chunks (with embeddings), chat sessions; running `$text` and `$vectorSearch` queries  
**Where to get it**: [cloud.mongodb.com](https://cloud.mongodb.com) → Create account → Build a Cluster → M0 Free  
**Free tier**: M0 — 512 MB storage, shared cluster. Supports `$vectorSearch` at no cost  
**Environment variable**: `MONGODB_URI` (format: `mongodb+srv://user:pass@cluster.mongodb.net/ragdb`)

### Optional (but recommended for production quality)

#### Cohere (cross-encoder re-ranking)
**Used for**: re-ranking RRF results with a cross-encoder ML model — significantly better answer quality for ambiguous queries  
**Without it**: falls back to keyword-bonus heuristic rerank automatically  
**Where to get it**: [cohere.com](https://cohere.com) → Sign up → API Keys  
**Free tier**: 1,000 requests/month, rate limited  
**Environment variable**: `COHERE_API_KEY`

---

### MongoDB Atlas Vector Search Index (manual setup — one time)

This step activates `$vectorSearch` HNSW indexing. Without it the system works correctly using in-memory cosine similarity, but queries are O(n) across all chunks.

1. Go to [cloud.mongodb.com](https://cloud.mongodb.com) → your cluster → **Search** tab → **Create Search Index**
2. Select **Atlas Vector Search** → **JSON Editor**
3. Choose database `ragdb`, collection `chunks`
4. Paste this configuration:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "repository_id"
    }
  ]
}
```

5. Set index name to exactly `vector_search_index`
6. Click **Create Search Index** and wait for it to become active (~2 minutes)

---

## Local Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- `git` installed and on PATH
- MongoDB Atlas account with connection string
- OpenAI API key

### Backend

```bash
# From project root
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r backend/requirements.txt

cp backend/.env.example backend/.env
# Edit backend/.env — fill in OPENAI_API_KEY, MONGODB_URI, JWT_SECRET
```

`backend/.env` minimum required:
```
OPENAI_API_KEY=sk-...
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/ragdb
JWT_SECRET=any-long-random-string-change-before-deploying
```

```bash
uvicorn backend.main:app --reload
# API:  http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App: http://localhost:5173
```

No frontend environment variables are required for local development. The app defaults to `http://localhost:8000` as the API base URL.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API key for embeddings and LLM |
| `MONGODB_URI` | **Yes** | — | MongoDB Atlas connection string |
| `JWT_SECRET` | **Yes** | insecure default | HS256 signing secret — use a strong random string in production |
| `COHERE_API_KEY` | No | — | Enables Cohere cross-encoder re-ranking; omit to use heuristic fallback |
| `LLM_MODEL` | No | `gpt-4o-mini` | OpenAI model name — e.g. `gpt-4o`, `gpt-4` |
| `LLM_MAX_TOKENS` | No | `2000` | Maximum tokens in LLM response |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000` | Comma-separated CORS origins (set to your Vercel URL in production) |

---

## Deployment

### Backend → Render

1. [render.com](https://render.com) → New → Web Service → Connect GitHub repo
2. Settings:
   - **Runtime**: Python 3
   - **Root Directory**: (leave empty)
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
3. Environment Variables (Render dashboard → Environment):
   - `OPENAI_API_KEY`
   - `MONGODB_URI`
   - `JWT_SECRET` (generate a strong random string)
   - `ALLOWED_ORIGINS` = your Vercel URL (set after frontend is deployed)
   - `COHERE_API_KEY` (optional)
4. Deploy — Render gives you a URL like `https://your-app.onrender.com`

> **Free tier note**: Render free tier spins down after 15 minutes of inactivity. First request after sleep takes ~30 seconds. The `Procfile` in the project root is configured correctly for Render and Railway.

### Frontend → Vercel

1. In `frontend/src/App.jsx` line 6, the API URL reads from an environment variable:
   ```js
   const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
   ```
2. [vercel.com](https://vercel.com) → New Project → Import GitHub repo
3. **Root Directory**: `frontend`
4. Framework: auto-detected as Vite
5. Environment Variable: `VITE_API_URL` = your Render backend URL
6. Deploy

`frontend/vercel.json` is already configured with SPA rewrites.

---

## API Reference

All endpoints except `/`, `/health`, `/auth/register`, and `/auth/login` require:
```
Authorization: Bearer <access_token>
```

### Authentication

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{username, password}` | `{access_token, token_type}` 201 |
| POST | `/auth/login` | `{username, password}` | `{access_token, token_type}` 200 |

### Repositories

| Method | Path | Notes | Rate Limit |
|---|---|---|---|
| GET | `/repositories` | List user's repos | 60/min |
| GET | `/repositories/{id}` | Single repo | 60/min |
| POST | `/repositories` | Create empty repo — body: `{name, description}` | 10/min |
| POST | `/repositories/upload` | Multipart ZIP upload — fields: `file`, `name?`, `description?` | 10/min |
| POST | `/repositories/import` | JSON body: `{url, name?, description?}` — public GitHub URLs only | 5/min |
| PUT | `/repositories/{id}` | Update name/description | 20/min |
| DELETE | `/repositories/{id}` | Deletes repo + all chunks | 10/min |
| GET | `/repositories/{id}/symbols` | Query params: `name`, `type` (`function`\|`class`) | 60/min |
| GET | `/repositories/{id}/stats` | Returns `{chunk_count, indexed}` | 60/min |
| POST | `/repositories/{id}/reindex` | Multipart ZIP — incremental re-index | 5/min |

### Chat

| Method | Path | Notes | Rate Limit |
|---|---|---|---|
| POST | `/chat/sessions` | Body: `{repository_id}` | 10/min |
| GET | `/chat/sessions` | Query: `repository_id?`, `limit?` | 30/min |
| GET | `/chat/sessions/{id}` | Full session with messages | 30/min |
| GET | `/chat/sessions/{id}/history` | Query: `limit?` | 30/min |
| DELETE | `/chat/sessions/{id}` | — | 10/min |
| POST | `/chat/query` | Body: `{question, repository_id, session_id?, limit?}` | 10/min |
| POST | `/chat/query/stream` | Same body as `/query` — returns `text/event-stream` | 10/min |

#### SSE Event Format (`/chat/query/stream`)

```
data: {"type": "token", "token": "...", "answer": "<accumulated so far>"}
data: {"type": "done",  "answer": "<full answer>", "sources": [...], "chunks_used": N}
data: {"type": "error", "answer": "...", "error": "rate_limit|api_error|unknown"}
```

#### `/chat/query` Response Shape

```json
{
  "answer": "string",
  "sources": [{"file_path": "...", "start_line": 0, "end_line": 0, "chunk_type": "...", "name": "...", "score": 0.0}],
  "chunks_found": 5,
  "citation_valid": true,
  "citation_warnings": [],
  "session_id": "string",
  "status": "success"
}
```

### System

| Method | Path | Response |
|---|---|---|
| GET | `/` | `{"message": "API is running"}` |
| GET | `/health` | `{"status": "healthy|unhealthy", "database": "connected|disconnected: ..."}` |

---

## Testing

```bash
# From project root (venv active)
python -m pytest backend/tests/ -q
```

**41 tests in two files:**

| File | Tests | What they cover |
|---|---|---|
| `backend/tests/test_unit.py` | 21 | JWT roundtrip and edge cases (4), CodeChunker AST extraction and token splitting (12), RRF scoring algorithm (5) |
| `backend/tests/test_api.py` | 20 | Auth register/login (6), repository CRUD and ownership (5), chat session lifecycle (4), auth edge cases (2), root and health endpoints (2) + 1 |

All API tests use `AsyncClient` with MongoDB and OpenAI mocked — no external services required to run them.

---

## Project Structure

```
.
├── backend/
│   ├── main.py                   # FastAPI app — lifespan, middleware, router registration
│   ├── database.py               # MongoDB motor singleton
│   ├── requirements.txt
│   ├── .env.example
│   ├── api/
│   │   ├── auth.py               # POST /auth/register, /auth/login
│   │   ├── repositories.py       # Repo CRUD + upload + import + reindex + symbols + stats
│   │   └── chat.py               # Sessions CRUD + POST /query + POST /query/stream (SSE)
│   ├── auth/
│   │   ├── jwt.py                # create_access_token, verify_token (HS256)
│   │   └── dependencies.py       # get_current_user FastAPI dependency
│   ├── middleware/
│   │   ├── error_handlers.py     # Exception → structured JSON response
│   │   └── rate_limiter.py       # SlowAPI instance
│   ├── models/
│   │   ├── repository.py         # RepositoryCreate, RepositoryImport, RepositoryResponse
│   │   └── chat.py               # Chat session Pydantic models
│   ├── services/
│   │   ├── file_scanner.py       # scan_directory — 15 file extensions, skips venv/node_modules
│   │   ├── ast_parser.py         # Python ast → functions, classes, imports with line numbers
│   │   ├── treesitter_parser.py  # tree-sitter → JS/TS/Go/Java/Rust/Ruby symbol extraction
│   │   ├── chunker.py            # CodeChunker — AST-aware chunking + line-based fallback
│   │   ├── embedding.py          # OpenAI text-embedding-3-small batch embedding
│   │   ├── vector_store.py       # $vectorSearch (HNSW) + in-memory cosine fallback
│   │   ├── keyword_search.py     # MongoDB $text compound index search + symbol lookup
│   │   ├── hybrid_search.py      # RRF fusion + Cohere re-rank (heuristic fallback)
│   │   ├── llm_service.py        # GPT answer generation, streaming, citation validation
│   │   ├── chat_service.py       # Session + message CRUD
│   │   ├── processor.py          # Ingestion orchestrator + incremental re-index
│   │   └── rag_pipeline.py       # Query + streaming pipeline orchestrator
│   └── tests/
│       ├── conftest.py           # Fixtures: mock_db, test_client, auth_headers
│       ├── test_unit.py          # JWT, CodeChunker, RRF (21 tests)
│       └── test_api.py           # API integration (20 tests, full mock isolation)
│
├── frontend/
│   └── src/
│       ├── App.jsx               # SPA — auth, upload, import, chat with session sidebar, streaming
│       ├── App.css               # Two-column responsive layout
│       └── main.jsx              # React entry point
│
├── Procfile                      # Render/Railway: uvicorn backend.main:app
├── pytest.ini                    # asyncio_mode=auto, testpaths=backend/tests
└── README.md
```

---

## Current Status

### Fully Implemented

| Feature | Notes |
|---|---|
| ZIP upload + full indexing | Upload → extract → parse → chunk → embed → store |
| GitHub URL import | `git clone --depth 1` any public repo |
| Incremental re-indexing | MD5 hash diff — only re-embeds changed files |
| Multi-language parsing | Python (AST), JS/TS/Go/Java/Rust (tree-sitter), line-based fallback |
| Atlas $vectorSearch | HNSW with in-memory cosine fallback |
| Keyword search | MongoDB $text compound index |
| Hybrid search (RRF) | Reciprocal Rank Fusion, k=60 |
| Cohere re-ranking | Cross-encoder with heuristic fallback |
| Citation enforcement | File path validation in LLM answers |
| LLM answer generation | gpt-4o-mini default, configurable |
| Streaming responses | SSE endpoint + frontend ReadableStream consumer |
| Multi-turn chat sessions | MongoDB-backed, 10-message history window |
| JWT authentication | HS256, 24h expiry, bcrypt passwords |
| Per-IP rate limiting | SlowAPI on all endpoints |
| Symbol search API | Exact function/class name lookup |
| Repository stats API | Chunk count and indexed status |
| Markdown rendering | react-markdown for assistant messages |
| 41 automated tests | Full mock isolation, no external services |
| Deployment configs | Procfile (Render/Railway), vercel.json (Vercel) |

### Requires Manual Setup

| Item | What to do |
|---|---|
| MongoDB Atlas Vector Search index | Create `vector_search_index` in Atlas UI (see instructions above). Without it, in-memory cosine fallback is used automatically. |
| Cohere re-ranking | Set `COHERE_API_KEY` in environment. Without it, heuristic fallback is used. |
| GitHub private repos | Not supported without additional GitHub token configuration. |

### Out of Scope

| Feature | Why |
|---|---|
| GitHub webhook auto-indexing | Requires a public webhook URL, GitHub App, and persistent server |
| JWT token refresh | Users re-authenticate after 24 hours |
| Observability (Langfuse/OTEL) | Useful in production; not in current scope |
| Dedicated vector store (Qdrant) | MongoDB Atlas handles current scale; migrate if >10K chunks/repo |
| Neo4j symbol dependency graph | Tracks cross-file call relationships; significant architectural addition |
| Cross-repository search | Single-repo scope by design |

---

## Troubleshooting

**"No code files found in repository"**  
The uploaded ZIP contains no files with supported extensions (`.py`, `.js`, `.ts`, `.go`, `.java`, `.rs`, etc.). Check `backend/services/file_scanner.py` for the full extension list.

**GitHub import fails with clone error**  
Ensure the repo URL is public and follows `https://github.com/owner/repo` format. `git` must be installed on the server. Private repos are not supported.

**Atlas Vector Search not returning results**  
Verify the index name is exactly `vector_search_index`. Verify `repository_id` is declared as a `filter` field in the index JSON. If the index shows as "pending", wait for it to become active.

**Streaming answers not appearing**  
Verify `ALLOWED_ORIGINS` includes your frontend URL (needed for SSE CORS). The browser must support `ReadableStream` (all modern browsers do).

**Rate limit 429 errors**  
SlowAPI limits requests per IP per minute. Limits are defined per endpoint in `backend/api/*.py`. Adjust them in development by editing the `@limiter.limit(...)` decorators.

**JWT expired / 401 on all requests**  
Tokens expire after 24 hours. Log out and log back in. No refresh token flow is implemented.

**Cohere re-ranking slow or failing**  
The free tier (1,000 req/month) rate-limits aggressively. If calls fail, the system falls back to heuristic re-ranking automatically — no user-visible error.
