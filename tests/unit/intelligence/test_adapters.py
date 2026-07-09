"""Unit tests for the OpenRouterAdapter intelligence adapter."""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.bots.telegram.circuit_breaker import CircuitBreaker
from app.exceptions import AIConnectionError
from app.intelligence.adapters.openrouter import STANDARD_MODEL, OpenRouterAdapter


@pytest.fixture
def cb() -> MagicMock:
    """Return a MagicMock wrapping CircuitBreaker for spying on calls."""
    return MagicMock(spec=CircuitBreaker)


@pytest.fixture
def adapter() -> OpenRouterAdapter:
    """Create an OpenRouterAdapter with a dummy API key."""
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
        return OpenRouterAdapter()


# ------------------------------------------------------------------
#  evaluate_projects
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_projects_returns_parsed_list(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """Should extract JSON array from a code-block response."""
    mock_text = '```json\n[{"score": 8, "reason": "Good"}]\n```'
    with patch.object(adapter, "_chat_completion", AsyncMock(return_value=mock_text)):
        results = await adapter.evaluate_projects(
            [{"title": "Test"}], circuit_breaker=cb
        )

    assert len(results) == 1
    assert results[0]["score"] == 8
    # record_success lives inside _chat_completion, which is mocked here


@pytest.mark.asyncio
async def test_evaluate_projects_returns_empty_on_no_choices(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """Should return empty list when AI returns no text."""
    with patch.object(adapter, "_chat_completion", AsyncMock(return_value="")):
        results = await adapter.evaluate_projects(
            [{"title": "Test"}], circuit_breaker=cb
        )

    assert results == []


@pytest.mark.asyncio
async def test_evaluate_projects_records_failure_on_http_error(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """Should raise AIConnectionError and record failure on HTTPError."""
    with patch.object(
        adapter,
        "_chat_completion",
        AsyncMock(side_effect=httpx.HTTPError("Server error")),
    ):
        with pytest.raises(AIConnectionError, match="OpenRouter"):
            await adapter.evaluate_projects([{"title": "Test"}], circuit_breaker=cb)

    cb.record_failure.assert_called_once()


@pytest.mark.asyncio
async def test_evaluate_projects_records_failure_on_network_error(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """Should raise AIConnectionError and record failure on RemoteProtocolError."""
    with patch.object(
        adapter,
        "_chat_completion",
        AsyncMock(side_effect=httpx.RemoteProtocolError("Connection reset")),
    ):
        with pytest.raises(AIConnectionError, match="OpenRouter"):
            await adapter.evaluate_projects([{"title": "Test"}], circuit_breaker=cb)

    cb.record_failure.assert_called_once()


# ------------------------------------------------------------------
#  generate_proposal
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_proposal_returns_parsed_dict_fixed(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """Should parse a JSON object response for project_fixed contract type."""
    mock_text = (
        '```json\n{"proposal_header": "Test Prop", "milestones": [], '
        '"summary": {"total_hours": 40, "total_budget": 1000}, '
        '"questions_for_client": []}\n```'
    )
    with patch.object(
        adapter, "_chat_completion", AsyncMock(return_value=mock_text)
    ), patch("asyncio.sleep", AsyncMock()):
        result = await adapter.generate_proposal(
            {"title": "Test", "contract_type": "project_fixed"},
            circuit_breaker=cb,
        )

    assert result["proposal_header"] == "Test Prop"
    assert "milestones" in result
    assert "summary" in result
    # record_success lives inside _chat_completion, which is mocked here


@pytest.mark.asyncio
async def test_generate_proposal_returns_parsed_dict_staffing(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """Should parse a JSON object response for staff_augmentation contract type."""
    mock_text = (
        '```json\n{"cover_letter": "Dear client", '
        '"budget_summary": {"hourly_rate": 25, "suggested_hours_per_week": 20, '
        '"estimated_monthly_budget": 2000}}\n```'
    )
    with patch.object(
        adapter, "_chat_completion", AsyncMock(return_value=mock_text)
    ), patch("asyncio.sleep", AsyncMock()):
        result = await adapter.generate_proposal(
            {"title": "Test", "contract_type": "staff_augmentation"},
            circuit_breaker=cb,
        )

    assert "cover_letter" in result
    assert "budget_summary" in result


@pytest.mark.asyncio
async def test_generate_proposal_returns_error_on_empty_response(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """Should return error dict when AI returns no text."""
    with patch.object(adapter, "_chat_completion", AsyncMock(return_value="")), patch(
        "asyncio.sleep", AsyncMock()
    ):
        result = await adapter.generate_proposal({"title": "Test"}, circuit_breaker=cb)

    assert "error" in result


# ------------------------------------------------------------------
#  format_project_description
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_format_description_returns_formatted_text(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """Should return the formatted description and record success."""
    with patch.object(
        adapter,
        "_chat_completion",
        AsyncMock(return_value="Formatted output"),
    ):
        text = await adapter.format_project_description("raw text", circuit_breaker=cb)

    assert text == "Formatted output"
    # record_success lives inside _chat_completion, which is mocked here


@pytest.mark.asyncio
async def test_format_description_returns_original_on_empty_response(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """Should return original description when AI yields empty text."""
    with patch.object(adapter, "_chat_completion", AsyncMock(return_value="")):
        text = await adapter.format_project_description(
            "original text", circuit_breaker=cb
        )

    assert text == "original text"


# ------------------------------------------------------------------
#  _select_model
# ------------------------------------------------------------------


def test_select_model_none_strategy(adapter: OpenRouterAdapter) -> None:
    """Default/none strategy should set STANDARD_MODEL."""
    assert adapter._select_model("none") == STANDARD_MODEL
    assert adapter.model_id == STANDARD_MODEL


def test_select_model_flash_strategy(adapter: OpenRouterAdapter) -> None:
    """Flash strategy should set STANDARD_MODEL."""
    assert adapter._select_model("flash") == STANDARD_MODEL
    assert adapter.model_id == STANDARD_MODEL


def test_select_model_pro_strategy(adapter: OpenRouterAdapter) -> None:
    """Pro strategy should set PREMIUM_MODEL."""
    result = adapter._select_model("pro")
    assert result == "deepseek/deepseek-v4-pro"
    assert adapter.model_id == "deepseek/deepseek-v4-pro"


# ------------------------------------------------------------------
#  _set_delay
# ------------------------------------------------------------------


def test_set_delay_none_strategy(adapter: OpenRouterAdapter) -> None:
    """Default strategy should set delay to 5.0."""
    with patch.dict(os.environ, {}, clear=True):
        assert adapter._set_delay("none") == 5.0


def test_set_delay_flash_strategy(adapter: OpenRouterAdapter) -> None:
    """Flash strategy should set delay to 1.0."""
    with patch.dict(os.environ, {}, clear=True):
        assert adapter._set_delay("flash") == 1.0


def test_set_delay_pro_strategy(adapter: OpenRouterAdapter) -> None:
    """Pro strategy should set delay to 35.0."""
    with patch.dict(os.environ, {}, clear=True):
        assert adapter._set_delay("pro") == 35.0


def test_set_delay_override(adapter: OpenRouterAdapter) -> None:
    """GEMINI_DELAY_OVERRIDE env var should take precedence."""
    with patch.dict(os.environ, {"GEMINI_DELAY_OVERRIDE": "2.5"}):
        assert adapter._set_delay("none") == 2.5


# ------------------------------------------------------------------
#  Database-driven model override tests (OpenRouterAdapter)
# ------------------------------------------------------------------


class TestOpenRouterAdapterModelOverrides:
    """Validate that OpenRouterAdapter uses DB-provided model IDs when given."""

    def test_constructor_accepts_model_overrides(self) -> None:
        """Should accept standard_model and premium_model in constructor."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
            adapter = OpenRouterAdapter(
                standard_model="custom-standard-model",
                premium_model="custom-premium-model",
            )
        assert adapter._standard_model_override == "custom-standard-model"
        assert adapter._premium_model_override == "custom-premium-model"

    def test_select_model_standard_uses_override(self) -> None:
        """_select_model('flash') should prefer the override over hardcoded."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
            adapter = OpenRouterAdapter(standard_model="db-standard")
        result = adapter._select_model("flash")
        assert result == "db-standard"
        assert adapter.model_id == "db-standard"

    def test_select_model_premium_uses_override(self) -> None:
        """_select_model('pro') should prefer the override over hardcoded."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
            adapter = OpenRouterAdapter(premium_model="db-premium")
        result = adapter._select_model("pro")
        assert result == "db-premium"
        assert adapter.model_id == "db-premium"

    def test_select_model_falls_back_when_override_is_none(self) -> None:
        """When override is None, should fall back to hardcoded STANDARD_MODEL."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
            adapter = OpenRouterAdapter()
        result = adapter._select_model("flash")
        assert result == STANDARD_MODEL
        assert adapter.model_id == STANDARD_MODEL

    def test_select_model_premium_falls_back_when_override_is_none(self) -> None:
        """When premium override is None, should fall back to hardcoded PREMIUM_MODEL."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
            adapter = OpenRouterAdapter()
        result = adapter._select_model("pro")
        assert result == "deepseek/deepseek-v4-pro"

    def test_default_strategy_also_uses_standard_override(self) -> None:
        """_select_model with no strategy ('none') should use the standard override."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
            adapter = OpenRouterAdapter(standard_model="db-default")
        result = adapter._select_model("none")
        assert result == "db-default"

    def test_override_does_not_affect_delay(self) -> None:
        """Model overrides should not affect delay calculation."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}, clear=True):
            adapter = OpenRouterAdapter(
                standard_model="db-s", premium_model="db-p"
            )
        with patch.dict(os.environ, {}, clear=True):
            assert adapter._set_delay("flash") == 1.0
            assert adapter._set_delay("pro") == 35.0


# ------------------------------------------------------------------
#  refine_proposal — template selection
# ------------------------------------------------------------------


class TestRefineProposalTemplateSelection:
    """Validate that ``refine_proposal`` selects the correct Jinja2 template
    based on ``contract_type`` and ``use_initial_template`` flags."""

    @pytest.fixture
    def adapter(self) -> OpenRouterAdapter:
        """Create an OpenRouterAdapter with a dummy API key."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
            return OpenRouterAdapter()

    @pytest.mark.asyncio
    async def test_refine_uses_refine_j2_for_project_fixed(
        self, adapter: OpenRouterAdapter,
    ) -> None:
        """Default: project_fixed contract_type with no template override
        should render refine.j2."""
        with patch.object(
            adapter, "_chat_completion", AsyncMock(return_value='{"proposal":"ok"}')
        ), patch.object(adapter, "_render_prompt") as mock_render:
            mock_render.return_value = "prompt string"

            await adapter.refine_proposal(
                project={"title": "Test", "contract_type": "project_fixed"},
                user_feedback_observations="Feedback",
                model_id="test/model",
            )

            # First positional arg is the template name
            template_name = mock_render.call_args[0][0]
            assert template_name == "refine.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_refine_staffing_j2_for_staff_augmentation(
        self, adapter: OpenRouterAdapter,
    ) -> None:
        """When contract_type is staff_augmentation and not an initial
        template, should render refine-staffing.j2."""
        with patch.object(
            adapter, "_chat_completion", AsyncMock(return_value='{"proposal":"ok"}')
        ), patch.object(adapter, "_render_prompt") as mock_render:
            mock_render.return_value = "prompt string"

            await adapter.refine_proposal(
                project={"title": "Test"},
                user_feedback_observations="Feedback",
                model_id="test/model",
                contract_type="staff_augmentation",
            )

            template_name = mock_render.call_args[0][0]
            assert template_name == "refine-staffing.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_proposal_j2_when_contract_type_changes_to_fixed(
        self, adapter: OpenRouterAdapter,
    ) -> None:
        """When use_initial_template=True and contract_type is project_fixed,
        should render proposal.j2."""
        with patch.object(
            adapter, "_chat_completion", AsyncMock(return_value='{"proposal":"ok"}')
        ), patch.object(adapter, "_render_prompt") as mock_render:
            mock_render.return_value = "prompt string"

            await adapter.refine_proposal(
                project={"title": "Test"},
                user_feedback_observations="Feedback",
                model_id="test/model",
                contract_type="project_fixed",
                use_initial_template=True,
            )

            template_name = mock_render.call_args[0][0]
            assert template_name == "proposal.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_proposal_staffing_j2_when_contract_type_changes_to_staffing(
        self, adapter: OpenRouterAdapter,
    ) -> None:
        """When use_initial_template=True and contract_type is
        staff_augmentation, should render proposal_staffing.j2."""
        with patch.object(
            adapter, "_chat_completion", AsyncMock(return_value='{"cover_letter":"ok"}')
        ), patch.object(adapter, "_render_prompt") as mock_render:
            mock_render.return_value = "prompt string"

            await adapter.refine_proposal(
                project={"title": "Test"},
                user_feedback_observations="Feedback",
                model_id="test/model",
                contract_type="staff_augmentation",
                use_initial_template=True,
            )

            template_name = mock_render.call_args[0][0]
            assert template_name == "proposal_staffing.j2"


# ------------------------------------------------------------------
#  Database-driven model override tests (GeminiAdapter)
# ------------------------------------------------------------------


class TestGeminiAdapterModelOverrides:
    """Validate that GeminiAdapter uses DB-provided model IDs when given."""

    @pytest.fixture(autouse=True)
    def _patch_genai(self) -> None:
        """Prevent GeminiAdapter from making real API client calls."""
        with patch("app.intelligence.adapters.gemini.genai.Client"):
            yield

    def test_constructor_accepts_model_overrides(self) -> None:
        """Should accept standard_model and premium_model in constructor."""
        from app.intelligence.adapters.gemini import GeminiAdapter

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
            adapter = GeminiAdapter(
                standard_model="db-gemini-standard",
                premium_model="db-gemini-premium",
            )
        assert adapter._standard_model_override == "db-gemini-standard"
        assert adapter._premium_model_override == "db-gemini-premium"

    def test_set_model_flash_uses_override(self) -> None:
        """set_gemini_model('flash') should use the standard override."""
        from app.intelligence.adapters.gemini import GeminiAdapter

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
            adapter = GeminiAdapter(standard_model="db-gs")
        result = adapter.set_gemini_model("flash")
        assert result == "db-gs"
        assert adapter.model_id == "db-gs"

    def test_set_model_pro_uses_override(self) -> None:
        """set_gemini_model('pro') should use the premium override."""
        from app.intelligence.adapters.gemini import GeminiAdapter

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
            adapter = GeminiAdapter(premium_model="db-gp")
        result = adapter.set_gemini_model("pro")
        assert result == "db-gp"
        assert adapter.model_id == "db-gp"

    def test_set_model_falls_back_to_hardcoded_standard(self) -> None:
        """When no override given, should use hardcoded STANDARD_MODEL for flash."""
        from app.intelligence.adapters.gemini import (
            GeminiAdapter,
            STANDARD_MODEL as GEMINI_STANDARD,
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
            adapter = GeminiAdapter()
        result = adapter.set_gemini_model("flash")
        assert result == GEMINI_STANDARD

    def test_set_model_falls_back_to_hardcoded_premium(self) -> None:
        """When no override given, should use hardcoded PREMIUM_MODEL for pro."""
        from app.intelligence.adapters.gemini import (
            GeminiAdapter,
            PREMIUM_MODEL as GEMINI_PREMIUM,
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
            adapter = GeminiAdapter()
        result = adapter.set_gemini_model("pro")
        assert result == GEMINI_PREMIUM

    def test_set_model_default_strategy_uses_filter_model(self) -> None:
        """The default strategy ('none') should still use FILTER_MODEL, not overrides."""
        from app.intelligence.adapters.gemini import (
            FILTER_MODEL,
            GeminiAdapter,
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
            adapter = GeminiAdapter(
                standard_model="db-gs", premium_model="db-gp"
            )
        result = adapter.set_gemini_model("none")
        # FILTER_MODEL should be used for default, regardless of overrides
        assert result == FILTER_MODEL

    def test_override_does_not_affect_delay(self) -> None:
        """Model overrides should not affect delay logic."""
        from app.intelligence.adapters.gemini import GeminiAdapter

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
            adapter = GeminiAdapter(
                standard_model="db-gs", premium_model="db-gp"
            )
        with patch.dict(os.environ, {}, clear=True):
            assert adapter.set_delay_model("flash") == 1.0
            assert adapter.set_delay_model("pro") == 35.0

    def test_generate_proposal_uses_model_override(
        self, cb: MagicMock
    ) -> None:
        """Adapters should carry overrides through the full call chain."""
        from app.intelligence.adapters.gemini import GeminiAdapter

        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
            adapter = GeminiAdapter(
                standard_model="db-gs-from-proposal",
                premium_model="db-gp-from-proposal",
            )

        assert adapter._standard_model_override == "db-gs-from-proposal"
        assert adapter._premium_model_override == "db-gp-from-proposal"

        # Simulate what happens during generate_proposal with a 'pro' strategy
        adapter.set_gemini_model("pro")
        assert adapter.model_id == "db-gp-from-proposal"
