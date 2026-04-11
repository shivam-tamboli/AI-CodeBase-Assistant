from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from contextlib import asynccontextmanager

load_dotenv()

from app.database import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management - connect/disconnect MongoDB"""
    mongodb_uri = os.getenv("MONGODB_URI")
    
    if not mongodb_uri:
        raise ValueError("MONGODB_URI not set in .env")
    
    await Database.connect(mongodb_uri)
    print("Connected to MongoDB")
    
    yield
    
    await Database.disconnect()
    print("Disconnected from MongoDB")


app = FastAPI(
    title="AI Codebase Assistant",
    description="Ask questions about your code",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import repositories_router, chat_router

app.include_router(repositories_router)
app.include_router(chat_router)


@app.get("/")
def root():
    """Root endpoint - test if API is running"""
    return {"message": "API is running"}


@app.get("/health")
def health_check():
    """Health check for monitoring"""
    return {"status": "healthy"}