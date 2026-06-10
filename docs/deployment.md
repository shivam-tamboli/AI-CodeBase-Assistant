# Deployment Guide

This guide covers every step needed to deploy the AI Codebase Assistant: setting up MongoDB Atlas, deploying the FastAPI backend, and deploying the React frontend.

---

## Overview

| Component | Platform | Notes |
|---|---|---|
| Database | MongoDB Atlas (M0 free) | Hosts the database and runs vector search |
| Backend API | Render | Persistent server — no cold-start limits |
| Frontend | Vercel | Static hosting, automatic from GitHub |

**Why Render and not Vercel for the backend?**  
Vercel's free tier enforces a 10-second function execution limit. LLM calls in this project can take 15–30 seconds. Render provides a persistent server with no execution timeout on the free plan.

---

## Step 1 — MongoDB Atlas

### Create a cluster

1. Go to [cloud.mongodb.com](https://cloud.mongodb.com) and sign up (free).
2. Click **Build a Cluster** → select **M0 Free** → choose any region → click **Create**.
3. Wait ~2 minutes for the cluster to provision.

### Create a database user

1. In the left sidebar, click **Database Access** → **Add New Database User**.
2. Choose **Password** authentication.
3. Set a username and a strong password — remember these; you'll use them in the connection string.
4. Under **Database User Privileges**, choose **Atlas admin** or **Read and write to any database**.
5. Click **Add User**.

### Allow network access

1. In the left sidebar, click **Network Access** → **Add IP Address**.
2. For development: click **Allow Access from Anywhere** (`0.0.0.0/0`).
3. For production: restrict to your backend host's IP if possible.

### Get the connection string

1. Click **Connect** on your cluster → **Drivers**.
2. Copy the connection string. It looks like:
   ```
   mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/
   ```
3. Replace `<username>` and `<password>` with your database user credentials.
4. Append `ragdb` as the database name:
   ```
   mongodb+srv://myuser:mypass@cluster0.xxxxx.mongodb.net/ragdb?retryWrites=true&w=majority
   ```

This value goes into `MONGODB_URI`.

### Create the Vector Search index (one-time)

This step enables `$vectorSearch` HNSW indexing for semantic search. Without it the system works correctly using an in-memory cosine similarity fallback — no errors, just slower at scale.

1. In Atlas, go to your cluster → **Atlas Search** tab → **Create Search Index**.
2. Choose **Atlas Vector Search** (not "Atlas Search").
3. Select database `ragdb`, collection `chunks`.
4. Click **JSON Editor** and paste:

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

5. Set the index name to exactly `vector_search_index`.
6. Click **Create Search Index**. Wait ~2 minutes for status to change to **Active**.

> **Keyword search index**: The application also uses a compound text index (`content_name_text_index`) on the `chunks` collection — `content` weighted 1 and `metadata.name` weighted 5. This index is created automatically at startup; no manual Atlas configuration is required.

---

## Step 2 — Backend Deployment

### Render

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. Click **New** → **Web Service** → **Connect** your repository.
3. Configure:

| Setting | Value |
|---|---|
| Runtime | Python 3 |
| Root Directory | (leave empty) |
| Build Command | `pip install -r backend/requirements.txt` |
| Start Command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |

4. In the **Environment** section, add these variables:

| Key | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `MONGODB_URI` | Your Atlas connection string |
| `JWT_SECRET` | A long random string — generate one: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ALLOWED_ORIGINS` | Your Vercel frontend URL (add after frontend is deployed) |
| `COHERE_API_KEY` | Optional — enables cross-encoder re-ranking |
| `LLM_PROVIDER` | `openai` or `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` (recommended for cost) |

5. Click **Create Web Service**. Render builds and deploys automatically.
6. Your backend URL will be: `https://your-app.onrender.com`

> **Free tier note**: Render free tier spins down after 15 minutes of inactivity. The first request after a spin-down takes ~30 seconds (cold start). For a demo, this is acceptable. Upgrade to a paid tier to eliminate cold starts.

---

## Step 3 — Frontend Deployment

### Configure the API URL

The frontend reads the backend URL from an environment variable:

```js
// frontend/src/App.jsx
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
```

### Deploy to Vercel

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub.
2. Click **New Project** → **Import** your repository.
3. Configure:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Vite (auto-detected) |
| Build Command | `npm run build` (auto-detected) |
| Output Directory | `dist` (auto-detected) |

4. Add environment variable:

| Key | Value |
|---|---|
| `VITE_API_URL` | Your Render backend URL (e.g., `https://your-app.onrender.com`) |

5. Click **Deploy**.
6. Vercel gives you a URL like `https://your-app.vercel.app`.

### Update CORS on the backend

After the frontend is deployed, go back to your Render dashboard and update:

```
ALLOWED_ORIGINS=https://your-app.vercel.app
```

Redeploy the backend. Without this, the browser will block cross-origin requests.

The `frontend/vercel.json` file in the repository is pre-configured with SPA rewrites so that deep-linking works correctly.

---

## Environment Variables Reference

Full reference of all supported environment variables. See [`backend/.env.example`](../backend/.env.example) for an annotated template.

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** (default config) | — | OpenAI API key |
| `MONGODB_URI` | **Yes** | — | MongoDB Atlas connection string |
| `JWT_SECRET` | **Yes** | insecure default | HS256 JWT signing secret — must be changed in production |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000` | Comma-separated CORS origins |
| `LLM_PROVIDER` | No | `openai` | `openai` or `anthropic` |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name — e.g. `gpt-4o`, `claude-sonnet-4-6` |
| `LLM_MAX_TOKENS` | No | `2000` | Maximum tokens in LLM response |
| `EMBEDDING_PROVIDER` | No | `openai` | Embedding provider |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | Embedding model |
| `ANTHROPIC_API_KEY` | No | — | Required when `LLM_PROVIDER=anthropic` |
| `COHERE_API_KEY` | No | — | Enables Cohere cross-encoder re-ranking |
| `GITHUB_TOKEN` | No | — | GitHub personal access token for private repo import |
| `ENABLE_CHUNK_SUMMARIES` | No | `false` | Generate LLM summaries per chunk at index time |

---

## Post-Deployment Checklist

- [ ] `GET /health` returns `{"status": "healthy", "database": "connected"}`
- [ ] Can register a new user and receive a JWT
- [ ] Can upload a small ZIP and poll `/repositories/{id}/status` until `indexed`
- [ ] Can ask a question and receive an answer with source citations
- [ ] Streaming responses appear progressively in the browser
- [ ] Atlas Vector Search index is **Active** (check in Atlas UI)
- [ ] `ALLOWED_ORIGINS` includes the Vercel frontend URL

---

> For deployment-specific errors (startup crashes, CORS, cold starts, connection timeouts), see [TROUBLESHOOTING.md](../TROUBLESHOOTING.md#deployment-errors).
