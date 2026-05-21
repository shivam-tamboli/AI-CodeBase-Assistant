from backend.database import Database
from backend.services.file_scanner import scan_directory, get_file_content
from backend.services.chunker import CodeChunker
from backend.services.vector_store import VectorStore
from typing import Dict, Any, Optional
import hashlib
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

_SUMMARIES_ENABLED = os.getenv("ENABLE_CHUNK_SUMMARIES", "false").lower() == "true"


class RepositoryProcessor:
    """Orchestrates repository processing: scan -> chunk -> embed -> store"""

    def __init__(self):
        self.vector_store = VectorStore()
        self.chunker = CodeChunker(max_tokens=1000, overlap=100)
        self._summary_service = None
        if _SUMMARIES_ENABLED:
            from backend.services.summary import SummaryService
            self._summary_service = SummaryService()
    
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
            content = get_file_content(file_info["path"])
            if content:
                file_hash = hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()
                chunks = self.chunker.chunk_file_multilang(
                    content, file_info["relative_path"], file_info["language"]
                )
                for chunk in chunks:
                    chunk["file_hash"] = file_hash
                all_chunks.extend(chunks)
        
        if not all_chunks:
            return {
                "status": "error",
                "message": "No valid code chunks created",
                "files_processed": len(files),
                "chunks_created": 0
            }
        
        await self._enrich_with_summaries(all_chunks)
        chunks_added = await self.vector_store.add_chunks(all_chunks, repository_id)

        return {
            "status": "success",
            "message": f"Processed {len(files)} files, created {chunks_added} chunks",
            "files_processed": len(files),
            "chunks_created": chunks_added
        }

    async def _enrich_with_summaries(self, chunks: list) -> None:
        """Attach LLM-generated summaries to chunks when ENABLE_CHUNK_SUMMARIES=true.

        Summaries are stored in chunk["summary"] and later written to metadata.
        No-op when the feature is disabled or summary service is not initialised.
        """
        if not self._summary_service or not chunks:
            return
        logger.info("Generating summaries for %d chunks...", len(chunks))
        summaries = await self._summary_service.summarize_chunks(chunks)
        for chunk, summary in zip(chunks, summaries):
            if summary:
                chunk["summary"] = summary

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
    
    async def process_repository_incremental(
        self, repository_id: str, local_path: str
    ) -> Dict[str, Any]:
        """Re-index only files whose content hash changed since the last indexing run.

        Compares MD5 hashes of current files against hashes stored in chunk metadata.
        Deletes stale chunks for changed or removed files, then re-embeds only the
        changed/new ones. Unchanged files are skipped entirely.
        """
        db = Database.get_db()

        # Collect existing (file_path, file_hash) pairs from stored chunks
        existing_chunks = await db.chunks.find(
            {"repository_id": repository_id},
            {"metadata.file_path": 1, "metadata.file_hash": 1}
        ).to_list(None)

        existing_hashes: Dict[str, str] = {}
        for chunk in existing_chunks:
            meta = chunk.get("metadata", {})
            fp = meta.get("file_path", "")
            fh = meta.get("file_hash", "")
            if fp and fh:
                existing_hashes[fp] = fh

        # Compute hashes for current files
        files = scan_directory(local_path)
        new_hashes: Dict[str, str] = {}
        file_info_map: Dict[str, Any] = {}
        for file_info in files:
            content = get_file_content(file_info["path"])
            if content:
                new_hashes[file_info["relative_path"]] = hashlib.md5(
                    content.encode("utf-8", errors="replace")
                ).hexdigest()
                file_info_map[file_info["relative_path"]] = (file_info, content)

        # Determine which files changed or were removed
        changed = {fp for fp, fh in new_hashes.items() if existing_hashes.get(fp) != fh}
        removed = set(existing_hashes.keys()) - set(new_hashes.keys())
        stale = changed | removed

        if stale:
            await db.chunks.delete_many({
                "repository_id": repository_id,
                "metadata.file_path": {"$in": list(stale)}
            })

        if not changed:
            return {
                "status": "success",
                "message": "No file changes detected — index is up to date",
                "files_changed": 0,
                "files_removed": len(removed),
                "chunks_created": 0
            }

        all_chunks = []
        for rel_path in changed:
            if rel_path not in file_info_map:
                continue
            file_info, content = file_info_map[rel_path]
            file_hash = new_hashes[rel_path]
            chunks = self.chunker.chunk_file_multilang(
                content, rel_path, file_info["language"]
            )
            for chunk in chunks:
                chunk["file_hash"] = file_hash
            all_chunks.extend(chunks)

        chunks_added = 0
        if all_chunks:
            await self._enrich_with_summaries(all_chunks)
            await self.vector_store.ensure_indexes()
            chunks_added = await self.vector_store.add_chunks(all_chunks, repository_id)

        return {
            "status": "success",
            "message": f"Re-indexed {len(changed)} changed file(s), removed {len(removed)} deleted file(s)",
            "files_changed": len(changed),
            "files_removed": len(removed),
            "chunks_created": chunks_added
        }

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