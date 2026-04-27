from backend.database import Database
from backend.services.file_scanner import scan_directory, get_file_content
from backend.services.chunker import CodeChunker
from backend.services.vector_store import VectorStore
from typing import Dict, Any, Optional
import os
from datetime import datetime


class RepositoryProcessor:
    """Orchestrates repository processing: scan -> chunk -> embed -> store"""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.chunker = CodeChunker(max_tokens=1000, overlap=100)
    
    async def process_repository(self, repository_id: str, local_path: str) -> Dict[str, Any]:
        """Process a local repository: scan, chunk, embed, and store
        
        Args:
            repository_id: ID of the repository in MongoDB
            local_path: Local path to the repository
            
        Returns:
            Processing summary with stats
        """
        await self.vector_store.ensure_indexes()
        
        files = scan_directory(local_path)
        
        if not files:
            return {
                "status": "error",
                "message": "No code files found in repository",
                "files_processed": 0,
                "chunks_created": 0
            }
        
        all_chunks = []
        
        for file_info in files:
            if file_info["language"] != "python":
                continue
            
            content = get_file_content(file_info["path"])
            if content:
                chunks = self.chunker.chunk_file(content, file_info["relative_path"])
                all_chunks.extend(chunks)
        
        if not all_chunks:
            return {
                "status": "error",
                "message": "No valid code chunks created",
                "files_processed": len(files),
                "chunks_created": 0
            }
        
        chunks_added = await self.vector_store.add_chunks(all_chunks, repository_id)
        
        return {
            "status": "success",
            "message": f"Processed {len(files)} files, created {chunks_added} chunks",
            "files_processed": len(files),
            "chunks_created": chunks_added
        }
    
    async def reprocess_repository(self, repository_id: str, local_path: str) -> Dict[str, Any]:
        """Reprocess repository (clears existing chunks first)
        
        Args:
            repository_id: ID of the repository
            local_path: Local path to repository
            
        Returns:
            Processing summary
        """
        deleted = await self.vector_store.delete_by_repository(repository_id)
        print(f"Deleted {deleted} existing chunks")
        
        return await self.process_repository(repository_id, local_path)
    
    async def delete_repository_data(self, repository_id: str) -> int:
        """Delete all data associated with a repository
        
        Args:
            repository_id: ID of repository
            
        Returns:
            Number of deleted chunks
        """
        return await self.vector_store.delete_by_repository(repository_id)
    
    async def get_repository_stats(self, repository_id: str) -> Dict[str, Any]:
        """Get processing statistics for a repository
        
        Args:
            repository_id: ID of repository
            
        Returns:
            Stats dict with chunk count
        """
        chunk_count = await self.vector_store.count_chunks(repository_id)
        
        return {
            "repository_id": repository_id,
            "chunk_count": chunk_count,
            "indexed": chunk_count > 0
        }