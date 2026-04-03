from fastapi import APIRouter, HTTPException, status
from typing import List
from datetime import datetime
from bson import ObjectId
from app.database import Database
from app.models.repository import RepositoryCreate, RepositoryResponse, RepositoryUpdate


router = APIRouter(prefix="/repositories", tags=["repositories"])


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("", response_model=List[RepositoryResponse])
async def list_repositories():
    """
    GET /repositories - List all repositories
    
    Returns all repositories in the database.
    """
    db = Database.get_db()
    repos = await db.repositories.find().to_list(100)
    return [serialize_doc(repo) for repo in repos]


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(repo_id: str):
    """
    GET /repositories/{id} - Get single repository by ID
    
    Args:
        repo_id: The unique identifier of the repository
        
    Returns:
        Repository object if found
        
    Raises:
        404: Repository not found
    """
    db = Database.get_db()
    
    try:
        repo = await db.repositories.find_one({"_id": ObjectId(repo_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository ID format"
        )
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repo_id}' not found"
        )
    
    return serialize_doc(repo)


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(repo: RepositoryCreate):
    """
    POST /repositories - Create new repository
    
    Args:
        repo: Repository data (name, description)
        
    Returns:
        Created repository with generated ID and timestamp
    """
    db = Database.get_db()
    
    doc = {
        "name": repo.name,
        "description": repo.description,
        "created_at": datetime.now(),
        "updated_at": None
    }
    
    result = await db.repositories.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    
    return doc


@router.put("/{repo_id}", response_model=RepositoryResponse)
async def update_repository(repo_id: str, repo_update: RepositoryUpdate):
    """
    PUT /repositories/{id} - Update entire repository
    
    Args:
        repo_id: The unique identifier of the repository
        repo_update: Updated repository data (all fields optional)
        
    Returns:
        Updated repository object
        
    Raises:
        404: Repository not found
    """
    db = Database.get_db()
    
    try:
        repo = await db.repositories.find_one({"_id": ObjectId(repo_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository ID format"
        )
    
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repo_id}' not found"
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
async def delete_repository(repo_id: str):
    """
    DELETE /repositories/{id} - Delete repository
    
    Args:
        repo_id: The unique identifier of the repository
        
    Returns:
        204 No Content on successful deletion
        
    Raises:
        404: Repository not found
    """
    db = Database.get_db()
    
    try:
        result = await db.repositories.delete_one({"_id": ObjectId(repo_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository ID format"
        )
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repo_id}' not found"
        )
    
    return None