"""
RAG Pipeline Service

Orchestrates the complete Retrieval Augmented Generation pipeline:
- Ingestion: Upload → Scan → Parse → Chunk → Embed → Store
- Query: Query → Search → Generate → Response

Phase 10: End-to-End RAG Pipeline
Phase 12: Added session/history support
"""

import logging
import time
from typing import Dict, Any, List, Optional

from app.services.processor import RepositoryProcessor
from app.services.hybrid_search import HybridSearchService
from app.services.llm_service import LLMService
from app.services.chat_service import ChatService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Orchestrates the complete RAG pipeline.
    
    Coordinates between:
    - RepositoryProcessor (ingestion)
    - HybridSearchService (retrieval)
    - LLMService (generation)
    """
    
    def __init__(self):
        self.processor = RepositoryProcessor()
        self.search_service = HybridSearchService()
        self.llm_service = LLMService()
        self.chat_service = ChatService()
        logger.info("RAGPipeline initialized")
    
    async def ingest_repository(
        self,
        repository_id: str,
        local_path: str
    ) -> Dict[str, Any]:
        """
        Ingestion pipeline: Process and index a repository.
        
        Flow: Upload → Scan → Parse → Chunk → Embed → Store
        
        Args:
            repository_id: ID of the repository in MongoDB
            local_path: Local path to the repository
            
        Returns:
            Processing summary with stats
        """
        start_time = time.time()
        logger.info(f"Starting ingestion for repository: {repository_id}")
        
        try:
            logger.info(f"Stage 1/4: Processing files...")
            result = await self.processor.process_repository(
                repository_id, local_path
            )
            
            if result["status"] == "success":
                elapsed = time.time() - start_time
                logger.info(f"Stage 2/4: Files processed successfully")
                logger.info(f"Stage 3/4: Chunks created: {result.get('chunks_created', 0)}")
                logger.info(f"Stage 4/4: Embeddings generated and stored")
                
                return {
                    "status": "success",
                    "repository_id": repository_id,
                    "files_processed": result.get("files_processed", 0),
                    "chunks_created": result.get("chunks_created", 0),
                    "processing_time_seconds": round(elapsed, 2)
                }
            else:
                logger.error(f"Ingestion failed: {result.get('message', 'Unknown error')}")
                return {
                    "status": "error",
                    "repository_id": repository_id,
                    "error": result.get("message", "Processing failed")
                }
                
        except Exception as e:
            logger.error(f"Ingestion pipeline error: {str(e)}")
            return {
                "status": "error",
                "repository_id": repository_id,
                "error": str(e)
            }
    
    async def query(
        self,
        question: str,
        repository_id: str,
        limit: int = 5,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query pipeline: Answer a question about the codebase.
        
        Flow: Query → Hybrid Search → LLM Generate → Response
        
        Args:
            question: User's question
            repository_id: Repository to query
            limit: Number of code chunks to retrieve
            session_id: Optional session ID for conversation history
            
        Returns:
            Answer with source citations
        """
        start_time = time.time()
        logger.info(f"Processing query for repository: {repository_id}")
        logger.info(f"Question: {question[:100]}...")
        
        try:
            if not question or not question.strip():
                logger.warning("Empty query received")
                return {
                    "status": "error",
                    "answer": "Please provide a valid question.",
                    "sources": []
                }
            
            chat_history = []
            if session_id:
                logger.info(f"Fetching chat history for session: {session_id}")
                chat_history = await self.chat_service.get_session_history(
                    session_id, limit=10
                )
                if chat_history:
                    logger.info(f"Using {len(chat_history)} previous messages for context")
            
            logger.info(f"Stage 1/3: Performing hybrid search...")
            search_results = await self.search_service.hybrid_search(
                question, repository_id, limit=limit
            )
            
            if not search_results:
                logger.info("No relevant code chunks found")
                return {
                    "status": "success",
                    "answer": "No relevant code found for your question. Try rephrasing or asking about a different aspect of the codebase.",
                    "sources": [],
                    "chunks_found": 0,
                    "session_id": session_id
                }
            
            logger.info(f"Stage 2/3: Found {len(search_results)} relevant chunks")
            
            logger.info(f"Stage 3/3: Generating answer with LLM...")
            llm_result = await self.llm_service.generate_answer(
                question, search_results, chat_history=chat_history
            )
            
            elapsed = time.time() - start_time
            logger.info(f"Query completed in {round(elapsed, 2)} seconds")
            
            sources = []
            for chunk in search_results:
                metadata = chunk.get("metadata", {})
                sources.append({
                    "file_path": metadata.get("file_path", ""),
                    "start_line": metadata.get("start_line", 0),
                    "end_line": metadata.get("end_line", 0),
                    "chunk_type": metadata.get("chunk_type", "code"),
                    "name": metadata.get("name", ""),
                    "score": chunk.get("final_score", chunk.get("hybrid_score", 0))
                })
            
            return {
                "status": "success",
                "answer": llm_result.get("answer", ""),
                "sources": sources,
                "chunks_found": len(search_results),
                "processing_time_seconds": round(elapsed, 2),
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Query pipeline error: {str(e)}")
            return {
                "status": "error",
                "answer": f"Error processing your question: {str(e)}",
                "sources": [],
                "chunks_found": 0,
                "session_id": session_id
            }
    
    async def query_with_streaming(
        self,
        question: str,
        repository_id: str,
        limit: int = 5,
        session_id: Optional[str] = None
    ):
        """
        Query pipeline with streaming response.
        
        Args:
            question: User's question
            repository_id: Repository to query
            limit: Number of code chunks to retrieve
            session_id: Optional session ID for conversation history
            
        Yields:
            Streaming response tokens
        """
        logger.info(f"Starting streaming query for repository: {repository_id}")
        
        try:
            chat_history = []
            if session_id:
                chat_history = await self.chat_service.get_session_history(
                    session_id, limit=10
                )
            
            search_results = await self.search_service.hybrid_search(
                question, repository_id, limit=limit
            )
            
            if not search_results:
                yield {
                    "type": "done",
                    "answer": "No relevant code found for your question.",
                    "sources": []
                }
                return
            
            async for chunk in self.llm_service.generate_streaming_answer(
                question, search_results, chat_history=chat_history
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"Streaming query error: {str(e)}")
            yield {
                "type": "error",
                "answer": f"Error: {str(e)}",
                "error": str(e)
            }
    
    async def get_repository_stats(self, repository_id: str) -> Dict[str, Any]:
        """
        Get statistics for a repository.
        
        Args:
            repository_id: Repository ID
            
        Returns:
            Statistics dictionary
        """
        try:
            stats = await self.processor.get_repository_stats(repository_id)
            logger.info(f"Retrieved stats for repository: {repository_id}")
            return {
                "status": "success",
                **stats
            }
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def reprocess_repository(
        self,
        repository_id: str,
        local_path: str
    ) -> Dict[str, Any]:
        """
        Reprocess a repository (clears existing data first).
        
        Args:
            repository_id: Repository ID
            local_path: Local path to repository
            
        Returns:
            Processing summary
        """
        logger.info(f"Reprocessing repository: {repository_id}")
        
        try:
            result = await self.processor.reprocess_repository(
                repository_id, local_path
            )
            
            if result["status"] == "success":
                logger.info(f"Reprocessing complete: {result.get('chunks_created')} chunks created")
            else:
                logger.error(f"Reprocessing failed: {result.get('message')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Reprocessing error: {str(e)}")
            return {
                "status": "error",
                "repository_id": repository_id,
                "error": str(e)
            }
    
    async def delete_repository(self, repository_id: str) -> Dict[str, Any]:
        """
        Delete all data for a repository.
        
        Args:
            repository_id: Repository ID
            
        Returns:
            Deletion summary
        """
        logger.info(f"Deleting repository data: {repository_id}")
        
        try:
            deleted_count = await self.processor.delete_repository_data(repository_id)
            logger.info(f"Deleted {deleted_count} chunks for repository: {repository_id}")
            
            return {
                "status": "success",
                "repository_id": repository_id,
                "chunks_deleted": deleted_count
            }
            
        except Exception as e:
            logger.error(f"Deletion error: {str(e)}")
            return {
                "status": "error",
                "repository_id": repository_id,
                "error": str(e)
            }
