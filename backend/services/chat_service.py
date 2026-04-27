"""
Chat Service

Handles session management and chat history persistence in MongoDB.

Phase 12: Chat Memory & Session Management
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId

from backend.database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChatService:
    """Handles chat session CRUD operations with MongoDB"""

    COLLECTION_NAME = "chat_sessions"

    @classmethod
    async def _get_collection(cls):
        """Get the chat sessions collection"""
        db = Database.get_db()
        return db[cls.COLLECTION_NAME]

    @classmethod
    async def create_session(
        cls,
        repository_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new chat session.

        Args:
            repository_id: ID of the repository to chat about
            user_id: Optional user ID for multi-user support

        Returns:
            Created session with ID
        """
        logger.info(f"Creating chat session for repo: {repository_id}")

        collection = await cls._get_collection()

        session_doc = {
            "user_id": user_id,
            "repository_id": repository_id,
            "messages": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await collection.insert_one(session_doc)
        session_id = str(result.inserted_id)

        logger.info(f"Created session: {session_id}")

        return {
            "status": "success",
            "session_id": session_id,
            "repository_id": repository_id,
            "user_id": user_id,
            "created_at": session_doc["created_at"]
        }

    @classmethod
    async def add_message(
        cls,
        session_id: str,
        role: str,
        content: str,
        tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Add a message to an existing session.

        Args:
            session_id: Session ID to add message to
            role: 'user' or 'assistant'
            content: Message content
            tokens: Optional token count

        Returns:
            Updated session info
        """
        logger.info(f"Adding {role} message to session: {session_id}")

        collection = await cls._get_collection()

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
            "tokens": tokens
        }

        result = await collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        if result.matched_count == 0:
            logger.warning(f"Session not found: {session_id}")
            return {
                "status": "error",
                "error": "Session not found"
            }

        logger.info(f"Message added to session: {session_id}")
        return {
            "status": "success",
            "session_id": session_id,
            "message_added": True
        }

    @classmethod
    async def get_session(
        cls,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID to retrieve

        Returns:
            Session data or None if not found
        """
        logger.info(f"Retrieving session: {session_id}")

        collection = await cls._get_collection()

        try:
            session = await collection.find_one({"_id": ObjectId(session_id)})

            if not session:
                logger.warning(f"Session not found: {session_id}")
                return None

            return {
                "id": str(session["_id"]),
                "user_id": session.get("user_id"),
                "repository_id": session["repository_id"],
                "messages": session.get("messages", []),
                "created_at": session["created_at"],
                "updated_at": session.get("updated_at"),
                "message_count": len(session.get("messages", []))
            }

        except Exception as e:
            logger.error(f"Error retrieving session: {str(e)}")
            return None

    @classmethod
    async def get_session_history(
        cls,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages from a session.

        Args:
            session_id: Session ID
            limit: Maximum number of messages to retrieve (default 20)

        Returns:
            List of recent messages
        """
        logger.info(f"Getting history for session: {session_id}, limit: {limit}")

        session = await cls.get_session(session_id)

        if not session:
            return []

        messages = session.get("messages", [])
        recent_messages = messages[-limit:] if limit > 0 else messages

        logger.info(f"Retrieved {len(recent_messages)} messages from session")
        return recent_messages

    @classmethod
    async def delete_session(cls, session_id: str) -> Dict[str, Any]:
        """
        Delete a chat session.

        Args:
            session_id: Session ID to delete

        Returns:
            Deletion result
        """
        logger.info(f"Deleting session: {session_id}")

        collection = await cls._get_collection()

        try:
            result = await collection.delete_one({"_id": ObjectId(session_id)})

            if result.deleted_count == 0:
                logger.warning(f"Session not found for deletion: {session_id}")
                return {
                    "status": "error",
                    "error": "Session not found"
                }

            logger.info(f"Deleted session: {session_id}")
            return {
                "status": "success",
                "session_id": session_id,
                "deleted": True
            }

        except Exception as e:
            logger.error(f"Error deleting session: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    @classmethod
    async def list_user_sessions(
        cls,
        user_id: Optional[str] = None,
        repository_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List sessions, optionally filtered by user or repository.

        Args:
            user_id: Filter by user ID
            repository_id: Filter by repository ID
            limit: Maximum sessions to return

        Returns:
            List of sessions
        """
        logger.info(f"Listing sessions - user: {user_id}, repo: {repository_id}")

        collection = await cls._get_collection()

        query = {}
        if user_id:
            query["user_id"] = user_id
        if repository_id:
            query["repository_id"] = repository_id

        cursor = collection.find(query).sort("updated_at", -1).limit(limit)

        sessions = []
        async for session in cursor:
            sessions.append({
                "id": str(session["_id"]),
                "user_id": session.get("user_id"),
                "repository_id": session["repository_id"],
                "created_at": session["created_at"],
                "updated_at": session.get("updated_at"),
                "message_count": len(session.get("messages", []))
            })

        logger.info(f"Found {len(sessions)} sessions")
        return sessions
