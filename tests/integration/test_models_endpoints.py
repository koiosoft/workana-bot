"""Integration tests for /api/models endpoints.

Covers:
  - GET /api/models/providers
  - GET /api/models (with and without filter parameter)
  - Invalid filter values

Note: These endpoints are currently public (no authentication required),
      consistent with the rest of the API.
"""

import os
from typing import Any, Dict, List

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.main import app
from app.database.mongo import get_database

pytestmark = pytest.mark.skipif(
    not os.getenv("MONGO_URI"),
    reason="MONGO_URI not set",
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def override_db_dependency(test_db: AsyncIOMotorDatabase):
    """Override FastAPI DB dependency to use the test database."""
    app.dependency_overrides[get_database] = lambda: test_db

    from app.database import mongo

    mongo._db = test_db

    yield

    app.dependency_overrides.clear()
    mongo._db = None


@pytest_asyncio.fixture
async def seed_providers(test_db: AsyncIOMotorDatabase) -> List[Dict[str, Any]]:
    """Insert test providers into the database."""
    providers = [
        {"key": "openrouter", "name": "OpenRouter", "url": "https://openrouter.ai/api/v1"},
        {"key": "gemini", "name": "Google Gemini", "url": "https://ai.google.dev"},
    ]
    await test_db["providers"].insert_many(providers)
    return providers


@pytest_asyncio.fixture
async def seed_models(test_db: AsyncIOMotorDatabase) -> List[Dict[str, Any]]:
    """Insert test models into the database."""
    models = [
        {
            "model_id": "qwen/qwen3-14b",
            "provider_key": "openrouter",
            "is_default": True,
            "is_premium": False,
        },
        {
            "model_id": "deepseek/deepseek-v4-pro",
            "provider_key": "openrouter",
            "is_default": True,
            "is_premium": True,
        },
        {
            "model_id": "models/gemini-2.5-flash",
            "provider_key": "gemini",
            "is_default": False,
            "is_premium": False,
        },
        {
            "model_id": "models/gemini-2.5-pro",
            "provider_key": "gemini",
            "is_default": False,
            "is_premium": True,
        },
    ]
    await test_db["models"].insert_many(models)
    return models


# ---------------------------------------------------------------------------
# list_providers tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_providers_returns_all(
    test_db: AsyncIOMotorDatabase,
    seed_providers: List[Dict[str, Any]],
) -> None:
    """GET /api/models/providers should return all providers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models/providers")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    keys = {p["key"] for p in data}
    assert "openrouter" in keys
    assert "gemini" in keys


@pytest.mark.asyncio
async def test_list_providers_empty(
    test_db: AsyncIOMotorDatabase,
) -> None:
    """GET /api/models/providers should return empty list when no providers exist."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models/providers")

    assert response.status_code == 200
    data = response.json()
    assert data == []


# ---------------------------------------------------------------------------
# list_models tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_models_returns_all(
    test_db: AsyncIOMotorDatabase,
    seed_providers: List[Dict[str, Any]],
    seed_models: List[Dict[str, Any]],
) -> None:
    """GET /api/models should return all models enriched with provider info."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 4

    # Every model should have provider_name and provider_url
    for model in data:
        assert "provider_name" in model
        assert "provider_url" in model
        assert model["provider_name"] is not None
        assert model["provider_url"] is not None


@pytest.mark.asyncio
async def test_list_models_filter_standard(
    test_db: AsyncIOMotorDatabase,
    seed_providers: List[Dict[str, Any]],
    seed_models: List[Dict[str, Any]],
) -> None:
    """GET /api/models?filter=standard should return only non-premium models."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models", params={"filter": "standard"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    for model in data:
        assert model["is_premium"] is False


@pytest.mark.asyncio
async def test_list_models_filter_premium(
    test_db: AsyncIOMotorDatabase,
    seed_providers: List[Dict[str, Any]],
    seed_models: List[Dict[str, Any]],
) -> None:
    """GET /api/models?filter=premium should return only premium models."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models", params={"filter": "premium"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    for model in data:
        assert model["is_premium"] is True


@pytest.mark.asyncio
async def test_list_models_invalid_filter(
    test_db: AsyncIOMotorDatabase,
    seed_providers: List[Dict[str, Any]],
    seed_models: List[Dict[str, Any]],
) -> None:
    """GET /api/models?filter=invalid should return 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models", params={"filter": "invalid"})

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_list_models_empty_without_data(
    test_db: AsyncIOMotorDatabase,
) -> None:
    """GET /api/models should return empty list when no models exist."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models")

    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_models_include_default_indicators(
    test_db: AsyncIOMotorDatabase,
    seed_providers: List[Dict[str, Any]],
    seed_models: List[Dict[str, Any]],
) -> None:
    """Each model in the response should include is_default and is_premium flags."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/models")

    assert response.status_code == 200
    data = response.json()

    for model in data:
        assert "is_default" in model
        assert "is_premium" in model
        assert isinstance(model["is_default"], bool)
        assert isinstance(model["is_premium"], bool)

    # Verify exactly the expected defaults
    default_standard = [m for m in data if m["is_default"] and not m["is_premium"]]
    default_premium = [m for m in data if m["is_default"] and m["is_premium"]]
    assert len(default_standard) == 1
    assert len(default_premium) == 1