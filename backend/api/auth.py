"""
Auth API Routes

Handles user registration and login.

Phase 13: Production Ready
"""

from fastapi import APIRouter, HTTPException, status, Request, Response, Cookie
from pydantic import BaseModel, Field, field_validator
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timedelta, timezone
from typing import Optional
import os
from backend.database import Database
from backend.auth.jwt import create_access_token, create_refresh_token, verify_token, REFRESH_TOKEN_EXPIRE_DAYS
from backend.middleware.rate_limiter import limiter
from passlib.context import CryptContext

IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# bcrypt only looks at the first 72 bytes, so anything longer would be
# silently truncated. Measured in bytes, not characters, for that reason.
PASSWORD_MIN_BYTES = 8
PASSWORD_MAX_BYTES = 72


class RegisterRequest(BaseModel):
    # Coarse caps bound the work; the validators below give the friendly messages.
    username: str = Field(..., max_length=256)
    password: str = Field(..., max_length=1024)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip()
        if not 3 <= len(v) <= 32:
            raise ValueError("Username must be 3-32 characters")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        n = len(v.encode("utf-8"))
        if not v.strip() or n < PASSWORD_MIN_BYTES:
            raise ValueError(f"Password must be at least {PASSWORD_MIN_BYTES} characters")
        if n > PASSWORD_MAX_BYTES:
            raise ValueError(f"Password must be at most {PASSWORD_MAX_BYTES} bytes")
        return v


class LoginRequest(BaseModel):
    # No minimums here: accounts created before RegisterRequest had rules
    # must still be able to sign in. The caps just bound the work per request.
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=1024)

    @field_validator("username", "password")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Must not be blank")
        return v


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
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, response: Response):
    db = Database.get_db()

    taken = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Username already taken"
    )
    existing = await db.users.find_one({"username": body.username})
    if existing:
        raise taken

    hashed_password = pwd_context.hash(body.password)
    try:
        result = await db.users.insert_one({
            "username": body.username,
            "password": hashed_password,
            "created_at": datetime.now(timezone.utc)
        })
    except DuplicateKeyError:
        # Lost a race with a concurrent register for the same name; the
        # unique index on username is the real guard, find_one is a fast path.
        raise taken
    user_id = str(result.inserted_id)

    access_token = create_access_token({"sub": user_id, "username": body.username})
    refresh_token = create_refresh_token({"sub": user_id, "username": body.username})

    await db.refresh_tokens.insert_one({
        "token": refresh_token,
        "user_id": user_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    })

    _set_refresh_cookie(response, refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response):
    db = Database.get_db()

    user = await db.users.find_one({"username": body.username})
    if not user or not pwd_context.verify(body.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    user_id = str(user["_id"])
    access_token = create_access_token({"sub": user_id, "username": body.username})
    refresh_token = create_refresh_token({"sub": user_id, "username": body.username})

    await db.refresh_tokens.insert_one({
        "token": refresh_token,
        "user_id": user_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
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