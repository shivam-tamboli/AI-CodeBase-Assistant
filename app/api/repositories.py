"""
Repository API Routes

Endpoints for repository management.

Phase 13: Added JWT authentication and authorization
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import zipfile
import io
import os
import shutil
import tempfile

from app.database import Database
from app.models.repository import RepositoryCreate, RepositoryResponse, RepositoryUpdate
from app.auth.dependencies import get_current_user
from app.middleware.rate_limiter import limiter
from app.services.processor import RepositoryProcessor

router = APIRouter(prefix="/repositories", tags=["repositories"])


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("", response_model=List[RepositoryResponse])
@limiter.limit("60/minute")
async def list_repositories(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    GET /repositories - List user's repositories

    Returns repositories owned by the authenticated user.
    Requires authentication.
    Rate limit: 60 requests per minute.
    """
    db = Database.get_db()
    user_id = current_user.get("user_id")

    repos = await db.repositories.find({"user_id": user_id}).to_list(100)
    return [serialize_doc(repo) for repo in repos]


@router.get("/{repo_id}", response_model=RepositoryResponse)
@limiter.limit("60/minute")
async def get_repository(
    request: Request,
    repo_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    GET /repositories/{id} - Get single repository by ID

    Args:
        repo_id: The unique identifier of the repository

    Returns:
        Repository object if found

    Raises:
        404: Repository not found
        403: Not authorized to access this repository
    """
    db = Database.get_db()
    user_id = current_user.get("user_id")

    try:
        repo = await db.repositories.find_one({"_id": ObjectId(repo_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository ID format"
        )

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repo_id}' not found"
        )

    if repo.get("user_id") and repo["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this repository"
        )

    return serialize_doc(repo)


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_repository(
    request: Request,
    repo: RepositoryCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    POST /repositories - Create new repository

    Args:
        repo: Repository data (name, description)

    Returns:
        Created repository with generated ID and timestamp

    Requires authentication.
    Rate limit: 20 requests per minute.
    """
    db = Database.get_db()
    user_id = current_user.get("user_id")

    doc = {
        "name": repo.name,
        "description": repo.description,
        "user_id": user_id,
        "created_at": datetime.now(),
        "updated_at": None
    }

    result = await db.repositories.insert_one(doc)
    doc["id"] = str(result.inserted_id)

    return doc


@router.post("/upload", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def upload_repository(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    POST /repositories/upload - Upload repository as ZIP file
    
    Accepts a ZIP file containing code files.
    Processes and indexes the uploaded code.
    
    Args:
        file: ZIP file containing code
        name: Repository name (optional, extracted from ZIP if not provided)
        description: Repository description
    
    Returns:
        Created repository with processing stats
    
    Requires authentication.
    Rate limit: 10 requests per minute.
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only ZIP files are accepted"
        )
    
    db = Database.get_db()
    user_id = current_user.get("user_id")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, file.filename)
        
        with open(zip_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        root_content = os.listdir(temp_dir)
        subdirectory = None
        extract_base = temp_dir
        
        if len(root_content) == 1 and os.path.isdir(os.path.join(temp_dir, root_content[0])):
            subdirectory = root_content[0]
            extract_base = os.path.join(temp_dir, subdirectory)
        
        repo_name = name or subdirectory or file.filename.replace('.zip', '')
        
        doc = {
            "name": repo_name,
            "description": description or "",
            "user_id": user_id,
            "file_path": extract_base,
            "created_at": datetime.now(),
            "updated_at": None
        }
        
        result = await db.repositories.insert_one(doc)
        repo_id = str(result.inserted_id)
        
        processor = RepositoryProcessor()
        processing_result = await processor.process_repository(repo_id, extract_base)
        
        return {
            "id": repo_id,
            "name": doc["name"],
            "description": doc["description"],
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],
            "processing": processing_result
        }


@router.put("/{repo_id}", response_model=RepositoryResponse)
@limiter.limit("20/minute")
async def update_repository(
    request: Request,
    repo_id: str,
    repo_update: RepositoryUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    PUT /repositories/{id} - Update entire repository

    Args:
        repo_id: The unique identifier of the repository
        repo_update: Updated repository data (all fields optional)

    Returns:
        Updated repository object

    Raises:
        404: Repository not found
        403: Not authorized to update this repository

    Requires authentication.
    Rate limit: 20 requests per minute.
    """
    db = Database.get_db()
    user_id = current_user.get("user_id")

    try:
        repo = await db.repositories.find_one({"_id": ObjectId(repo_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository ID format"
        )

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repo_id}' not found"
        )

    if repo.get("user_id") and repo["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to update this repository"
        )

    update_data = {"updated_at": datetime.now()}

    if repo_update.name is not None:
        update_data["name"] = repo_update.name
    if repo_update.description is not None:
        update_data["description"] = repo_update.description

    await db.repositories.update_one(
        {"_id": ObjectId(repo_id)},
        {"$set": update_data}
    )

    updated_repo = await db.repositories.find_one({"_id": ObjectId(repo_id)})
    return serialize_doc(updated_repo)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_repository(
    request: Request,
    repo_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    DELETE /repositories/{id} - Delete repository

    Args:
        repo_id: The unique identifier of the repository

    Returns:
        204 No Content on successful deletion

    Raises:
        404: Repository not found
        403: Not authorized to delete this repository

    Requires authentication.
    Rate limit: 10 requests per minute.
    """
    db = Database.get_db()
    user_id = current_user.get("user_id")

    try:
        repo = await db.repositories.find_one({"_id": ObjectId(repo_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository ID format"
        )

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repo_id}' not found"
        )

    if repo.get("user_id") and repo["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to delete this repository"
        )

    await db.repositories.delete_one({"_id": ObjectId(repo_id)})

    return None
