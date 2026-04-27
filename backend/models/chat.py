from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class Message(BaseModel):
    """Individual chat message model"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tokens: Optional[int] = Field(None, description="Token count for the message")

    class Config:
        from_attributes = True


class ChatSessionBase(BaseModel):
    """Base model for chat session"""
    repository_id: str = Field(..., description="Associated repository ID")


class ChatSessionCreate(ChatSessionBase):
    """Model for creating a chat session"""
    user_id: Optional[str] = Field(None, description="User ID if authenticated")


class ChatSessionResponse(BaseModel):
    """Model for API response - includes all session data"""
    id: str
    user_id: Optional[str] = None
    repository_id: str
    messages: List[Message] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None
    message_count: int = 0

    class Config:
        from_attributes = True

    @field_serializer('id')
    def serialize_id(self, value):
        """Convert MongoDB ObjectId to string"""
        if isinstance(value, ObjectId):
            return str(value)
        return value


class ChatMessageCreate(BaseModel):
    """Model for adding a message to a session"""
    session_id: str = Field(..., description="Session ID to add message to")
    role: str = Field(..., pattern="^(user|assistant)$", description="Message role")
    content: str = Field(..., min_length=1, description="Message content")
    tokens: Optional[int] = Field(None, description="Token count")


class ChatQueryRequest(BaseModel):
    """Model for chat query request with optional session"""
    question: str = Field(..., min_length=1, description="User's question")
    repository_id: str = Field(..., description="Repository to query")
    session_id: Optional[str] = Field(None, description="Optional session for context")
    limit: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")
