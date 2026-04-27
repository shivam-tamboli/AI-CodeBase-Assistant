"""
Hybrid Search Service

Combines semantic search (vector similarity) and keyword search (exact matching)
using Reciprocal Rank Fusion (RRF) algorithm.

Phase 8: Hybrid Search Implementation
"""

from backend.services.vector_store import VectorStore
from backend.services.keyword_search import KeywordSearchService
from typing import List, Dict, Any, Optional
from collections import defaultdict
import hashlib


class HybridSearchService:
    """Combines semantic and keyword search for optimal results"""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.keyword_service = KeywordSearchService()
        self.k = 60  # RRF constant - stabilizes rankings
        self.max_results_per_search = 20
        self.default_limit = 10
    
    async def hybrid_search(
        self, 
        query: str, 
        repository_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining semantic and keyword methods
        
        Args:
            query: User search query
            repository_id: Repository to search in
            limit: Maximum results to return
            
        Returns:
            List of combined and ranked results
        """
        if not query or not query.strip():
            return []
        
        semantic_results = await self.vector_store.semantic_search(
            query, repository_id, limit=self.max_results_per_search
        )
        
        keyword_results = await self.keyword_service.keyword_search(
            query, repository_id, limit=self.max_results_per_search
        )
        
        combined = self._reciprocal_rank_fusion(semantic_results, keyword_results)
        
        reranked = self._rerank(combined, query)
        
        return reranked[:limit]
    
    def _reciprocal_rank_fusion(
        self, 
        semantic_results: List[Dict], 
        keyword_results: List[Dict]
    ) -> List[Dict]:
        """Combine rankings from both searches using RRF algorithm
        
        RRF_score = Σ (1 / (rank + k))
        Where k = 60 (constant that stabilizes rankings)
        
        Args:
            semantic_results: Results from vector search
            keyword_results: Results from keyword search
            
        Returns:
            Combined and sorted results
        """
        rrf_scores = defaultdict(float)
        doc_map = {}
        
        for rank, doc in enumerate(semantic_results):
            doc_id = self._get_doc_id(doc)
            rrf_scores[doc_id] += 1.0 / (rank + self.k)
            doc_map[doc_id] = doc
        
        for rank, doc in enumerate(keyword_results):
            doc_id = self._get_doc_id(doc)
            rrf_scores[doc_id] += 1.0 / (rank + self.k)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
        
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        results = []
        for doc_id, rrf_score in sorted_docs:
            doc = doc_map[doc_id]
            normalized_score = (rrf_score * self.k) / 2
            doc["hybrid_score"] = normalized_score
            doc["semantic_rank"] = self._get_rank(doc_id, semantic_results)
            doc["keyword_rank"] = self._get_rank(doc_id, keyword_results)
            results.append(doc)
        
        return results
    
    def _get_doc_id(self, doc: Dict) -> str:
        """Generate unique ID for a document
        
        Args:
            doc: Document dictionary
            
        Returns:
            Unique string identifier
        """
        metadata = doc.get("metadata", {})
        file_path = metadata.get("file_path", "")
        start_line = metadata.get("start_line", 0)
        end_line = metadata.get("end_line", 0)
        content = doc.get("content", "")[:100]
        
        id_string = f"{file_path}:{start_line}-{end_line}:{content}"
        return hashlib.md5(id_string.encode()).hexdigest()
    
    def _get_rank(self, doc_id: str, results: List[Dict]) -> Optional[int]:
        """Get rank of document in a list
        
        Args:
            doc_id: Document ID to find
            results: List of results
            
        Returns:
            Rank (1-based) or None if not found
        """
        for rank, doc in enumerate(results, 1):
            if self._get_doc_id(doc) == doc_id:
                return rank
        return None
    
    def _rerank(
        self, 
        results: List[Dict], 
        query: str
    ) -> List[Dict]:
        """Apply reranking with exact match bonus
        
        Args:
            results: Combined results from RRF
            query: Original search query
            
        Returns:
            Reranked results
        """
        query_terms = query.lower().split()
        
        for doc in results:
            bonus = 0.0
            content = doc.get("content", "").lower()
            metadata = doc.get("metadata", {})
            name = metadata.get("name", "").lower()
            
            for term in query_terms:
                if len(term) < 3:
                    continue
                
                if term in name:
                    bonus += 0.2
                
                if term in content:
                    term_count = content.count(term)
                    if term_count > 0:
                        bonus += min(0.1 * min(term_count, 5), 0.3)
            
            doc["hybrid_score"] = doc.get("hybrid_score", 0) + bonus
        
        return sorted(results, key=lambda x: x.get("hybrid_score", 0), reverse=True)
    
    async def search_with_filters(
        self,
        query: str,
        repository_id: str,
        chunk_type: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Hybrid search with additional filters
        
        Args:
            query: Search query
            repository_id: Repository ID
            chunk_type: Filter by function/class/imports
            file_path: Filter by specific file
            limit: Max results
            
        Returns:
            Filtered and ranked results
        """
        results = await self.hybrid_search(query, repository_id, limit=limit * 2)
        
        filtered = []
        for doc in results:
            metadata = doc.get("metadata", {})
            
            if chunk_type and metadata.get("chunk_type") != chunk_type:
                continue
            
            if file_path:
                doc_path = metadata.get("file_path", "")
                if file_path.lower() not in doc_path.lower():
                    continue
            
            filtered.append(doc)
        
        return filtered[:limit]
    
    async def get_search_stats(
        self,
        query: str,
        repository_id: str
    ) -> Dict[str, Any]:
        """Get statistics about search results
        
        Args:
            query: Search query
            repository_id: Repository ID
            
        Returns:
            Dictionary with search statistics
        """
        semantic_results = await self.vector_store.semantic_search(
            query, repository_id, limit=self.max_results_per_search
        )
        
        keyword_results = await self.keyword_service.keyword_search(
            query, repository_id, limit=self.max_results_per_search
        )
        
        semantic_doc_ids = {self._get_doc_id(d) for d in semantic_results}
        keyword_doc_ids = {self._get_doc_id(d) for d in keyword_results}
        overlap = semantic_doc_ids & keyword_doc_ids
        
        return {
            "query": query,
            "semantic_results_count": len(semantic_results),
            "keyword_results_count": len(keyword_results),
            "overlap_count": len(overlap),
            "overlap_percentage": (
                len(overlap) / max(len(semantic_results), 1) * 100
            )
        }