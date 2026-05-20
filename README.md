# AI Codebase Assistant

A full-stack RAG (Retrieval Augmented Generation) application that lets developers upload a Python codebase as a ZIP file, ask natural language questions about it, and receive answers with exact file path and line number citations.

**Built with**: Python, FastAPI, MongoDB, OpenAI API, React — deployed on Vercel (frontend) + Render (backend).

---

## What It Does

You upload your project → the system reads and indexes all Python code → you ask questions in plain English → the AI answers with specific file/line references from your own codebase, with full multi-turn conversation history.

**Example**: "Where is the authentication logic?" → "Authentication is handled in `auth.py` lines 15–40. The `authenticate()` function checks password hashes using bcrypt..."

---

## Status

| Area | Status |
|---|---|
| Core RAG pipeline (upload → index → query) | Working |
| JWT authentication + bcrypt passwords | Working |
| Hybrid search (semantic + keyword + RRF) | Working |
| Multi-turn chat session UI | Working (new) |
| Symbol/function search API | Working (new) |
| Semantic search chunk limit bug | Fixed |
| Frontend repo reload on refresh bug | Fixed |
| Orphaned chunks on delete bug | Fixed |
| MongoDB text index conflict | Fixed |
| GitHub repository import | Not implemented |
| Multi-language indexing (JS, Go, Java…) | Not implemented (Python only) |
| Response streaming | Backend ready, no API endpoint |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI 0.104, Uvicorn |
| Database | MongoDB Atlas (motor async driver) |
| AI / Embeddings | OpenAI text-embedding-3-small (1536 dimensions) |
| AI / LLM | OpenAI GPT-4 (configurable) |
| Auth | JWT (python-jose, HS256, 24h expiry) + bcrypt |
| Rate Limiting | SlowAPI — per-IP on all endpoints |
| Frontend | React 19, Vite, Axios |
| Deployment | Vercel (frontend) + Render (backend) |

---

## Architecture Summary

```
User (Browser)
     │
     ▼
React SPA (Vite) — Vercel
     │  HTTP/JSON + Bearer token
     ▼
FastAPI (Python) — Render
     ├── Middleware: CORS, Rate Limiting, Error Handlers
     ├── Auth: JWT verification dependency
     ├── /auth        → register, login
     ├── /repositories → CRUD + ZIP upload + symbol search
     └── /chat        → sessions CRUD + query (RAG)
          │
          ├── RepositoryProcessor: scan → AST parse → chunk → embed → store
          ├── HybridSearchService: semantic (cosine) + keyword ($text) → RRF fusion
          └── LLMService: GPT-4 prompt → answer with citations

MongoDB Atlas (ragdb)
  ├── users           — accounts
  ├── repositories    — uploaded repos
  ├── chunks          — code + 1536-dim embeddings
  └── chat_sessions   — conversation history
```

---

## Features

### Authentication
- Register / Login with username + password
- Passwords hashed with bcrypt
- JWT tokens (24-hour expiry, stored in localStorage)
- All data scoped to the logged-in user

### Repository Management
- Upload a ZIP file of any Python project
- Automatic extraction, scanning, and indexing
- AST-based intelligent chunking (extracts functions, classes, imports with exact line numbers)
- Full CRUD: list, view, rename, delete (chunks deleted with the repo)

### AI-Powered Q&A
- Ask natural language questions about your codebase
- Hybrid search: semantic similarity (OpenAI embeddings + cosine) + keyword (`$text`) combined with Reciprocal Rank Fusion (RRF)
- GPT-4 answers with exact source citations (file path, line numbers, function/class name)
- Every answer shows which code chunks were used as context

### Conversation Sessions
- Create multiple conversations per repository
- Full conversation history stored in MongoDB
- Continue previous conversations — AI remembers context
- Switch between sessions, delete old ones
- Session sidebar visible while chatting

### Symbol Search API
- `GET /repositories/{id}/symbols?name=foo&type=function`
- Find any function or class by exact name
- Returns source code, file path, and line numbers
- Useful for debugging and code navigation

### Infrastructure
- Rate limiting on all endpoints (SlowAPI)
- Centralized error handling with structured JSON responses
- MongoDB connection with auto-index creation on startup
- Health check endpoint at `/health`

---

## Project Structure

