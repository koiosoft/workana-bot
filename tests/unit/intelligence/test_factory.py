"""Unit tests for the intelligence service factory.

Covers the refactored factory module with provider-driven adapter selection:
each default model's ``provider_key`` determines which adapter class to use.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from app.intelligence import factory
from app.intelligence.factory import ModelInfo
from app.intelligence.adapters.gemini import GeminiAdapter
from app.intelligence.adapters.openrouter import OpenRouterAdapter
from app.intelligence.port import IntelligencePort


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_instances() -> None:
    """Reset the cached adapters dict before each test for isolation."""
    factory._instances.clear()
    yield
    factory._instances.clear()


@pytest.fixture
def patch_gemini_client() -> None:
    """Prevent GeminiAdapter from attempting real API client construction."""
    with patch("app.intelligence.adapters.gemini.genai.Client"):
        yield


@pytest.fixture
def valid_db_models() -> tuple[ModelInfo, ModelInfo]:
    """Return fake ModelInfo simulating a fully populated ``models`` collection."""
    return (
        ModelInfo(model_id="models/gemini-2.5-flash", provider_key="gemini"),
        ModelInfo(model_id="models/gemini-2.5-pro", provider_key="gemini"),
    )


@pytest.fixture
def mixed_provider_models() -> tuple[ModelInfo, ModelInfo]:
    """STANDARD via Gemini, PREMIUM via OpenRouter."""
    return (
        ModelInfo(model_id="models/gemini-2.5-flash", provider_key="gemini"),
        ModelInfo(model_id="deepseek/deepseek-v4-pro", provider_key="openrouter"),
    )


@pytest.fixture
def mock_db_with_models(valid_db_models: tuple[ModelInfo, ModelInfo]) -> None:
    """Patch ``get_default_models_from_db`` to return valid ModelInfo."""
    async def _mock(*args, **kwargs):
        return valid_db_models

    with patch.object(
        factory, "get_default_models_from_db", side_effect=_mock
    ):
        yield


@pytest.fixture
def mock_db_mixed(mixed_provider_models: tuple[ModelInfo, ModelInfo]) -> None:
    """Patch to return mixed-provider models (Gemini + OpenRouter)."""
    async def _mock(*args, **kwargs):
        return mixed_provider_models

    with patch.object(
        factory, "get_default_models_from_db", side_effect=_mock
    ):
        yield


@pytest.fixture
def mock_db_unavailable() -> None:
    """Patch to simulate MongoDB being down."""
    async def _mock(*args, **kwargs):
        raise factory.ModelsCollectionUnavailableError("Connection refused")

    with patch.object(
        factory, "get_default_models_from_db", side_effect=_mock
    ):
        yield


@pytest.fixture
def mock_db_missing_models() -> None:
    """Patch to simulate missing default models."""
    async def _mock(*args, **kwargs):
        raise factory.DefaultModelNotFoundError(
            "Missing default models in DB: STANDARD"
        )

    with patch.object(
        factory, "get_default_models_from_db", side_effect=_mock
    ):
        yield


# ---------------------------------------------------------------------------
# get_intelligence_service
# ---------------------------------------------------------------------------

class TestGetIntelligenceService:
    """Tests for the async ``get_intelligence_service()`` wrapper."""

    @pytest.mark.asyncio
    async def test_returns_standard_adapter(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            service = await factory.get_intelligence_service()
            assert isinstance(service, GeminiAdapter)

    @pytest.mark.asyncio
    async def test_caches_after_first_call(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            first = await factory.get_intelligence_service()
            second = await factory.get_intelligence_service()
            assert first is second

    @pytest.mark.asyncio
    async def test_returns_standard_when_db_unavailable(
        self, patch_gemini_client: None, mock_db_unavailable: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            service = await factory.get_intelligence_service()
            assert isinstance(service, GeminiAdapter)

    @pytest.mark.asyncio
    async def test_returns_standard_when_models_missing(
        self, patch_gemini_client: None, mock_db_missing_models: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            service = await factory.get_intelligence_service()
            assert isinstance(service, GeminiAdapter)


# ---------------------------------------------------------------------------
# create_intelligence_service
# ---------------------------------------------------------------------------

class TestCreateIntelligenceService:
    """Tests for ``create_intelligence_service()``."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_three_keys(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            adapters = await factory.create_intelligence_service()
            assert isinstance(adapters, dict)
            assert set(adapters.keys()) == {"STANDARD", "PREMIUM", "FILTER"}

    @pytest.mark.asyncio
    async def test_all_adapters_are_gemini_when_both_models_gemini(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            adapters = await factory.create_intelligence_service()
            for key, adapter in adapters.items():
                assert isinstance(adapter, GeminiAdapter), f"{key} not GeminiAdapter"

    @pytest.mark.asyncio
    async def test_mixed_providers_standard_gemini_premium_openrouter(
        self, mock_db_mixed: None,
    ) -> None:
        """STANDARD model → GeminiAdapter, PREMIUM model → OpenRouterAdapter."""
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "dummy", "OPENROUTER_API_KEY": "dummy"},
        ):
            adapters = await factory.create_intelligence_service()

        assert isinstance(adapters["STANDARD"], GeminiAdapter)
        assert isinstance(adapters["PREMIUM"], OpenRouterAdapter)
        # FILTER shares STANDARD's model → also Gemini
        assert isinstance(adapters["FILTER"], GeminiAdapter)

    @pytest.mark.asyncio
    async def test_filter_shares_standard_adapter_provider(
        self, mock_db_mixed: None,
    ) -> None:
        """FILTER adapter must use the same provider as STANDARD."""
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "dummy", "OPENROUTER_API_KEY": "dummy"},
        ):
            adapters = await factory.create_intelligence_service()

        assert type(adapters["FILTER"]) is type(adapters["STANDARD"])
        assert type(adapters["FILTER"]) is not type(adapters["PREMIUM"])

    @pytest.mark.asyncio
    async def test_adapter_instances_are_distinct(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            adapters = await factory.create_intelligence_service()
            assert adapters["STANDARD"] is not adapters["PREMIUM"]
            assert adapters["STANDARD"] is not adapters["FILTER"]
            assert adapters["PREMIUM"] is not adapters["FILTER"]

    @pytest.mark.asyncio
    async def test_raises_value_error_for_unknown_provider(
        self,
    ) -> None:
        """When a model has an unknown provider_key, _create_adapter raises."""
        async def _mock(*args, **kwargs):
            return (
                ModelInfo(model_id="m1", provider_key="unknown-provider"),
                ModelInfo(model_id="m2", provider_key="gemini"),
            )

        with patch.object(factory, "get_default_models_from_db", side_effect=_mock):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
                with pytest.raises(ValueError, match="Unknown AI provider"):
                    await factory.create_intelligence_service()

    @pytest.mark.asyncio
    async def test_caches_on_second_call(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            first = await factory.create_intelligence_service()
            second = await factory.create_intelligence_service()
            assert first is second

    @pytest.mark.asyncio
    async def test_falls_back_on_db_unavailable(
        self, patch_gemini_client: None, mock_db_unavailable: None,
    ) -> None:
        """Fallback: both models default to gemini provider."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            adapters = await factory.create_intelligence_service()
            for key in ("STANDARD", "PREMIUM", "FILTER"):
                assert isinstance(adapters[key], GeminiAdapter)

    @pytest.mark.asyncio
    async def test_falls_back_on_missing_models(
        self, patch_gemini_client: None, mock_db_missing_models: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            adapters = await factory.create_intelligence_service()
            for key in ("STANDARD", "PREMIUM", "FILTER"):
                assert isinstance(adapters[key], GeminiAdapter)


# ---------------------------------------------------------------------------
# DB-driven model ID injection
# ---------------------------------------------------------------------------

class TestDbModelInjection:
    """Verify that model IDs and provider keys from DB are correctly
    injected into each adapter's internal overrides."""

    DB_STD_ID = "db-models/flash-custom"
    DB_PRM_ID = "db-models/pro-custom"

    @pytest.fixture
    def mock_custom_db(self) -> None:
        async def _mock(*args, **kwargs):
            return (
                ModelInfo(model_id=self.DB_STD_ID, provider_key="gemini"),
                ModelInfo(model_id=self.DB_PRM_ID, provider_key="openrouter"),
            )

        with patch.object(factory, "get_default_models_from_db", side_effect=_mock):
            yield

    @pytest.mark.asyncio
    async def test_standard_adapter_receives_standard_model(
        self, mock_custom_db: None,
    ) -> None:
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "dummy", "OPENROUTER_API_KEY": "dummy"},
        ):
            adapters = await factory.create_intelligence_service()
            std = adapters["STANDARD"]
            assert std._standard_model_override == self.DB_STD_ID
            assert std._premium_model_override == self.DB_STD_ID
            assert std._filter_model_override == self.DB_STD_ID

    @pytest.mark.asyncio
    async def test_premium_adapter_receives_premium_model(
        self, mock_custom_db: None,
    ) -> None:
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "dummy", "OPENROUTER_API_KEY": "dummy"},
        ):
            adapters = await factory.create_intelligence_service()
            prm = adapters["PREMIUM"]
            assert prm._standard_model_override == self.DB_PRM_ID
            assert prm._premium_model_override == self.DB_PRM_ID
            assert prm._filter_model_override == self.DB_PRM_ID

    @pytest.mark.asyncio
    async def test_filter_adapter_shares_standard_model(
        self, mock_custom_db: None,
    ) -> None:
        """FILTER adapter uses the STANDARD model (same model_id)."""
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "dummy", "OPENROUTER_API_KEY": "dummy"},
        ):
            adapters = await factory.create_intelligence_service()
            flt = adapters["FILTER"]
            assert flt._standard_model_override == self.DB_STD_ID
            assert flt._premium_model_override == self.DB_STD_ID
            assert flt._filter_model_override == self.DB_STD_ID

    @pytest.mark.asyncio
    async def test_standard_adapter_uses_hardcoded_fallback_when_db_empty(
        self, patch_gemini_client: None, mock_db_unavailable: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            adapters = await factory.create_intelligence_service()
            std = adapters["STANDARD"]
            assert std._standard_model_override is None

    @pytest.mark.asyncio
    async def test_isolation_premium_never_receives_standard_model(
        self, mock_custom_db: None,
    ) -> None:
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "dummy", "OPENROUTER_API_KEY": "dummy"},
        ):
            adapters = await factory.create_intelligence_service()
            prm = adapters["PREMIUM"]
            assert prm._standard_model_override != self.DB_STD_ID


