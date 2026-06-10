# AI Codebase Assistant

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![OpenAI](https://img.shields.io/badge/OpenAI-API-412991?logo=openai&logoColor=white)
![Tests](https://img.shields.io/badge/tests-41_passing-4CAF50)
![License](https://img.shields.io/badge/license-MIT-blue)

Upload a codebase as a ZIP or import from GitHub, then ask questions about it in plain English. Answers stream live to the browser with exact file and line citations.

**Live app:** https://ai-code-base-assistant-kws4.vercel.app

![Demo screenshot](docs/demo.png)

---

## The problem it solves

Reading an unfamiliar codebase is slow. You scan files, trace call chains, and grep around before you can ask a single meaningful question. This project replaces that process — upload a repo once and ask anything. The system finds the relevant code, cites the exact files and lines, and explains what it found without hallucinating paths it didn't retrieve.

---

## How it works

There are two pipelines that share the same MongoDB collections.

**Ingestion** — when you upload a ZIP or give a GitHub URL, the backend extracts the archive, parses each file into AST-aware chunks (function and class boundaries), embeds them in batches, and stores everything in MongoDB. The upload endpoint returns 202 immediately; indexing runs in the background and you poll `/status`.

**Query** — when you ask a question, it gets embedded and passed to both semantic search (`$vectorSearch` HNSW) and keyword search (`$text`) in parallel. The results are merged with Reciprocal Rank Fusion, optionally re-ranked by Cohere, and the top chunks become context for the LLM. The answer streams back over SSE.

```
Upload/GitHub URL
      │
      ▼
 FileScanner → AST Parser → CodeChunker → EmbeddingService → MongoDB
 
User question
      │
      ├─→ $vectorSearch (semantic)  ─┐
      │                              ├─→ RRF Fusion → Rerank → LLM → SSE stream
      └─→ $text search (keyword)   ─┘
```

**Data model:**

```
USERS ──< REPOSITORIES ──< CHUNKS
  │
  ├──< CHAT_SESSIONS
  └──< REFRESH_TOKENS
```

---

## Tech stack

| Layer | What |
|---|---|
| API | FastAPI + Uvicorn (async) |
| Database | MongoDB Atlas — stores everything: users, repos, chunks with embeddings, sessions |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim, batched) |
| Vector search | MongoDB Atlas `$vectorSearch` HNSW — no separate vector DB needed |
| LLM | OpenAI GPT or Anthropic Claude — switchable via env var, no code changes |
| Re-ranking | Cohere `rerank-english-v3.0`; BM25 fallback when key is absent |
| AST parsing | Python `ast` for Python; tree-sitter for JS/TS/Go/Java/Rust |
| Frontend | React 19 + Vite + Axios — single-file SPA, SSE via `ReadableStream` |
| Deployment | Render (backend) + Vercel (frontend) |

---

## Getting started

### Prerequisites

- Python 3.12, Node.js 18+, `git` on PATH
- MongoDB Atlas free tier — [cloud.mongodb.com](https://cloud.mongodb.com)
- OpenAI API key — [platform.openai.com](https://platform.openai.com)

### Backend

```bash
git clone https://github.com/shivam-tamboli/AI-CodeBase-Assistant.git
cd AI-CodeBase-Assistant

python3.12 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt

cp backend/.env.example backend/.env
# Edit backend/.env — set OPENAI_API_KEY, MONGODB_URI, JWT_SECRET
```

Minimum `.env`:
```env
OPENAI_API_KEY=sk-...
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/ragdb?retryWrites=true&w=majority
JWT_SECRET=<run: python3 -c "import secrets; print(secrets.token_hex(32))">
```

```bash
uvicorn backend.main:app --reload
# API:     http://localhost:8000
# Swagger: http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

No frontend env vars needed for local dev — defaults to `http://localhost:8000`.

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | Embeddings + LLM (when `LLM_PROVIDER=openai`) |
| `MONGODB_URI` | Yes | — | Atlas connection string — must include `/ragdb` |
| `JWT_SECRET` | Yes | insecure default | HS256 signing key — generate with `secrets.token_hex(32)` |
| `LLM_PROVIDER` | No | `openai` | `openai` or `anthropic` |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name for the selected provider |
| `ANTHROPIC_API_KEY` | No | — | Required when `LLM_PROVIDER=anthropic` |
| `COHERE_API_KEY` | No | — | Enables Cohere re-ranking; omit for BM25 fallback |
| `GITHUB_TOKEN` | No | — | For importing private repositories |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000` | Comma-separated CORS origins |
| `ENVIRONMENT` | No | `development` | Set to `production` on Render — enables secure httpOnly cookies |

---

## Testing

```bash
python -m pytest backend/tests/ -q
```

41 tests, no external services required — MongoDB and OpenAI are fully mocked.

| File | Tests | Covers |
|---|---|---|
| `test_unit.py` | 21 | JWT, CodeChunker, RRF scoring |
| `test_api.py` | 20 | Auth, repo CRUD, ownership isolation, session lifecycle |

---

## What I learned

**Hybrid search matters.** Vector search alone handles conceptual questions well ("how are passwords secured?") but fails on exact names ("find the verify_token function"). Adding keyword search and fusing the two ranked lists with RRF gave noticeably better results than either alone.

**SSE over WebSockets for streaming.** WebSockets require a persistent connection and are harder to load-balance. SSE is one-directional but that's all we need — the server pushes tokens, the client doesn't send anything mid-stream. I used `ReadableStream` instead of `EventSource` because `EventSource` doesn't support POST requests with auth headers.

**Provider abstraction is harder than it looks.** The OpenAI and Anthropic APIs have different shapes — the `system` prompt is a top-level parameter in Anthropic but a message role in OpenAI. Building the abstract interface before I saw those differences meant I had to revise it. The lesson: look at both APIs first, then design the interface.

---

## Atlas Vector Search index (one-time setup)

Without this index the system falls back to in-memory cosine similarity — no errors, just slower at scale.

1. Atlas → your cluster → **Atlas Search** → **Create Search Index** → **Atlas Vector Search** → **JSON Editor**
2. Database: `ragdb`, Collection: `chunks`
3. Paste and create:

```json
{
  "fields": [
    { "type": "vector", "path": "embedding", "numDimensions": 1536, "similarity": "cosine" },
    { "type": "filter", "path": "repository_id" }
  ]
}
```

Name it `vector_search_index`. Wait ~2 minutes for status **Active**.

---

## API reference

All endpoints except `/`, `/health`, `/auth/register`, and `/auth/login` require:
```
Authorization: Bearer <access_token>
```

### Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{username, password}` | `{access_token}` 201 + sets `refresh_token` cookie |
| POST | `/auth/login` | `{username, password}` | `{access_token}` 200 + sets `refresh_token` cookie |
| POST | `/auth/refresh` | — (reads httpOnly cookie) | `{access_token}` 200 |
| POST | `/auth/logout` | — (reads httpOnly cookie) | 200, clears cookie |

### Repositories

| Method | Path | Description |
|---|---|---|
| GET | `/repositories` | List your repositories |
| POST | `/repositories/upload` | Upload ZIP — multipart: `file`, `name?` |
| POST | `/repositories/import` | Import from GitHub — `{url}` |
| GET | `/repositories/{id}/status` | Poll status — `pending\|indexing\|indexed\|failed` |
| POST | `/repositories/{id}/reindex` | Re-index from new ZIP |
| DELETE | `/repositories/{id}` | Delete repo and all its chunks |

Upload and import return `202 Accepted` — poll `/status` until `indexed` or `failed`.

### Chat

| Method | Path | Description |
|---|---|---|
| POST | `/chat/query/stream` | Ask a question — SSE stream |
| POST | `/chat/sessions` | Create a session |
| GET | `/chat/sessions` | List sessions for a repo |
| DELETE | `/chat/sessions/{id}` | Delete a session |

SSE event format:
```
data: {"type": "token", "answer": "<accumulated so far>"}
data: {"type": "done",  "answer": "<full>", "sources": [...]}
data: {"type": "error", "error": "rate_limit | api_error | unknown"}
```

---

## Deployment

See [docs/deployment.md](docs/deployment.md) for step-by-step instructions.

**Backend (Render)**
```
Build:  pip install -r backend/requirements.txt
Start:  uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Frontend (Vercel)**
- Root directory: `frontend`
- Environment variable: `VITE_API_URL` = your backend URL

---

## Future improvements

- **GitHub OAuth** — private repos currently use a single `GITHUB_TOKEN`. Proper per-user OAuth would scope access correctly.
- **Webhook re-indexing** — re-indexing is triggered manually. A GitHub App webhook could handle it automatically on push.
- **Cross-repo search** — queries are scoped to one repo. Spanning multiple repos (e.g. "how does service A call service B?") would require a different retrieval strategy.
- **Docker Compose** — local setup needs separate terminal windows and Atlas. A Compose file would simplify it.

---

## License

MIT — see [LICENSE](LICENSE).
