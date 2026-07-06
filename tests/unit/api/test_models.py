"""Unit tests for Models & Providers endpoints.

Covers:
  - POST /api/models/providers : create provider
  - POST /api/models           : create model
  - PUT  /api/models/providers/{provider_key} : update provider
  - PUT  /api/models/{model_id}               : update model flags
  - DELETE /api/models/providers/{provider_key} : soft-delete provider
  - DELETE /api/models/{model_id}               : soft-delete model

All database interactions are mocked — no network I/O.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from app.api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# POST /providers tests
# ---------------------------------------------------------------------------


def test_create_provider_success() -> None:
    """POST /providers with valid data should return 201 and the created provider."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__.return_value = mock_providers

    fake_inserted_id = "507f1f77bcf86cd799439011"
    mock_result = MagicMock()
    mock_result.inserted_id = fake_inserted_id
    mock_providers.insert_one = AsyncMock(return_value=mock_result)

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.post(
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
    assert data["_id"] == fake_inserted_id
    mock_providers.insert_one.assert_called_once()


def test_create_provider_duplicate_key() -> None:
    """POST /providers with an existing key should return 409 Conflict."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__.return_value = mock_providers

    mock_providers.insert_one = AsyncMock(
        side_effect=DuplicateKeyError("E11000 duplicate key error")
    )

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.post(
            "/api/models/providers",
            json={
                "key": "openrouter",
                "name": "OpenRouter",
                "url": "https://openrouter.ai/api/v1",
            },
        )

    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["error"] == "Conflict"
    assert "already exists" in data["detail"]["message"]


def test_create_provider_validation_error() -> None:
    """POST /providers with missing required fields should return 422."""
    response = client.post(
        "/api/models/providers",
        json={"key": "openrouter"},  # missing name and url
    )

    assert response.status_code == 422


def test_create_provider_empty_key() -> None:
    """POST /providers with empty key should return 422."""
    response = client.post(
        "/api/models/providers",
        json={
            "key": "",
            "name": "OpenRouter",
            "url": "https://openrouter.ai/api/v1",
        },
    )

    assert response.status_code == 422


def test_create_provider_unexpected_error() -> None:
    """POST /providers should return 500 on unexpected database errors."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__.return_value = mock_providers

    mock_providers.insert_one = AsyncMock(
        side_effect=RuntimeError("Connection lost")
    )

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.post(
            "/api/models/providers",
            json={
                "key": "gemini",
                "name": "Google Gemini",
                "url": "https://ai.google.dev",
            },
        )

    assert response.status_code == 500
    data = response.json()
    assert data["detail"]["error"] == "Internal Server Error"


# ---------------------------------------------------------------------------
# POST /models tests
# ---------------------------------------------------------------------------


def test_create_model_success() -> None:
    """POST /models with valid data should return 201 and the created model."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_models = AsyncMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda coll: {
        "providers": mock_providers,
        "models": mock_models,
    }[coll])

    # Simulate provider exists
    mock_providers.find_one = AsyncMock(return_value={"key": "openrouter", "name": "OpenRouter"})

    fake_inserted_id = "507f1f77bcf86cd799439012"
    mock_result = MagicMock()
    mock_result.inserted_id = fake_inserted_id
    mock_models.insert_one = AsyncMock(return_value=mock_result)

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.post(
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
    assert data["_id"] == fake_inserted_id
    mock_models.insert_one.assert_called_once()


def test_create_model_provider_not_found() -> None:
    """POST /models with non-existent provider_key should return 400."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda coll: {
        "providers": mock_providers,
    }[coll])

    # Simulate provider does not exist
    mock_providers.find_one = AsyncMock(return_value=None)

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.post(
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


def test_create_model_duplicate_key() -> None:
    """POST /models with existing (model_id, provider_key) should return 409."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_models = AsyncMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda coll: {
        "providers": mock_providers,
        "models": mock_models,
    }[coll])

    mock_providers.find_one = AsyncMock(return_value={"key": "openrouter"})
    mock_models.insert_one = AsyncMock(
        side_effect=DuplicateKeyError("E11000 duplicate key error")
    )

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.post(
            "/api/models",
            json={
                "model_id": "gpt-4o",
                "provider_key": "openrouter",
                "is_default": False,
                "is_premium": True,
            },
        )

    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["error"] == "Conflict"
    assert "already exists" in data["detail"]["message"]


def test_create_model_validation_error() -> None:
    """POST /models with missing required fields should return 422."""
    response = client.post(
        "/api/models",
        json={"model_id": "gpt-4o"},  # missing provider_key, is_default, is_premium
    )

    assert response.status_code == 422


def test_create_model_invalid_boolean_fields() -> None:
    """POST /models with non-boolean is_default should return 422."""
    response = client.post(
        "/api/models",
        json={
            "model_id": "gpt-4o",
            "provider_key": "openrouter",
            "is_default": 42,  # integer, not a boolean
            "is_premium": False,
        },
    )

    assert response.status_code == 422


def test_create_model_unexpected_error() -> None:
    """POST /models should return 500 on unexpected database errors."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_models = AsyncMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda coll: {
        "providers": mock_providers,
        "models": mock_models,
    }[coll])

    mock_providers.find_one = AsyncMock(return_value={"key": "openrouter"})
    mock_models.insert_one = AsyncMock(
        side_effect=RuntimeError("Database unreachable")
    )

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.post(
            "/api/models",
            json={
                "model_id": "gpt-4o",
                "provider_key": "openrouter",
                "is_default": False,
                "is_premium": False,
            },
        )

    assert response.status_code == 500
    data = response.json()
    assert data["detail"]["error"] == "Internal Server Error"


