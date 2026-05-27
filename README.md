# AI Codebase Assistant

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![OpenAI](https://img.shields.io/badge/OpenAI-API-412991?logo=openai&logoColor=white)
![Tests](https://img.shields.io/badge/tests-41_passing-4CAF50)
![License](https://img.shields.io/badge/license-MIT-blue)

Upload a codebase as a ZIP or import from GitHub — then ask questions about it in plain English and get AI-generated answers with exact file and line citations, streamed live to the browser.

---

## Demo

**Live app:** https://ai-code-base-assistant-kws4.vercel.app

<!-- TODO: replace with a GIF or screenshot of the chat interface in use -->
![Demo screenshot placeholder](docs/demo.png)

---

## Problem

Reading an unfamiliar codebase takes hours. You scan files, trace call chains, and search for where things happen — before you can ask a single meaningful question. This project replaces that process with a natural-language interface: upload a repository once and ask anything about it. The system finds the relevant code, cites the exact files and lines, and explains what it found using an LLM — without hallucinating file paths it didn't actually retrieve.

---

## Features

**Ingestion**
- ZIP upload or GitHub import (`git clone --depth 1`) — public and private repos via `GITHUB_TOKEN`
- Multi-language AST parsing: Python (stdlib `ast`), JavaScript, TypeScript, Go, Java, Rust (tree-sitter), line-based fallback for all other languages
- Symbol-aware chunking at function and class boundaries with 100-token overlap, so context windows contain complete logical units
- Incremental re-indexing: MD5 hash diff skips unchanged files — re-indexing a large repo with one changed file uses only one API call
- Optional LLM-generated chunk summaries prepended before embedding, improving retrieval for conceptual queries
- 202 Accepted pattern: upload returns immediately; background task indexes; client polls `/status`

**Search**
- Semantic search: OpenAI embeddings → MongoDB Atlas `$vectorSearch` (HNSW approximate nearest neighbor); automatic in-memory cosine fallback when the Atlas index is not configured
- Keyword search: MongoDB `$text` compound index with symbol names weighted 5× over body text
- Reciprocal Rank Fusion (k=60) merges both ranked lists into a single score without requiring normalization
- Cohere cross-encoder re-ranking (`rerank-english-v3.0`) when `COHERE_API_KEY` is configured; BM25Okapi fallback otherwise

**Answer generation**
- Answers stream token-by-token via Server-Sent Events; browser reads with the `ReadableStream` API
- Multi-turn conversation sessions backed by MongoDB with tiktoken-based context window management
- Citation enforcement: regex validates every cited file path against the retrieved chunk metadata and flags unverified references
- Provider-agnostic LLM layer: switch between OpenAI GPT and Anthropic Claude models with a single environment variable change, no code modifications

**Auth and operations**
- JWT authentication (HS256, 24-hour expiry) with bcrypt password hashing
- Per-IP rate limiting on every endpoint via SlowAPI
- 41 automated tests (pytest + httpx) — fully mock-isolated, no external services required to run them

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| API | FastAPI 0.104 + Uvicorn | Async-native; lifespan hooks initialize DB connection and service singletons once at startup |
| Database | MongoDB Atlas (Motor async driver) | Stores users, repositories, chunks (with embeddings), and chat sessions in one place; Atlas provides both `$vectorSearch` and `$text` indexes |
| Embeddings | OpenAI `text-embedding-3-small` | 1536-dimensional vectors; batched with exponential-backoff retry on rate limits |
| Vector search | MongoDB Atlas `$vectorSearch` (HNSW) | Chosen to avoid a separate vector database (Pinecone, Weaviate); one fewer infrastructure dependency |
| LLM | OpenAI GPT / Anthropic Claude (switchable) | Abstract `LLMProvider` interface; concrete implementations in `providers/`; factory reads `LLM_PROVIDER` env var |
| Re-ranking | Cohere `rerank-english-v3.0` | Cross-encoder reads query + document together — more accurate than bi-encoder similarity alone; BM25 fallback when key is absent |
| AST parsing | Python `ast` + tree-sitter | `ast` is exact for Python; tree-sitter covers 6 other languages with a single unified API |
| Frontend | React 19 + Vite + Axios | Single-file SPA (`App.jsx`); SSE streaming consumed with `ReadableStream`, not `EventSource`, to allow POST requests with auth headers |
| Deployment | Render (backend) + Vercel (frontend) | Render chosen over Vercel for the backend because Vercel serverless functions time out at 10 seconds — LLM calls can take 15–30 seconds |

---

## Architecture

The system has two independent pipelines that share the same MongoDB collections.

**Ingestion pipeline** (triggered by upload/import): the uploaded archive is extracted to a temp directory, scanned for code files, parsed into AST-aware chunks, embedded in batches, and stored in MongoDB alongside their source content and metadata. The HTTP response returns 202 immediately; all of this runs as a background task.

**Query pipeline** (triggered by each chat message): the user's question is embedded and passed to both semantic and keyword search in parallel using `asyncio.gather`. Results are merged with Reciprocal Rank Fusion, optionally re-ranked by Cohere, and the top-N chunks are formatted as context for the LLM. The answer streams back token-by-token over SSE.

```mermaid
flowchart LR
    A([Upload ZIP\nor GitHub URL]) --> B[FileScanner]
    B --> C{Language}
    C -->|Python| D[ast parser]
    C -->|JS/TS/Go/Java\nRust| E[tree-sitter]
    C -->|Other| F[line-based]
    D & E & F --> G[CodeChunker\nmax 1000 tokens\n100-token overlap]
    G --> H[EmbeddingService\nbatch embed]
    H --> I[(MongoDB Atlas\nchunks collection)]

    J([User question]) --> K[Embed query]
    J --> L[$text keyword\nsearch]
    K --> M[$vectorSearch\nHNSW]
    M & L --> N[RRF Fusion\nk=60]
    N --> O[Cohere rerank\nor BM25 fallback]
    O --> P[LLMService\nSSE stream]
    I --> M
    I --> L
    P --> Q([Answer +\ncitations])
```

**RAG query sequence:**

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as FastAPI
    participant HS as HybridSearch
    participant VS as VectorStore
    participant KS as KeywordSearch
    participant LLM as LLMService

    B->>API: POST /chat/query/stream {question, repo_id, session_id}
    API->>HS: hybrid_search(query, repo_id, limit)
    par asyncio.gather
        HS->>VS: semantic_search() via $vectorSearch HNSW
        HS->>KS: keyword_search() via $text index
    end
    VS-->>HS: top-20 semantic results
    KS-->>HS: top-20 keyword results
    HS->>HS: Reciprocal Rank Fusion (k=60)
    HS->>HS: Cohere rerank or BM25 fallback
    HS-->>API: top-N ranked chunks
    API->>LLM: stream(context + history + question)
    loop SSE token stream
        LLM-->>B: data: {"type":"token","token":"..."}
    end
    LLM-->>B: data: {"type":"done","sources":[...],"citation_valid":true}
```

**Data model:**

```mermaid
erDiagram
    USERS {
        ObjectId _id
        string username
        string hashed_password
        datetime created_at
    }
    REPOSITORIES {
        ObjectId _id
        string user_id
        string name
        string status
        object processing
        string github_url
        datetime created_at
    }
    CHUNKS {
        ObjectId _id
        string repository_id
        string content
        float[] embedding
        object metadata
        string file_hash
    }
    CHAT_SESSIONS {
        ObjectId _id
        string repository_id
        string user_id
        array messages
        datetime updated_at
    }
    USERS ||--o{ REPOSITORIES : owns
    REPOSITORIES ||--o{ CHUNKS : "indexed into"
    REPOSITORIES ||--o{ CHAT_SESSIONS : "discussed in"
    USERS ||--o{ CHAT_SESSIONS : starts
```

For a deeper technical walkthrough of each component, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Getting Started

### Prerequisites

- Python 3.12, Node.js 18+, `git` on PATH
- MongoDB Atlas account (free M0 tier — [cloud.mongodb.com](https://cloud.mongodb.com))
- OpenAI API key ([platform.openai.com](https://platform.openai.com))

### Backend

```bash
# Clone and create virtual environment
git clone https://github.com/shivam-tamboli/AI-CodeBase-Assistant.git
cd AI-CodeBase-Assistant

python3.12 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
python3 -m pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env — minimum required: OPENAI_API_KEY, MONGODB_URI, JWT_SECRET
```

Minimum `backend/.env`:
```env
OPENAI_API_KEY=sk-...
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/ragdb?retryWrites=true&w=majority
JWT_SECRET=<run: python3 -c "import secrets; print(secrets.token_hex(32))">
```

```bash
# Run from the project root (not from inside backend/)
uvicorn backend.main:app --reload
# API:     http://localhost:8000
# Swagger: http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App: http://localhost:5173
```

No frontend environment variables needed for local development — the app defaults to `http://localhost:8000`.

---

## Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API key (embeddings + LLM when `LLM_PROVIDER=openai`) |
| `MONGODB_URI` | **Yes** | — | MongoDB Atlas connection string — must include `/ragdb` |
| `JWT_SECRET` | **Yes** | insecure default | HS256 signing secret — generate with `secrets.token_hex(32)` |
| `LLM_PROVIDER` | No | `openai` | `openai` or `anthropic` |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name for the selected provider |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model |
| `ANTHROPIC_API_KEY` | No | — | Required when `LLM_PROVIDER=anthropic` |
| `COHERE_API_KEY` | No | — | Enables Cohere cross-encoder re-ranking; omit for BM25 fallback |
| `GITHUB_TOKEN` | No | — | Personal access token for importing private repositories |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000` | Comma-separated CORS origins; set to your frontend URL in production |
| `ENABLE_CHUNK_SUMMARIES` | No | `false` | Generate LLM summaries per chunk at index time (improves retrieval; increases cost) |

See [`backend/.env.example`](backend/.env.example) for a fully annotated template.

---

## Project Structure

```
.
├── backend/
│   ├── main.py                       # FastAPI app — lifespan, middleware, routers
│   ├── database.py                   # MongoDB Motor singleton
│   ├── api/
│   │   ├── auth.py                   # POST /auth/register, /auth/login
│   │   ├── repositories.py           # Repo CRUD, upload, GitHub import, reindex, symbols
│   │   └── chat.py                   # Sessions CRUD + /query + /query/stream (SSE)
│   ├── services/
│   │   ├── file_scanner.py           # Directory walker — 15 extensions, skips venv/node_modules
│   │   ├── ast_parser.py             # Python ast — functions, classes, imports + line numbers
│   │   ├── treesitter_parser.py      # tree-sitter — JS/TS/Go/Java/Rust symbol extraction
│   │   ├── chunker.py                # AST-aware chunking + token-based overlap
│   │   ├── vector_store.py           # $vectorSearch HNSW + in-memory cosine fallback
│   │   ├── keyword_search.py         # MongoDB $text compound index + symbol lookup
│   │   ├── hybrid_search.py          # RRF fusion + Cohere/BM25 re-ranking
│   │   ├── llm_service.py            # Streaming answer generation + citation validation
│   │   ├── processor.py              # Ingestion orchestrator + incremental re-index (MD5 diff)
│   │   ├── rag_pipeline.py           # Query pipeline orchestrator
│   │   └── providers/
│   │       ├── base.py               # LLMProvider + EmbeddingProvider abstract interfaces
│   │       ├── openai_provider.py    # OpenAI LLM + embedding implementations
│   │       ├── anthropic_provider.py # Anthropic Claude LLM implementation
│   │       └── factory.py            # get_llm_provider(), get_embedding_provider()
│   └── tests/
│       ├── conftest.py               # Fixtures: mock_db, test_client, auth_headers
│       ├── test_unit.py              # JWT, CodeChunker, RRF (21 tests)
│       └── test_api.py               # Full API integration — mock-isolated (20 tests)
│
├── frontend/src/
│   ├── App.jsx                       # Entire SPA — auth, upload, import, chat, SSE streaming
│   └── App.css                       # Two-column layout + dark design system
│
├── Procfile                          # Render/Railway start command
├── runtime.txt                       # Python 3.12.0 pin for Render
└── docs/
    ├── deployment.md                 # MongoDB Atlas, Render, Vercel step-by-step
    ├── search-pipeline.md            # Hybrid search internals: RRF, BM25, Cohere
    └── provider-architecture.md      # Provider abstraction and extension guide
```

---

## Testing

```bash
python -m pytest backend/tests/ -q
```

41 tests, no external services required — MongoDB and OpenAI are fully mocked.

| File | Tests | What is covered |
|---|---|---|
| `test_unit.py` | 21 | JWT encode/decode + edge cases, CodeChunker AST extraction, RRF scoring algorithm |
| `test_api.py` | 20 | Auth register/login, repository CRUD + ownership isolation, chat session lifecycle, health endpoint |

---

## What I Learned

<!-- Fill these in with your own words — interviewers will ask about them directly -->

**Hybrid search and why vector search alone is not enough**
<!-- Suggested talking point: semantic search handles "how are passwords secured?" but fails on "find the verify_token function" — exact name lookup requires keyword search. RRF was a specific design decision, not the obvious choice. What made you pick k=60? What did you try before that? -->

**Streaming LLM responses over HTTP**
<!-- Suggested talking point: why SSE and not WebSockets? Why ReadableStream instead of EventSource in the frontend? What problems did you run into with partial JSON chunks and how did you handle the token accumulation on the client side? -->

**Designing for provider abstraction**
<!-- Suggested talking point: OpenAI and Anthropic have meaningfully different API shapes — the system parameter is top-level in Anthropic but a message role in OpenAI. What did the abstract interface look like before you saw those differences, and how did it change? What would it take to add a third provider? -->

---

## Future Improvements

- **GitHub OAuth** — private repo access currently uses a single `GITHUB_TOKEN`. A proper implementation would authenticate each user via GitHub OAuth so they access only their own repositories.
- **Webhook-based auto-indexing** — re-indexing is triggered manually. A GitHub App webhook could trigger incremental re-index on every push, keeping the index current automatically.
- **Docker Compose** — local setup currently requires separate terminal windows and manual MongoDB Atlas setup. A Compose file would bring up the full stack with a single command.
- **Cross-repository search** — queries are scoped to one repository. Many interesting questions span multiple repos (e.g. "how does service A call service B?").
- **Observability** — LLM call latency and search hit rates are logged but not instrumented. OpenTelemetry spans on the query pipeline would make it easy to see where time is spent.

---

## Deployment

See [docs/deployment.md](docs/deployment.md) for step-by-step instructions (MongoDB Atlas, Render/Railway, Vercel).

**Backend (Render or Railway)**
```
Build command: pip install -r backend/requirements.txt
Start command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Frontend (Vercel)**
- Root directory: `frontend`
- Environment variable: `VITE_API_URL` = your backend URL

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

| Method | Path | Description |
|---|---|---|
| GET | `/repositories` | List user's repositories |
| POST | `/repositories/upload` | Upload ZIP — multipart: `file`, `name?`, `description?` |
| POST | `/repositories/import` | Import from GitHub — `{url, name?, branch?}` |
| GET | `/repositories/{id}/status` | Poll indexing progress — `pending\|indexing\|indexed\|failed` |
| POST | `/repositories/{id}/reindex` | Re-index from new ZIP (MD5 diff — skips unchanged files) |
| GET | `/repositories/{id}/symbols` | Symbol lookup — `?name=foo&type=function\|class` |
| DELETE | `/repositories/{id}` | Delete repository and all indexed chunks |

Upload, Import, and Reindex return `202 Accepted`. Poll `/status` until `indexed` or `failed`.

### Chat

| Method | Path | Description |
|---|---|---|
| POST | `/chat/query/stream` | Ask a question — SSE stream of `token` / `done` / `error` events |
| POST | `/chat/query` | Ask a question — blocking, returns full answer |
| POST | `/chat/sessions` | Create a session — `{repository_id}` |
| GET | `/chat/sessions` | List sessions — `?repository_id` |
| DELETE | `/chat/sessions/{id}` | Delete a session |

**SSE event format:**
```
data: {"type": "token", "token": "...", "answer": "<accumulated so far>"}
data: {"type": "done",  "answer": "<full answer>", "sources": [...], "citation_valid": true}
data: {"type": "error", "error": "rate_limit | api_error | unknown"}
```

---

## External Services

| Service | Required | Free Tier | Purpose |
|---|---|---|---|
| MongoDB Atlas | Yes | M0 — 512 MB | Database, vector search, full-text search |
| OpenAI | Yes (default) | $5 trial credit | Embeddings + LLM completions |
| Anthropic | No | $5 trial credit | Alternative LLM (`LLM_PROVIDER=anthropic`) |
| Cohere | No | 1,000 req/month | Cross-encoder re-ranking |

### Atlas Vector Search Index (one-time setup)

Without this index the system falls back to in-memory cosine similarity automatically — no errors, just slower at scale.

1. Atlas → your cluster → **Atlas Search** → **Create Search Index** → **Atlas Vector Search** → **JSON Editor**
2. Database: `ragdb`, Collection: `chunks`
3. Paste:

```json
{
  "fields": [
    { "type": "vector", "path": "embedding", "numDimensions": 1536, "similarity": "cosine" },
    { "type": "filter", "path": "repository_id" }
  ]
}
```

4. Name: `vector_search_index` → Create. Wait ~2 minutes for status **Active**.

---

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical deep dive with Mermaid diagrams for every major flow |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branching conventions, PR guidelines, code style |
| [docs/deployment.md](docs/deployment.md) | Step-by-step: Atlas, Render/Railway, Vercel |
| [docs/search-pipeline.md](docs/search-pipeline.md) | Hybrid search internals: RRF, BM25, Cohere |
| [docs/provider-architecture.md](docs/provider-architecture.md) | LLM/embedding provider system and how to add new providers |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common errors, root causes, and fixes |

---

## License

MIT — see [LICENSE](LICENSE).
