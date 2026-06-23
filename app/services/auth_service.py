"""
Authentication Service - Application Core

This module contains the pure business logic for authentication.
It follows the Hexagonal Architecture pattern, defining inbound ports
and implementing use cases that are independent of external frameworks.

Dependencies:
- No direct imports from infrastructure libraries (motor, bcrypt, etc.)
- All external I/O is delegated to outbound ports (repositories)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr
import os


# =============================================================================
# Pydantic Models (Domain Data Transfer Objects)
# =============================================================================

class User(BaseModel):
    """Domain model representing an authenticated user."""
    id: str
    email: EmailStr
    name: str
    role: str = "user"


class TokenPayload(BaseModel):
    """JWT token payload structure."""
    sub: str  # user_id
    email: str
    name: str
    role: str
    exp: datetime


class AuthResult(BaseModel):
    """Result of an authentication attempt."""
    success: bool
    user: Optional[User] = None
    token: Optional[str] = None
    message: Optional[str] = None


# =============================================================================
# Configuration (Environment-based)
# =============================================================================

def _get_auth_config() -> tuple[str, str, int]:
    """
    Load authentication configuration from environment variables.
    
    Returns:
        Tuple of (auth_secret, algorithm, token_expire_hours)
    
    Note:
        In production, AUTH_SECRET should always be set. A development fallback
        is provided only for local testing.
    """
    secret = os.getenv("AUTH_SECRET")
    environment = os.getenv("ENVIRONMENT", "development")
    
    if not secret:
        if environment == "production":
            raise ValueError(
                "AUTH_SECRET environment variable is not set. "
                "Please configure it in your .env.local file."
            )
        # Development fallback - use a deterministic secret
        secret = "dev-only-insecure-secret-do-not-use-in-production"
    
    algorithm = os.getenv("AUTH_JWT_ALGORITHM", "HS256")
    expire_hours = int(os.getenv("AUTH_TOKEN_EXPIRE_HOURS", "24"))
    return secret, algorithm, expire_hours


# =============================================================================
# Token Management (Pure Functions)
# =============================================================================

def create_access_token(
    user_id: str,
    email: str,
    name: str,
    role: str,
) -> str:
    """
    Create a JWT access token for a user.
    
    Args:
        user_id: Unique identifier for the user.
        email: User's email address.
        name: User's display name.
        role: User's role (e.g., 'admin', 'user').
    
    Returns:
        Encoded JWT token string.
    """
    secret, algorithm, expire_hours = _get_auth_config()
    
    expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    
    return jwt.encode(payload, secret, algorithm=algorithm)


def verify_token(token: str) -> Optional[TokenPayload]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token string to verify.
    
    Returns:
        TokenPayload if valid, None if invalid or expired.
    """
    secret, algorithm, _ = _get_auth_config()
    
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return TokenPayload(
            sub=payload["sub"],
            email=payload["email"],
            name=payload["name"],
            role=payload["role"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except JWTError:
        return None


# =============================================================================
# Authentication Service (Inbound Port Implementation)
# =============================================================================

class AuthService:
    """
    Authentication service implementing the inbound port for auth operations.
    
    This service orchestrates the authentication workflow using the users
    repository to verify credentials and generate tokens.
    """
    
    def __init__(self, users_repository: "UsersRepositoryProtocol") -> None:
        """
        Initialize the auth service with a users repository.
        
        Args:
            users_repository: The outbound port for user data access.
        """
        self._users_repo = users_repository
    
    async def authenticate(
        self,
        email: str,
        password: str,
    ) -> AuthResult:
        """
        Authenticate a user with email and password.
        
        Args:
            email: User's email address.
            password: User's plain-text password.
        
        Returns:
            AuthResult with success status, user data, and token if successful.
        """
        # Step 1: Retrieve user by email (case-insensitive)
        user_data = await self._users_repo.get_user_by_email(email)
        
        if user_data is None:
            return AuthResult(
                success=False,
                message="Credenciales inválidas",
            )
        
        # Step 2: Verify password against stored hash
        if not await self._users_repo.verify_password(password, user_data["passwordHash"]):
            return AuthResult(
                success=False,
                message="Credenciales inválidas",
            )
        
        # Step 3: Authentication successful - generate token
        token = create_access_token(
            user_id=str(user_data["_id"]),
            email=user_data["email"],
            name=user_data["name"],
            role=user_data["role"],
        )
        
        user = User(
            id=str(user_data["_id"]),
            email=user_data["email"],
            name=user_data["name"],
            role=user_data["role"],
        )
        
        return AuthResult(
            success=True,
            user=user,
            token=token,
        )


# =============================================================================
# Type Protocol for Dependency Injection
# =============================================================================

class UsersRepositoryProtocol:
    """
    Protocol defining the contract for user data access.
    
    This allows for easy mocking in tests and maintains loose coupling
    between the auth service and the actual repository implementation.
    """
    
    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Retrieve a user document by email (case-insensitive)."""
        ...
    
    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password."""
        ...