```
.
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── database.py              # MongoDB singleton connection
│   ├── requirements.txt
│   ├── .env.example
│   ├── api/
│   │   ├── auth.py              # POST /auth/register, POST /auth/login
│   │   ├── repositories.py      # Repo CRUD + upload + symbol search
│   │   └── chat.py              # Sessions + POST /chat/query
│   ├── auth/
│   │   ├── jwt.py               # JWT create + verify
│   │   └── dependencies.py      # get_current_user FastAPI dependency
│   ├── middleware/
│   │   ├── error_handlers.py    # Exception → structured JSON
│   │   └── rate_limiter.py      # SlowAPI instance
│   ├── models/
│   │   ├── repository.py        # Pydantic models for repo
│   │   └── chat.py              # Pydantic models for chat/sessions
│   └── services/
│       ├── file_scanner.py      # Finds code files (15 extensions)
│       ├── ast_parser.py        # Python AST → functions/classes/imports
│       ├── chunker.py           # Token-aware code chunks
│       ├── embedding.py         # OpenAI embeddings (batch)
│       ├── vector_store.py      # MongoDB storage + cosine search
│       ├── keyword_search.py    # MongoDB $text search + symbol lookup
│       ├── hybrid_search.py     # RRF fusion of both search methods
│       ├── llm_service.py       # GPT-4 answer generation
│       ├── chat_service.py      # Session + message persistence
│       ├── processor.py         # Ingestion orchestrator
│       └── rag_pipeline.py      # Query orchestrator
│
├── frontend/
│   └── src/
│       ├── App.jsx              # Full SPA with session sidebar + chat UI
│       ├── App.css              # Responsive two-column layout
│       └── main.jsx             # React entry point
│
├── Procfile                     # Render/Railway process definition
├── pytest.ini                   # Test runner configuration
└── README.md
```

---

## Quick Start (Local)

### Prerequisites
- Python 3.10+, Node.js 18+, MongoDB Atlas account, OpenAI API key

### Backend

```bash
# Run from the project ROOT (not inside backend/)
cd "AI CodeBase Assistance"

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r backend/requirements.txt

cp backend/.env.example backend/.env
# Edit backend/.env and fill in OPENAI_API_KEY, MONGODB_URI, JWT_SECRET

uvicorn backend.main:app --reload
# API at http://localhost:8000
# Auto-docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App at http://localhost:5173
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `MONGODB_URI` | Yes | MongoDB Atlas connection string |
| `JWT_SECRET` | Yes | Any long random string (change before deploying!) |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins (default: localhost:3000) |
| `LLM_MODEL` | No | OpenAI model name (default: `gpt-4o-mini`; set `gpt-4o` or `gpt-4` for higher capability) |
| `LLM_MAX_TOKENS` | No | Max response tokens (default: 2000) |

---

## API Reference

### Authentication
```
POST /auth/register   {username, password} → {access_token, token_type}
POST /auth/login      {username, password} → {access_token, token_type}
```

All other endpoints require: `Authorization: Bearer <token>`

### Repositories
```
GET    /repositories                  → list your repositories
GET    /repositories/{id}             → single repository
POST   /repositories                  {name, description} → create empty
POST   /repositories/upload           multipart .zip → upload + index
PUT    /repositories/{id}             {name?, description?} → update
DELETE /repositories/{id}             → 204 (also deletes all chunks)
GET    /repositories/{id}/symbols     ?name=foo&type=function|class → find symbols
```

### Chat
```
POST   /chat/sessions             {repository_id} → create session
GET    /chat/sessions             ?repository_id&limit → list sessions
GET    /chat/sessions/{id}        → full session with messages
GET    /chat/sessions/{id}/history  ?limit → recent messages
DELETE /chat/sessions/{id}        → 204
POST   /chat/query                {question, repository_id, session_id?, limit?} → answer
```

### System
```
GET  /         → {"message": "API is running"}
GET  /health   → {status, database}
```

---

## Deployment

### Frontend → Vercel (Recommended)

Vercel works perfectly for the React frontend.

1. Push your code to GitHub (if not already)
2. Go to [vercel.com](https://vercel.com) → Sign up with GitHub
3. Click "Add New Project" → Import your GitHub repo
4. **Important**: Set **Root Directory** to `frontend`
5. Vercel auto-detects Vite. Build settings will be:
   - Build Command: `npm run build`
   - Output Directory: `dist`
6. Add Environment Variable:
   - `VITE_API_URL` = your Render backend URL (see below)
7. Deploy

Then update `App.jsx` line 5:
```js
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
```

### Backend → Render (Free Tier)

> **Why not Vercel for the backend?** Vercel's free tier has a 10-second function timeout. LLM calls in this project can take 15–30 seconds. Render gives you a persistent server with no timeout, which is what FastAPI needs.

1. Go to [render.com](https://render.com) → Sign up with GitHub
2. New → **Web Service** → Connect your GitHub repo
3. Settings:
   - **Root Directory**: (leave empty — uses project root)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Environment Variables (set in Render dashboard):
   - `OPENAI_API_KEY`
   - `MONGODB_URI`
   - `JWT_SECRET` (use a strong random string)
   - `ALLOWED_ORIGINS` = your Vercel frontend URL
5. Deploy → Render gives you a URL like `https://your-app.onrender.com`

