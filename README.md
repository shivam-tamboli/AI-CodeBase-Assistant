# AI Codebase Assistant

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/tests-98_passing-4CAF50)
![License](https://img.shields.io/badge/license-MIT-blue)

Point it at a GitHub repo (or upload a ZIP) and ask questions about the code in plain English. Answers stream in as they're written, and each one lists the files and line ranges it was built from.

**Live app:** https://ai-code-base-assistant-kws4.vercel.app

![Asking the demo repo how expired tokens are rejected](docs/demo.png)

## Try it in a minute

1. Open the live app and create an account (username of 3–32 characters, password of at least 8).
2. Click **Try a demo repo**. It loads [`pallets/itsdangerous`](https://github.com/pallets/itsdangerous), which is already indexed.
3. Click one of the suggested questions, or ask your own.

The backend runs on Render's free tier, which puts the server to sleep after 15 minutes without traffic. Waking it up takes 50–60 seconds. Uptime Robot hits `/health` every 5 minutes so it doesn't fall asleep in the first place. If it ever does (a redeploy, a missed ping), the login page pings the server as soon as it loads. Most of the wake-up then happens while you're typing your details.

## Why I built it

Reading an unfamiliar codebase is slow. You open files, follow imports and grep for names before you can ask a useful question. I wanted to ask the question first and get pointed at the right code, with citations I can check, not a confident paragraph about files that don't exist.

## What it does

- **Imports code** from a public GitHub URL, a ZIP upload, or a private repo using your own GitHub token. The token is sent once and never stored.
- **Splits code along real boundaries.** Python is parsed with `ast`, and JS, TS, Go, Java and Rust with tree-sitter, so chunks are whole functions and classes. Other file types (15 extensions in total) are split into overlapping windows of lines.
- **Searches two ways at once.** Vector search finds code by meaning, and keyword search finds exact names. Both lists are merged with Reciprocal Rank Fusion, then reranked by Cohere. When Cohere isn't configured, BM25 is fused with the existing ranking instead of replacing it.
- **Streams answers** over Server-Sent Events and lists the sources in relevance order.
- **Remembers conversations** per repo and per user.
- **Has a shared demo repo** that every user can read and nobody can change.

The security and reliability work is listed under [Recent changes](#recent-changes).

<a id="architecture"></a>

## How it works

There are two pipelines, and they share the same MongoDB collections.

**Ingestion.** An upload or import returns `202 Accepted` straight away. A background task scans the files, parses them into chunks, embeds the chunks in batches with OpenAI and stores them. The client polls `/repositories/{id}/status` until it says `indexed`.

**Query.** The question is embedded and sent to vector search and keyword search in parallel. The results are fused, reranked, and stripped of near-duplicate windows of the same symbol. The top 5 chunks become the model's context, and the answer streams back token by token.

```
Upload ZIP / GitHub URL
        │
        ▼
FileScanner → AST / tree-sitter parser → CodeChunker → embeddings → MongoDB

Question
   ├─→ vector search ($vectorSearch, or in-memory cosine) ─┐
   │                                                       ├─→ RRF → Cohere rerank (or fused BM25) → drop overlaps → LLM → SSE
   └─→ keyword search ($text) ─────────────────────────────┘
```

```
USERS ──< REPOSITORIES ──< CHUNKS          (one shared repo has is_demo: true and no owner)
  │            └──< CHAT_SESSIONS
  ├──< CHAT_SESSIONS
  └──< REFRESH_TOKENS
```

More detail: [ARCHITECTURE.md](ARCHITECTURE.md), [docs/search-pipeline.md](docs/search-pipeline.md), [docs/provider-architecture.md](docs/provider-architecture.md).

## Tech stack

| Layer | What I used |
|---|---|
| API | FastAPI + Uvicorn, async throughout, Motor for MongoDB |
| Database | MongoDB Atlas for users, repos, chunks with their embeddings, sessions and refresh tokens |
| Vector search | Atlas `$vectorSearch`, falling back to in-memory cosine similarity if the index doesn't exist |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dimensions) |
| LLM | OpenAI `gpt-4o-mini` by default; Anthropic Claude with one env var change |
| Reranking | Cohere `rerank-english-v3.0`, with BM25 as the fallback |
| Parsing | Python `ast`, tree-sitter for the other AST languages |
| Auth | JWT access tokens (15 min), plus refresh tokens in an httpOnly cookie |
| Frontend | React 19 + Vite. Split into `Auth`, `Sidebar` and `Chat` components; `api.js` holds every API call and adds the auth header in one place |
| Hosting | Render free tier (backend), Vercel (frontend), Uptime Robot to keep Render awake, GitHub Actions running the tests on every PR |

<a id="quick-start"></a>

## Running it locally

You need Python 3.12, Node 18+, `git`, an OpenAI API key, and MongoDB: a free Atlas cluster, or a local `mongod`.

### Backend

```bash
git clone https://github.com/shivam-tamboli/AI-CodeBase-Assistant.git
cd AI-CodeBase-Assistant

python3.12 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt

cp backend/.env.example backend/.env
```

Then open `backend/.env` and fill in at least these three:

```env
OPENAI_API_KEY=sk-...
MONGODB_URI=mongodb+srv://user:pass@cluster.xxxxx.mongodb.net/ragdb?retryWrites=true&w=majority
JWT_SECRET=<output of: python3 -c "import secrets; print(secrets.token_hex(32))">
```

- Keep `/ragdb` in the URI; that's the database the app uses.
- For a local MongoDB instead of Atlas, use `mongodb://localhost:27017/ragdb?ssl=false`. The `ssl=false` matters, because the app adds TLS options to any URI that doesn't mention `ssl`.

Run it from the repo root:

```bash
uvicorn backend.main:app --reload
# API:  http://localhost:8000
# Docs: http://localhost:8000/docs
```

On first start it clones and indexes the demo repo in the background, which takes about 15 seconds. Set `DEMO_REPO_URL=` to an empty value to skip that.

### Frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

The frontend talks to `http://localhost:8000` unless you set `VITE_API_URL`. The default `ALLOWED_ORIGINS` in `.env.example` already includes port 5173.

## Configuration

All backend settings live in `backend/.env`. [`backend/.env.example`](backend/.env.example) has every one, with comments.

| Variable | Required | Default | What it does |
|---|---|---|---|
| `OPENAI_API_KEY` | yes | — | Embeddings, plus the LLM when `LLM_PROVIDER=openai` |
| `MONGODB_URI` | yes | — | Connection string; must include `/ragdb` |
| `JWT_SECRET` | yes | insecure placeholder | Signs access and refresh tokens |
| `ENVIRONMENT` | on Render | `development` | Set to `production` when hosting, so the refresh cookie is `Secure; SameSite=None` and works across the two domains |
| `ALLOWED_ORIGINS` | no | `http://localhost:3000` | Comma-separated CORS origins |
| `LLM_PROVIDER` / `LLM_MODEL` | no | `openai` / `gpt-4o-mini` | Switch to `anthropic` and a Claude model if you like |
| `LLM_MAX_TOKENS` | no | `2000` | Maximum answer length |
| `ANTHROPIC_API_KEY` | if using Claude | — | |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | no | `openai` / `text-embedding-3-small` | |
| `COHERE_API_KEY` | no | — | Turns on Cohere reranking; without it, BM25 fusion is used |
| `MAX_UPLOAD_MB` | no | `50` | Largest ZIP accepted (413 above it) |
| `MAX_EXTRACTED_MB` | no | `200` | Largest size a ZIP may unpack to (zip-bomb guard) |
| `DEMO_REPO_URL` | no | `https://github.com/pallets/itsdangerous` | Repo used as the shared demo; empty disables it |
| `ENABLE_CHUNK_SUMMARIES` | no | `false` | Asks the LLM for a one-line summary per chunk at index time (slower, costs more) |

There's no server-side GitHub token. Public repos are cloned anonymously, and private ones need the user's own token in the import form.

## Tests

```bash
python -m pytest backend/tests -q
```

98 tests, with MongoDB, OpenAI and git mocked, so nothing external is needed. CI runs them on every pull request.

- `test_unit.py`: JWT handling, the chunker (including the overlap regression), RRF, the BM25 fallback fusion, overlap dedupe, and choosing the Cohere client.
- `test_api.py`: auth, validation and rate limits; upload limits and path traversal; repo ownership; the demo repo being read-only; chat refusing other users' repos; GitHub tokens never leaking; timestamps being timezone-aware.

## API

Everything except `/`, `/health`, `/auth/register` and `/auth/login` needs `Authorization: Bearer <access_token>`. Interactive docs are at `/docs` on a running backend.

**Auth** (register and login are limited to 5 requests a minute per client)

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | `{username, password}`; username 3–32 characters, password 8–72 bytes |
| POST | `/auth/login` | Returns `{access_token}` and sets the refresh cookie |
| POST | `/auth/refresh` | Uses the cookie; returns a new access token |
| POST | `/auth/logout` | Revokes the refresh token and clears the cookie |

**Repositories**

| Method | Path | Notes |
|---|---|---|
| GET | `/repositories` | Your repos |
| GET | `/repositories/demo` | The shared demo repo, plus suggested questions |
| POST | `/repositories/import` | `{url, github_token?, branch?, name?}`; returns 202 |
| POST | `/repositories/upload` | Multipart ZIP; returns 202 |
| GET | `/repositories/{id}/status` | `pending`, `indexing`, `indexed` or `failed` |
| GET | `/repositories/{id}`, `/stats`, `/symbols` | Details, chunk counts, symbol search |
| PUT / DELETE | `/repositories/{id}` | Rename / delete (not allowed on the demo) |
| POST | `/repositories/{id}/reindex` | Re-index from a new ZIP; only changed files are re-embedded |

**Chat**

| Method | Path | Notes |
|---|---|---|
| POST | `/chat/query/stream` | `{repository_id, question, session_id?}`; Server-Sent Events |
| POST | `/chat/query` | Same, but returns the whole answer in one response |
| POST / GET | `/chat/sessions` | Create a session / list yours for a repo |
| GET / DELETE | `/chat/sessions/{id}` | One session / delete it |
| GET | `/chat/sessions/{id}/history` | Its messages |

The stream sends one JSON object per line:

```
data: {"type": "token", "token": "...", "answer": "<answer so far>"}
data: {"type": "done",  "answer": "<full answer>", "sources": [{"file_path", "start_line", "end_line", "name", "chunk_type", "score"}], ...}
data: {"type": "error", "error": "rate_limit | api_error | unknown", "answer": "..."}
```

## Deploying

The step-by-step guide is in [docs/deployment.md](docs/deployment.md). In short:

- **Render (backend):**
  - Build with `pip install -r backend/requirements.txt`, start with `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
  - Set `OPENAI_API_KEY`, `MONGODB_URI`, `JWT_SECRET`, `ALLOWED_ORIGINS` (your Vercel URL) and `ENVIRONMENT=production`.
- **Vercel (frontend):** root directory `frontend`, with `VITE_API_URL` set to your Render URL.
- **Atlas vector index (optional but faster):** create a vector search index called `vector_search_index` on `ragdb.chunks`, with 1536 dimensions, cosine similarity, and a filter on `repository_id`. Without it, search still works using in-memory cosine similarity.
- **Uptime Robot (keeps the free Render instance awake):**
  - Add a monitor for `https://<your-app>.onrender.com/health`, checked every 5 minutes.
  - Make it a **Keyword** monitor that looks for `healthy`, not a plain HTTP monitor. Plain HTTP monitors send `HEAD` requests on the free plan, and `/health` only answers `GET`. A `HEAD` returns 405, so the monitor would report the site as down even while the pings keep it awake. Keyword monitors use `GET`.
  - Render gives 750 free instance hours a month, which covers one service running all month. A second always-on free service would run out.

Once it's live, `GET /health` should return `{"status": "healthy", "database": "connected"}`.

## Recent changes

Each of these went through an issue and a PR with tests:

- **Your own GitHub token for private repos ([#94](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/94)).** The server used to clone with its own token for anyone who asked.
- **Auth hardening ([#96](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/96), [#98](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/98)):**
  - rate limits on login and register, keyed on Cloudflare's `CF-Connecting-IP` because Render sits behind Cloudflare
  - input validation
  - no 500 error on a duplicate-username race
- **Upload hardening ([#96](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/96)):** filenames can't escape the temp folder, and ZIP size and unpacked size are capped.
- **Chat checks repo ownership ([#112](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/112)).** Before, anyone who had a repo's ID could chat with it.
- **Timezone-aware UTC timestamps ([#104](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/104)).** Session times were off by the viewer's UTC offset.
- **Chunking fix ([#108](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/108)).** Overlap was counted in lines instead of tokens, which turned one 400-line file into 125 near-identical chunks.
- **Reranking fix ([#110](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/110)).** The fallback reranker was discarding the semantic ranking, and the Cohere call broke on older SDK versions.
- **Demo repo ([#112](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/112)), mobile header ([#114](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/114)), chat layout ([#106](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/106)), and a landing page that shows the real API ([#116](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/116)).**
- **`App.jsx` split ([#102](https://github.com/shivam-tamboli/AI-CodeBase-Assistant/pull/102)).** It was one 1,566-line file.

## What I learned

**Check the fix in production, not just in tests.** My first rate-limit fix passed every test and still never fired on Render. The real request chain (Cloudflare → Render proxy → app) wasn't the one my tests imagined. Hitting the live endpoint and getting `401` six times instead of `401 ×5 → 429` is how I found it.

**Retrieval problems often start at ingestion.** When answers came back vague, I first looked at prompts and ranking. The real cause was the chunker, which was producing a hundred copies of one class, and those copies crowded everything else out of the context window.

**Hybrid search matters.** Vector search handles "how are passwords secured?" and misses "find `verify_token`". Keyword search is the reverse. Fusing the two ranked lists does better than either one alone, as long as the later reranking step doesn't throw that fusion away.

**SSE was enough.** The server only ever pushes tokens to the browser, so I didn't need WebSockets. I read the stream with `fetch` and `ReadableStream`, because `EventSource` can't send a POST body or an auth header.

**Look at both APIs before designing the abstraction.** OpenAI puts the system prompt in the messages, while Anthropic takes it as a separate parameter. I designed the provider interface before noticing that, and had to redo it.

## Limitations and next steps

- **The free Render instance can still go cold.** Uptime Robot stops the 15-minute sleep, but a redeploy or restart still costs about a minute on the first request. A paid instance is the real fix.
- **Retrieval is per repo**, five chunks at a time. Broad "explain the whole architecture" questions get decent answers, not great ones.
- **Private repos** need a personal access token pasted on each import. GitHub OAuth would be nicer.
- **Re-indexing is manual.** A GitHub webhook could do it on every push.
- **Running locally** needs a few separate pieces. A Docker Compose file would make setup one command.

## License

MIT. See [LICENSE](LICENSE).
