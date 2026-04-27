from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from contextlib import asynccontextmanager

load_dotenv()

from app.database import Database
from app.middleware.error_handlers import register_error_handlers
from app.middleware.rate_limiter import limiter
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
    print("Users collection indexes initialized")
    
    from app.services.vector_store import VectorStore
    from app.services.keyword_search import KeywordSearchService
    
    vector_store = VectorStore()
    await vector_store.ensure_indexes()
    
    keyword_search = KeywordSearchService()
    await keyword_search.ensure_indexes()
    
    print("Indexes initialized")
    
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

from app.api import repositories_router, chat_router
from app.api.auth import router as auth_router

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