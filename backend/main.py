from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from contextlib import asynccontextmanager

load_dotenv()

from backend.database import Database
from backend.middleware.error_handlers import register_error_handlers
from backend.middleware.rate_limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management - connect/disconnect MongoDB"""
    mongodb_uri = os.getenv("MONGODB_URI")
    
    if not mongodb_uri:
        raise ValueError("MONGODB_URI not set in .env")
    
    await Database.connect(mongodb_uri)
    print("Connected to MongoDB")
    
    db = Database.get_db()
    await db.users.create_index("username", unique=True)
    await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.refresh_tokens.create_index("user_id")
    print("Users collection indexes initialized")
    
    from backend.services.vector_store import VectorStore
    from backend.services.keyword_search import KeywordSearchService
    from backend.services.processor import RepositoryProcessor
    from backend.services.rag_pipeline import RAGPipeline

    vector_store = VectorStore()
    await vector_store.ensure_indexes()

    keyword_search = KeywordSearchService()
    await keyword_search.ensure_indexes()

    # Shared singletons — one API client / connection pool per service type
    app.state.processor = RepositoryProcessor()
    app.state.keyword_service = keyword_search
    app.state.rag_pipeline = RAGPipeline()

    print("Indexes and services initialized")

    yield

    await Database.disconnect()
    print("Disconnected from MongoDB")


app = FastAPI(
    title="AI Codebase Assistant",
    description="Ask questions about your code",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

register_error_handlers(app)

from backend.api import repositories_router, chat_router
from backend.api.auth import router as auth_router

app.include_router(auth_router)
app.include_router(repositories_router)
app.include_router(chat_router)


@app.get("/")
def root():
    """Root endpoint - test if API is running"""
    return {"message": "API is running"}


@app.get("/health")
async def health_check():
    """Health check for monitoring"""
    try:
        await Database.client.admin.command('ping')
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status
    }