A `Procfile` is included in the project root for Render/Railway:
```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

> **Free tier note**: Render's free tier spins down after 15 minutes of inactivity. First request after sleep takes ~30 seconds. Upgrade to a paid plan ($7/month) for a production-quality demo.

---

## Known Limitations

- **Python only**: Despite detecting 14 languages, only Python code is indexed. JS, Go, Java etc. are scanned but not processed.
- **Temp file storage**: Uploaded ZIPs are deleted after processing. Re-indexing requires re-uploading.
- **In-memory semantic search**: Cosine similarity computed in Python (fixed chunk limit removed). For very large repos (1000+ functions), MongoDB Atlas Vector Search would be faster.
- **No token refresh**: JWT expires after 24 hours. User must log in again.
- **GitHub import**: Not implemented. Only ZIP upload supported.

---

## Roadmap

Improvements are ordered by engineering impact and implementation complexity.

### Near-term

- **Markdown rendering**: Replace plain-text LLM output in the chat UI with a markdown renderer (`react-markdown`). Responses already include code blocks and formatting — rendering them correctly is a one-dependency change.
- **MongoDB Atlas Vector Search**: Replace the current in-memory cosine similarity loop with a `$vectorSearch` aggregation pipeline. Eliminates the O(n) full-collection scan on every query; HNSW indexing at the database layer handles similarity without loading embeddings into Python.
- **GitHub URL import**: Accept a repository URL in addition to ZIP upload. `PyGithub` is already a declared dependency — clone server-side and pass the directory to the existing `RepositoryProcessor` pipeline.
- **Repository stats endpoint**: `RAGPipeline.get_repository_stats()` is implemented but not exposed. A `GET /repositories/{id}/stats` endpoint returning file, function, class, and chunk counts is a straightforward addition.

### Medium-term

- **Multi-language indexing**: `file_scanner.py` detects 15 extensions; `processor.py` filters to Python only. Integrating `tree-sitter` enables language-agnostic AST parsing for JS/TS, Go, Java, Rust, and others without changing the chunking or embedding pipeline.
- **LLM response streaming**: `LLMService.generate_streaming_answer()` and `RAGPipeline.query_with_streaming()` are already implemented. Exposing a `/chat/query/stream` SSE endpoint and adding a frontend `EventSource` consumer completes the feature.
- **Cross-encoder re-ranking**: Add a Cohere or `bge-reranker` pass after RRF fusion. A cross-encoder reads query and candidate chunk together, producing meaningfully better ranking than the current heuristic keyword-bonus approach.
- **Incremental indexing**: On re-upload, diff the file list against stored chunk metadata and only re-embed changed files. Reduces re-indexing time and embedding API cost on iterative updates.

### Long-term

- **Dedicated vector store (Qdrant)**: At scale beyond ~10K chunks per repository, a dedicated vector database with native HNSW indexing and payload filtering outperforms MongoDB Atlas Vector Search. Migration is isolated to `vector_store.py`.
- **Citation enforcement**: Post-process LLM output to verify each cited `file:line` reference exists in the indexed chunks before returning the response. Rejects hallucinated citations.
- **GitHub webhook integration**: Trigger incremental re-indexing automatically on push events rather than requiring manual re-upload.
- **Observability**: Structured request tracing (Langfuse or OpenTelemetry) to instrument retrieval latency, embedding cost per query, and chunk relevance scores over time.
