from pydantic import BaseModel, Field, SecretStr, field_serializer, field_validator
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId
import re

_GITHUB_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]{20,255}$")


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
    # SecretStr keeps the token out of reprs and validation-error logs.
    github_token: Optional[SecretStr] = Field(
        None,
        description="The caller's own GitHub token, required only for private repos. Never stored."
    )

    @field_validator("github_token")
    @classmethod
    def _check_token_shape(cls, v: Optional[SecretStr]) -> Optional[SecretStr]:
        if v is None:
            return None
        raw = v.get_secret_value().strip()
        if not raw:
            return None
        # GitHub tokens are [A-Za-z0-9_] only; rejecting anything else also
        # rules out newline/header injection when the token becomes an HTTP header.
        if not _GITHUB_TOKEN_RE.match(raw):
            raise ValueError("github_token is not a valid GitHub token")
        return SecretStr(raw)


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