# ---------------------------------------------------------------------------
# get_default_models_from_db
# ---------------------------------------------------------------------------

class TestGetDefaultModelsFromDb:
    """Tests for the database query function."""

    @pytest.mark.asyncio
    async def test_returns_two_model_infos(self) -> None:
        mock_db = AsyncMock()
        mock_db.__getitem__.return_value.find_one = AsyncMock(
            side_effect=[
                {"model_id": "m1", "provider_key": "gemini"},
                {"model_id": "m2", "provider_key": "openrouter"},
            ]
        )

        std_info, prm_info = await factory.get_default_models_from_db(mock_db)
        assert std_info.model_id == "m1"
        assert std_info.provider_key == "gemini"
        assert prm_info.model_id == "m2"
        assert prm_info.provider_key == "openrouter"

    @pytest.mark.asyncio
    async def test_raises_when_standard_missing(self) -> None:
        mock_db = AsyncMock()
        mock_db.__getitem__.return_value.find_one = AsyncMock(
            side_effect=[
                None,                                   # STANDARD missing
                {"model_id": "m2", "provider_key": "g"},
            ]
        )

        with pytest.raises(factory.DefaultModelNotFoundError, match="STANDARD"):
            await factory.get_default_models_from_db(mock_db)

    @pytest.mark.asyncio
    async def test_raises_when_premium_missing(self) -> None:
        mock_db = AsyncMock()
        mock_db.__getitem__.return_value.find_one = AsyncMock(
            side_effect=[
                {"model_id": "m1", "provider_key": "g"},
                None,                                   # PREMIUM missing
            ]
        )

        with pytest.raises(factory.DefaultModelNotFoundError, match="PREMIUM"):
            await factory.get_default_models_from_db(mock_db)

    @pytest.mark.asyncio
    async def test_raises_when_both_missing(self) -> None:
        mock_db = AsyncMock()
        mock_db.__getitem__.return_value.find_one = AsyncMock(
            side_effect=[None, None]
        )

        with pytest.raises(factory.DefaultModelNotFoundError) as excinfo:
            await factory.get_default_models_from_db(mock_db)

        message = str(excinfo.value)
        assert "STANDARD" in message
        assert "PREMIUM" in message

    @pytest.mark.asyncio
    async def test_raises_unavailable_on_db_error(self) -> None:
        mock_db = AsyncMock()
        mock_db.__getitem__.return_value.find_one = AsyncMock(
            side_effect=Exception("Network timeout")
        )

        with pytest.raises(factory.ModelsCollectionUnavailableError):
            await factory.get_default_models_from_db(mock_db)

    @pytest.mark.asyncio
    async def test_defaults_provider_key_to_gemini_when_missing(self) -> None:
        """If provider_key is absent from the DB document, default to 'gemini'."""
        mock_db = AsyncMock()
        mock_db.__getitem__.return_value.find_one = AsyncMock(
            side_effect=[
                {"model_id": "m1"},   # no provider_key
                {"model_id": "m2", "provider_key": "openrouter"},
            ]
        )

        std_info, prm_info = await factory.get_default_models_from_db(mock_db)
        assert std_info.provider_key == "gemini"
        assert prm_info.provider_key == "openrouter"


