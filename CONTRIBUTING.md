# Contributing

Thank you for your interest in contributing. This guide covers how to set up a development environment, run tests, and open pull requests.

---

## Development Setup

Follow the [Quick Start in README.md](README.md#quick-start) to clone, install dependencies, configure `backend/.env`, and start both servers.

Once both are running, Swagger UI is available at `http://localhost:8000/docs` — useful for manual API testing without the frontend.

For common startup errors and their fixes, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Running Tests

```bash
# From project root (venv active)
python -m pytest backend/tests/ -q
```

The test suite is fully mock-isolated — MongoDB and OpenAI are replaced by in-memory fakes. No real API keys or database connection are required.

```bash
# Run with verbose output to see individual test names
python -m pytest backend/tests/ -v

# Run a specific file
python -m pytest backend/tests/test_unit.py -v

# Run a specific test
python -m pytest backend/tests/test_api.py::TestRepositories::test_list_repositories -v
```

All tests must pass before a pull request is considered for merge.

---

## Project Layout

The key directories you will work in:

```
backend/api/          — HTTP route handlers (input validation + response formatting only)
backend/services/     — All business logic (chunking, search, LLM, embeddings)
backend/models/       — Pydantic request/response models
backend/tests/        — pytest test suite
frontend/src/         — React SPA (single file: App.jsx)
```

The rule: **no business logic in API handlers**. Route handlers validate input, call services, and return responses. Everything that does real work lives in `backend/services/`.

(`repositories.py`'s upload/import routes are the one exception — they handle zip extraction and git cloning directly. Don't use them as a pattern for new routes.)

---

## Branch Naming

| Type | Pattern | Example |
|---|---|---|
| Feature | `feature/<short-description>` | `feature/chunk-summaries` |
| Bug fix | `fix/<short-description>` | `fix/citation-validation` |
| Refactor | `refactor/<short-description>` | `refactor/provider-factory` |
| Infrastructure | `infra/<short-description>` | `infra/docker-compose` |
| Documentation | `docs/<short-description>` | `docs/search-pipeline` |

---

## Pull Request Workflow

1. **Open an issue first** — describe the problem or feature before writing code. This avoids duplicate work and lets maintainers give early feedback.

2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Write tests** for any new behaviour. The test suite lives in `backend/tests/`. Use the existing fixtures in `conftest.py` (`test_client`, `auth_headers`, `mock_db`).

4. **Run the full test suite** and confirm all tests pass:
   ```bash
   python -m pytest backend/tests/ -q
   ```

5. **Commit** with a clear message describing *what* and *why*:
   ```
   feat: add BM25 fallback reranking when Cohere is not configured
   
   Replaces the ad-hoc term-count heuristic with BM25Okapi from rank-bm25.
   Symbol name tokens are weighted 3x to surface exact-match results higher.
   ```

6. **Open a PR** against `main`. Link the related issue in the PR description (`Closes #N`).

---

## Code Style

- Follow existing patterns in the file you are editing
- Type hints on all public functions and method signatures
- No comments explaining *what* code does — only *why* when the reason is non-obvious
- Keep route handlers thin: validate → call service → return response
- Use `async`/`await` for all database and HTTP calls
- Prefer `asyncio.gather()` over sequential `await` when operations are independent

---

## Adding a New LLM Provider

See [docs/provider-architecture.md](docs/provider-architecture.md) for a step-by-step guide.

---

## Reporting Bugs

Open an issue with:
- Python version (`python --version`)
- What you did
- What you expected to happen
- What actually happened (include the full error message and traceback)
- Relevant environment variables (redact API keys)
