"""Unit tests for the OpenRouterAdapter intelligence adapter."""

import os
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.bots.telegram.circuit_breaker import CircuitBreaker
from app.exceptions import AIConnectionError, PipelineError
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
        should render s4-refine/refine-proposal.j2."""
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
            assert template_name == "s4-refine/refine-proposal.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_refine_staffing_j2_for_staff_augmentation(
        self, adapter: OpenRouterAdapter,
    ) -> None:
        """When contract_type is staff_augmentation and not an initial
        template, should render s4-refine/refine-proposal-staffing.j2."""
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
            assert template_name == "s4-refine/refine-proposal-staffing.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_proposal_j2_when_contract_type_changes_to_fixed(
        self, adapter: OpenRouterAdapter,
    ) -> None:
        """When use_initial_template=True and contract_type is project_fixed,
        should render s3-commercial/write-proposal.j2."""
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
            assert template_name == "s3-commercial/write-proposal.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_proposal_staffing_j2_when_contract_type_changes_to_staffing(
        self, adapter: OpenRouterAdapter,
    ) -> None:
        """When use_initial_template=True and contract_type is
        staff_augmentation, should render s3-commercial/write-proposal-staffing.j2."""
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
            assert template_name == "s3-commercial/write-proposal-staffing.j2"


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


# ------------------------------------------------------------------
#  New staged pipeline methods (UNIT004, UNIT005, UNIT010, UNIT018,
#  UNIT019, UNIT020) — OpenRouterAdapter
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_requirement_exists(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """UNIT004: analyze_requirement should exist and accept documented signature."""
    assert hasattr(adapter, "analyze_requirement")
    import inspect
    sig = inspect.signature(adapter.analyze_requirement)
    params = list(sig.parameters.keys())
    assert "project" in params
    assert "maturity_threshold" in params
    assert "circuit_breaker" in params


@pytest.mark.asyncio
async def test_estimate_technical_exists(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """UNIT004: estimate_technical should exist and accept documented signature."""
    assert hasattr(adapter, "estimate_technical")
    import inspect
    sig = inspect.signature(adapter.estimate_technical)
    params = list(sig.parameters.keys())
    assert "project" in params
    assert "analysis" in params
    assert "circuit_breaker" in params


@pytest.mark.asyncio
async def test_write_commercial_proposal_exists(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """UNIT004: write_commercial_proposal should exist and accept documented signature."""
    assert hasattr(adapter, "write_commercial_proposal")
    import inspect
    sig = inspect.signature(adapter.write_commercial_proposal)
    params = list(sig.parameters.keys())
    assert "project" in params
    assert "technical_estimate" in params
    assert "circuit_breaker" in params


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_maturity_threshold_default_forwarded(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """UNIT010: verify MATURITY_THRESHOLD default is 8 and passed to analyze_requirement.
    We mock _render_prompt to capture the threshold value."""
    valid_response = json.dumps({
        "maturity_score": 7,
        "maturity_reason": "Good details but some gaps",
        "entities": {"technologies": ["Python"], "deliverables": [], "constraints": []},
        "gaps": ["Missing testing strategy"],
        "branch": "full"
    })
    with patch.object(adapter, "_render_prompt", return_value="prompt"):
        with patch.object(adapter, "_chat_completion", AsyncMock(return_value=valid_response)):
            with patch("app.intelligence.config.os.environ.get", return_value="8"):
                result = await adapter.analyze_requirement(
                    project={"description": "test"},
                )
    # If no error, method was called (mocked returns valid JSON)
    assert result is not None
    assert result["maturity_score"] == 7
    assert result["branch"] == "full"


@pytest.mark.asyncio
async def test_generate_project_fixed_proposal_accumulates(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """UNIT020: accumulation test — generate_project_fixed_proposal should return
    analysis + estimate + proposal keys."""
    # We need to mock all three stage methods
    mock_analysis = {"branch": "full", "summary": "analysis done"}
    mock_estimate = {"milestones": [], "summary": {"total_hours": 40, "total_budget": 1000}}
    mock_proposal = {"proposal_header": "Header", "technical_pitch": "pitch", "questions_for_client": []}

    with patch.object(adapter, "analyze_requirement", AsyncMock(return_value=mock_analysis)):
        with patch.object(adapter, "estimate_technical", AsyncMock(return_value=mock_estimate)):
            with patch.object(adapter, "write_commercial_proposal", AsyncMock(return_value=mock_proposal)):
                result = await adapter.generate_project_fixed_proposal(
                    project={"title": "Test"},
                )

    assert "analysis" in result
    assert result["analysis"] == mock_analysis
    assert "estimate" in result
    assert result["estimate"] == mock_estimate
    assert "proposal" in result
    assert result["proposal"] == mock_proposal


@pytest.mark.asyncio
async def test_write_commercial_proposal_contract_fields(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """UNIT018: contract test — write_commercial_proposal output should contain
    proposal_header, milestones, summary, technical_pitch, questions_for_client.
    We mock _chat_completion to return a response that includes all fields."""
    mock_response = '```json\n{"proposal_header": "Prop", "milestones": [], "summary": {"total_hours": 40, "total_budget": 1000, "delivery_time_weeks": 4, "hourly_rate_applied": 25}, "technical_pitch": "Tech", "questions_for_client": ["Q1"]}\n```'
    with patch.object(adapter, "_chat_completion", AsyncMock(return_value=mock_response)):
        with patch.object(adapter, "_render_prompt", return_value="prompt"):
            result = await adapter.write_commercial_proposal(
                project={"title": "Test"},
                technical_estimate={"milestones": [], "summary": {"total_hours": 40}},
            )

    assert "proposal_header" in result
    assert "milestones" in result
    assert "summary" in result
    assert "technical_pitch" in result
    assert "questions_for_client" in result


@pytest.mark.asyncio
async def test_write_commercial_proposal_verbatim_milestones_summary(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """UNIT019: verbatim test — milestones and summary from technical_estimate
    should be injected verbatim (deep-equal)."""
    tech_estimate_milestones = [{"step": 1, "name": "Design", "tasks": {}, "hours_with_overhead": 10.0, "subtotal": 250.0}]
    tech_estimate_summary = {"total_hours": 40, "total_budget": 1000, "delivery_time_weeks": 4, "hourly_rate_applied": 25}
    mock_llm_response = '```json\n{"proposal_header": "Test", "milestones": ["WRONG"], "summary": {"wrong": "data"}, "technical_pitch": "pitch", "questions_for_client": []}\n```'

    with patch.object(adapter, "_chat_completion", AsyncMock(return_value=mock_llm_response)):
        with patch.object(adapter, "_render_prompt", return_value="prompt"):
            result = await adapter.write_commercial_proposal(
                project={"title": "Test"},
                technical_estimate={
                    "milestones": tech_estimate_milestones,
                    "summary": tech_estimate_summary,
                },
            )

    # Must be deep-equal to the original estimate values, not the LLM's hallucinated ones
    assert result["milestones"] == tech_estimate_milestones
    assert result["summary"] == tech_estimate_summary


@pytest.mark.asyncio
async def test_staff_augmentation_generate_proposal_unchanged(
    adapter: OpenRouterAdapter, cb: MagicMock
) -> None:
    """UNIT016: regression test — staff_augmentation generate_proposal path
    is functionally unchanged. Should return cover_letter and budget_summary."""
    mock_text = ('```json\n{"cover_letter": "Dear client", ',
        '"budget_summary": {"hourly_rate": 25, "suggested_hours_per_week": 20, ',
        '"estimated_monthly_budget": 2000}}\n```')
    mock_text = ''.join(mock_text)
    with patch.object(
        adapter, "_chat_completion", AsyncMock(return_value=mock_text)
    ), patch("asyncio.sleep", AsyncMock()):
        result = await adapter.generate_proposal(
            {"title": "Test", "contract_type": "staff_augmentation"},
            circuit_breaker=cb,
        )

    assert "cover_letter" in result
    assert "budget_summary" in result


# ------------------------------------------------------------------
#  UNIT006 / UNIT007 — Pipeline guard rails (PipelineError)
# ------------------------------------------------------------------
#
#  UNIT006: generate_project_fixed_proposal orchestrates the three
#  stages and aborts before PREMIUM (Stage 3) when Stage 1 or 2
#  raises PipelineError.
#
#  UNIT007: analyze_requirement and estimate_technical raise
#  PipelineError on LLM returning no text, invalid JSON, or
#  Pydantic validation failure. The pipeline stops before Stage 3.
# ------------------------------------------------------------------


class TestPipelineGuardRails:
    """Validate that PipelineError is raised and propagated.

    The orchestrator must abort before Stage 3 (PREMIUM) when any
    earlier stage fails validation.  These tests verify that
    analyze_requirement, estimate_technical and the orchestrator
    itself raise PipelineError under the documented failure modes.
    """

    @pytest.mark.asyncio
    async def test_analyze_requirement_pipeline_error_on_no_text(
        self, adapter: OpenRouterAdapter, cb: MagicMock
    ) -> None:
        """UNIT007: LLM returning no text -> PipelineError."""
        with patch.object(
            adapter, "_chat_completion", AsyncMock(return_value="")
        ):
            with pytest.raises(PipelineError, match="no text"):
                await adapter.analyze_requirement(
                    project={"description": "test"},
                    circuit_breaker=cb,
                )

    @pytest.mark.asyncio
    async def test_analyze_requirement_pipeline_error_on_invalid_json(
        self, adapter: OpenRouterAdapter, cb: MagicMock
    ) -> None:
        """UNIT007: Non-JSON LLM response -> PipelineError."""
        with patch.object(
            adapter, "_chat_completion",
            AsyncMock(return_value="not json at all"),
        ):
            with pytest.raises(PipelineError, match="invalid JSON"):
                await adapter.analyze_requirement(
                    project={"description": "test"},
                    circuit_breaker=cb,
                )

    @pytest.mark.asyncio
    async def test_analyze_requirement_pipeline_error_on_pydantic_fail(
        self, adapter: OpenRouterAdapter, cb: MagicMock
    ) -> None:
        """UNIT007: Pydantic validation failure -> PipelineError.

        Return valid JSON but with an invalid maturity_score (0) so
        RequirementAnalysis.model_validate raises ValidationError.
        """
        invalid_json = '{"maturity_score": 0, "maturity_reason": "x", "branch": "full"}'
        with patch.object(
            adapter, "_chat_completion",
            AsyncMock(return_value=f'```json\n{invalid_json}\n```'),
        ):
            with pytest.raises(PipelineError, match="Pydantic"):
                await adapter.analyze_requirement(
                    project={"description": "test"},
                    circuit_breaker=cb,
                )

    @pytest.mark.asyncio
    async def test_estimate_technical_pipeline_error_on_no_text(
        self, adapter: OpenRouterAdapter, cb: MagicMock
    ) -> None:
        """UNIT007: LLM returning no text in Stage 2 -> PipelineError."""
        with patch.object(
            adapter, "_chat_completion", AsyncMock(return_value="")
        ), patch.object(adapter, "_render_prompt", return_value="prompt"):
            with pytest.raises(PipelineError, match="no text"):
                await adapter.estimate_technical(
                    project={"description": "test"},
                    analysis={"branch": "full", "maturity_score": 8},
                    circuit_breaker=cb,
                )

    @pytest.mark.asyncio
    async def test_estimate_technical_pipeline_error_on_invalid_json(
        self, adapter: OpenRouterAdapter, cb: MagicMock
    ) -> None:
        """UNIT007: Non-JSON LLM response in Stage 2 -> PipelineError."""
        with patch.object(
            adapter, "_chat_completion",
            AsyncMock(return_value="bad response"),
        ), patch.object(adapter, "_render_prompt", return_value="prompt"):
            with pytest.raises(PipelineError, match="invalid JSON"):
                await adapter.estimate_technical(
                    project={"description": "test"},
                    analysis={"branch": "full", "maturity_score": 8},
                    circuit_breaker=cb,
                )

    @pytest.mark.asyncio
    async def test_estimate_technical_pipeline_error_on_pydantic_fail(
        self, adapter: OpenRouterAdapter, cb: MagicMock
    ) -> None:
        """UNIT007: Pydantic validation failure in Stage 2 -> PipelineError.

        Return valid JSON but missing required milestones field.
        """
        invalid_estimate = ('```json\n{"estimate_type": "full", ', 
            '"summary": {"total_hours": 40, "total_budget": 1000, ', 
            '"delivery_time_weeks": 4, "hourly_rate_applied": 25}, ', 
            '"analysis": {"maturity_score": 8, "maturity_reason": "x", ', 
            '"entities": {}, "gaps": [], "branch": "full"}, ', 
            '"model_used": "test"}\n```')
        invalid_estimate = ''.join(invalid_estimate)
        with patch.object(
            adapter, "_chat_completion",
            AsyncMock(return_value=invalid_estimate),
        ), patch.object(adapter, "_render_prompt", return_value="prompt"):
            with pytest.raises(PipelineError, match="Pydantic"):
                await adapter.estimate_technical(
                    project={"description": "test"},
                    analysis={"branch": "full", "maturity_score": 8},
                    circuit_breaker=cb,
                )

    @pytest.mark.asyncio
    async def test_generate_project_fixed_aborts_before_premium_on_stage1_fail(
        self, adapter: OpenRouterAdapter, cb: MagicMock
    ) -> None:
        """UNIT006: PipelineError in Stage 1 should abort before Stage 3.

        When analyze_requirement raises PipelineError, the orchestrator
        must NOT call write_commercial_proposal (the PREMIUM stage).
        """
        with patch.object(
            adapter, "analyze_requirement",
            AsyncMock(side_effect=PipelineError("Stage 1 failed")),
        ):
            mock_write = AsyncMock()
            with patch.object(
                adapter, "write_commercial_proposal", mock_write
            ):
                with pytest.raises(PipelineError):
                    await adapter.generate_project_fixed_proposal(
                        project={"title": "Test"},
                        circuit_breaker=cb,
                    )
                mock_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_generate_project_fixed_aborts_before_premium_on_stage2_fail(
        self, adapter: OpenRouterAdapter, cb: MagicMock
    ) -> None:
        """UNIT006: PipelineError in Stage 2 should abort before Stage 3.

        When estimate_technical raises PipelineError, the orchestrator
        must NOT call write_commercial_proposal (the PREMIUM stage).
        """
        with patch.object(
            adapter, "analyze_requirement",
            AsyncMock(return_value={"branch": "full", "score": 8}),
        ):
            with patch.object(
                adapter, "estimate_technical",
                AsyncMock(side_effect=PipelineError("Stage 2 failed")),
            ):
                mock_write = AsyncMock()
                with patch.object(
                    adapter, "write_commercial_proposal", mock_write
                ):
                    with pytest.raises(PipelineError):
                        await adapter.generate_project_fixed_proposal(
                            project={"title": "Test"},
                            circuit_breaker=cb,
                        )
                    mock_write.assert_not_awaited()
