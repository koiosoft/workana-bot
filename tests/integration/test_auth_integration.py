import os
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("MONGODB_URI"),
    reason="MONGODB_URI not set"
)

@pytest.mark.asyncio
async def test_login_success(test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]) -> None:
    """
    Test successful login with valid credentials.
    Asserts 200 status code and HttpOnly auth_session cookie.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/auth/login",
            json={
                "email": "admin@example.com",
                "password": "SecurePassword123!"
            }
        )
        
        assert response.status_code == 200
        
        # Check for set-cookie header
        assert "set-cookie" in response.headers
        
        # Check if auth_session cookie is present and HttpOnly
        cookies = response.headers["set-cookie"]
        assert "auth_session=" in cookies
        assert "HttpOnly" in cookies

@pytest.mark.asyncio
async def test_login_failure_invalid_credentials(test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]) -> None:
    """
    Test login failure with invalid credentials.
    Asserts 401 Unauthorized status code.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/auth/login",
            json={
                "email": "invalid@example.com",
                "password": "wrong"
            }
        )
        
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_logout_success(test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]) -> None:
    """
    Test successful logout.
    Asserts 200 status code and explicitly clears the auth_session cookie.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/auth/logout")
        
        assert response.status_code == 200
        
        # Check for set-cookie header indicating cookie deletion
        assert "set-cookie" in response.headers
        cookies = response.headers["set-cookie"]
        assert "auth_session=" in cookies
        # Check for Max-Age=0 or Expires in the past to confirm deletion
        assert "Max-Age=0" in cookies or "Expires=" in cookies
