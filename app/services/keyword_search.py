from app.database import Database
from typing import List, Dict, Any, Optional
import re


class KeywordSearchService:
    """Handles keyword-based search in MongoDB using text indexes"""
    
    CONTENT_INDEX_NAME = "content_text_index"
    METADATA_NAME_INDEX = "metadata_name_text_index"
    
    async def ensure_indexes(self):
        """Create text indexes on code_chunks collection if they don't exist"""
        db = Database.get_db()
        
        try:
            existing_indexes = await db.code_chunks.list_indexes()
            existing_names = [idx.get("name") for idx in await existing_indexes.to_list(None)]
            
            if self.CONTENT_INDEX_NAME not in existing_names:
                await db.code_chunks.create_index(
                    [("content", "text")],
                    default_language="english",
                    name=self.CONTENT_INDEX_NAME
                )
                print(f"Created text index: {self.CONTENT_INDEX_NAME}")
            
            if self.METADATA_NAME_INDEX not in existing_names:
                await db.code_chunks.create_index(
                    [("metadata.name", "text")],
                    default_language="english",
                    name=self.METADATA_NAME_INDEX
                )
                print(f"Created text index: {self.METADATA_NAME_INDEX}")
                
        except Exception as e:
            print(f"Index creation warning: {e}")
    
    async def keyword_search(
        self, 
        query: str, 
        repository_id: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for exact keyword matches using MongoDB text search
        
        Args:
            query: Search query string
            repository_id: ID of repository to search in
            limit: Maximum number of results
            
        Returns:
            List of matching code chunks with relevance scores
        """
        if not query or not query.strip():
            return []
        
        db = Database.get_db()
        
        sanitized_query = self._sanitize_query(query)
        
        pipeline = [
            {
                "$match": {
                    "repository_id": repository_id,
                    "$text": {"$search": sanitized_query}
                }
            },
            {
                "$addFields": {
                    "textScore": {"$meta": "textScore"}
                }
            },
            {
                "$sort": {"textScore": -1}
            },
            {
                "$limit": limit
            },
            {
                "$project": {
                    "content": 1,
                    "metadata": 1,
                    "textScore": 1
                }
            }
        ]
        
        results = await db.code_chunks.aggregate(pipeline).to_list(limit)
        return results
    
    async def search_by_file_path(
        self, 
        file_path: str, 
        repository_id: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for chunks in a specific file
        
        Args:
            file_path: File path to search for
            repository_id: Repository ID
            limit: Maximum results
            
        Returns:
            List of matching chunks
        """
        db = Database.get_db()
        
        pipeline = [
            {
                "$match": {
                    "repository_id": repository_id,
                    "metadata.file_path": {"$regex": file_path, "$options": "i"}
                }
            },
            {
                "$limit": limit
            },
            {
                "$project": {
                    "content": 1,
                    "metadata": 1
                }
            }
        ]
        
        results = await db.code_chunks.aggregate(pipeline).to_list(limit)
        return results
    
    async def search_function_names(
        self, 
        function_name: str, 
        repository_id: str
    ) -> List[Dict[str, Any]]:
        """Search for specific function by exact name
        
        Args:
            function_name: Name of function to find
            repository_id: Repository ID
            
        Returns:
            List of matching chunks
        """
        db = Database.get_db()
        
        pipeline = [
            {
                "$match": {
                    "repository_id": repository_id,
                    "metadata.name": function_name,
                    "metadata.chunk_type": "function"
                }
            },
            {
                "$project": {
                    "content": 1,
                    "metadata": 1
                }
            }
        ]
        
        results = await db.code_chunks.aggregate(pipeline).to_list(50)
        return results
    
    async def search_class_names(
        self, 
        class_name: str, 
        repository_id: str
    ) -> List[Dict[str, Any]]:
        """Search for specific class by exact name
        
        Args:
            class_name: Name of class to find
            repository_id: Repository ID
            
        Returns:
            List of matching chunks
        """
        db = Database.get_db()
        
        pipeline = [
            {
                "$match": {
                    "repository_id": repository_id,
                    "metadata.name": class_name,
                    "metadata.chunk_type": "class"
                }
            },
            {
                "$project": {
                    "content": 1,
                    "metadata": 1
                }
            }
        ]
        
        results = await db.code_chunks.aggregate(pipeline).to_list(50)
        return results
    
    async def search_exact_phrase(
        self, 
        phrase: str, 
        repository_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for exact phrase (quoted string)
        
        Args:
            phrase: Exact phrase to search for
            repository_id: Repository ID
            limit: Maximum results
            
        Returns:
            List of matching chunks
        """
        if not phrase:
            return []
        
        db = Database.get_db()
        
        quoted_phrase = f'"{phrase}"'
        
        pipeline = [
            {
                "$match": {
                    "repository_id": repository_id,
                    "$text": {"$search": quoted_phrase}
                }
            },
            {
                "$addFields": {
                    "textScore": {"$meta": "textScore"}
                }
            },
            {
                "$sort": {"textScore": -1}
            },
            {
                "$limit": limit
            },
            {
                "$project": {
                    "content": 1,
                    "metadata": 1,
                    "textScore": 1
                }
            }
        ]
        
        results = await db.code_chunks.aggregate(pipeline).to_list(limit)
        return results
    
    def _sanitize_query(self, query: str) -> str:
        """Sanitize search query to prevent injection and handle special chars
        
        Args:
            query: Raw query string
            
        Returns:
            Sanitized query
        """
        query = query.strip()
        
        query = re.sub(r'[^\w\s\-\.\:]', ' ', query)
        
        query = re.sub(r'\s+', ' ', query)
        
        return query
    
    async def get_search_suggestions(
        self, 
        prefix: str, 
        repository_id: str, 
        limit: int = 10
    ) -> List[str]:
        """Get function/class name suggestions based on prefix
        
        Args:
            prefix: Prefix to search for
            repository_id: Repository ID
            limit: Maximum suggestions
            
        Returns:
            List of matching names
        """
        db = Database.get_db()
        
        pipeline = [
            {
                "$match": {
                    "repository_id": repository_id,
                    "metadata.name": {"$regex": f"^{prefix}", "$options": "i"}
                }
            },
            {
                "$group": {
                    "_id": "$metadata.name"
                }
            },
            {
                "$limit": limit
            }
        ]
        
        results = await db.code_chunks.aggregate(pipeline).to_list(limit)
        return [r["_id"] for r in results]