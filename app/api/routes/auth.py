"""
Authentication Router - FastAPI Driving Adapter

This module defines the API endpoints for authentication,
implementing the POST /api/auth/login and POST /api/auth/logout routes.

Following Hexagonal Architecture, this router acts as the driving adapter,
receiving HTTP requests and delegating business logic to the auth service.
"""

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.services.auth_service import AuthService
from app.database.users_repository import UsersRepository
from loguru import logger


# =============================================================================
# Pydantic Request/Response Models
# =============================================================================

class LoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Response model for user data in login success."""
    name: str
    email: EmailStr
    role: str = "user"


class LoginSuccessResponse(BaseModel):
    """Response model for successful login."""
    success: bool = True
    user: UserResponse


class LogoutResponse(BaseModel):
    """Response model for successful logout."""
    success: bool = True
    message: str = "Logout successful"


class ErrorResponse(BaseModel):
    """Response model for authentication errors."""
    error: str = "Unauthorized"
    message: str


# =============================================================================
# Router Definition
# =============================================================================

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Service instance (lazy initialization per request for proper dependency scope)
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """
    Get or create the authentication service instance.
    
    Using a factory function ensures proper lifecycle management
    and allows for future dependency injection frameworks.
    """
    global _auth_service
    if _auth_service is None:
        users_repo = UsersRepository()
        _auth_service = AuthService(users_repo)
    return _auth_service


# =============================================================================
# Authentication Endpoints
# =============================================================================

@router.post(
    "/login",
    response_model=LoginSuccessResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
    },
)
async def login(request: LoginRequest, response: Response) -> LoginSuccessResponse:
    """
    Authenticate a user and set an HttpOnly auth_session cookie.
    
    This endpoint:
    1. Validates the email and password.
    2. Verifies credentials against the database.
    3. Generates a JWT token on success.
    4. Sets an HttpOnly secure cookie with the token.
    
    Args:
        request: Login credentials (email, password).
        response: FastAPI Response object for setting cookies.
    
    Returns:
        LoginSuccessResponse with user data on success.
    
    Raises:
        HTTPException 401: If credentials are invalid.
    """
    logger.info(f"Login attempt for email: {request.email}")
    
    auth_service = get_auth_service()
    result = await auth_service.authenticate(
        email=request.email,
        password=request.password,
    )
    
    if not result.success:
        logger.warning(f"Failed login attempt for email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Unauthorized",
                "message": result.message or "Credenciales inválidas",
            }
        )
    
    # Set HttpOnly cookie with JWT token
    response.set_cookie(
        key="auth_session",
        value=result.token,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    
    logger.info(f"Successful login for user: {result.user.email}")
    
    return LoginSuccessResponse(
        success=True,
        user=UserResponse(
            name=result.user.name,
            email=result.user.email,
            role=result.user.role,
        ),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
)
async def logout(response: Response) -> LogoutResponse:
    """
    Log out a user and clear the auth_session cookie.
    
    This endpoint:
    1. Returns a success response.
    2. Clears the auth_session cookie by setting its max_age to 0.
    
    Args:
        response: FastAPI Response object for clearing cookies.
    
    Returns:
        LogoutResponse indicating successful logout.
    """
    response.delete_cookie(
        key="auth_session",
        httponly=True,
        secure=True,
        samesite="lax",
    )
    
    logger.info("User logged out successfully")
    
    return LogoutResponse(
        success=True,
        message="Logout successful",
    )