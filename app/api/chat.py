"""
Chat API Routes

Endpoints for chat session management and querying with context.

Phase 12: Chat Memory & Session Management
Phase 13: Added JWT authentication and rate limiting
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import Optional, List
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.chat_service import ChatService
from app.services.rag_pipeline import RAGPipeline
from app.auth.dependencies import get_current_user, get_optional_user
from app.middleware.rate_limiter import limiter

router = APIRouter(prefix="/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    repository_id: str


class CreateSessionResponse(BaseModel):
    session_id: str
    repository_id: str
    created_at: str


class ChatQueryRequest(BaseModel):
    question: str
    repository_id: str
    session_id: Optional[str] = None
    limit: int = 5


class ChatQueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    chunks_found: int
    session_id: Optional[str] = None
    status: str


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str
    tokens: Optional[int] = None


class SessionResponse(BaseModel):
    id: str
    user_id: Optional[str]
    repository_id: str
    messages: List[MessageResponse]
    message_count: int
    created_at: str
    updated_at: Optional[str] = None


@router.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_chat_session(
    request: Request,
    chat_request: CreateSessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    POST /chat/sessions - Create a new chat session

    Creates a new session linked to a repository for multi-turn conversations.
    Requires authentication.
    Rate limit: 10 requests per minute.
    """
    user_id = current_user.get("user_id")

    result = await ChatService.create_session(
        repository_id=chat_request.repository_id,
        user_id=user_id
    )

    if result["status"] != "success":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )

    return {
        "session_id": result["session_id"],
        "repository_id": result["repository_id"],
        "created_at": result["created_at"].isoformat()
    }


@router.get("/sessions/{session_id}", response_model=SessionResponse)
@limiter.limit("30/minute")
async def get_chat_session(
    request: Request,
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    GET /chat/sessions/{id} - Get session with full history

    Retrieves a chat session including all messages.
    Requires authentication.
    Rate limit: 30 requests per minute.
    """
    session = await ChatService.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found"
        )

    if session.get("user_id") and session["user_id"] != current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session"
        )

    messages = []
    for msg in session.get("messages", []):
        messages.append({
            "role": msg.get("role", "unknown"),
            "content": msg.get("content", ""),
            "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else "",
            "tokens": msg.get("tokens")
        })

    return {
        "id": session["id"],
        "user_id": session.get("user_id"),
        "repository_id": session["repository_id"],
        "messages": messages,
        "message_count": session.get("message_count", 0),
        "created_at": session["created_at"].isoformat() if session.get("created_at") else "",
        "updated_at": session["updated_at"].isoformat() if session.get("updated_at") else None
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_chat_session(
    request: Request,
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    DELETE /chat/sessions/{id} - Delete a chat session

    Permanently deletes a chat session and all its messages.
    Requires authentication.
    Rate limit: 10 requests per minute.
    """
    session = await ChatService.get_session(session_id)

    if session and session.get("user_id") and session["user_id"] != current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to delete this session"
        )

    result = await ChatService.delete_session(session_id)

    if result["status"] == "error":
        if "not found" in result.get("error", "").lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session with id '{session_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )

    return None


@router.get("/sessions/{session_id}/history")
@limiter.limit("30/minute")
async def get_session_history(
    request: Request,
    session_id: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """
    GET /chat/sessions/{id}/history - Get recent messages

    Retrieves recent messages from a session without full session details.
    Requires authentication.
    Rate limit: 30 requests per minute.
    """
    session = await ChatService.get_session(session_id)

    if session and session.get("user_id") and session["user_id"] != current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session"
        )

    messages = await ChatService.get_session_history(session_id, limit=limit)

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": msg.get("role", "unknown"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else "",
                "tokens": msg.get("tokens")
            }
            for msg in messages
        ],
        "count": len(messages)
    }


rag_pipeline = RAGPipeline()


@router.post("/query", response_model=ChatQueryResponse)
@limiter.limit("10/minute")
async def chat_query(
    request: Request,
    chat_request: ChatQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    POST /chat/query - Query with optional session context

    Answers a question about the codebase, optionally using chat history
    for multi-turn conversation context.
    Requires authentication.
    Rate limit: 10 requests per minute.
    """
    session_id = chat_request.session_id

    if session_id:
        session = await ChatService.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session with id '{session_id}' not found"
            )

        if session.get("user_id") and session["user_id"] != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this session"
            )

    result = await rag_pipeline.query(
        question=chat_request.question,
        repository_id=chat_request.repository_id,
        limit=chat_request.limit,
        session_id=session_id
    )

    if session_id and result["status"] == "success":
        await ChatService.add_message(
            session_id=session_id,
            role="user",
            content=chat_request.question
        )
        await ChatService.add_message(
            session_id=session_id,
            role="assistant",
            content=result["answer"]
        )

    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "chunks_found": result.get("chunks_found", 0),
        "session_id": session_id,
        "status": result.get("status", "unknown")
    }


@router.get("/sessions")
@limiter.limit("30/minute")
async def list_sessions(
    request: Request,
    repository_id: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    GET /chat/sessions - List sessions with optional filters

    Lists the authenticated user's sessions.
    Requires authentication.
    Rate limit: 30 requests per minute.
    """
    user_id = current_user.get("user_id")

    sessions = await ChatService.list_user_sessions(
        user_id=user_id,
        repository_id=repository_id,
        limit=limit
    )

    return {
        "sessions": [
            {
                "id": s["id"],
                "user_id": s.get("user_id"),
                "repository_id": s["repository_id"],
                "message_count": s.get("message_count", 0),
                "created_at": s["created_at"].isoformat() if s.get("created_at") else "",
                "updated_at": s.get("updated_at").isoformat() if s.get("updated_at") else None
            }
            for s in sessions
        ],
        "count": len(sessions)
    }
