"""Integration tests for the intelligence service factory.

Exercises ``create_intelligence_service`` and ``get_default_models_from_db``
against a real MongoDB instance.  Validates end-to-end behaviour with
provider-driven adapter selection: each default model's ``provider_key``
determines which adapter class is instantiated.

Requires ``MONGO_URI`` environment variable.  Tests are skipped if not set.
"""

import os

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.intelligence import factory
from app.intelligence.factory import ModelInfo
from app.intelligence.adapters.gemini import GeminiAdapter
from app.intelligence.adapters.openrouter import OpenRouterAdapter
from app.database.mongo import get_database
from app.database.mongo import (
    ensure_providers_collection,
    ensure_models_collection,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("MONGO_URI"),
    reason="MONGO_URI not set",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_provider_doc(key: str, name: str, url: str = "https://example.com") -> dict:
    """Build a provider document matching the ``providers`` collection schema."""
    return {"key": key, "name": name, "url": url}


def _build_model_doc(
    model_id: str,
    provider_key: str,
    is_premium: bool = False,
    name: str = "Test Model",
) -> dict:
    """Build a model document matching the ``models`` collection schema."""
    return {
        "model_id": model_id,
        "provider_key": provider_key,
        "name": name,
        "is_default": True,
        "is_premium": is_premium,
    }


@pytest_asyncio.fixture(scope="function", autouse=False)
async def seed_default_models(test_db: AsyncIOMotorDatabase) -> tuple[str, str]:
    """Seed two default models (STANDARD + PREMIUM) and their providers.

    Returns the two ``model_id`` values for assertions.
    """
    await ensure_providers_collection()
    await ensure_models_collection()

    # Clean up from previous runs
    await test_db["providers"].delete_many({"key": {"$in": ["gemini", "openrouter"]}})
    await test_db["models"].delete_many({"provider_key": {"$in": ["gemini", "openrouter"]}})

    # Seed providers
    await test_db["providers"].insert_many([
        _build_provider_doc("gemini", "Google Gemini"),
        _build_provider_doc("openrouter", "OpenRouter"),
    ])

    std_id = "models/test-standard"
    prm_id = "models/test-premium"

    await test_db["models"].insert_many([
        _build_model_doc(std_id, "gemini", is_premium=False, name="Test Standard"),
        _build_model_doc(prm_id, "gemini", is_premium=True, name="Test Premium"),
    ])

    yield std_id, prm_id

    await test_db["models"].delete_many({"provider_key": {"$in": ["gemini", "openrouter"]}})
    await test_db["providers"].delete_many({"key": {"$in": ["gemini", "openrouter"]}})


@pytest_asyncio.fixture(scope="function", autouse=False)
async def seed_mixed_providers(test_db: AsyncIOMotorDatabase) -> None:
    """Seed STANDARD via Gemini, PREMIUM via OpenRouter."""
    await ensure_providers_collection()
    await ensure_models_collection()

    await test_db["providers"].delete_many({"key": {"$in": ["gemini", "openrouter"]}})
    await test_db["models"].delete_many({"provider_key": {"$in": ["gemini", "openrouter"]}})

    await test_db["providers"].insert_many([
        _build_provider_doc("gemini", "Google Gemini"),
        _build_provider_doc("openrouter", "OpenRouter"),
    ])

    await test_db["models"].insert_many([
        _build_model_doc("models/test-standard", "gemini", is_premium=False),
        _build_model_doc("models/test-premium", "openrouter", is_premium=True),
    ])

    yield

    await test_db["models"].delete_many({"provider_key": {"$in": ["gemini", "openrouter"]}})
    await test_db["providers"].delete_many({"key": {"$in": ["gemini", "openrouter"]}})


@pytest_asyncio.fixture(scope="function", autouse=False)
async def seed_partial_models(test_db: AsyncIOMotorDatabase) -> None:
    """Seed only STANDARD — PREMIUM intentionally missing."""
    await ensure_providers_collection()
    await ensure_models_collection()

    await test_db["providers"].delete_many({"key": "gemini"})
    await test_db["models"].delete_many({"provider_key": "gemini"})

    await test_db["providers"].insert_one(_build_provider_doc("gemini", "Google Gemini"))
    await test_db["models"].insert_one(
        _build_model_doc("models/test-standard", "gemini", is_premium=False)
    )

    yield

    await test_db["models"].delete_many({"provider_key": "gemini"})
    await test_db["providers"].delete_many({"key": "gemini"})


def _patch_fake_client():
    """Replace genai.Client with a no-op stub so tests don't hit the network."""
    import app.intelligence.adapters.gemini as gemini_mod
    original = gemini_mod.genai.Client

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

    gemini_mod.genai.Client = _FakeClient  # type: ignore[assignment]
    return original


def _restore_client(original):
    import app.intelligence.adapters.gemini as gemini_mod
    gemini_mod.genai.Client = original


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCreateIntelligenceServiceIntegration:
    """End-to-end tests with a real MongoDB instance."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("seed_default_models")
    async def test_all_three_adapters_instantiated(
        self, test_db: AsyncIOMotorDatabase,
    ) -> None:
        factory._instances.clear()
        original = _patch_fake_client()

        try:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("GEMINI_API_KEY", "dummy-integration-key")
                adapters = await factory.create_intelligence_service(db=test_db)
        finally:
            _restore_client(original)

        assert set(adapters.keys()) == {"STANDARD", "PREMIUM", "FILTER"}
        assert isinstance(adapters["STANDARD"], GeminiAdapter)
        assert isinstance(adapters["PREMIUM"], GeminiAdapter)
        assert isinstance(adapters["FILTER"], GeminiAdapter)
        assert adapters["STANDARD"] is not adapters["PREMIUM"]
        assert adapters["STANDARD"] is not adapters["FILTER"]
        assert adapters["PREMIUM"] is not adapters["FILTER"]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("seed_default_models")
    async def test_adapter_model_overrides_match_seeded_data(
        self, test_db: AsyncIOMotorDatabase,
        seed_default_models: tuple[str, str],
    ) -> None:
        factory._instances.clear()
        std_id, prm_id = seed_default_models
        original = _patch_fake_client()

        try:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("GEMINI_API_KEY", "dummy-integration-key")
                adapters = await factory.create_intelligence_service(db=test_db)
        finally:
            _restore_client(original)

        assert adapters["STANDARD"]._standard_model_override == std_id
        assert adapters["PREMIUM"]._premium_model_override == prm_id
        # FILTER shares STANDARD's model
        assert adapters["FILTER"]._filter_model_override == std_id

    @pytest.mark.asyncio
    async def test_falls_back_when_no_models_in_db(
        self, test_db: AsyncIOMotorDatabase,
    ) -> None:
        factory._instances.clear()
        await ensure_models_collection()
        original = _patch_fake_client()

        try:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("GEMINI_API_KEY", "dummy-integration-key")
                adapters = await factory.create_intelligence_service(db=test_db)
        finally:
            _restore_client(original)

        assert set(adapters.keys()) == {"STANDARD", "PREMIUM", "FILTER"}
        for key in ("STANDARD", "PREMIUM", "FILTER"):
            assert isinstance(adapters[key], GeminiAdapter)
        for adapter in adapters.values():
            assert adapter._standard_model_override is None

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("seed_partial_models")
    async def test_falls_back_when_premium_missing(
        self, test_db: AsyncIOMotorDatabase,
    ) -> None:
        factory._instances.clear()
        original = _patch_fake_client()

        try:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("GEMINI_API_KEY", "dummy-integration-key")
                adapters = await factory.create_intelligence_service(db=test_db)
        finally:
            _restore_client(original)

        # All three created via fallback
        for key in ("STANDARD", "PREMIUM", "FILTER"):
            assert isinstance(adapters[key], GeminiAdapter)
        for adapter in adapters.values():
            assert adapter._standard_model_override is None

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("seed_mixed_providers")
    async def test_mixed_providers_standard_gemini_premium_openrouter(
        self, test_db: AsyncIOMotorDatabase,
    ) -> None:
        """STANDARD provider_key → GeminiAdapter, PREMIUM → OpenRouterAdapter."""
        factory._instances.clear()

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("GEMINI_API_KEY", "dummy-integration-key")
            mp.setenv("OPENROUTER_API_KEY", "dummy-integration-key")
            adapters = await factory.create_intelligence_service(db=test_db)

        assert isinstance(adapters["STANDARD"], GeminiAdapter)
        assert isinstance(adapters["PREMIUM"], OpenRouterAdapter)
        # FILTER shares STANDARD's provider → also Gemini
        assert isinstance(adapters["FILTER"], GeminiAdapter)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("seed_mixed_providers")
    async def test_filter_shares_standard_model_id(
        self, test_db: AsyncIOMotorDatabase,
    ) -> None:
        """FILTER adapter must have the same model_id as STANDARD."""
        factory._instances.clear()

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("GEMINI_API_KEY", "dummy-integration-key")
            mp.setenv("OPENROUTER_API_KEY", "dummy-integration-key")
            adapters = await factory.create_intelligence_service(db=test_db)

        assert (
            adapters["FILTER"]._standard_model_override
            == adapters["STANDARD"]._standard_model_override
        )

    @pytest.mark.asyncio
    async def test_caching_prevents_repeated_db_queries(
        self, test_db: AsyncIOMotorDatabase,
    ) -> None:
        factory._instances.clear()
        original = _patch_fake_client()

        try:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("GEMINI_API_KEY", "dummy-integration-key")
                first = await factory.create_intelligence_service(db=test_db)
                second = await factory.create_intelligence_service(db=test_db)
        finally:
            _restore_client(original)

        assert first is second
        assert first["STANDARD"] is second["STANDARD"]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("seed_default_models")
    async def test_get_intelligence_adapters_after_creation(
        self, test_db: AsyncIOMotorDatabase,
    ) -> None:
        factory._instances.clear()
        original = _patch_fake_client()

        try:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("GEMINI_API_KEY", "dummy-integration-key")
                await factory.create_intelligence_service(db=test_db)
        finally:
            _restore_client(original)

        adapters = factory.get_intelligence_adapters()
        assert adapters is not None
        assert set(adapters.keys()) == {"STANDARD", "PREMIUM", "FILTER"}

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("seed_default_models")
    async def test_model_info_has_correct_provider_key(
        self, test_db: AsyncIOMotorDatabase,
        seed_default_models: tuple[str, str],
    ) -> None:
        """``get_default_models_from_db`` returns ModelInfo with correct provider_key."""
        std_id, prm_id = seed_default_models

        std_info, prm_info = await factory.get_default_models_from_db(db=test_db)

        assert std_info.model_id == std_id
        assert std_info.provider_key == "gemini"
        assert prm_info.model_id == prm_id
        assert prm_info.provider_key == "gemini"