from backend.database import Database
from backend.services.embedding import EmbeddingService
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages vector storage and semantic search in MongoDB"""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.index_name = "vector_search_index"

    async def ensure_indexes(self):
        """Create standard MongoDB indexes on the chunks collection.

        Note: The Atlas Vector Search index (HNSW, 1536 dims, cosine) must be
        created manually in the MongoDB Atlas UI or via the Atlas Admin API.
        Motor cannot create search indexes programmatically.

        Required Atlas index configuration:
          - Index name: vector_search_index
          - Field: embedding  (type: vector, dimensions: 1536, similarity: cosine)
          - Filter field: repository_id  (type: filter)
        """
        db = Database.get_db()

        try:
            existing_indexes = db.chunks.list_indexes()
            existing_names = [idx.get("name") for idx in await existing_indexes.to_list(None)]

            if "repository_id_1" not in existing_names:
                await db.chunks.create_index([("repository_id", 1)])
                logger.info("Created index: repository_id_1")

        except Exception as e:
            logger.warning("Index creation warning: %s", e)

    async def add_chunks(self, chunks: List[Dict[str, Any]], repository_id: str) -> int:
        """Embed and store code chunks in MongoDB."""
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
                    "token_count": chunk.get("token_count", 0),
                    "file_hash": chunk.get("file_hash", "")
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
        """Return the top-k most similar chunks for a query.

        Attempts MongoDB Atlas $vectorSearch first (O(log n) HNSW).
        Falls back to in-memory cosine similarity when the Atlas vector
        index is not configured (e.g., local MongoDB or missing index).
        """
        logger.info("[Semantic Search] Generating query embedding...")
        query_embedding = await self.embedding_service.generate_embedding(query)

        db = Database.get_db()

        try:
            results = await self._atlas_vector_search(query_embedding, repository_id, limit, db)
            logger.info("[Semantic Search] Atlas Vector Search returned %d results", len(results))
            return results
        except Exception as e:
            logger.warning(
                "[Semantic Search] Atlas Vector Search unavailable (%s), using in-memory fallback", e
            )
            return await self._in_memory_search(query_embedding, repository_id, limit, db)

    async def _atlas_vector_search(
        self,
        query_embedding: List[float],
        repository_id: str,
        limit: int,
        db
    ) -> List[Dict[str, Any]]:
        """Run $vectorSearch aggregation pipeline on MongoDB Atlas."""
        num_candidates = min(limit * 15, 150)

        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.index_name,
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": num_candidates,
                    "limit": limit,
                    "filter": {"repository_id": repository_id}
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        results = await db.chunks.aggregate(pipeline).to_list(limit)
        return results

    async def _in_memory_search(
        self,
        query_embedding: List[float],
        repository_id: str,
        limit: int,
        db
    ) -> List[Dict[str, Any]]:
        """Compute cosine similarity in Python across all repository chunks."""
        import numpy as np

        chunks = await db.chunks.find({"repository_id": repository_id}).to_list(None)

        if not chunks:
            return []

        logger.info("[Semantic Search] In-memory cosine over %d chunks", len(chunks))

        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)

        scored = []
        for chunk in chunks:
            chunk_embedding = chunk.get("embedding")
            if not chunk_embedding:
                continue

            chunk_vec = np.array(chunk_embedding)
            chunk_norm = np.linalg.norm(chunk_vec)

            if query_norm == 0 or chunk_norm == 0:
                similarity = 0.0
            else:
                similarity = float(np.dot(query_vec, chunk_vec) / (query_norm * chunk_norm))

            scored.append({**chunk, "score": similarity})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    async def delete_by_repository(self, repository_id: str) -> int:
        """Delete all chunks for a repository."""
        db = Database.get_db()
        result = await db.chunks.delete_many({"repository_id": repository_id})
        return result.deleted_count

    async def count_chunks(self, repository_id: str) -> int:
        """Count total chunks for a repository."""
        db = Database.get_db()
        return await db.chunks.count_documents({"repository_id": repository_id})

    async def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a single chunk by ID."""
        from bson import ObjectId

        db = Database.get_db()

        try:
            chunk = await db.chunks.find_one({"_id": ObjectId(chunk_id)})
            if chunk:
                chunk["id"] = str(chunk.pop("_id"))
            return chunk
        except Exception:
            return None