def test_create_model_empty_model_id() -> None:
    """POST /models with empty model_id should return 422."""
    response = client.post(
        "/api/models",
        json={
            "model_id": "",
            "provider_key": "openrouter",
            "is_default": False,
            "is_premium": False,
        },
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT /providers/{provider_key} tests
# ---------------------------------------------------------------------------


def test_update_provider_success() -> None:
    """PUT /providers/{key} should update name and return the updated provider."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__.return_value = mock_providers

    # find_one called twice: first to check existence, second to return updated
    mock_providers.find_one = AsyncMock(side_effect=[
        {"key": "openrouter", "name": "Old Name", "url": "https://old.url"},
        {"key": "openrouter", "name": "OpenRouter v2", "url": "https://old.url"},
    ])
    mock_providers.update_one = AsyncMock()

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/providers/openrouter",
            json={"name": "OpenRouter v2"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "OpenRouter v2"

    # Verify the update was called with correct fields
    call_args = mock_providers.update_one.call_args
    assert call_args[0][0] == {"key": "openrouter"}
    assert call_args[0][1] == {"$set": {"name": "OpenRouter v2"}}


def test_update_provider_not_found() -> None:
    """PUT /providers/{key} with non-existent key should return 404."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__.return_value = mock_providers

    mock_providers.find_one = AsyncMock(return_value=None)

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/providers/nonexistent",
            json={"name": "New Name"},
        )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"] == "Not Found"


def test_update_provider_empty_body() -> None:
    """PUT /providers/{key} with empty body should return 400."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__.return_value = mock_providers

    mock_providers.find_one = AsyncMock(return_value={
        "key": "openrouter", "name": "OpenRouter"
    })

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/providers/openrouter",
            json={},
        )

    assert response.status_code == 400
    assert "No valid fields" in response.json()["detail"]["message"]


def test_update_provider_unexpected_error() -> None:
    """PUT /providers/{key} should return 500 on unexpected DB errors."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__.return_value = mock_providers

    mock_providers.find_one = AsyncMock(return_value={
        "key": "gemini", "name": "Gemini"
    })
    mock_providers.update_one = AsyncMock(
        side_effect=RuntimeError("Connection lost")
    )

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/providers/gemini",
            json={"url": "https://new.url"},
        )

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "Internal Server Error"


def test_update_provider_empty_url() -> None:
    """PUT /providers/{key} with empty url string should return 422."""
    response = client.put(
        "/api/models/providers/openrouter",
        json={"url": ""},
    )

    assert response.status_code == 422


