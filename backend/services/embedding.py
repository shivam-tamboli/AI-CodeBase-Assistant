from openai import AsyncOpenAI
from typing import List
import os


class EmbeddingService:
    """Handles OpenAI embedding generation"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in .env")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "text-embedding-3-small"
        self.dimensions = 1536
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            1536-dimensional embedding vector
        """
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (batch processing)
        
        Args:
            texts: List of texts to generate embeddings for
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float"
        )
        
        return [item.embedding for item in response.data]
    
    async def generate_embedding_with_dimensions(self, text: str, dimensions: int = 1536) -> List[float]:
        """Generate embedding with custom dimensions (text-embedding-3-small supports 256-3072)
        
        Args:
            text: Text to generate embedding for
            dimensions: Number of dimensions (default 1536)
            
        Returns:
            Embedding vector with specified dimensions
        """
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=dimensions,
            encoding_format="float"
        )
        return response.data[0].embedding