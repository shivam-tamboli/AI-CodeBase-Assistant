from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class Database:
    """Singleton database connection"""
    client: Optional[AsyncIOMotorClient] = None
    _database_name: str = "ragdb"

    @classmethod
    async def connect(cls, connection_string: str):
        """Connect to MongoDB with logging"""
        try:
            # Fix SSL certificate issue on macOS
            if "ssl" not in connection_string.lower():
                if "?retryWrites" in connection_string:
                    connection_string = connection_string.replace("?retryWrites=true&w=majority", 
                                              "?retryWrites=true&w=majority&ssl=true&tlsAllowInvalidCertificates=true")
                else:
                    connection_string += "?ssl=true&tlsAllowInvalidCertificates=true"
            
            cls.client = AsyncIOMotorClient(connection_string)
            
            if "/ragdb?" in connection_string:
                cls._database_name = "ragdb"
            elif "?retryWrites" in connection_string:
                start = connection_string.find("mongodb+srv://")
                end = connection_string.find("?")
                if start != -1 and end != -1:
                    cluster_part = connection_string[start:end]
                    if "/" in cluster_part:
                        cls._database_name = cluster_part.split("/")[-1]
            
            await cls.client.admin.command('ping')
            logger.info(f"✓ MongoDB connected successfully to database: {cls._database_name}")
            print(f"✓ MongoDB connected successfully to database: {cls._database_name}")
        except Exception as e:
            logger.error(f"✗ MongoDB connection failed: {e}")
            raise

    @classmethod
    def get_db(cls, database_name: str = None):
        """Get database instance"""
        if cls.client is None:
            raise RuntimeError("Database not connected. Call Database.connect() first")
        db_name = database_name or cls._database_name
        return cls.client[db_name]

    @classmethod
    async def disconnect(cls):
        """Disconnect from MongoDB"""
        if cls.client:
            cls.client.close()
            cls.client = None
            logger.info("MongoDB disconnected")