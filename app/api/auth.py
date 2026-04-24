"""
Auth API Routes

Handles user registration and login.

Phase 13: Production Ready
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
from app.database import Database
from app.auth.jwt import create_access_token
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """
    POST /auth/register - Register a new user
    
    Args:
        username: Unique username
        password: User password
    
    Returns:
        Access token
    """
    db = Database.get_db()
    
    existing = await db.users.find_one({"username": request.username})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    hashed_password = pwd_context.hash(request.password)
    
    doc = {
        "username": request.username,
        "password": hashed_password,
        "created_at": datetime.now()
    }
    
    result = await db.users.insert_one(doc)
    user_id = str(result.inserted_id)
    
    token = create_access_token({"sub": user_id, "username": request.username})
    
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    POST /auth/login - Login with username and password
    
    Args:
        username: Username
        password: Password
    
    Returns:
        Access token
    """
    db = Database.get_db()
    
    user = await db.users.find_one({"username": request.username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not pwd_context.verify(request.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    user_id = str(user["_id"])
    token = create_access_token({"sub": user_id, "username": request.username})
    
    return {"access_token": token, "token_type": "bearer"}