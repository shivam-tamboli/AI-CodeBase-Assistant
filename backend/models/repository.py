from pydantic import BaseModel, Field, field_serializer
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId


class RepositoryBase(BaseModel):
    """Base model - shared fields for repository"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    file_path: Optional[str] = None


class RepositoryCreate(RepositoryBase):
    """Model for creating a repository - input validation"""
    pass


class RepositoryImport(BaseModel):
    """Model for importing a repository from a GitHub URL"""
    url: str = Field(..., description="GitHub repository URL (public or private)")
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    branch: Optional[str] = Field(
        None,
        description="Branch to clone (defaults to repository HEAD)"
    )


class RepositoryUpdate(BaseModel):
    """Model for updating a repository - all fields optional"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    file_path: Optional[str] = None


class RepositoryResponse(RepositoryBase):
    """Model for API responses - includes ID and timestamps"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True

    @field_serializer('id')
    def serialize_id(self, value):
        """Convert MongoDB ObjectId to string"""
        if isinstance(value, ObjectId):
            return str(value)
        return value
