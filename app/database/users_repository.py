"""
Users Repository - Secondary Adapter (Driven Adapter)

This module implements the outbound port for user data persistence,
providing MongoDB-based storage for user authentication data.

It follows the Hexagonal Architecture pattern, encapsulating all
infrastructure-specific details (Motor, bcrypt) within this adapter.
"""

from typing import Optional, Dict, Any
from pymongo import ASCENDING
import bcrypt
from app.database.mongo import get_database
from app.services.auth_service import UsersRepositoryProtocol
from loguru import logger


class UsersRepository(UsersRepositoryProtocol):
    """
    Repository for user data operations in MongoDB.
    
    Implements the UsersRepositoryProtocol for dependency injection
    into the authentication service.
    """
    
    COLLECTION_NAME = "users"
    
    def __init__(self) -> None:
        """Initialize the users repository."""
        self._indexes_ready = False
    
    @property
    def collection(self):
        """
        Obtain the users collection dynamically, ensuring DB is initialized.
        
        Returns:
            The MongoDB 'users' collection.
        """
        return get_database()[self.COLLECTION_NAME]
    
    async def ensure_indexes(self) -> None:
        """
        Create necessary indexes for the users collection.
        
        Indexes:
        - email (unique, case-insensitive)
        """
        if self._indexes_ready:
            return
        
        await self.collection.create_index(
            [("email", ASCENDING)],
            unique=True,
            collation={"locale": "en", "strength": 2},  # Case-insensitive
            name="email_unique_case_insensitive"
        )
        self._indexes_ready = True
        logger.info("Users collection indexes ensured.")
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a plain-text password using bcrypt.
        
        Args:
            password: Plain-text password to hash.
        
        Returns:
            Hashed password string.
        """
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    
    async def verify_password(
        self,
        plain_password: str,
        hashed_password: str,
    ) -> bool:
        """
        Verify a plain-text password against a stored hash.
        
        Args:
            plain_password: The plain-text password to verify.
            hashed_password: The bcrypt hash to verify against.
        
        Returns:
            True if the password matches, False otherwise.
        """
        try:
            password_bytes = plain_password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception:
            return False
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user document by email address (case-insensitive).
        
        Args:
            email: The email address to search for.
        
        Returns:
            User document dict if found, None otherwise.
        """
        await self.ensure_indexes()
        
        # Case-insensitive search using collation
        user = await self.collection.find_one(
            {"email": {"$regex": f"^{email}$", "$options": "i"}},
            collation={"locale": "en", "strength": 2}
        )
        
        if user is None:
            logger.debug(f"User not found for email: {email}")
        else:
            logger.debug(f"User found: {email}")
        
        return user
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user document by their MongoDB _id.
        
        Args:
            user_id: The string representation of the user's ObjectId.
        
        Returns:
            User document dict if found, None otherwise.
        """
        from bson import ObjectId
        from bson.errors import InvalidId
        
        await self.ensure_indexes()
        
        try:
            obj_id = ObjectId(user_id)
        except InvalidId:
            logger.warning(f"Invalid user ID format: {user_id}")
            return None
        
        return await self.collection.find_one({"_id": obj_id})
    
    async def create_user(
        self,
        email: str,
        password: str,
        name: str,
        role: str = "user",
    ) -> Optional[str]:
        """
        Create a new user document.
        
        Args:
            email: User's email address (will be normalized to lowercase).
            password: Plain-text password (will be hashed).
            name: User's display name.
            role: User's role (default: 'user').
        
        Returns:
            The string ID of the created user, or None if creation failed.
        """
        await self.ensure_indexes()
        
        password_hash = self.hash_password(password)
        
        doc = {
            "email": email.lower().strip(),
            "name": name.strip(),
            "passwordHash": password_hash,
            "role": role,
            "createdAt": self._get_utc_now_iso(),
        }
        
        try:
            result = await self.collection.insert_one(doc)
            logger.info(f"User created successfully: {email}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to create user {email}: {str(e)}")
            return None
    
    async def update_password(
        self,
        user_id: str,
        new_password: str,
    ) -> bool:
        """
        Update a user's password.
        
        Args:
            user_id: The string representation of the user's ObjectId.
            new_password: The new plain-text password.
        
        Returns:
            True if the password was updated, False otherwise.
        """
        from bson import ObjectId
        from bson.errors import InvalidId
        
        try:
            obj_id = ObjectId(user_id)
        except InvalidId:
            return False
        
        password_hash = self.hash_password(new_password)
        
        result = await self.collection.update_one(
            {"_id": obj_id},
            {"$set": {"passwordHash": password_hash, "updatedAt": self._get_utc_now_iso()}}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def _get_utc_now_iso() -> str:
        """Get current UTC time as ISO 8601 string."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()