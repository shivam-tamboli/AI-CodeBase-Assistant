"""
GitHub Integration Service

Handles GitHub API interactions for repository import functionality.
Supports OAuth authentication and repository operations.

Phase 11: GitHub Integration
"""

from github import Github, GithubException
from typing import List, Dict, Any, Optional
import base64
import logging
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)


class GitHubService:
    """
    Handles GitHub API interactions.
    
    Provides methods for:
    - Listing user repositories
    - Getting repository details
    - Listing repository contents
    - Downloading files and repositories
    """
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize GitHub service.
        
        Args:
            access_token: GitHub personal access token or OAuth token
                         If not provided, reads from GITHUB_TOKEN env var
        """
        token = access_token or os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GitHub access token not provided. Set GITHUB_TOKEN environment variable.")
        
        self.client = Github(token)
        self.token = token
        logger.info("GitHubService initialized")
    
    def list_repositories(self, sort: str = "updated") -> List[Dict[str, Any]]:
        """
        List user's repositories.
        
        Args:
            sort: Sort by 'updated', 'created', 'pushed', 'full_name'
            
        Returns:
            List of repository dictionaries
        """
        logger.info(f"Listing user repositories (sort: {sort})")
        
        try:
            repos = self.client.get_user().get_repos(sort=sort)
            
            return [
                {
                    "id": repo.id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "description": repo.description or "",
                    "private": repo.private,
                    "default_branch": repo.default_branch,
                    "language": repo.language,
                    "stargazers_count": repo.stargazers_count,
                    "forks_count": repo.forks_count,
                    "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                    "html_url": repo.html_url
                }
                for repo in repos
            ]
            
        except GithubException as e:
            logger.error(f"GitHub API error listing repos: {e}")
            raise ValueError(f"Failed to list repositories: {e}")
    
    def get_repository(self, full_name: str) -> Dict[str, Any]:
        """
        Get repository details.
        
        Args:
            full_name: Repository name in format 'owner/repo'
            
        Returns:
            Repository details dictionary
        """
        logger.info(f"Getting repository: {full_name}")
        
        try:
            repo = self.client.get_repo(full_name)
            
            return {
                "id": repo.id,
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description or "",
                "private": repo.private,
                "default_branch": repo.default_branch,
                "language": repo.language,
                "stargazers_count": repo.stargazers_count,
                "forks_count": repo.forks_count,
                "open_issues_count": repo.open_issues_count,
                "watchers_count": repo.watchers_count,
                "size": repo.size,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                "html_url": repo.html_url
            }
            
        except GithubException as e:
            logger.error(f"GitHub API error getting repo {full_name}: {e}")
            raise ValueError(f"Repository '{full_name}' not found or access denied")
    
    def get_contents(self, full_name: str, path: str = "") -> List[Dict[str, Any]]:
        """
        Get repository contents at a specific path.
        
        Args:
            full_name: Repository name in format 'owner/repo'
            path: Directory path within the repository
            
        Returns:
            List of file/directory entries
        """
        logger.info(f"Getting contents of {full_name}/{path}")
        
        try:
            repo = self.client.get_repo(full_name)
            contents = repo.get_contents(path)
            
            result = []
            for item in contents:
                result.append({
                    "name": item.name,
                    "path": item.path,
                    "type": item.type,
                    "size": item.size,
                    "sha": item.sha,
                    "download_url": item.download_url
                })
            
            return result
            
        except GithubException as e:
            logger.error(f"GitHub API error getting contents: {e}")
            raise ValueError(f"Failed to get contents: {e}")
    
    def download_file(self, full_name: str, path: str) -> Dict[str, Any]:
        """
        Download a single file's content.
        
        Args:
            full_name: Repository name in format 'owner/repo'
            path: File path within the repository
            
        Returns:
            Dictionary with file content and metadata
        """
        logger.info(f"Downloading file {full_name}/{path}")
        
        try:
            repo = self.client.get_repo(full_name)
            file_content = repo.get_contents(path)
            
            if isinstance(file_content, list):
                raise ValueError(f"{path} is a directory, not a file")
            
            decoded_content = base64.b64decode(file_content.content).decode('utf-8')
            
            return {
                "name": file_content.name,
                "path": file_content.path,
                "content": decoded_content,
                "size": file_content.size,
                "sha": file_content.sha,
                "encoding": "base64"
            }
            
        except GithubException as e:
            logger.error(f"GitHub API error downloading file: {e}")
            raise ValueError(f"Failed to download file: {e}")
    
    def download_repository(
        self,
        full_name: str,
        extensions: Optional[List[str]] = None,
        max_files: int = 1000
    ) -> Dict[str, Any]:
        """
        Download entire repository contents.
        
        Args:
            full_name: Repository name in format 'owner/repo'
            extensions: List of file extensions to include (e.g., ['.py', '.js'])
                       If None, includes all code files
            max_files: Maximum number of files to download
            
        Returns:
            Dictionary with repository info and files
        """
        logger.info(f"Downloading repository {full_name}")
        
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', 
                        '.rb', '.rs', '.cpp', '.c', '.h', '.cs', '.swift', '.kt']
        
        try:
            repo = self.client.get_repo(full_name)
            files = {}
            dirs_to_process = [""]
            files_downloaded = 0
            skipped_binary = 0
            
            while dirs_to_process and files_downloaded < max_files:
                current_path = dirs_to_process.pop(0)
                
                try:
                    contents = repo.get_contents(current_path)
                    
                    for item in contents:
                        if files_downloaded >= max_files:
                            break
                        
                        if item.type == "dir":
                            dirs_to_process.append(item.path)
                        else:
                            ext = os.path.splitext(item.name)[1].lower()
                            if ext in extensions:
                                try:
                                    file_data = self.download_file(full_name, item.path)
                                    files[item.path] = file_data["content"]
                                    files_downloaded += 1
                                    logger.debug(f"Downloaded: {item.path}")
                                except Exception as e:
                                    logger.warning(f"Failed to download {item.path}: {e}")
                            else:
                                logger.debug(f"Skipped (extension): {item.path}")
                                
                except GithubException as e:
                    logger.warning(f"Failed to read directory {current_path}: {e}")
                    continue
            
            logger.info(f"Downloaded {files_downloaded} files from {full_name}")
            
            return {
                "name": repo.name,
                "full_name": repo.full_name,
                "default_branch": repo.default_branch,
                "files": files,
                "files_count": files_downloaded,
                "skipped_binary": skipped_binary
            }
            
        except GithubException as e:
            logger.error(f"GitHub API error downloading repo: {e}")
            raise ValueError(f"Failed to download repository: {e}")
    
    def get_rate_limit(self) -> Dict[str, Any]:
        """
        Get current API rate limit status.
        
        Returns:
            Rate limit information
        """
        try:
            rate_limit = self.client.get_rate_limit()
            return {
                "limit": rate_limit.limit,
                "remaining": rate_limit.remaining,
                "reset": rate_limit.reset.isoformat() if rate_limit.reset else None,
                "used": rate_limit.used
            }
        except GithubException as e:
            logger.error(f"GitHub API error getting rate limit: {e}")
            return {"error": str(e)}
    
    def search_repositories(self, query: str, max_results: int = 30) -> List[Dict[str, Any]]:
        """
        Search repositories by query.
        
        Args:
            query: Search query (e.g., "user:username language:python")
            max_results: Maximum number of results
            
        Returns:
            List of matching repositories
        """
        logger.info(f"Searching repositories: {query}")
        
        try:
            results = self.client.search_repositories(query, sort="stars", order="desc")
            
            repos = []
            for i, repo in enumerate(results):
                if i >= max_results:
                    break
                repos.append({
                    "id": repo.id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "description": repo.description or "",
                    "language": repo.language,
                    "stargazers_count": repo.stargazers_count,
                    "html_url": repo.html_url
                })
            
            return repos
            
        except GithubException as e:
            logger.error(f"GitHub API error searching repos: {e}")
            raise ValueError(f"Search failed: {e}")
