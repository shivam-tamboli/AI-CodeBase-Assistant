"""
Test configuration and shared fixtures.

All API tests use an AsyncClient with the FastAPI app. MongoDB and the OpenAI
API are mocked out so no real services are required.

Why OPENAI_API_KEY is set at the top of this file:
  backend/api/chat.py instantiates RAGPipeline() at module scope (line 226).
  That triggers EmbeddingService.__init__() which raises ValueError when
  OPENAI_API_KEY is missing — before any per-test mock can intercept it.
  Setting a dummy value here prevents the import-time crash.
"""

import os

# Must be set before any backend module is imported
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used-in-tests")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/ragdb_test")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# In-memory mock DB
# ---------------------------------------------------------------------------

def make_mock_collection():
    """Mock MongoDB collection with async methods."""
    col = MagicMock()
    col.find_one = AsyncMock(return_value=None)
    col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="507f1f77bcf86cd799439011"))
    col.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[])
    ))
    col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    col.create_index = AsyncMock(return_value="index_name")
    col.list_indexes = AsyncMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[])
    ))
    col.count_documents = AsyncMock(return_value=0)
    return col


@pytest.fixture
def mock_db():
    """Mock DB whose collections are pre-wired with async mocks.

    Supports both attribute access (db.users) and item access (db["chat_sessions"])
    because different services use different access patterns.
    """
    db = MagicMock()
    collections = {
        "users": make_mock_collection(),
        "repositories": make_mock_collection(),
        "chunks": make_mock_collection(),
        "chat_sessions": make_mock_collection(),
    }
    # Attribute access
    db.users = collections["users"]
    db.repositories = collections["repositories"]
    db.chunks = collections["chunks"]
    db.chat_sessions = collections["chat_sessions"]
    # Item access (db["chat_sessions"]) — used by ChatService
    db.__getitem__ = lambda self, key: collections.get(key, make_mock_collection())
    return db


# ---------------------------------------------------------------------------
# App + test client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_client(mock_db):
    """
    AsyncClient against the FastAPI app, with Database fully mocked.
    No real MongoDB or OpenAI calls are made.
    """
    with patch("backend.database.Database.get_db", return_value=mock_db), \
         patch("backend.database.Database.connect", new_callable=AsyncMock), \
         patch("backend.database.Database.disconnect", new_callable=AsyncMock), \
         patch("backend.database.Database.client", create=True, new=MagicMock()), \
         patch("backend.services.embedding.EmbeddingService.generate_embeddings",
               new_callable=AsyncMock, return_value=[[0.1] * 1536]):

        from backend.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_token():
    """Real JWT for a synthetic user."""
    from backend.auth.jwt import create_access_token
    return create_access_token({"sub": "507f1f77bcf86cd799439011", "username": "testuser"})


@pytest.fixture
def auth_headers(valid_token):
    return {"Authorization": f"Bearer {valid_token}"}
