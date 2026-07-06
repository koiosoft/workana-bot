"""Integration tests for Models & Providers endpoints.

Covers:
  - POST /api/models/providers : create provider
  - POST /api/models           : create model
  - PUT  /api/models/providers/{provider_key} : update provider
  - PUT  /api/models/{model_id}               : update model flags
  - DELETE /api/models/providers/{provider_key} : soft-delete provider
  - DELETE /api/models/{model_id}               : soft-delete model

Requires MONGO_URI environment variable. Tests are skipped if not set.
Uses a dedicated test database (suffixed with '_test') for isolation.
"""

import os
from typing import Any, Dict, List

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
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
def override_db_dependency(test_db: AsyncIOMotorDatabase) -> None:
    """Override FastAPI DB dependency to use the test database."""
    app.dependency_overrides[get_database] = lambda: test_db

    from app.database import mongo

    mongo._db = test_db

    yield

    app.dependency_overrides.clear()
    mongo._db = None


@pytest_asyncio.fixture
async def ensure_collections(test_db: AsyncIOMotorDatabase) -> None:
    """Ensure the providers and models collections exist with indexes."""
    from app.database.mongo import ensure_providers_collection, ensure_models_collection

    await ensure_providers_collection()
    await ensure_models_collection()


# ---------------------------------------------------------------------------
# POST /providers tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_provider_success(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /providers should create a provider and persist it to MongoDB."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models/providers",
            json={
                "key": "openrouter",
                "name": "OpenRouter",
                "url": "https://openrouter.ai/api/v1",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["key"] == "openrouter"
    assert data["name"] == "OpenRouter"
    assert data["url"] == "https://openrouter.ai/api/v1"
    assert "_id" in data

    # Verify it actually exists in the database
    stored = await test_db["providers"].find_one({"key": "openrouter"})
    assert stored is not None
    assert stored["name"] == "OpenRouter"


@pytest.mark.asyncio
async def test_create_provider_duplicate_key(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /providers with an existing key should return 409 Conflict."""
    # Pre-insert a provider
    await test_db["providers"].insert_one({
        "key": "gemini",
        "name": "Google Gemini",
        "url": "https://ai.google.dev",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models/providers",
            json={
                "key": "gemini",
                "name": "Duplicate Gemini",
                "url": "https://example.com",
            },
        )

    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["error"] == "Conflict"
    assert "gemini" in data["detail"]["message"]


@pytest.mark.asyncio
async def test_create_provider_validation_missing_fields(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /providers with missing required fields should return 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models/providers",
            json={"key": "openrouter"},  # missing name and url
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_provider_empty_key(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /providers with empty key should return 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models/providers",
            json={
                "key": "",
                "name": "Empty Key Provider",
                "url": "https://example.com",
            },
        )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /models tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_model_success(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /models should create a model and persist it to MongoDB."""
    # Pre-insert a provider
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models",
            json={
                "model_id": "gpt-4o",
                "provider_key": "openrouter",
                "is_default": True,
                "is_premium": False,
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["model_id"] == "gpt-4o"
    assert data["provider_key"] == "openrouter"
    assert data["is_default"] is True
    assert data["is_premium"] is False
    assert "_id" in data

    # Verify it actually exists in the database
    stored = await test_db["models"].find_one({"model_id": "gpt-4o"})
    assert stored is not None
    assert stored["provider_key"] == "openrouter"
    assert stored["is_default"] is True


@pytest.mark.asyncio
async def test_create_model_provider_not_found(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /models with non-existent provider_key should return 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models",
            json={
                "model_id": "gpt-4o",
                "provider_key": "nonexistent",
                "is_default": True,
                "is_premium": False,
            },
        )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"] == "Bad Request"
    assert "does not exist" in data["detail"]["message"]


@pytest.mark.asyncio
async def test_create_model_duplicate_key(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /models with existing (model_id, provider_key) should return 409."""
    # Pre-insert a provider and a model
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })
    await test_db["models"].insert_one({
        "model_id": "gpt-4o",
        "provider_key": "openrouter",
        "is_default": False,
        "is_premium": True,
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models",
            json={
                "model_id": "gpt-4o",
                "provider_key": "openrouter",
                "is_default": True,
                "is_premium": False,
            },
        )

    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["error"] == "Conflict"
    assert "already exists" in data["detail"]["message"]


@pytest.mark.asyncio
async def test_create_model_validation_missing_fields(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /models with missing required fields should return 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models",
            json={"model_id": "gpt-4o"},  # missing provider_key, is_default, is_premium
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_model_empty_model_id(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /models with empty model_id should return 422."""
    # Pre-insert a provider
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models",
            json={
                "model_id": "",
                "provider_key": "openrouter",
                "is_default": False,
                "is_premium": False,
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_model_persists_exact_fields(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """POST /models should persist all submitted fields exactly in MongoDB."""
    await test_db["providers"].insert_one({
        "key": "gemini",
        "name": "Google Gemini",
        "url": "https://ai.google.dev",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/models",
            json={
                "model_id": "models/gemini-2.5-pro",
                "provider_key": "gemini",
                "is_default": True,
                "is_premium": True,
            },
        )

    assert response.status_code == 201

    stored = await test_db["models"].find_one({"model_id": "models/gemini-2.5-pro"})
    assert stored is not None
    assert stored["model_id"] == "models/gemini-2.5-pro"
    assert stored["provider_key"] == "gemini"
    assert stored["is_default"] is True
    assert stored["is_premium"] is True


# ---------------------------------------------------------------------------
# PUT /providers/{provider_key} tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_provider_success(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """PUT /providers/{key} should update the provider and persist changes."""
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "Old Name",
        "url": "https://old.url",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/models/providers/openrouter",
            json={"name": "OpenRouter v2"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "OpenRouter v2"
    assert data["url"] == "https://old.url"  # unchanged

    # Verify database state
    stored = await test_db["providers"].find_one({"key": "openrouter"})
    assert stored["name"] == "OpenRouter v2"
    assert stored["url"] == "https://old.url"


@pytest.mark.asyncio
async def test_update_provider_not_found(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """PUT /providers/{key} with non-existent key should return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/models/providers/nonexistent",
            json={"name": "New Name"},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Not Found"


@pytest.mark.asyncio
async def test_update_provider_empty_body(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """PUT /providers/{key} with empty body should return 400."""
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/models/providers/openrouter",
            json={},
        )

    assert response.status_code == 400
    assert "No valid fields" in response.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_update_provider_empty_name(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """PUT /providers/{key} with empty name should return 422."""
    await test_db["providers"].insert_one({
        "key": "gemini",
        "name": "Google Gemini",
        "url": "https://ai.google.dev",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/models/providers/gemini",
            json={"name": ""},
        )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT /models/{model_id} tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_model_mutual_exclusion_standard(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """PUT /models/{model_id} setting is_default=True should unset other defaults in the same tier."""
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })

    # Insert two standard models, one already default
    await test_db["models"].insert_many([
        {"model_id": "gpt-4o", "provider_key": "openrouter", "is_default": True, "is_premium": False},
        {"model_id": "claude-3", "provider_key": "openrouter", "is_default": False, "is_premium": False},
        {"model_id": "gemini-pro", "provider_key": "openrouter", "is_default": True, "is_premium": True},
    ])

    # Set claude-3 as default (standard tier)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/models/claude-3",
            json={"is_default": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_default"] is True

    # Verify: claude-3 is now default, gpt-4o is not, gemini-pro (premium) unaffected
    gpt = await test_db["models"].find_one({"model_id": "gpt-4o"})
    claude = await test_db["models"].find_one({"model_id": "claude-3"})
    gemini = await test_db["models"].find_one({"model_id": "gemini-pro"})

    assert gpt["is_default"] is False  # was unset
    assert claude["is_default"] is True  # newly set
    assert gemini["is_default"] is True  # premium, unaffected


@pytest.mark.asyncio
async def test_update_model_mutual_exclusion_premium(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """PUT /models/{model_id} setting is_default=True on premium model should unset other premium defaults."""
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })

    await test_db["models"].insert_many([
        {"model_id": "gpt-4o", "provider_key": "openrouter", "is_default": False, "is_premium": False},
        {"model_id": "claude-opus", "provider_key": "openrouter", "is_default": True, "is_premium": True},
        {"model_id": "gemini-ultra", "provider_key": "openrouter", "is_default": False, "is_premium": True},
    ])

    # Set gemini-ultra as default (premium tier)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/models/gemini-ultra",
            json={"is_default": True},
        )

    assert response.status_code == 200

    # Verify: gemini-ultra is now default, claude-opus is not, gpt-4o (standard) unaffected
    gpt = await test_db["models"].find_one({"model_id": "gpt-4o"})
    claude = await test_db["models"].find_one({"model_id": "claude-opus"})
    gemini = await test_db["models"].find_one({"model_id": "gemini-ultra"})

    assert gpt["is_default"] is False  # standard, unaffected
    assert claude["is_default"] is False  # was unset (premium)
    assert gemini["is_default"] is True  # newly set


@pytest.mark.asyncio
async def test_update_model_clear_default(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """PUT /models/{model_id} setting is_default=False should not affect other models."""
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })

    await test_db["models"].insert_many([
        {"model_id": "gpt-4o", "provider_key": "openrouter", "is_default": True, "is_premium": False},
        {"model_id": "claude-3", "provider_key": "openrouter", "is_default": True, "is_premium": True},
    ])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/models/gpt-4o",
            json={"is_default": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_default"] is False

    # claude-3 should still be default
    claude = await test_db["models"].find_one({"model_id": "claude-3"})
    assert claude["is_default"] is True


@pytest.mark.asyncio
async def test_update_model_not_found(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """PUT /models/{model_id} with non-existent model should return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/models/nonexistent",
            json={"is_default": True},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Not Found"


@pytest.mark.asyncio
async def test_update_model_empty_body(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """PUT /models/{model_id} with empty body should return 400."""
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })
    await test_db["models"].insert_one({
        "model_id": "gpt-4o",
        "provider_key": "openrouter",
        "is_default": True,
        "is_premium": False,
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/models/gpt-4o",
            json={},
        )

    assert response.status_code == 400
    assert "No valid fields" in response.json()["detail"]["message"]


# ---------------------------------------------------------------------------
# DELETE /providers/{provider_key} tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_provider_cascade(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """DELETE /providers/{key} should soft-delete provider and cascade to all associated models."""
    # Seed provider and models
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })
    await test_db["models"].insert_many([
        {"model_id": "gpt-4o", "provider_key": "openrouter", "is_default": True, "is_premium": False},
        {"model_id": "claude-3", "provider_key": "openrouter", "is_default": False, "is_premium": True},
    ])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/models/providers/openrouter")

    assert response.status_code == 200
    data = response.json()
    assert "soft-deleted" in data["message"]
    assert data["cascaded_models"] == 2

    # Verify provider is soft-deleted
    provider = await test_db["providers"].find_one({"key": "openrouter"})
    assert provider["is_deleted"] is True

    # Verify all associated models are soft-deleted
    models = await test_db["models"].find({"provider_key": "openrouter"}).to_list(length=10)
    assert len(models) == 2
    for model in models:
        assert model["is_deleted"] is True


@pytest.mark.asyncio
async def test_delete_provider_not_found(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """DELETE /providers/{key} with non-existent key should return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/models/providers/nonexistent")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Not Found"


# ---------------------------------------------------------------------------
# DELETE /models/{model_id} tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_model_success(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """DELETE /models/{model_id} should soft-delete the model."""
    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })
    await test_db["models"].insert_one({
        "model_id": "gpt-4o",
        "provider_key": "openrouter",
        "is_default": True,
        "is_premium": False,
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/models/gpt-4o")

    assert response.status_code == 200
    data = response.json()
    assert "soft-deleted" in data["message"]

    # Verify model is soft-deleted in the database
    model = await test_db["models"].find_one({"model_id": "gpt-4o"})
    assert model["is_deleted"] is True

    # Original data is preserved
    assert model["provider_key"] == "openrouter"
    assert model["is_default"] is True


@pytest.mark.asyncio
async def test_delete_model_not_found(
    test_db: AsyncIOMotorDatabase,
    ensure_collections: None,
) -> None:
    """DELETE /models/{model_id} with non-existent model should return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/models/nonexistent")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Not Found"