def test_update_provider_empty_name() -> None:
    """PUT /providers/{key} with empty name string should return 422."""
    response = client.put(
        "/api/models/providers/openrouter",
        json={"name": ""},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# PUT /models/{model_id} tests
# ---------------------------------------------------------------------------


def test_update_model_set_default() -> None:
    """PUT /models/{model_id} should update is_default and apply mutual exclusion."""
    mock_db = MagicMock()
    mock_models = AsyncMock()
    mock_db.__getitem__.return_value = mock_models

    # Simulate existing model with is_default=False, is_premium=False
    call_count = 0
    find_responses = [
        {"model_id": "gpt-4o", "provider_key": "openrouter", "is_default": False, "is_premium": False},
        {"model_id": "gpt-4o", "provider_key": "openrouter", "is_default": True, "is_premium": False},
    ]
    def find_one_side_effect(query=None, *args, **kwargs):
        nonlocal call_count
        resp = find_responses[call_count % len(find_responses)]
        call_count += 1
        return resp

    mock_models.find_one = AsyncMock(side_effect=find_one_side_effect)
    mock_models.update_one = AsyncMock()
    mock_models.update_many = AsyncMock()

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/gpt-4o",
            json={"is_default": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_default"] is True

    # Verify mutual exclusion was triggered for standard tier
    mock_models.update_many.assert_called_once_with(
        {"model_id": {"$ne": "gpt-4o"}, "is_premium": False, "is_default": True},
        {"$set": {"is_default": False}},
    )


def test_update_model_mutual_exclusion_premium() -> None:
    """PUT /models/{model_id} setting is_default=True on premium model should unset other premium defaults."""
    mock_db = MagicMock()
    mock_models = AsyncMock()
    mock_db.__getitem__.return_value = mock_models

    call_count = 0
    find_responses = [
        {"model_id": "gemini-pro", "provider_key": "gemini", "is_default": False, "is_premium": True},
        {"model_id": "gemini-pro", "provider_key": "gemini", "is_default": True, "is_premium": True},
    ]
    def find_one_side_effect(query=None, *args, **kwargs):
        nonlocal call_count
        resp = find_responses[call_count % len(find_responses)]
        call_count += 1
        return resp

    mock_models.find_one = AsyncMock(side_effect=find_one_side_effect)
    mock_models.update_one = AsyncMock()
    mock_models.update_many = AsyncMock()

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/gemini-pro",
            json={"is_default": True},
        )

    assert response.status_code == 200

    # Mutual exclusion should target premium tier
    mock_models.update_many.assert_called_once_with(
        {"model_id": {"$ne": "gemini-pro"}, "is_premium": True, "is_default": True},
        {"$set": {"is_default": False}},
    )


def test_update_model_clear_default() -> None:
    """PUT /models/{model_id} setting is_default=False should not trigger mutual exclusion."""
    mock_db = MagicMock()
    mock_models = AsyncMock()
    mock_db.__getitem__.return_value = mock_models

    call_count = 0
    find_responses = [
        {"model_id": "gpt-4o", "provider_key": "openrouter", "is_default": True, "is_premium": False},
        {"model_id": "gpt-4o", "provider_key": "openrouter", "is_default": False, "is_premium": False},
    ]
    def find_one_side_effect(query=None, *args, **kwargs):
        nonlocal call_count
        resp = find_responses[call_count % len(find_responses)]
        call_count += 1
        return resp

    mock_models.find_one = AsyncMock(side_effect=find_one_side_effect)
    mock_models.update_one = AsyncMock()
    mock_models.update_many = AsyncMock()

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/gpt-4o",
            json={"is_default": False},
        )

    assert response.status_code == 200
    # Mutual exclusion should NOT be called when setting default to False
    mock_models.update_many.assert_not_called()


def test_update_model_not_found() -> None:
    """PUT /models/{model_id} with non-existent model should return 404."""
    mock_db = MagicMock()
    mock_models = AsyncMock()
    mock_db.__getitem__.return_value = mock_models

    mock_models.find_one = AsyncMock(return_value=None)

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/nonexistent",
            json={"is_default": True},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Not Found"


def test_update_model_empty_body() -> None:
    """PUT /models/{model_id} with empty body should return 400."""
    mock_db = MagicMock()
    mock_models = AsyncMock()
    mock_db.__getitem__.return_value = mock_models

    mock_models.find_one = AsyncMock(return_value={
        "model_id": "gpt-4o", "is_default": True, "is_premium": False
    })

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/gpt-4o",
            json={},
        )

    assert response.status_code == 400
    assert "No valid fields" in response.json()["detail"]["message"]


def test_update_model_invalid_boolean() -> None:
    """PUT /models/{model_id} with non-boolean is_default should return 422."""
    response = client.put(
        "/api/models/gpt-4o",
        json={"is_default": "not-a-bool"},
    )

    assert response.status_code == 422


