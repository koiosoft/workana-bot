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
    assert result == "google/gemini-2.5-pro"
    assert adapter.model_id == "google/gemini-2.5-pro"


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
