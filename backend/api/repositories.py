"""
Repository API Routes

Endpoints for repository management.

Phase 13: Added JWT authentication and authorization
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status, Depends, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import zipfile
import base64
import io
import os
import shutil
import tempfile

import asyncio
import logging
import re

from backend.database import Database
from backend.models.repository import RepositoryCreate, RepositoryImport, RepositoryResponse, RepositoryUpdate
from backend.auth.dependencies import get_current_user
from backend.middleware.rate_limiter import limiter
from backend.services.processor import RepositoryProcessor
from backend.services.keyword_search import KeywordSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["repositories"])


MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
MAX_EXTRACTED_BYTES = int(os.getenv("MAX_EXTRACTED_MB", "200")) * 1024 * 1024


def _save_upload(file: UploadFile, temp_dir: str) -> str:
    """Stream the uploaded ZIP into temp_dir, enforcing MAX_UPLOAD_BYTES.

    The filename is reduced to its basename: it comes from the client, and
    joining it as-is would let "../../x.zip" write outside temp_dir.
    """
    safe_name = os.path.basename(file.filename or "") or "upload.zip"
    zip_path = os.path.join(temp_dir, safe_name)
    written = 0
    with open(zip_path, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"ZIP is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
                )
            f.write(chunk)
    return zip_path


def _extract_zip(zip_path: str, dest: str) -> None:
    """Extract after checking the declared uncompressed size (zip-bomb guard)."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            total = sum(info.file_size for info in zip_ref.infolist())
            if total > MAX_EXTRACTED_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"ZIP expands to more than {MAX_EXTRACTED_BYTES // (1024 * 1024)} MB"
                )
            zip_ref.extractall(dest)
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a valid ZIP archive"
        )


