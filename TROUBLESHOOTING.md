# Troubleshooting

Complete reference for diagnosing and fixing common failures in the AI Codebase Assistant.

> For setup and startup instructions, see [README.md](README.md#quick-start).  
> For deployment, see [docs/deployment.md](docs/deployment.md).

---

## Required API Keys

| Key | Required | Where to get it |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** | https://platform.openai.com/api-keys |
| `MONGODB_URI` | **Yes** | MongoDB Atlas → Connect → Drivers |
| `JWT_SECRET` | **Yes** | Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ANTHROPIC_API_KEY` | Only if `LLM_PROVIDER=anthropic` | https://console.anthropic.com |
| `COHERE_API_KEY` | No (enables better re-ranking) | https://cohere.com (free tier: 1000 req/month) |
| `GITHUB_TOKEN` | No (enables private repo import) | https://github.com/settings/tokens → scope: `repo` (read-only) |

---

## Common Errors and Root Causes

### CORS blocked — "No 'Access-Control-Allow-Origin' header"

**Symptom**: Browser console shows CORS policy error on `/auth/login`, `/auth/register`, etc.

**Root causes**:
1. Frontend is on a port not in `ALLOWED_ORIGINS` (most common: 5174 or 5175 instead of 5173)
2. Backend restarted but didn't pick up updated `.env`
3. Two Vite instances running — the second one increments port

**Fix**:
```bash
# Kill all processes on dev ports
lsof -ti :5173 :5174 :5175 | xargs kill -9 2>/dev/null
# Kill backend if needed
lsof -ti :8000 | xargs kill -9 2>/dev/null
# Restart backend (picks up updated .env)
source venv/bin/activate && uvicorn backend.main:app --reload
# Restart frontend (always lands on 5173 now)
cd frontend && npm run dev
```

**Prevention**: `vite.config.js` has `strictPort: true` — if 5173 is taken, `npm run dev` fails immediately with a clear error instead of silently using 5174.

---

### `NameError: name 'asyncio' is not defined`

**Symptom**: Every chat question returns `{"type":"error","error":"name 'asyncio' is not defined"}` in the SSE stream.

**Root cause**: `backend/services/hybrid_search.py` uses `asyncio.gather()` but was missing `import asyncio`.

**Status**: Fixed in commit `f684cca`. If you see this after pulling, your local file is outdated — pull main.

---

### `ModuleNotFoundError: No module named 'rank_bm25'`

**Symptom**: SSE stream returns `{"type":"error","error":"No module named 'rank_bm25'"}`.

**Root cause**: `rank-bm25` is listed in `requirements.txt` but wasn't installed because the venv's `pip` shebang pointed to the old project path after the project directory was renamed/moved.

**Fix**:
```bash
# Find the Python your backend is actually running under
ps aux | grep uvicorn | grep -v grep | awk '{print $11}'

# Install into that Python directly (replace path if different)
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pip install rank-bm25

# Or safer — reinstall everything using python3 -m pip
source venv/bin/activate
python3 -m pip install -r backend/requirements.txt
```

**Prevention**: Always use `python3 -m pip install` instead of bare `pip install` to avoid shebang path issues.

---

### `[Errno 48] Address already in use` on port 8000

**Symptom**: `uvicorn backend.main:app --reload` fails immediately.

**Root cause**: A previous uvicorn process is still running (closed terminal tab, Ctrl+Z instead of Ctrl+C, etc.)

**Fix**:
```bash
lsof -ti :8000 | xargs kill -9 2>/dev/null && uvicorn backend.main:app --reload
```

**Prevention**: Always stop uvicorn with **Ctrl+C** (not Ctrl+Z, not closing the tab). Ctrl+Z sends SIGTSTP (suspend) — the process stays alive holding the port.

---

### `MONGODB_URI` not set / connection timeout

**Symptom**: Backend crashes on startup with `ValueError: MONGODB_URI not set in .env` or fails to connect.

**Common mistakes**:
- Forgot to rename `.env.example` to `.env`
- Missing database name in URI (must end with `/ragdb?retryWrites=true&w=majority`)
- Password contains special characters (URL-encode them)
- MongoDB Atlas network access doesn't allow the IP

**Check Atlas**:
1. Atlas → Network Access → add `0.0.0.0/0` for development
2. Atlas → Database Access → verify user has read/write permissions

**Verify URI format**:
```
mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/ragdb?retryWrites=true&w=majority
```
The `/ragdb` before `?` is the database name — without it, documents go to the `test` database.

---

### Repository upload succeeds but repo never appears / stays `pending`

**Symptom**: Upload returns 202, polling shows `pending` forever, or repo never appears in the dropdown.

**Root cause A**: Background indexing crashed silently. Check backend logs:
```bash
# While uvicorn is running, upload a ZIP and watch logs
tail -f /tmp/backend.log
```

**Root cause B**: The frontend wasn't calling `fetchRepositories` after upload (fixed in PR #77 — pull latest main).

**Root cause C**: Atlas vector index not created. Without it, the system falls back to in-memory cosine similarity — still works, just slower.

---

### Chat returns error / no answer

**Symptom**: Sending a question shows an error or empty response.

**Steps to diagnose**:
```bash
# 1. Test the SSE endpoint directly
curl -X POST http://localhost:8000/chat/query/stream \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{"question":"test","repository_id":"<repo_id>","limit":3}' \
  --max-time 30

# 2. Check the event type in the response
# - {"type":"token",...} = working normally (streaming)
# - {"type":"done",...}  = finished (check "sources" array)
# - {"type":"error",...} = backend error (read "error" field)
```

**Common causes**:
- `OpenAI API key invalid` → check `OPENAI_API_KEY` in `.env`
- `asyncio not defined` → pull latest main (fixed in PR #78)
- `No module named rank_bm25` → reinstall requirements (see above)
- Repository not yet indexed → wait for status to be `indexed`

---

### Frontend shows blank page or won't load

**Symptom**: `http://localhost:5173` shows nothing.

**Fix**:
```bash
cd frontend
rm -rf node_modules
npm install
npm run dev
```

---

## Verifying the Full Stack is Healthy

Run this sequence to confirm everything works before starting development:

```bash
# 1. Health check
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"connected"}

# 2. Register (or login if already registered)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test1234"}'
# Expected: {"access_token":"eyJ...","token_type":"bearer"}

# 3. List repos (should be [] on first run)
curl http://localhost:8000/repositories \
  -H "Authorization: Bearer <token>"

# 4. CORS preflight from Vite origin
curl -X OPTIONS http://localhost:8000/auth/login \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -D - 2>/dev/null | grep -E "HTTP|Access-Control"
# Expected: HTTP/1.1 200 OK
```

---

## Issues Found and Fixed (Debugging Session — 2026-05-22)

| # | Issue | Root cause | Fix | PR |
|---|---|---|---|---|
| 1 | CORS blocked on port 5174/5175 | Vite silently increments port when 5173 busy | Pin Vite to 5173 with `strictPort`; extend `ALLOWED_ORIGINS` | #78 |
| 2 | SSE streaming always errored | `import asyncio` missing in `hybrid_search.py` | Add import | #78 |
| 3 | `rank_bm25` not installed | Broken venv pip shebang (project renamed) | Install via `python3 -m pip`; document in setup guide | #78 |
| 4 | `.env.example` missing 10+ variables | Template never updated after features were added | Full rewrite with all variables and doc links | #78 |
| 5 | Repo invisible during indexing | `fetchRepositories` not called after 202 upload | Call immediately after 202, auto-select repo | #77 |
| 6 | Same ZIP can't be re-uploaded | Native `<input>` value not cleared after upload | Add `inputRef.current.value = ''` | #77 |
| 7 | Hint chips did nothing | `<span>` elements with no onClick | Add `onClick={() => setQuestion(hint)}` | #77 |
| 8 | Chat works on pending repo | No readiness guard on chat input | Disable textarea+send when `repoStatus !== 'indexed'` | #77 |
