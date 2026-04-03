from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import os


class Database:
    """Singleton database connection"""
    client: Optional[AsyncIOMotorClient] = None

    @classmethod
    async def connect(cls, connection_string: str):
        """Connect to MongoDB"""
        cls.client = AsyncIOMotorClient(connection_string)

    @classmethod
    def get_db(cls, database_name: str = "codebase_assistant"):
        """Get database instance"""
        if cls.client is None:
            raise RuntimeError("Database not connected. Call Database.connect() first")
        return cls.client[database_name]

    @classmethod
    async def disconnect(cls):
        """Disconnect from MongoDB"""
        if cls.client:
            cls.client.close()
            cls.client = None