async def _run_ingestion(
    repo_id: str,
    extract_base: str,
    temp_dir: str,
    processor: RepositoryProcessor,
    incremental: bool = False,
) -> None:
    """Background task: run ingestion and update repository status.

    Owns the temp_dir lifecycle — always cleans up on exit regardless of outcome.
    """
    db = Database.get_db()
    try:
        await db.repositories.update_one(
            {"_id": ObjectId(repo_id)},
            {"$set": {"status": "indexing"}},
        )
        if incremental:
            result = await processor.process_repository_incremental(repo_id, extract_base)
        else:
            result = await processor.process_repository(repo_id, extract_base)

        final_status = "indexed" if result.get("status") == "success" else "failed"
        await db.repositories.update_one(
            {"_id": ObjectId(repo_id)},
            {"$set": {
                "status": final_status,
                "processing": result,
                "updated_at": datetime.now(timezone.utc),
            }},
        )
    except Exception as exc:
        logger.error("Ingestion background task failed for %s: %s", repo_id, exc)
        await db.repositories.update_one(
            {"_id": ObjectId(repo_id)},
            {"$set": {"status": "failed", "error": str(exc), "updated_at": datetime.now(timezone.utc)}},
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


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
        "created_at": datetime.now(timezone.utc),
        "updated_at": None
    }

    result = await db.repositories.insert_one(doc)
    doc["id"] = str(result.inserted_id)

    return doc


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def upload_repository(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """POST /repositories/upload — Upload repository as ZIP and index asynchronously.

    Extracts the ZIP, inserts the repository record with status='pending', and
    schedules indexing as a background task. Returns immediately (HTTP 202).

    Poll GET /repositories/{id}/status to track progress.
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only ZIP files are accepted"
        )

    db = Database.get_db()
    user_id = current_user.get("user_id")

    # mkdtemp instead of TemporaryDirectory — background task owns cleanup.
    temp_dir = tempfile.mkdtemp()
    try:
        zip_path = _save_upload(file, temp_dir)
        _extract_zip(zip_path, temp_dir)

        root_content = [e for e in os.listdir(temp_dir) if e != os.path.basename(zip_path)]
        subdirectory = None
        extract_base = temp_dir
        if len(root_content) == 1 and os.path.isdir(os.path.join(temp_dir, root_content[0])):
            subdirectory = root_content[0]
            extract_base = os.path.join(temp_dir, subdirectory)

        repo_name = name or subdirectory or os.path.basename(zip_path)[:-len('.zip')]

        doc = {
            "name": repo_name,
            "description": description or "",
            "user_id": user_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }

        result = await db.repositories.insert_one(doc)
        repo_id = str(result.inserted_id)

        background_tasks.add_task(
            _run_ingestion,
            repo_id,
            extract_base,
            temp_dir,
            request.app.state.processor,
            False,
        )

        return {
            "id": repo_id,
            "name": repo_name,
            "description": doc["description"],
            "status": "pending",
            "created_at": doc["created_at"],
            "updated_at": None,
        }

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@router.post("/{repo_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def reindex_repository(
    request: Request,
    repo_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Re-index a repository from a new ZIP, updating only changed files.

    Computes MD5 content hashes and skips files whose hash matches the
    stored value. Only changed and new files are re-embedded; chunks for
    removed files are deleted. Returns 202 immediately — poll
    GET /repositories/{id}/status to track progress.

    Rate limit: 5 requests per minute.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only ZIP files are accepted"
        )

    db = Database.get_db()
    user_id = current_user.get("user_id")

    try:
        repo = await db.repositories.find_one({"_id": ObjectId(repo_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid repository ID format")

    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repo_id}' not found")

    if repo.get("user_id") and repo["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this repository")

    temp_dir = tempfile.mkdtemp()
    try:
        zip_path = _save_upload(file, temp_dir)
        _extract_zip(zip_path, temp_dir)

        root_content = [e for e in os.listdir(temp_dir) if e != os.path.basename(zip_path)]
        extract_base = temp_dir
        if len(root_content) == 1 and os.path.isdir(os.path.join(temp_dir, root_content[0])):
            extract_base = os.path.join(temp_dir, root_content[0])

        await db.repositories.update_one(
            {"_id": ObjectId(repo_id)},
            {"$set": {"status": "pending", "updated_at": datetime.now(timezone.utc)}},
        )

        background_tasks.add_task(
            _run_ingestion,
            repo_id,
            extract_base,
            temp_dir,
            request.app.state.processor,
            True,
        )

        return {"repository_id": repo_id, "status": "pending"}

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


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

    update_data = {"updated_at": datetime.now(timezone.utc)}

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

    processor: RepositoryProcessor = request.app.state.processor
    await processor.delete_repository_data(repo_id)

    await db.repositories.delete_one({"_id": ObjectId(repo_id)})

    return None


@router.get("/{repo_id}/symbols")
@limiter.limit("60/minute")
async def search_symbols(
    request: Request,
    repo_id: str,
    name: str,
    type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    GET /repositories/{id}/symbols?name=foo&type=function

    Search for functions or classes by exact name within a repository.

    Args:
        repo_id: Repository ID to search in
        name: Symbol name to search for
        type: Optional filter — 'function' or 'class' (searches both if omitted)

    Returns:
        List of matching symbols with file path, line numbers, and source content

    Requires authentication.
    Rate limit: 60 requests per minute.
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

    if not name or not name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name query parameter is required"
        )

    keyword_service: KeywordSearchService = request.app.state.keyword_service

    symbol_type = (type or "").lower()

    if symbol_type == "class":
        results = await keyword_service.search_class_names(name.strip(), repo_id)
    elif symbol_type == "function":
        results = await keyword_service.search_function_names(name.strip(), repo_id)
    else:
        functions = await keyword_service.search_function_names(name.strip(), repo_id)
        classes = await keyword_service.search_class_names(name.strip(), repo_id)
        results = functions + classes

    symbols = []
    for doc in results:
        metadata = doc.get("metadata", {})
        symbols.append({
            "name": metadata.get("name", ""),
            "type": metadata.get("chunk_type", "unknown"),
            "file_path": metadata.get("file_path", ""),
            "start_line": metadata.get("start_line", 0),
            "end_line": metadata.get("end_line", 0),
            "token_count": metadata.get("token_count", 0),
            "content": doc.get("content", "")
        })

    return {
        "repository_id": repo_id,
        "query": name,
        "type_filter": type,
        "count": len(symbols),
        "symbols": symbols
    }


@router.get("/{repo_id}/stats")
@limiter.limit("60/minute")
async def get_repository_stats(
    request: Request,
    repo_id: str,
    current_user: dict = Depends(get_current_user)
):
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

    processor: RepositoryProcessor = request.app.state.processor
    stats = await processor.get_repository_stats(repo_id)

    return {
        "repository_id": repo_id,
        "chunk_count": stats.get("chunk_count", 0),
        "indexed": stats.get("indexed", False)
    }


@router.get("/{repo_id}/status")
@limiter.limit("60/minute")
async def get_repository_status(
    request: Request,
    repo_id: str,
    current_user: dict = Depends(get_current_user)
):
    """GET /repositories/{id}/status — Poll async ingestion progress.

    Returns:
        id, name, status — one of: pending | indexing | indexed | failed
        processing — result dict from the processor (present once indexed)
        error — error message (present when status is 'failed')

    Rate limit: 60 requests per minute.
    """
    db = Database.get_db()
    user_id = current_user.get("user_id")

    try:
        repo = await db.repositories.find_one({"_id": ObjectId(repo_id)})
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid repository ID format")

    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repo_id}' not found")

    if repo.get("user_id") and repo["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this repository")

    response: dict = {
        "id": repo_id,
        "name": repo.get("name", ""),
        "status": repo.get("status", "unknown"),
    }
    if "processing" in repo:
        response["processing"] = repo["processing"]
    if "error" in repo:
        response["error"] = repo["error"]

    return response


_GITHUB_URL_RE = re.compile(
    r'^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$'
)


def _git_clone_env(user_token: Optional[str]) -> dict:
    """Environment for `git clone` that can only ever use the caller's credentials.

    - credential.helper is blanked so a helper on the host (keychain, store)
      can't silently authenticate the clone.
    - GIT_TERMINAL_PROMPT=0 makes a private repo fail fast instead of hanging.
    - The user's token is passed as an auth header via GIT_CONFIG_* env vars,
      which keeps it out of argv, the clone URL, and the clone's .git/config.
    """
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        # An empty helper value resets any helpers inherited from system/global config.
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "",
    }
    if user_token:
        basic = base64.b64encode(f"x-access-token:{user_token}".encode()).decode()
        env.update({
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_1": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_1": f"Authorization: Basic {basic}",
        })
    return env


def _scrub_secret(text: str, secret: Optional[str]) -> str:
    if not secret:
        return text
    basic = base64.b64encode(f"x-access-token:{secret}".encode()).decode()
    return text.replace(secret, "***").replace(basic, "***")


@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def import_repository(
    request: Request,
    payload: RepositoryImport,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Clone a GitHub repository and index it asynchronously.

    Validates the URL and performs the git clone synchronously (so auth/
    network errors surface immediately), then schedules indexing as a
    background task and returns 202. Poll GET /repositories/{id}/status
    to track progress.

    Public repos clone anonymously. Private repos need the caller's own
    token in `github_token`; the server's GITHUB_TOKEN is never used here,
    otherwise any registered user could read whatever that token can.
    Rate limit: 5 requests per minute (clone is network-bound).
    """
    url = payload.url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    if not _GITHUB_URL_RE.match(url + "/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must be a GitHub repository (https://github.com/owner/repo)"
        )

    user_token = payload.github_token.get_secret_value() if payload.github_token else None

    repo_slug = url.split("/")[-1]
    repo_name = payload.name or repo_slug
    db = Database.get_db()
    user_id = current_user.get("user_id")

    # mkdtemp — background task owns cleanup via _run_ingestion finally block.
    temp_dir = tempfile.mkdtemp()
    try:
        clone_path = os.path.join(temp_dir, repo_slug)

        clone_cmd = ["git", "clone", "--depth", "1"]
        if payload.branch:
            clone_cmd += ["--branch", payload.branch]
        clone_cmd += ["--", url, clone_path]

        proc = await asyncio.create_subprocess_exec(
            *clone_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_git_clone_env(user_token),
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Clone timed out after 120 seconds"
            )

        if proc.returncode != 0:
            # Scrub the token from stderr before returning it to the client.
            error_msg = _scrub_secret(stderr.decode(errors="replace").strip(), user_token)
            shutil.rmtree(temp_dir, ignore_errors=True)
            auth_failed = any(m in error_msg for m in (
                "could not read Username", "Authentication failed", "Repository not found",
            ))
            if auth_failed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Clone failed: the token was rejected or can't access this repository."
                        if user_token else
                        "Clone failed: repository not found or private. "
                        "To import a private repo, provide your own GitHub access token."
                    ),
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Clone failed: {error_msg}"
            )

        doc = {
            "name": repo_name,
            "description": payload.description or f"Imported from {url}",
            "user_id": user_id,
            "source_url": url,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }

        result = await db.repositories.insert_one(doc)
        repo_id = str(result.inserted_id)

        background_tasks.add_task(
            _run_ingestion,
            repo_id,
            clone_path,
            temp_dir,
            request.app.state.processor,
            False,
        )

        return {
            "id": repo_id,
            "name": repo_name,
            "description": doc["description"],
            "source_url": url,
            "status": "pending",
            "created_at": doc["created_at"],
            "updated_at": None,
        }

    except HTTPException:
        raise
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
