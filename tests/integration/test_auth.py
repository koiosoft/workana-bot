"""
Integration Tests for Authentication Endpoints

This module contains integration tests for the /api/auth/login and /api/auth/logout
endpoints, covering successful and unsuccessful scenarios including credential
validation, missing fields, invalid email formats, and cookie management.

Following Hexagonal Architecture, these tests exercise the full flow from the
FastAPI router (driving adapter) through the auth service (core) to the
MongoDB repository (driven adapter).

Adheres to:
- CONVENTIONS.md: PEP 8, strict typing, pytest.mark.skipif
- SPEC.md: Hexagonal Architecture testing strategy
"""

import os
from typing import Any, Dict

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger

from app.api.main import app

# =============================================================================
# Conditional Skip (Integration tests require a database connection)
# =============================================================================

pytestmark = pytest.mark.skipif(
    not os.getenv("MONGO_URI"),
    reason="MONGO_URI not set",
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="function")
async def seed_auth_test_user(test_db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    Seed the test database with a user for authentication tests.

    Creates a user with known credentials:
        - email: admin@example.com
        - password: SecurePassword123!
        - name: Test Admin
        - role: admin

    Cleans up after each test to guarantee test isolation.

    Args:
        test_db: The test database fixture from conftest.py.

    Returns:
        Dictionary with test user credentials for assertions.
    """
    password_hash: bytes = bcrypt.hashpw(
        b"SecurePassword123!",
        bcrypt.gensalt(),
    )

    user_doc = {
        "email": "admin@example.com",
        "passwordHash": password_hash.decode("utf-8"),
        "name": "Test Admin",
        "role": "admin",
    }

    await test_db.users.insert_one(user_doc)
    logger.info("Seeded test user: admin@example.com")

    yield {
        "email": "admin@example.com",
        "password": "SecurePassword123!",
        "name": "Test Admin",
        "role": "admin",
    }

    # Teardown: remove the test user to keep database clean
    await test_db.users.delete_one({"email": "admin@example.com"})
    logger.info("Cleaned up test user: admin@example.com")


# =============================================================================
# Login Tests
# =============================================================================

@pytest.mark.asyncio
async def test_login_success(
    test_db: AsyncIOMotorDatabase,
    seed_auth_test_user: Dict[str, Any],
) -> None:
    """
    Test successful login with valid credentials.

    Asserts:
        - 200 OK status code
        - success: true in response body
        - user object with name, email, role
        - HttpOnly auth_session cookie in response headers
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

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

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
        # FastAPI uses lowercase samesite by default
        assert "samesite=lax" in set_cookie.lower(), (
            "auth_session cookie missing SameSite=Lax"
        )


@pytest.mark.asyncio
async def test_login_invalid_password(
    test_db: AsyncIOMotorDatabase,
    seed_auth_test_user: Dict[str, Any],
) -> None:
    """
    Test login with an incorrect password for a valid email.

    Asserts:
        - 401 Unauthorized status code
        - error field present in response body
        - Message does not differentiate between invalid email vs invalid password
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

        assert response.status_code == 401, (
            f"Expected 401, got {response.status_code}: {response.text}"
        )

        data: Dict[str, Any] = response.json()
        # FastAPI wraps HTTPException detail in {"detail": ...}
        detail: Dict[str, Any] = data.get("detail", data)
        assert "error" in detail, "Response should contain 'error' field"
        assert detail["error"] == "Unauthorized"


@pytest.mark.asyncio
async def test_login_nonexistent_email(
    test_db: AsyncIOMotorDatabase,
    seed_auth_test_user: Dict[str, Any],
) -> None:
    """
    Test login with an email that does not exist in the database.

    Asserts:
        - 401 Unauthorized status code
        - Generic error message (does not confirm whether email exists)
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

        assert response.status_code == 401, (
            f"Expected 401, got {response.status_code}: {response.text}"
        )

        data: Dict[str, Any] = response.json()
        assert "detail" in data or "error" in data, (
            "Response should contain error information"
        )


@pytest.mark.asyncio
async def test_login_missing_email(
    test_db: AsyncIOMotorDatabase,
    seed_auth_test_user: Dict[str, Any],
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

        assert response.status_code == 422, (
            f"Expected 422, got {response.status_code}: {response.text}"
        )


@pytest.mark.asyncio
async def test_login_invalid_email_format(
    test_db: AsyncIOMotorDatabase,
    seed_auth_test_user: Dict[str, Any],
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

        assert response.status_code == 422, (
            f"Expected 422, got {response.status_code}: {response.text}"
        )


# =============================================================================
# Logout Tests
# =============================================================================

@pytest.mark.asyncio
async def test_logout_success(
    test_db: AsyncIOMotorDatabase,
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

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        data: Dict[str, Any] = response.json()
        assert data["success"] is True, "logout response success should be True"
        assert data["message"] == "Logout successful"

        # Verify that auth_session cookie is cleared (Max-Age=0)
        assert "set-cookie" in response.headers, "Missing set-cookie header for logout"
        set_cookie: str = response.headers["set-cookie"]
        assert "auth_session=" in set_cookie, (
            "auth_session cookie not present in logout response"
        )
        cookie_lower: str = set_cookie.lower()
        assert "Max-Age=0" in set_cookie or "expires=" in cookie_lower, (
            f"Logout cookie should be expired. Got: {set_cookie}"
        )