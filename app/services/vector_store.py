from app.database import Database
from app.services.embedding import EmbeddingService
from typing import List, Dict, Any, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages vector storage and semantic search in MongoDB"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.index_name = "vector_search_index"
    
    async def ensure_indexes(self):
        """Create indexes on chunks collection"""
        db = Database.get_db()
        
        try:
            existing_indexes = db.chunks.list_indexes()
            existing_names = [idx.get("name") for idx in await existing_indexes.to_list(None)]
            
            # Create repository_id index for filtering
            if "repository_id_1" not in existing_names:
                await db.chunks.create_index([("repository_id", 1)])
                print("Created index: repository_id_1")
            
            # Vector search requires Atlas Vector Search (paid) - skip for free tier
            # Using standard indexes for semantic search via $searchMeta or workaround
            print("Using standard indexes (vector search requires Atlas paid tier)")
                
        except Exception as e:
            print(f"Index creation warning: {e}")
    
    async def add_chunks(self, chunks: List[Dict[str, Any]], repository_id: str) -> int:
        """Add code chunks with embeddings to MongoDB
        
        Args:
            chunks: List of code chunks (from chunker)
            repository_id: ID of the parent repository
            
        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0
        
        db = Database.get_db()
        
        texts = [chunk["content"] for chunk in chunks]
        embeddings = await self.embedding_service.generate_embeddings(texts)
        
        documents = []
        for chunk, embedding in zip(chunks, embeddings):
            documents.append({
                "repository_id": repository_id,
                "content": chunk["content"],
                "embedding": embedding,
                "metadata": {
                    "file_path": chunk.get("file_path", ""),
                    "chunk_type": chunk.get("chunk_type", "unknown"),
                    "name": chunk.get("name", ""),
                    "start_line": chunk.get("start_line", 0),
                    "end_line": chunk.get("end_line", 0),
                    "token_count": chunk.get("token_count", 0)
                }
            })
        
        if documents:
            result = await db.chunks.insert_many(documents)
            return len(result.inserted_ids)
        
        return 0
    
    async def semantic_search(
        self, 
        query: str, 
        repository_id: str, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar code using cosine similarity
        
        Args:
            query: User query string
            repository_id: ID of repository to search in
            limit: Maximum number of results
            
        Returns:
            List of relevant code chunks with scores
        """
        print(f"[Semantic Search] Generating query embedding...")
        query_embedding = await self.embedding_service.generate_embedding(query)
        
        db = Database.get_db()
        
        chunks = await db.chunks.find({"repository_id": repository_id}).to_list(100)
        
        if not chunks:
            return []
        
        print(f"[Semantic Search] Computing similarity for {len(chunks)} chunks...")
        
        scored_chunks = []
        for chunk in chunks:
            chunk_embedding = chunk.get("embedding")
            if not chunk_embedding:
                continue
            
            similarity = self._cosine_similarity(query_embedding, chunk_embedding)
            scored_chunks.append({
                **chunk,
                "score": similarity
            })
        
        scored_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        print(f"[Semantic Search] Found {len(scored_chunks)} results, returning top {limit}")
        
        return scored_chunks[:limit]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score (0 to 1)
        """
        import numpy as np
        
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    async def delete_by_repository(self, repository_id: str) -> int:
        """Delete all chunks for a repository
        
        Args:
            repository_id: ID of repository to delete
            
        Returns:
            Number of deleted documents
        """
        db = Database.get_db()
        result = await db.chunks.delete_many({"repository_id": repository_id})
        return result.deleted_count
    
    async def count_chunks(self, repository_id: str) -> int:
        """Count total chunks for a repository
        
        Args:
            repository_id: ID of repository
            
        Returns:
            Number of chunks
        """
        db = Database.get_db()
        return await db.chunks.count_documents({"repository_id": repository_id})
    
    async def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a single chunk by ID
        
        Args:
            chunk_id: The chunk's MongoDB ObjectId as string
            
        Returns:
            Chunk document or None
        """
        from bson import ObjectId
        
        db = Database.get_db()
        
        try:
            chunk = await db.chunks.find_one({"_id": ObjectId(chunk_id)})
            if chunk:
                chunk["id"] = str(chunk.pop("_id"))
            return chunk
        except Exception:
            return None