def test_update_model_unexpected_error() -> None:
    """PUT /models/{model_id} should return 500 on unexpected DB errors."""
    mock_db = MagicMock()
    mock_models = AsyncMock()
    mock_db.__getitem__.return_value = mock_models

    mock_models.find_one = AsyncMock(return_value={
        "model_id": "gpt-4o", "is_default": False, "is_premium": False
    })
    mock_models.update_one = AsyncMock(
        side_effect=RuntimeError("Database unreachable")
    )

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.put(
            "/api/models/gpt-4o",
            json={"is_premium": True},
        )

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "Internal Server Error"


# ---------------------------------------------------------------------------
# DELETE /providers/{provider_key} tests
# ---------------------------------------------------------------------------


def test_delete_provider_success() -> None:
    """DELETE /providers/{key} should soft-delete the provider and cascade to models."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_models = AsyncMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda coll: {
        "providers": mock_providers,
        "models": mock_models,
    }[coll])

    # Provider exists
    mock_providers.find_one = AsyncMock(return_value={
        "key": "openrouter", "name": "OpenRouter"
    })
    mock_providers.update_one = AsyncMock()

    # Cascade result
    cascade_mock = MagicMock()
    cascade_mock.modified_count = 3
    mock_models.update_many = AsyncMock(return_value=cascade_mock)

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.delete("/api/models/providers/openrouter")

    assert response.status_code == 200
    data = response.json()
    assert "soft-deleted" in data["message"]
    assert data["cascaded_models"] == 3

    # Verify soft-delete was called on provider
    mock_providers.update_one.assert_called_once_with(
        {"key": "openrouter"},
        {"$set": {"is_deleted": True}},
    )

    # Verify cascade to models
    mock_models.update_many.assert_called_once_with(
        {"provider_key": "openrouter"},
        {"$set": {"is_deleted": True}},
    )


def test_delete_provider_not_found() -> None:
    """DELETE /providers/{key} with non-existent key should return 404."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__.return_value = mock_providers

    mock_providers.find_one = AsyncMock(return_value=None)

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.delete("/api/models/providers/nonexistent")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Not Found"


def test_delete_provider_unexpected_error() -> None:
    """DELETE /providers/{key} should return 500 on unexpected DB errors."""
    mock_db = MagicMock()
    mock_providers = AsyncMock()
    mock_db.__getitem__.return_value = mock_providers

    mock_providers.find_one = AsyncMock(return_value={
        "key": "gemini", "name": "Gemini"
    })
    mock_providers.update_one = AsyncMock(
        side_effect=RuntimeError("Connection lost")
    )

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.delete("/api/models/providers/gemini")

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "Internal Server Error"


# ---------------------------------------------------------------------------
# DELETE /models/{model_id} tests
# ---------------------------------------------------------------------------


def test_delete_model_success() -> None:
    """DELETE /models/{model_id} should soft-delete the model."""
    mock_db = MagicMock()
    mock_models = AsyncMock()
    mock_db.__getitem__.return_value = mock_models

    mock_models.find_one = AsyncMock(return_value={
        "model_id": "gpt-4o", "provider_key": "openrouter"
    })
    mock_models.update_one = AsyncMock()

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.delete("/api/models/gpt-4o")

    assert response.status_code == 200
    data = response.json()
    assert "soft-deleted" in data["message"]

    # Verify soft-delete was called
    mock_models.update_one.assert_called_once_with(
        {"model_id": "gpt-4o"},
        {"$set": {"is_deleted": True}},
    )


def test_delete_model_not_found() -> None:
    """DELETE /models/{model_id} with non-existent model should return 404."""
    mock_db = MagicMock()
    mock_models = AsyncMock()
    mock_db.__getitem__.return_value = mock_models

    mock_models.find_one = AsyncMock(return_value=None)

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.delete("/api/models/nonexistent")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Not Found"


def test_delete_model_unexpected_error() -> None:
    """DELETE /models/{model_id} should return 500 on unexpected DB errors."""
    mock_db = MagicMock()
    mock_models = AsyncMock()
    mock_db.__getitem__.return_value = mock_models

    mock_models.find_one = AsyncMock(return_value={
        "model_id": "gpt-4o", "provider_key": "openrouter"
    })
    mock_models.update_one = AsyncMock(
        side_effect=RuntimeError("Database unreachable")
    )

    with patch("app.api.routes.models.get_database", return_value=mock_db):
        response = client.delete("/api/models/gpt-4o")

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "Internal Server Error"