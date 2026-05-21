# AI Codebase Assistant

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![OpenAI](https://img.shields.io/badge/OpenAI-API-412991?logo=openai&logoColor=white)
![Tests](https://img.shields.io/badge/tests-41_passing-4CAF50)
![License](https://img.shields.io/badge/license-MIT-blue)

A production-grade **Retrieval Augmented Generation (RAG)** system for querying code repositories in natural language. Upload a project as a ZIP or import directly from GitHub — public or private — ask questions in plain English, and receive AI-generated answers with exact file and line number citations, streamed token-by-token to the browser.

---

## Key Features

**Ingestion**
- ZIP upload or GitHub import (`git clone --depth 1`, public + private via `GITHUB_TOKEN`)
- Multi-language AST parsing: Python (stdlib `ast`), JavaScript, TypeScript, Go, Java, Rust, Ruby (tree-sitter), with line-based fallback for other languages
- Symbol-aware chunking at function and class boundaries with 100-token overlap
- Incremental re-indexing: MD5 hash diff — only re-embeds changed files, unchanged files produce zero API calls
- Optional LLM-generated chunk summaries prepended before embedding for richer semantic retrieval
- Async ingestion: HTTP 202 returned immediately; indexing runs as a background task

**Search (Hybrid)**
- Semantic search via OpenAI embeddings → MongoDB Atlas `$vectorSearch` (HNSW); automatic in-memory cosine fallback
- Keyword search via MongoDB `$text` compound index (symbol names weighted 5× over body text)
- Reciprocal Rank Fusion (k=60) merges both ranked lists mathematically
- Cohere cross-encoder re-ranking (`rerank-english-v3.0`) when configured; BM25Okapi fallback otherwise

**Answer Generation**
- Answers stream token-by-token via Server-Sent Events; browser consumes with `ReadableStream`
- Multi-turn conversation sessions backed by MongoDB with tiktoken-based history window
- Citation enforcement: regex validates every cited file path against retrieved chunk metadata; warns on unverified references
- Provider-agnostic LLM layer: switch between OpenAI GPT models and Anthropic Claude with a single environment variable

**Security & Operations**
- JWT authentication (HS256, 24-hour expiry) with bcrypt password hashing
- Per-IP rate limiting on every endpoint
- 41 automated tests (pytest + httpx, fully mock-isolated — no external services required)

---

## How It Works

```mermaid
flowchart LR
    A([Upload ZIP\nor GitHub URL]) --> B[FileScanner]
    B --> C{Language}
    C -->|Python| D[ast parser]
    C -->|JS/TS/Go/Java\nRust/Ruby| E[tree-sitter]
    C -->|Other| F[line-based]
    D & E & F --> G[CodeChunker]
    G --> H[EmbeddingService\nbatch embed]
    H --> I[(MongoDB Atlas\nchunks)]

    J([User question]) --> K[Embed query]
    J --> L[$text keyword\nsearch]
    K --> M[$vectorSearch\nHNSW]
    M & L --> N[RRF Fusion\nk=60]
    N --> O[Cohere / BM25\nrerank]
    O --> P[LLMService\nSSE stream]
    I --> M
    I --> L
    P --> Q([Answer +\ncitations])
```

For a detailed walkthrough of each component, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Quick Start

### Prerequisites
- Python 3.10+, Node.js 18+, `git` on PATH
- MongoDB Atlas account (free M0 tier — [cloud.mongodb.com](https://cloud.mongodb.com))
- OpenAI API key ([platform.openai.com](https://platform.openai.com))

### Backend

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env — minimum required: OPENAI_API_KEY, MONGODB_URI, JWT_SECRET
```

`backend/.env` minimum:
```env
OPENAI_API_KEY=sk-...
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/ragdb
JWT_SECRET=any-long-random-string
```

```bash
uvicorn backend.main:app --reload
# API:       http://localhost:8000
# Swagger:   http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App: http://localhost:5173
```

No frontend environment variables are needed for local development. The app defaults to `http://localhost:8000`.

---

## Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API key (embeddings + LLM when `LLM_PROVIDER=openai`) |
| `MONGODB_URI` | **Yes** | — | MongoDB Atlas connection string |
| `JWT_SECRET` | **Yes** | insecure default | HS256 signing secret — use a strong random string in production |
| `LLM_PROVIDER` | No | `openai` | `openai` or `anthropic` |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name for the selected provider |
| `EMBEDDING_PROVIDER` | No | `openai` | `openai` (only supported option currently) |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model |
| `ANTHROPIC_API_KEY` | No | — | Required when `LLM_PROVIDER=anthropic` |
| `COHERE_API_KEY` | No | — | Enables Cohere cross-encoder re-ranking; omit for BM25 fallback |
| `GITHUB_TOKEN` | No | — | Personal access token for importing private GitHub repositories |
| `ENABLE_CHUNK_SUMMARIES` | No | `false` | Generate LLM summaries per chunk at index time to improve retrieval |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000` | Comma-separated CORS origins; set to your Vercel URL in production |
| `LLM_MAX_TOKENS` | No | `2000` | Maximum tokens in LLM response |

See [`backend/.env.example`](backend/.env.example) for a fully annotated template.

---

## External Services

| Service | Required | Free Tier | Purpose |
|---|---|---|---|
| **MongoDB Atlas** | Yes | M0 — 512 MB | Database, vector search, text search |
| **OpenAI** | Yes (default) | $5 trial credit | Embeddings + LLM completions |
| **Anthropic** | No — alt LLM | $5 trial credit | LLM completions (`LLM_PROVIDER=anthropic`) |
| **Cohere** | No | 1,000 req/month | Cross-encoder re-ranking |
| **GitHub Token** | No | Free | Importing private repositories |

### MongoDB Atlas Vector Search Index (one-time setup)

The `$vectorSearch` HNSW index must be created manually through the Atlas UI. Without it the system falls back to in-memory cosine similarity automatically — no configuration change needed.

1. Atlas → your cluster → **Atlas Search** tab → **Create Search Index**
2. Select **Atlas Vector Search** → **JSON Editor**
3. Database: `ragdb`, Collection: `chunks`
4. Paste:

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

5. Name: `vector_search_index` → **Create**. Wait ~2 minutes for activation.

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

| Method | Path | Description | Rate Limit |
|---|---|---|---|
| GET | `/repositories` | List user's repositories | 60/min |
| GET | `/repositories/{id}` | Get single repository | 60/min |
| POST | `/repositories` | Create empty repository — `{name, description}` | 20/min |
| POST | `/repositories/upload` | Upload ZIP — multipart: `file`, `name?`, `description?` | 10/min |
| POST | `/repositories/import` | Import from GitHub — `{url, name?, description?, branch?}` | 5/min |
| GET | `/repositories/{id}/status` | Poll async ingestion progress | 60/min |
| PUT | `/repositories/{id}` | Update name / description | 20/min |
| DELETE | `/repositories/{id}` | Delete repository and all indexed chunks | 10/min |
| POST | `/repositories/{id}/reindex` | Re-index from new ZIP (incremental, MD5 diff) | 5/min |
| GET | `/repositories/{id}/symbols` | Symbol lookup — `?name=foo&type=function\|class` | 60/min |
| GET | `/repositories/{id}/stats` | Chunk count and indexed status | 60/min |

**Upload / Import / Reindex** return `202 Accepted` immediately. Poll `/repositories/{id}/status` to track progress.

```json
// GET /repositories/{id}/status response
{
  "id": "string",
  "name": "string",
  "status": "pending | indexing | indexed | failed",
  "processing": { "files_processed": 42, "chunks_created": 318 },
  "error": "string (present only on failure)"
}
```

### Chat

| Method | Path | Description | Rate Limit |
|---|---|---|---|
| POST | `/chat/sessions` | Create session — `{repository_id}` | 10/min |
| GET | `/chat/sessions` | List sessions — `?repository_id&limit` | 30/min |
| GET | `/chat/sessions/{id}` | Get session with full message history | 30/min |
| GET | `/chat/sessions/{id}/history` | Recent messages — `?limit` | 30/min |
| DELETE | `/chat/sessions/{id}` | Delete session | 10/min |
| POST | `/chat/query` | Ask a question (blocking) | 10/min |
| POST | `/chat/query/stream` | Ask a question (SSE streaming) | 10/min |

**Query body:**
```json
{
  "question": "string",
  "repository_id": "string",
  "session_id": "string (optional — enables multi-turn memory)",
  "limit": 5
}
```

**`/chat/query` response:**
```json
{
  "answer": "string",
  "sources": [
    {
      "file_path": "src/auth.py",
      "start_line": 42,
      "end_line": 67,
      "chunk_type": "function",
      "name": "verify_token",
      "score": 0.91
    }
  ],
  "chunks_found": 5,
  "citation_valid": true,
  "citation_warnings": [],
  "session_id": "string",
  "status": "success"
}
```

**SSE event format (`/chat/query/stream`):**
```
data: {"type": "token",  "token": "...", "answer": "<accumulated>"}
data: {"type": "done",   "answer": "<full>", "sources": [...], "citation_valid": true}
data: {"type": "error",  "error": "rate_limit | api_error | unknown"}
```

### System

| Method | Path | Response |
|---|---|---|
| GET | `/` | `{"message": "API is running"}` |
| GET | `/health` | `{"status": "healthy", "database": "connected"}` |

---

## Deployment

See [docs/deployment.md](docs/deployment.md) for step-by-step instructions covering MongoDB Atlas, Railway/Render (backend), and Vercel (frontend).

**Backend → Render or Railway**
```
Build command: pip install -r backend/requirements.txt
Start command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```
Set environment variables in the platform dashboard. The `Procfile` in the project root is pre-configured.

**Frontend → Vercel**
- Root directory: `frontend`
- Framework: Vite (auto-detected)
- Environment variable: `VITE_API_URL` = your backend URL

---

## Testing

```bash
python -m pytest backend/tests/ -q
```

41 tests, no external services required (MongoDB and OpenAI are fully mocked).

| File | Tests | Coverage |
|---|---|---|
| `test_unit.py` | 21 | JWT roundtrip + edge cases, CodeChunker AST extraction, RRF scoring algorithm |
| `test_api.py` | 20 | Auth register/login, repository CRUD + ownership, chat session lifecycle, health + root |

---

## Project Structure

```
.
├── backend/
│   ├── main.py                       # FastAPI app — lifespan, middleware, routers
│   ├── database.py                   # MongoDB motor singleton
│   ├── requirements.txt
│   ├── .env.example                  # Fully annotated environment template
│   ├── api/
│   │   ├── auth.py                   # POST /auth/register, /auth/login
│   │   ├── repositories.py           # Repo CRUD + upload + import + reindex + symbols + status
│   │   └── chat.py                   # Sessions CRUD + /query + /query/stream (SSE)
│   ├── auth/
│   │   ├── jwt.py                    # create_access_token, verify_token (HS256)
│   │   └── dependencies.py           # get_current_user FastAPI dependency
│   ├── middleware/
│   │   ├── error_handlers.py         # Exception → structured JSON
│   │   └── rate_limiter.py           # SlowAPI instance
│   ├── models/
│   │   ├── repository.py             # Pydantic models: Create, Import, Update, Response
│   │   └── chat.py                   # Chat session Pydantic models
│   ├── services/
│   │   ├── file_scanner.py           # Directory walker — 15 extensions, skips venv/node_modules
│   │   ├── ast_parser.py             # Python ast — functions, classes, imports + line numbers
│   │   ├── treesitter_parser.py      # tree-sitter — JS/TS/Go/Java/Rust/Ruby symbol extraction
│   │   ├── chunker.py                # AST-aware chunking + token-based overlap + line fallback
│   │   ├── embedding.py              # Thin wrapper over EmbeddingProvider
│   │   ├── vector_store.py           # $vectorSearch HNSW + in-memory cosine fallback
│   │   ├── keyword_search.py         # MongoDB $text compound index + symbol lookup
│   │   ├── hybrid_search.py          # RRF fusion + Cohere/BM25 reranking
│   │   ├── llm_service.py            # Streaming answer gen + citation validation
│   │   ├── summary.py                # Optional LLM chunk summaries (ENABLE_CHUNK_SUMMARIES)
│   │   ├── chat_service.py           # Session + message CRUD
│   │   ├── processor.py              # Ingestion orchestrator + incremental re-index
│   │   ├── rag_pipeline.py           # Query pipeline orchestrator
│   │   └── providers/
│   │       ├── base.py               # LLMProvider + EmbeddingProvider abstract interfaces
│   │       ├── openai_provider.py    # OpenAI LLM + embedding implementations
│   │       ├── anthropic_provider.py # Anthropic Claude LLM implementation
│   │       └── factory.py            # get_llm_provider(), get_embedding_provider()
│   └── tests/
│       ├── conftest.py               # Fixtures: mock_db, test_client, auth_headers
│       ├── test_unit.py              # JWT, CodeChunker, RRF (21 tests)
│       └── test_api.py               # API integration — full mock isolation (20 tests)
│
├── frontend/
│   └── src/
│       ├── App.jsx                   # SPA — auth, upload, import, chat, session sidebar, SSE
│       ├── App.css                   # Two-column responsive layout
│       └── main.jsx                  # React entry point
│
├── Procfile                          # Render/Railway: uvicorn backend.main:app
├── pytest.ini                        # asyncio_mode=auto, testpaths=backend/tests
├── ARCHITECTURE.md                   # Technical deep dive with component diagrams
├── CONTRIBUTING.md                   # Development setup and contribution guidelines
└── docs/
    ├── deployment.md                 # MongoDB Atlas, Render, Vercel step-by-step
    ├── search-pipeline.md            # Hybrid search system internals
    └── provider-architecture.md      # LLM/embedding provider abstraction guide
```

---

## Roadmap

| Feature | Priority | Notes |
|---|---|---|
| Docker Compose local setup | Medium | Single-command local dev environment |
| JWT refresh tokens | Low | Currently re-login after 24h |
| Webhook-based auto-indexing | Low | Requires GitHub App + persistent server |
| Cross-repository search | Low | Current scope is single-repo |
| Observability (OpenTelemetry) | Low | Tracing for LLM calls and search latency |
| Additional embedding providers | Low | Cohere/Voyage embeddings via EmbeddingProvider interface |

---

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture with Mermaid diagrams for every major flow |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, branching conventions, PR guidelines |
| [docs/deployment.md](docs/deployment.md) | Step-by-step deployment: Atlas, Render/Railway, Vercel |
| [docs/search-pipeline.md](docs/search-pipeline.md) | Hybrid search internals: RRF, BM25, Cohere |
| [docs/provider-architecture.md](docs/provider-architecture.md) | LLM/embedding provider system and how to add new providers |

---

## License

MIT — see [LICENSE](LICENSE).
