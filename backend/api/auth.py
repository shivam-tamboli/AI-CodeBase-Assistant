"""
Auth API Routes

Handles user registration and login.

Phase 13: Production Ready
"""

from fastapi import APIRouter, HTTPException, status, Response, Cookie
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import os
from backend.database import Database
from backend.auth.jwt import create_access_token, create_refresh_token, verify_token, REFRESH_TOKEN_EXPIRE_DAYS
from passlib.context import CryptContext

IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

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


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="none" if IS_PRODUCTION else "lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, response: Response):
    db = Database.get_db()

    existing = await db.users.find_one({"username": request.username})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    hashed_password = pwd_context.hash(request.password)
    result = await db.users.insert_one({
        "username": request.username,
        "password": hashed_password,
        "created_at": datetime.now()
    })
    user_id = str(result.inserted_id)

    access_token = create_access_token({"sub": user_id, "username": request.username})
    refresh_token = create_refresh_token({"sub": user_id, "username": request.username})

    await db.refresh_tokens.insert_one({
        "token": refresh_token,
        "user_id": user_id,
        "expires_at": datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    })

    _set_refresh_cookie(response, refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, response: Response):
    db = Database.get_db()

    user = await db.users.find_one({"username": request.username})
    if not user or not pwd_context.verify(request.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    user_id = str(user["_id"])
    access_token = create_access_token({"sub": user_id, "username": request.username})
    refresh_token = create_refresh_token({"sub": user_id, "username": request.username})

    await db.refresh_tokens.insert_one({
        "token": refresh_token,
        "user_id": user_id,
        "expires_at": datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    })

    _set_refresh_cookie(response, refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh")
async def refresh(response: Response, refresh_token: Optional[str] = Cookie(None)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    payload = verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    db = Database.get_db()
    stored = await db.refresh_tokens.find_one({"token": refresh_token})
    if not stored:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    user_id = payload["sub"]
    username = payload.get("username", "")
    new_access_token = create_access_token({"sub": user_id, "username": username})

    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response, refresh_token: Optional[str] = Cookie(None)):
    if refresh_token:
        db = Database.get_db()
        await db.refresh_tokens.delete_one({"token": refresh_token})

    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="none" if IS_PRODUCTION else "lax",
    )
    return {"message": "Logged out"}