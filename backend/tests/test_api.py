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
            "username": "existing", "password": "pass"
        })
        assert r.status_code == 400

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
