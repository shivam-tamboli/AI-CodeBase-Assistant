from app.database import Database
from app.services.embedding import EmbeddingService
from typing import List, Dict, Any, Optional
import os


class VectorStore:
    """Manages vector storage and semantic search in MongoDB"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.index_name = "vector_search_index"
    
    async def ensure_indexes(self):
        """Create vector search index on code_chunks collection if it doesn't exist"""
        db = Database.get_db()
        
        try:
            existing_indexes = await db.code_chunks.list_indexes()
            existing_names = [idx.get("name") for idx in await existing_indexes.to_list(None)]
            
            if self.index_name not in existing_names:
                await db.code_chunks.create_index(
                    [("embedding", "vectorSearchIndex")],
                    vectorSearchIndex={
                        "type": "cosine",
                        "dimensions": 1536,
                        "numCandidates": 100
                    },
                    name=self.index_name
                )
                print(f"Created vector search index: {self.index_name}")
            else:
                print(f"Vector search index already exists: {self.index_name}")
                
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
            result = await db.code_chunks.insert_many(documents)
            return len(result.inserted_ids)
        
        return 0
    
    async def semantic_search(
        self, 
        query: str, 
        repository_id: str, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar code using vector similarity
        
        Args:
            query: User query string
            repository_id: ID of repository to search in
            limit: Maximum number of results
            
        Returns:
            List of relevant code chunks with scores
        """
        query_embedding = await self.embedding_service.generate_embedding(query)
        
        db = Database.get_db()
        
        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.index_name,
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 100,
                    "limit": limit
                }
            },
            {
                "$match": {
                    "repository_id": repository_id
                }
            },
            {
                "$project": {
                    "content": 1,
                    "metadata": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        
        results = await db.code_chunks.aggregate(pipeline).to_list(limit)
        return results
    
    async def delete_by_repository(self, repository_id: str) -> int:
        """Delete all chunks for a repository
        
        Args:
            repository_id: ID of repository to delete
            
        Returns:
            Number of deleted documents
        """
        db = Database.get_db()
        result = await db.code_chunks.delete_many({"repository_id": repository_id})
        return result.deleted_count
    
    async def count_chunks(self, repository_id: str) -> int:
        """Count total chunks for a repository
        
        Args:
            repository_id: ID of repository
            
        Returns:
            Number of chunks
        """
        db = Database.get_db()
        return await db.code_chunks.count_documents({"repository_id": repository_id})
    
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
            chunk = await db.code_chunks.find_one({"_id": ObjectId(chunk_id)})
            if chunk:
                chunk["id"] = str(chunk.pop("_id"))
            return chunk
        except Exception:
            return None