"""
Chat API Routes

Endpoints for chat session management and querying with context.

Phase 12: Chat Memory & Session Management
"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel
from app.services.chat_service import ChatService
from app.services.rag_pipeline import RAGPipeline

router = APIRouter(prefix="/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    """Request model for creating a chat session"""
    repository_id: str
    user_id: Optional[str] = None


class CreateSessionResponse(BaseModel):
    """Response model for created session"""
    session_id: str
    repository_id: str
    user_id: Optional[str] = None
    created_at: str


class ChatQueryRequest(BaseModel):
    """Request model for chat query"""
    question: str
    repository_id: str
    session_id: Optional[str] = None
    limit: int = 5


class ChatQueryResponse(BaseModel):
    """Response model for chat query"""
    answer: str
    sources: List[dict]
    chunks_found: int
    session_id: Optional[str] = None
    status: str


class MessageResponse(BaseModel):
    """Response model for a single message"""
    role: str
    content: str
    timestamp: str
    tokens: Optional[int] = None


class SessionResponse(BaseModel):
    """Response model for session details"""
    id: str
    user_id: Optional[str]
    repository_id: str
    messages: List[MessageResponse]
    message_count: int
    created_at: str
    updated_at: Optional[str] = None


@router.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(request: CreateSessionRequest):
    """
    POST /chat/sessions - Create a new chat session

    Creates a new session linked to a repository for multi-turn conversations.

    Args:
        request: Session creation data (repository_id, optional user_id)

    Returns:
        Created session with session_id
    """
    result = await ChatService.create_session(
        repository_id=request.repository_id,
        user_id=request.user_id
    )

    if result["status"] != "success":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to create session")
        )

    return {
        "session_id": result["session_id"],
        "repository_id": result["repository_id"],
        "user_id": result.get("user_id"),
        "created_at": result["created_at"].isoformat()
    }


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_chat_session(session_id: str):
    """
    GET /chat/sessions/{id} - Get session with full history

    Retrieves a chat session including all messages.

    Args:
        session_id: The session ID

    Returns:
        Full session with messages

    Raises:
        404: Session not found
    """
    session = await ChatService.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id '{session_id}' not found"
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
async def delete_chat_session(session_id: str):
    """
    DELETE /chat/sessions/{id} - Delete a chat session

    Permanently deletes a chat session and all its messages.

    Args:
        session_id: The session ID to delete

    Returns:
        204 No Content on success

    Raises:
        404: Session not found
    """
    result = await ChatService.delete_session(session_id)

    if result["status"] == "error":
        if "not found" in result.get("error", "").lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session with id '{session_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to delete session")
        )

    return None


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 20):
    """
    GET /chat/sessions/{id}/history - Get recent messages

    Retrieves recent messages from a session without full session details.

    Args:
        session_id: The session ID
        limit: Maximum messages to return (default 20)

    Returns:
        List of recent messages
    """
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
async def chat_query(request: ChatQueryRequest):
    """
    POST /chat/query - Query with optional session context

    Answers a question about the codebase, optionally using chat history
    for multi-turn conversation context.

    Args:
        request: Query data (question, repository_id, optional session_id)

    Returns:
        Answer with source citations
    """
    session_id = request.session_id

    if session_id:
        session = await ChatService.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session with id '{session_id}' not found"
            )

    result = await rag_pipeline.query(
        question=request.question,
        repository_id=request.repository_id,
        limit=request.limit,
        session_id=session_id
    )

    if session_id and result["status"] == "success":
        await ChatService.add_message(
            session_id=session_id,
            role="user",
            content=request.question
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
async def list_sessions(
    user_id: Optional[str] = None,
    repository_id: Optional[str] = None,
    limit: int = 50
):
    """
    GET /chat/sessions - List sessions with optional filters

    Args:
        user_id: Filter by user ID
        repository_id: Filter by repository ID
        limit: Maximum sessions to return

    Returns:
        List of sessions
    """
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