# ---------------------------------------------------------------------------
# _create_adapter
# ---------------------------------------------------------------------------

class TestCreateAdapter:
    """Tests for the internal ``_create_adapter`` helper."""

    def test_creates_gemini_adapter(self, patch_gemini_client: None) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            adapter = factory._create_adapter("gemini", "models/x")
            assert isinstance(adapter, GeminiAdapter)
            assert adapter._standard_model_override == "models/x"

    def test_creates_openrouter_adapter(self) -> None:
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy"}):
            adapter = factory._create_adapter("openrouter", "models/y")
            assert isinstance(adapter, OpenRouterAdapter)
            assert adapter._standard_model_override == "models/y"

    def test_raises_for_unknown_provider(self) -> None:
        with pytest.raises(ValueError, match="Unknown AI provider"):
            factory._create_adapter("unknown", "models/z")

    def test_none_model_id_preserved(self, patch_gemini_client: None) -> None:
        """None model_id signals 'use hardcoded default' — must not be coerced."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            adapter = factory._create_adapter("gemini", None)
            assert adapter._standard_model_override is None


# ---------------------------------------------------------------------------
# get_intelligence_adapters
# ---------------------------------------------------------------------------

class TestGetIntelligenceAdapters:
    """Tests for the sync ``get_intelligence_adapters()`` helper."""

    def test_returns_none_when_cache_is_empty(self) -> None:
        assert factory.get_intelligence_adapters() is None

    @pytest.mark.asyncio
    async def test_returns_dict_after_create(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            await factory.create_intelligence_service()
            adapters = factory.get_intelligence_adapters()
            assert isinstance(adapters, dict)
            assert set(adapters.keys()) == {"STANDARD", "PREMIUM", "FILTER"}


# ---------------------------------------------------------------------------
# select_initial_proposal_template
# ---------------------------------------------------------------------------


class TestSelectInitialProposalTemplate:
    """Tests for ``select_initial_proposal_template``."""

    def test_returns_proposal_j2_for_project_fixed(self) -> None:
        result = factory.select_initial_proposal_template("project_fixed")
        assert result == "proposal.j2"

    def test_returns_proposal_staffing_j2_for_staff_augmentation(self) -> None:
        result = factory.select_initial_proposal_template("staff_augmentation")
        assert result == "proposal_staffing.j2"

    def test_defaults_to_proposal_j2_for_unknown_type(self) -> None:
        """Any unrecognized contract type falls back to proposal.j2."""
        result = factory.select_initial_proposal_template("unknown_type")
        assert result == "proposal.j2"


# ---------------------------------------------------------------------------
# refine_proposal (factory-level) — contract_type routing
# ---------------------------------------------------------------------------


class TestRefineProposalContractTypeRouting:
    """Tests for the factory-level ``refine_proposal`` function that validate
    correct routing of ``contract_type`` and ``use_initial_template`` to the
    underlying adapter."""

    @pytest.mark.asyncio
    async def test_passes_use_initial_template_true_when_contract_type_changes(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        """When contract_type differs from the project's existing value,
        ``use_initial_template=True`` must be passed to the adapter."""
        project = {"title": "Test", "contract_type": "project_fixed"}

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            # Ensure adapters are initialised
            await factory.create_intelligence_service()

        adapter = factory._instances["STANDARD"]
        with patch.object(adapter, "refine_proposal", new_callable=AsyncMock) as mock_refine:
            mock_refine.return_value = {"proposal": "refined"}

            await factory.refine_proposal(
                project=project,
                user_feedback_observations="Make it better",
                model_id="test/model",
                contract_type="staff_augmentation",
            )

            mock_refine.assert_awaited_once()
            call_kwargs = mock_refine.call_args.kwargs
            assert call_kwargs["contract_type"] == "staff_augmentation"
            assert call_kwargs["use_initial_template"] is True

    @pytest.mark.asyncio
    async def test_passes_use_initial_template_false_when_same_contract_type(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        """When contract_type matches the project's existing value,
        ``use_initial_template=False`` must be passed."""
        project = {"title": "Test", "contract_type": "staff_augmentation"}

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            await factory.create_intelligence_service()

        adapter = factory._instances["STANDARD"]
        with patch.object(adapter, "refine_proposal", new_callable=AsyncMock) as mock_refine:
            mock_refine.return_value = {"proposal": "refined"}

            await factory.refine_proposal(
                project=project,
                user_feedback_observations="Adjust hours",
                model_id="test/model",
                contract_type="staff_augmentation",
            )

            mock_refine.assert_awaited_once()
            call_kwargs = mock_refine.call_args.kwargs
            assert call_kwargs["contract_type"] == "staff_augmentation"
            assert call_kwargs["use_initial_template"] is False

    @pytest.mark.asyncio
    async def test_passes_use_initial_template_false_when_contract_type_none(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        """When no contract_type is provided (None), ``use_initial_template``
        must be False and the existing contract_type is used."""
        project = {"title": "Test", "contract_type": "project_fixed"}

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            await factory.create_intelligence_service()

        adapter = factory._instances["STANDARD"]
        with patch.object(adapter, "refine_proposal", new_callable=AsyncMock) as mock_refine:
            mock_refine.return_value = {"proposal": "refined"}

            await factory.refine_proposal(
                project=project,
                user_feedback_observations="Refine",
                model_id="test/model",
            )

            mock_refine.assert_awaited_once()
            call_kwargs = mock_refine.call_args.kwargs
            assert call_kwargs["contract_type"] == "project_fixed"
            assert call_kwargs["use_initial_template"] is False

    @pytest.mark.asyncio
    async def test_defaults_to_project_fixed_when_contract_type_missing_from_project(
        self, patch_gemini_client: None, mock_db_with_models: None,
    ) -> None:
        """When a project has no contract_type field, default to
        ``project_fixed``."""
        project = {"title": "Test"}  # no contract_type

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
            await factory.create_intelligence_service()

        adapter = factory._instances["STANDARD"]
        with patch.object(adapter, "refine_proposal", new_callable=AsyncMock) as mock_refine:
            mock_refine.return_value = {"proposal": "refined"}

            await factory.refine_proposal(
                project=project,
                user_feedback_observations="Refine",
                model_id="test/model",
            )

            mock_refine.assert_awaited_once()
            call_kwargs = mock_refine.call_args.kwargs
            assert call_kwargs["contract_type"] == "project_fixed"
            assert call_kwargs["use_initial_template"] is False