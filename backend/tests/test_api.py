"""
API integration tests.

These tests hit the FastAPI app through an AsyncClient with all MongoDB calls
mocked out. They verify request/response shapes, auth enforcement, and error
handling without needing a running database or OpenAI API key.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_user_doc(username="testuser", user_id="507f1f77bcf86cd799439011"):
    """Minimal user document as returned by MongoDB."""
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("correctpassword")
    return {
        "_id": ObjectId(user_id),
        "username": username,
        "password": pwd,
    }


def _fake_repo_doc(user_id="507f1f77bcf86cd799439011"):
    return {
        "_id": ObjectId("617f1f77bcf86cd799439022"),
        "name": "my-repo",
        "description": "test repo",
        "user_id": user_id,
        "file_count": 3,
        "chunk_count": 10,
        "created_at": "2024-01-01T00:00:00",
    }


# ---------------------------------------------------------------------------
# Root / Health
# ---------------------------------------------------------------------------

class TestRootEndpoints:
    async def test_root_returns_200(self, test_client):
        r = await test_client.get("/")
        assert r.status_code == 200
        assert "message" in r.json()

    async def test_health_returns_json(self, test_client):
        # health checks Mongo ping — mock client.admin.command
        with patch("backend.database.Database.client") as mock_client:
            mock_client.admin.command = AsyncMock(return_value={"ok": 1})
            r = await test_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "database" in data

    async def test_health_accepts_head(self, test_client):
        # Uptime monitors send HEAD; it must not be a 405.
        with patch("backend.database.Database.client") as mock_client:
            mock_client.admin.command = AsyncMock(return_value={"ok": 1})
            r = await test_client.head("/health")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Auth — Register
# ---------------------------------------------------------------------------

class TestRegister:
    async def test_register_new_user_returns_token(self, test_client, mock_db):
        mock_db.users.find_one.return_value = None  # username not taken
        r = await test_client.post("/auth/register", json={
            "username": "newuser", "password": "secret123"
        })
        assert r.status_code == 201
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_register_duplicate_username_returns_400(self, test_client, mock_db):
        mock_db.users.find_one.return_value = _fake_user_doc("existing")
        r = await test_client.post("/auth/register", json={
            "username": "existing", "password": "password123"
        })
        assert r.status_code == 400
        assert r.json()["detail"] == "Username already taken"

    async def test_register_race_duplicate_key_returns_400(self, test_client, mock_db):
        # Both requests passed find_one; the unique index rejects the second insert.
        from pymongo.errors import DuplicateKeyError
        mock_db.users.find_one.return_value = None
        mock_db.users.insert_one.side_effect = DuplicateKeyError("E11000 duplicate key")
        r = await test_client.post("/auth/register", json={
            "username": "racer", "password": "password123"
        })
        assert r.status_code == 400
        assert r.json()["detail"] == "Username already taken"

    @pytest.mark.parametrize("username,password", [
        ("", "password123"),
        ("   ", "password123"),
        ("ab", "password123"),
        ("a" * 33, "password123"),
        ("validname", ""),
        ("validname", "short7!"),
        ("validname", "        "),
        ("validname", "a" * 73),
        ("validname", "é" * 37),   # 37 chars but 74 bytes
    ])
    async def test_register_rejects_bad_credentials(self, test_client, mock_db, username, password):
        r = await test_client.post("/auth/register", json={"username": username, "password": password})
        assert r.status_code == 422
        mock_db.users.insert_one.assert_not_called()

    async def test_register_accepts_boundaries_and_trims_username(self, test_client, mock_db):
        mock_db.users.find_one.return_value = None
        r = await test_client.post("/auth/register", json={
            "username": "  abc  ", "password": "a" * 72,
        })
        assert r.status_code == 201
        assert mock_db.users.insert_one.call_args[0][0]["username"] == "abc"

    async def test_register_missing_fields_returns_422(self, test_client):
        r = await test_client.post("/auth/register", json={"username": "only"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Auth — Login
# ---------------------------------------------------------------------------

class TestLogin:
    async def test_login_correct_credentials_returns_token(self, test_client, mock_db):
        mock_db.users.find_one.return_value = _fake_user_doc()
        r = await test_client.post("/auth/login", json={
            "username": "testuser", "password": "correctpassword"
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_login_wrong_password_returns_401(self, test_client, mock_db):
        mock_db.users.find_one.return_value = _fake_user_doc()
        r = await test_client.post("/auth/login", json={
            "username": "testuser", "password": "wrongpassword"
        })
        assert r.status_code == 401

    async def test_login_unknown_user_returns_401(self, test_client, mock_db):
        mock_db.users.find_one.return_value = None
        r = await test_client.post("/auth/login", json={
            "username": "ghost", "password": "any"
        })
        assert r.status_code == 401

    async def test_login_blank_fields_rejected(self, test_client):
        r = await test_client.post("/auth/login", json={"username": " ", "password": ""})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Rate limiting on auth
# ---------------------------------------------------------------------------

class TestAuthRateLimit:
    # Mirrors production: the peer is Render's internal proxy (loopback here),
    # X-Forwarded-For ends with a Cloudflare edge IP that changes per request,
    # and CF-Connecting-IP carries the real visitor address.
    async def _login(self, client, visitor, edge="104.16.0.1"):
        headers = {"CF-Connecting-IP": visitor, "X-Forwarded-For": f"{visitor}, {edge}"}
        return await client.post("/auth/login", headers=headers,
                                 json={"username": "ghost", "password": "whatever"})

    async def test_sixth_login_in_a_minute_is_429(self, test_client, mock_db):
        mock_db.users.find_one.return_value = None
        codes = [(await self._login(test_client, "203.0.113.7", edge=f"104.16.0.{i}")).status_code
                 for i in range(6)]
        assert codes == [401] * 5 + [429]

    async def test_spoofed_forwarded_for_does_not_reset_limit(self, test_client, mock_db):
        mock_db.users.find_one.return_value = None
        for i in range(6):
            r = await test_client.post("/auth/login", json={"username": "ghost", "password": "whatever"},
                                       headers={"CF-Connecting-IP": "203.0.113.7",
                                                "X-Forwarded-For": f"10.0.0.{i}, 172.16.0.{i}"})
        assert r.status_code == 429

    async def test_different_clients_have_separate_buckets(self, test_client, mock_db):
        mock_db.users.find_one.return_value = None
        for _ in range(5):
            await self._login(test_client, "203.0.113.7")
        assert (await self._login(test_client, "198.51.100.9")).status_code == 401

    async def test_register_is_rate_limited_too(self, test_client, mock_db):
        mock_db.users.find_one.return_value = _fake_user_doc("taken")
        codes = [
            (await test_client.post("/auth/register", headers={"CF-Connecting-IP": "203.0.113.8"},
                                    json={"username": "taken", "password": "password123"})).status_code
            for _ in range(6)
        ]
        assert codes == [400] * 5 + [429]


class TestClientIpKey:
    @staticmethod
    def _request(peer, headers=None):
        from starlette.requests import Request
        return Request({
            "type": "http",
            "client": (peer, 1234),
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        })

    def test_trusts_cf_header_from_internal_proxy(self):
        from backend.middleware.rate_limiter import client_ip
        assert client_ip(self._request("10.1.2.3", {"CF-Connecting-IP": "203.0.113.7"})) == "203.0.113.7"

    def test_ignores_cf_header_from_public_peer(self):
        # Someone talking to the app directly can't pick their own bucket.
        from backend.middleware.rate_limiter import client_ip
        assert client_ip(self._request("8.8.8.8", {"CF-Connecting-IP": "1.1.1.1"})) == "8.8.8.8"

    def test_ignores_forwarded_for(self):
        from backend.middleware.rate_limiter import client_ip
        assert client_ip(self._request("10.1.2.3", {"X-Forwarded-For": "1.1.1.1, 2.2.2.2"})) == "10.1.2.3"


# ---------------------------------------------------------------------------
# Repositories — List
# ---------------------------------------------------------------------------

class TestRepositoriesList:
    async def test_list_repos_requires_auth(self, test_client):
        r = await test_client.get("/repositories")
        assert r.status_code in (401, 403)  # FastAPI HTTPBearer returns 403 for missing, 401 for invalid

    async def test_list_repos_returns_empty_list(self, test_client, mock_db, auth_headers):
        mock_db.repositories.find.return_value = MagicMock(
            to_list=AsyncMock(return_value=[])
        )
        r = await test_client.get("/repositories", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_repos_returns_user_repos(self, test_client, mock_db, auth_headers):
        repo = _fake_repo_doc()
        mock_db.repositories.find.return_value = MagicMock(
            to_list=AsyncMock(return_value=[repo])
        )
        r = await test_client.get("/repositories", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "my-repo"


# ---------------------------------------------------------------------------
# Repositories — Get single
# ---------------------------------------------------------------------------

class TestRepositoryGet:
    async def test_get_nonexistent_repo_returns_404(self, test_client, mock_db, auth_headers):
        mock_db.repositories.find_one.return_value = None
        fake_id = "617f1f77bcf86cd799439022"
        r = await test_client.get(f"/repositories/{fake_id}", headers=auth_headers)
        assert r.status_code == 404

    async def test_get_other_users_repo_returns_403(self, test_client, mock_db, auth_headers):
        # Repo belongs to a different user
        repo = _fake_repo_doc(user_id="000000000000000000000001")
        mock_db.repositories.find_one.return_value = repo
        r = await test_client.get(f"/repositories/617f1f77bcf86cd799439022",
                                  headers=auth_headers)
        assert r.status_code == 403

    async def test_get_own_repo_returns_200(self, test_client, mock_db, auth_headers):
        # user_id must match token sub = "507f1f77bcf86cd799439011"
        repo = _fake_repo_doc(user_id="507f1f77bcf86cd799439011")
        mock_db.repositories.find_one.return_value = repo
        r = await test_client.get("/repositories/617f1f77bcf86cd799439022",
                                  headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == "my-repo"


# ---------------------------------------------------------------------------
# Chat Sessions
# ---------------------------------------------------------------------------

class TestChatSessions:
    async def test_create_session_requires_auth(self, test_client):
        r = await test_client.post("/chat/sessions",
                                   json={"repository_id": "617f1f77bcf86cd799439022"})
        assert r.status_code in (401, 403)

    async def test_create_session_returns_session_id(self, test_client, mock_db, auth_headers):
        from datetime import datetime
        mock_db.chat_sessions.insert_one.return_value = MagicMock(
            inserted_id=ObjectId("617f1f77bcf86cd799439099")
        )
        mock_db.chat_sessions.find_one.return_value = {
            "_id": ObjectId("617f1f77bcf86cd799439099"),
            "repository_id": "617f1f77bcf86cd799439022",
            "user_id": "507f1f77bcf86cd799439011",
            "messages": [],
            "created_at": datetime.now(),
        }
        mock_db.repositories.find_one.return_value = _fake_repo_doc()  # caller owns it
        r = await test_client.post("/chat/sessions",
                                   json={"repository_id": "617f1f77bcf86cd799439022"},
                                   headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert "session_id" in body
        assert "repository_id" in body

    async def test_list_sessions_requires_auth(self, test_client):
        r = await test_client.get("/chat/sessions")
        assert r.status_code in (401, 403)

    async def test_list_sessions_returns_list(self, test_client, mock_db, auth_headers):
        mock_db.chat_sessions.find.return_value = MagicMock(
            sort=MagicMock(return_value=MagicMock(
                to_list=AsyncMock(return_value=[])
            ))
        )
        r = await test_client.get("/chat/sessions", headers=auth_headers)
        assert r.status_code == 200
        assert "sessions" in r.json()


# ---------------------------------------------------------------------------
# Auth — token validation edge cases
# ---------------------------------------------------------------------------

class TestAuthEdgeCases:
    async def test_invalid_token_format_rejected(self, test_client):
        r = await test_client.get("/repositories",
                                  headers={"Authorization": "Bearer not.a.valid.token"})
        assert r.status_code == 401

    async def test_no_auth_header_rejected(self, test_client):
        r = await test_client.get("/repositories")
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GitHub import — credentials
# ---------------------------------------------------------------------------

SERVER_TOKEN = "ghp_SERVERTOKENshouldNEVERbeUSED0000000000"
USER_TOKEN = "ghp_userSuppliedToken1234567890abcdefgh"


def _fake_clone(returncode=0, stderr=b""):
    """Stand-in for asyncio.create_subprocess_exec that records the call."""
    calls = []

    async def fake_exec(*args, **kwargs):
        calls.append({"args": args, "env": kwargs.get("env") or {}})
        proc = MagicMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(b"", stderr))
        return proc

    return fake_exec, calls


class TestGitHubImportCredentials:
    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch):
        from backend.main import app
        monkeypatch.setenv("GITHUB_TOKEN", SERVER_TOKEN)
        # ASGITransport skips lifespan, so the shared processor isn't created.
        monkeypatch.setattr(app.state, "processor", MagicMock(), raising=False)
        with patch("backend.api.repositories._run_ingestion", new_callable=AsyncMock):
            yield

    async def test_server_token_never_reaches_git(self, test_client, auth_headers):
        fake_exec, calls = _fake_clone()
        with patch("backend.api.repositories.asyncio.create_subprocess_exec", fake_exec):
            r = await test_client.post("/repositories/import", headers=auth_headers,
                                       json={"url": "https://github.com/octocat/Hello-World"})
        assert r.status_code == 202
        (call,) = calls
        assert not any(SERVER_TOKEN in str(a) for a in call["args"])
        env_without_inherited = {k: v for k, v in call["env"].items() if k.startswith("GIT_")}
        assert SERVER_TOKEN not in str(env_without_inherited)
        assert "https://github.com/octocat/Hello-World" in call["args"]
        # credential helpers are reset, so the host can't authenticate the clone either
        assert call["env"]["GIT_CONFIG_KEY_0"] == "credential.helper"
        assert call["env"]["GIT_CONFIG_VALUE_0"] == ""
        assert call["env"]["GIT_TERMINAL_PROMPT"] == "0"

    async def test_user_token_sent_as_header_not_in_argv(self, test_client, mock_db, auth_headers):
        fake_exec, calls = _fake_clone()
        with patch("backend.api.repositories.asyncio.create_subprocess_exec", fake_exec):
            r = await test_client.post("/repositories/import", headers=auth_headers, json={
                "url": "https://github.com/me/private-repo", "github_token": USER_TOKEN,
            })
        assert r.status_code == 202
        (call,) = calls
        assert not any(USER_TOKEN in str(a) for a in call["args"])
        assert call["env"]["GIT_CONFIG_KEY_1"] == "http.https://github.com/.extraheader"
        assert call["env"]["GIT_CONFIG_VALUE_1"].startswith("Authorization: Basic ")
        assert USER_TOKEN not in r.text
        stored = mock_db.repositories.insert_one.call_args[0][0]
        assert USER_TOKEN not in str(stored)

    async def test_private_repo_without_token_explains_why(self, test_client, auth_headers):
        fake_exec, _ = _fake_clone(
            returncode=128,
            stderr=b"fatal: could not read Username for 'https://github.com': terminal prompts disabled",
        )
        with patch("backend.api.repositories.asyncio.create_subprocess_exec", fake_exec):
            r = await test_client.post("/repositories/import", headers=auth_headers,
                                       json={"url": "https://github.com/me/private-repo"})
        assert r.status_code == 422
        assert "provide your own GitHub access token" in r.json()["detail"]

    async def test_malformed_token_rejected_without_echoing_it(self, test_client, auth_headers):
        bad = "ghp_abcdefghijklmnopqrstuvwxyz\r\nX-Injected: 1"
        r = await test_client.post("/repositories/import", headers=auth_headers, json={
            "url": "https://github.com/me/private-repo", "github_token": bad,
        })
        assert r.status_code == 422
        assert "X-Injected" not in r.text


# ---------------------------------------------------------------------------
# ZIP upload hardening
# ---------------------------------------------------------------------------

def _zip_bytes(files: dict) -> bytes:
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


class TestUploadHardening:
    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch, tmp_path):
        import tempfile
        from backend.main import app
        monkeypatch.setattr(app.state, "processor", MagicMock(), raising=False)
        # Every mkdtemp lands under tmp_path so we can see exactly what got written.
        self.root = tmp_path
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        with patch("backend.api.repositories._run_ingestion", new_callable=AsyncMock):
            yield

    async def _upload(self, client, headers, filename, content):
        return await client.post("/repositories/upload", headers=headers,
                                 files={"file": (filename, content, "application/zip")})

    async def test_traversal_filename_stays_inside_temp_dir(self, test_client, auth_headers):
        r = await self._upload(test_client, auth_headers, "../../escaped.zip",
                               _zip_bytes({"app.py": "print(1)"}))
        assert r.status_code == 202
        assert r.json()["name"] == "escaped"
        assert not (self.root.parent / "escaped.zip").exists()
        assert not (self.root.parent.parent / "escaped.zip").exists()
        assert list(self.root.glob("*/escaped.zip"))  # saved under its own temp dir

    async def test_oversized_upload_is_413(self, test_client, auth_headers, monkeypatch):
        monkeypatch.setattr("backend.api.repositories.MAX_UPLOAD_BYTES", 1024)
        r = await self._upload(test_client, auth_headers, "big.zip", b"x" * 4096)
        assert r.status_code == 413

    async def test_zip_bomb_is_413(self, test_client, auth_headers, monkeypatch):
        monkeypatch.setattr("backend.api.repositories.MAX_EXTRACTED_BYTES", 10_000)
        r = await self._upload(test_client, auth_headers, "bomb.zip",
                               _zip_bytes({"zeros.txt": "0" * 1_000_000}))
        assert r.status_code == 413
        assert not list(self.root.glob("*/zeros.txt"))  # never extracted

    async def test_not_a_zip_is_400(self, test_client, auth_headers):
        r = await self._upload(test_client, auth_headers, "fake.zip", b"definitely not a zip")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Timestamps — always timezone-aware UTC
# ---------------------------------------------------------------------------

def _is_aware_utc(dt):
    from datetime import timedelta
    return dt.tzinfo is not None and dt.utcoffset() == timedelta(0)


class TestUtcTimestamps:
    async def test_register_stores_aware_utc(self, test_client, mock_db):
        mock_db.users.find_one.return_value = None
        r = await test_client.post("/auth/register", json={"username": "tzuser", "password": "password123"})
        assert r.status_code == 201
        assert _is_aware_utc(mock_db.users.insert_one.call_args[0][0]["created_at"])
        assert _is_aware_utc(mock_db.refresh_tokens.insert_one.call_args[0][0]["expires_at"])

    async def test_login_refresh_token_expiry_is_aware_utc(self, test_client, mock_db):
        mock_db.users.find_one.return_value = _fake_user_doc()
        r = await test_client.post("/auth/login", json={"username": "testuser", "password": "correctpassword"})
        assert r.status_code == 200
        assert _is_aware_utc(mock_db.refresh_tokens.insert_one.call_args[0][0]["expires_at"])

    async def test_chat_session_timestamps_are_aware_utc(self, mock_db):
        from backend.services.chat_service import ChatService
        with patch("backend.database.Database.get_db", return_value=mock_db):
            await ChatService.create_session("617f1f77bcf86cd799439022", "507f1f77bcf86cd799439011")
            session_doc = mock_db.chat_sessions.insert_one.call_args[0][0]
            assert _is_aware_utc(session_doc["created_at"]) and _is_aware_utc(session_doc["updated_at"])

    def test_no_naive_now_or_utcnow_in_backend_source(self):
        # Guard against regressions: naive datetimes are local time on any
        # non-UTC machine and serialize without an offset.
        import pathlib, re
        root = pathlib.Path(__file__).resolve().parents[1]
        pattern = re.compile(r"datetime\.(utcnow\(|now\(\))")
        offenders = [
            f"{p.relative_to(root)}:{i}"
            for p in root.rglob("*.py")
            if "venv" not in p.parts and "tests" not in p.parts
            for i, line in enumerate(p.read_text().splitlines(), 1)
            if pattern.search(line)
        ]
        assert offenders == []

    async def test_mongo_client_is_tz_aware(self):
        from datetime import timezone
        from backend.database import Database
        with patch("backend.database.AsyncIOMotorClient") as client_cls:
            client_cls.return_value.admin.command = AsyncMock(return_value={"ok": 1})
            await Database.connect("mongodb://localhost:27017/ragdb?ssl=false")
        kwargs = client_cls.call_args.kwargs
        assert kwargs["tz_aware"] is True and kwargs["tzinfo"] == timezone.utc


class TestCurrentUserPayload:
    async def test_only_user_id_is_exposed(self):
        from fastapi.security import HTTPAuthorizationCredentials
        from backend.auth.dependencies import get_current_user, get_optional_user
        from backend.auth.jwt import create_access_token
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=create_access_token({"sub": "abc123", "username": "u"}))
        assert await get_current_user(creds) == {"user_id": "abc123"}
        assert await get_optional_user(creds) == {"user_id": "abc123"}


# ---------------------------------------------------------------------------
# Repository access from chat + the shared demo repo
# ---------------------------------------------------------------------------

def _demo_repo_doc(status_="indexed"):
    return {"_id": ObjectId("6170000000000000000000de"), "name": "itsdangerous", "description": "Demo",
            "user_id": None, "is_demo": True, "status": status_,
            "source_url": "https://github.com/pallets/itsdangerous"}


class TestChatRepoAccess:
    @pytest.fixture(autouse=True)
    def _session_insert(self, mock_db):
        mock_db.chat_sessions.insert_one.return_value = MagicMock(inserted_id=ObjectId("617f1f77bcf86cd799439099"))

    async def test_cannot_open_session_on_someone_elses_repo(self, test_client, mock_db, auth_headers):
        mock_db.repositories.find_one.return_value = _fake_repo_doc(user_id="999999999999999999999999")
        r = await test_client.post("/chat/sessions", json={"repository_id": "617f1f77bcf86cd799439022"}, headers=auth_headers)
        assert r.status_code == 403
        mock_db.chat_sessions.insert_one.assert_not_called()

    async def test_cannot_query_someone_elses_repo(self, test_client, mock_db, auth_headers):
        mock_db.repositories.find_one.return_value = _fake_repo_doc(user_id="999999999999999999999999")
        for path in ("/chat/query", "/chat/query/stream"):
            r = await test_client.post(path, headers=auth_headers,
                                       json={"question": "dump the code", "repository_id": "617f1f77bcf86cd799439022"})
            assert r.status_code == 403, path

    async def test_unknown_repo_is_404(self, test_client, mock_db, auth_headers):
        mock_db.repositories.find_one.return_value = None
        r = await test_client.post("/chat/sessions", json={"repository_id": "617f1f77bcf86cd799439022"}, headers=auth_headers)
        assert r.status_code == 404

    async def test_anyone_can_open_a_session_on_the_demo(self, test_client, mock_db, auth_headers):
        mock_db.repositories.find_one.return_value = _demo_repo_doc()
        r = await test_client.post("/chat/sessions", json={"repository_id": "6170000000000000000000de"}, headers=auth_headers)
        assert r.status_code == 201


class TestDemoRepo:
    async def test_demo_endpoint_returns_demo_with_suggestions(self, test_client, mock_db, auth_headers):
        mock_db.repositories.find_one.return_value = _demo_repo_doc()
        r = await test_client.get("/repositories/demo", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["is_demo"] is True and body["status"] == "indexed" and body["id"] == "6170000000000000000000de"
        assert len(body["suggested_questions"]) >= 3
        assert mock_db.repositories.find_one.call_args[0][0] == {"is_demo": True}

    async def test_demo_endpoint_404_when_not_seeded(self, test_client, mock_db, auth_headers):
        mock_db.repositories.find_one.return_value = None
        r = await test_client.get("/repositories/demo", headers=auth_headers)
        assert r.status_code == 404

    async def test_demo_endpoint_requires_auth(self, test_client):
        assert (await test_client.get("/repositories/demo")).status_code == 401

    async def test_demo_is_read_only(self, test_client, mock_db, auth_headers):
        from backend.main import app
        app.state.processor = MagicMock(delete_repository_data=AsyncMock())
        mock_db.repositories.find_one.return_value = _demo_repo_doc()
        rid = "6170000000000000000000de"
        assert (await test_client.put(f"/repositories/{rid}", json={"name": "pwned"}, headers=auth_headers)).status_code == 403
        assert (await test_client.delete(f"/repositories/{rid}", headers=auth_headers)).status_code == 403
        r = await test_client.post(f"/repositories/{rid}/reindex", headers=auth_headers,
                                   files={"file": ("x.zip", b"PK", "application/zip")})
        assert r.status_code == 403
        mock_db.repositories.update_one.assert_not_called()
        mock_db.repositories.delete_one.assert_not_called()
        app.state.processor.delete_repository_data.assert_not_called()

    async def test_demo_readable_through_repo_routes(self, test_client, mock_db, auth_headers):
        mock_db.repositories.find_one.return_value = _demo_repo_doc()
        r = await test_client.get("/repositories/6170000000000000000000de/status", headers=auth_headers)
        assert r.status_code == 200


class TestEnsureDemoRepo:
    async def test_noop_when_already_indexed(self, mock_db):
        from backend.api import repositories as repos
        mock_db.repositories.find_one.return_value = _demo_repo_doc("indexed")
        with patch("backend.database.Database.get_db", return_value=mock_db), \
             patch.object(repos, "_git_clone", new_callable=AsyncMock) as clone:
            await repos.ensure_demo_repo(MagicMock())
        clone.assert_not_called()
        mock_db.repositories.insert_one.assert_not_called()

    async def test_creates_and_indexes_when_missing(self, mock_db):
        from backend.api import repositories as repos
        mock_db.repositories.find_one.return_value = None
        mock_db.repositories.insert_one.return_value = MagicMock(inserted_id=ObjectId("6170000000000000000000de"))
        with patch("backend.database.Database.get_db", return_value=mock_db), \
             patch.object(repos, "_git_clone", new_callable=AsyncMock, return_value=(0, "")) as clone, \
             patch.object(repos, "_run_ingestion", new_callable=AsyncMock) as ingest:
            await repos.ensure_demo_repo(MagicMock())
        doc = mock_db.repositories.insert_one.call_args[0][0]
        assert doc["is_demo"] is True and doc["user_id"] is None and doc["source_url"] == repos.DEMO_REPO_URL
        clone.assert_awaited_once()
        assert ingest.await_args[0][0] == "6170000000000000000000de"

    async def test_rebuilds_a_stale_half_indexed_demo(self, mock_db):
        from backend.api import repositories as repos
        mock_db.repositories.find_one.return_value = _demo_repo_doc("indexing")  # previous process died mid-run
        processor = MagicMock(delete_repository_data=AsyncMock())
        with patch("backend.database.Database.get_db", return_value=mock_db), \
             patch.object(repos, "_git_clone", new_callable=AsyncMock, return_value=(0, "")), \
             patch.object(repos, "_run_ingestion", new_callable=AsyncMock) as ingest:
            await repos.ensure_demo_repo(processor)
        processor.delete_repository_data.assert_awaited_once_with("6170000000000000000000de")
        mock_db.repositories.insert_one.assert_not_called()
        ingest.assert_awaited_once()

    async def test_disabled_when_url_empty(self, mock_db, monkeypatch):
        from backend.api import repositories as repos
        monkeypatch.setattr(repos, "DEMO_REPO_URL", "")
        with patch("backend.database.Database.get_db", return_value=mock_db):
            await repos.ensure_demo_repo(MagicMock())
        mock_db.repositories.find_one.assert_not_called()
