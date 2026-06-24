"""
Integration Tests for Authentication Endpoints

Covers the /api/auth/login and /api/auth/logout endpoints: successful and
unsuccessful scenarios including credential validation, missing fields,
invalid email formats, and cookie management.

Adheres to:
- CONVENTIONS.md: PEP 8, strict typing, pytest.mark.skipif, Loguru
- SPEC.md: Hexagonal Architecture testing strategy
"""

import os
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.main import app

# =============================================================================
# Conditional Skip (Integration tests require a database connection)
# =============================================================================

pytestmark = pytest.mark.skipif(
    not os.getenv("MONGO_URI"),
    reason="MONGO_URI not set",
)

# =============================================================================
# Login Tests
# =============================================================================


@pytest.mark.asyncio
async def test_login_success(
    test_db: AsyncIOMotorDatabase,
    seed_test_data: Dict[str, Any],
) -> None:
    """
    Test successful login with valid credentials.

    Asserts:
        - 200 OK status code
        - success: true and user object with email, name, role
        - HttpOnly + Secure auth_session cookie with SameSite=Lax
    """
    transport: ASGITransport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@example.com",
                "password": "SecurePassword123!",
            },
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data: Dict[str, Any] = response.json()
        assert data["success"] is True
        assert "user" in data
        assert data["user"]["email"] == "admin@example.com"
        assert data["user"]["name"] == "Test Admin"
        assert data["user"]["role"] == "admin"

        # Verify HttpOnly auth_session cookie is set
        assert "set-cookie" in response.headers, "Missing set-cookie header"
        set_cookie: str = response.headers["set-cookie"]
        assert "auth_session=" in set_cookie, "auth_session cookie not found"
        assert "HttpOnly" in set_cookie, "auth_session cookie is not HttpOnly"
        assert "Secure" in set_cookie, "auth_session cookie is not Secure"
        assert (
            "samesite=lax" in set_cookie.lower()
        ), "auth_session cookie missing SameSite=Lax"

        logger.info("test_login_success passed")


@pytest.mark.asyncio
async def test_login_failure_invalid_credentials(
    test_db: AsyncIOMotorDatabase,
    seed_test_data: Dict[str, Any],
) -> None:
    """
    Test login failure with completely invalid credentials (non-existent email).

    Asserts:
        - 401 Unauthorized status code
        - Generic error message that does not confirm whether email exists
    """
    transport: ASGITransport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "invalid@example.com",
                "password": "wrong",
            },
        )

        assert (
            response.status_code == 401
        ), f"Expected 401, got {response.status_code}: {response.text}"

        data: Dict[str, Any] = response.json()
        assert (
            "detail" in data or "error" in data
        ), "Response should contain error information"

        logger.info("test_login_failure_invalid_credentials passed")


@pytest.mark.asyncio
async def test_login_invalid_password(
    test_db: AsyncIOMotorDatabase,
    seed_test_data: Dict[str, Any],
) -> None:
    """
    Test login with a correct email but incorrect password.

    Asserts:
        - 401 Unauthorized status code
        - Error message present (does not differentiate email from password)
    """
    transport: ASGITransport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@example.com",
                "password": "wrongpassword",
            },
        )

        assert (
            response.status_code == 401
        ), f"Expected 401, got {response.status_code}: {response.text}"

        data: Dict[str, Any] = response.json()
        # FastAPI wraps HTTPException detail in {"detail": ...}
        detail: Dict[str, Any] = data.get("detail", data)
        assert "error" in detail, "Response should contain 'error' field"

        logger.info("test_login_invalid_password passed")


@pytest.mark.asyncio
async def test_login_nonexistent_email(
    test_db: AsyncIOMotorDatabase,
    seed_test_data: Dict[str, Any],
) -> None:
    """
    Test login with an email not present in the database.

    Asserts:
        - 401 Unauthorized status code
        - Generic error message (does not leak whether email exists)
    """
    transport: ASGITransport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SecurePassword123!",
            },
        )

        assert (
            response.status_code == 401
        ), f"Expected 401, got {response.status_code}: {response.text}"

        data: Dict[str, Any] = response.json()
        assert (
            "detail" in data or "error" in data
        ), "Response should contain error information"

        logger.info("test_login_nonexistent_email passed")


@pytest.mark.asyncio
async def test_login_missing_email(
    test_db: AsyncIOMotorDatabase,
    seed_test_data: Dict[str, Any],
) -> None:
    """
    Test login without providing an email field (Pydantic validation).

    Asserts:
        - 422 Unprocessable Entity status code
    """
    transport: ASGITransport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "password": "SecurePassword123!",
            },
        )

        assert (
            response.status_code == 422
        ), f"Expected 422, got {response.status_code}: {response.text}"

        logger.info("test_login_missing_email passed")


@pytest.mark.asyncio
async def test_login_invalid_email_format(
    test_db: AsyncIOMotorDatabase,
    seed_test_data: Dict[str, Any],
) -> None:
    """
    Test login with a malformed email address (Pydantic EmailStr validation).

    Asserts:
        - 422 Unprocessable Entity status code
    """
    transport: ASGITransport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "not-an-email",
                "password": "SecurePassword123!",
            },
        )

        assert (
            response.status_code == 422
        ), f"Expected 422, got {response.status_code}: {response.text}"

        logger.info("test_login_invalid_email_format passed")


# =============================================================================
# Logout Tests
# =============================================================================


@pytest.mark.asyncio
async def test_logout_success(
    test_db: AsyncIOMotorDatabase,
    seed_test_data: Dict[str, Any],
) -> None:
    """
    Test successful logout clears the auth_session cookie.

    Asserts:
        - 200 OK status code
        - success: true and message: "Logout successful" in response body
        - set-cookie header with Max-Age=0 indicating cookie deletion
    """
    transport: ASGITransport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/logout")

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data: Dict[str, Any] = response.json()
        assert data["success"] is True, "logout response success should be True"
        assert data["message"] == "Logout successful"

        # Verify that auth_session cookie is cleared (Max-Age=0)
        assert "set-cookie" in response.headers, "Missing set-cookie header for logout"
        set_cookie: str = response.headers["set-cookie"]
        assert (
            "auth_session=" in set_cookie
        ), "auth_session cookie not present in logout response"
        cookie_lower: str = set_cookie.lower()
        assert (
            "Max-Age=0" in set_cookie or "expires=" in cookie_lower
        ), f"Logout cookie should be expired. Got: {set_cookie}"

        logger.info("test_logout_success passed")
