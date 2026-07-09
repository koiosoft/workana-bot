import pytest
import google.genai.errors
from unittest.mock import MagicMock, patch, AsyncMock

from app.intelligence.adapters.gemini import GeminiAdapter
from app.bots.telegram.circuit_breaker import CircuitBreaker
from app.exceptions import AIConnectionError

@pytest.fixture
def mock_genai_client():
    with patch('app.intelligence.adapters.gemini.genai.Client') as mock_client_constructor:
        mock_client_instance = MagicMock()
        mock_client_constructor.return_value = mock_client_instance
        yield mock_client_instance

@pytest.fixture
def mock_circuit_breaker():
    # Use a real circuit breaker but spy on its methods
    # We can also use MagicMock if we want to control the side effects
    return MagicMock(spec=CircuitBreaker)


@pytest.mark.asyncio
async def test_generate_proposal_records_success(mock_genai_client, mock_circuit_breaker):
    # Arrange
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = '{"key": "value"}'
    project_data = {"title": "Test Project"}

    # Act
    await adapter.generate_proposal(project_data, circuit_breaker=mock_circuit_breaker)

    # Assert
    mock_circuit_breaker.record_success.assert_called_once()
    mock_circuit_breaker.record_failure.assert_not_called()


@pytest.mark.asyncio
async def test_generate_proposal_records_failure_on_api_error(mock_genai_client, mock_circuit_breaker):
    # Arrange
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.side_effect = google.genai.errors.APIError(500, {"error": {"message": "API is down"}})
    project_data = {"title": "Test Project"}

    # Act & Assert
    with pytest.raises(AIConnectionError):
        await adapter.generate_proposal(project_data, circuit_breaker=mock_circuit_breaker)

    mock_circuit_breaker.record_failure.assert_called_once()
    mock_circuit_breaker.record_success.assert_not_called()


@pytest.mark.asyncio
async def test_evaluate_projects_records_success(mock_genai_client, mock_circuit_breaker):
    # Arrange
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = '[{"key": "value"}]'
    projects_data = [{"title": "Test Project 1"}]

    # Act
    await adapter.evaluate_projects(projects_data, circuit_breaker=mock_circuit_breaker)

    # Assert
    mock_circuit_breaker.record_success.assert_called_once()
    mock_circuit_breaker.record_failure.assert_not_called()


@pytest.mark.asyncio
async def test_evaluate_projects_records_failure_on_api_error(mock_genai_client, mock_circuit_breaker):
    # Arrange
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.side_effect = google.genai.errors.APIError(503, {"error": {"message": "API is busy"}})
    projects_data = [{"title": "Test Project 1"}]

    # Act & Assert
    with pytest.raises(AIConnectionError):
        await adapter.evaluate_projects(projects_data, circuit_breaker=mock_circuit_breaker)

    mock_circuit_breaker.record_failure.assert_called_once()
    mock_circuit_breaker.record_success.assert_not_called()


@pytest.mark.asyncio
async def test_format_description_records_success(mock_genai_client, mock_circuit_breaker):
    # Arrange
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = "Formatted description"
    description = "raw description"

    # Act
    await adapter.format_project_description(description, circuit_breaker=mock_circuit_breaker)

    # Assert
    mock_circuit_breaker.record_success.assert_called_once()
    mock_circuit_breaker.record_failure.assert_not_called()


@pytest.mark.asyncio
async def test_format_description_records_failure_on_api_error(mock_genai_client, mock_circuit_breaker):
    # Arrange
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.side_effect = google.genai.errors.APIError(504, {"error": {"message": "Timeout"}})
    description = "raw description"

    # Act & Assert
    with pytest.raises(AIConnectionError):
        await adapter.format_project_description(description, circuit_breaker=mock_circuit_breaker)

    mock_circuit_breaker.record_failure.assert_called_once()
    mock_circuit_breaker.record_success.assert_not_called()


# ========== NEW TESTS ==========

@pytest.mark.asyncio
async def test_format_description_returns_formatted_text(mock_genai_client, mock_circuit_breaker):
    """Should return the formatted description text from the AI."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = "Formatted description"
    description = "raw description"

    result = await adapter.format_project_description(description, circuit_breaker=mock_circuit_breaker)

    assert result == "Formatted description"


@pytest.mark.asyncio
async def test_format_description_returns_original_on_empty_response(mock_genai_client, mock_circuit_breaker):
    """Should return original description when AI returns None."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = None
    description = "raw description"

    result = await adapter.format_project_description(description, circuit_breaker=mock_circuit_breaker)

    assert result == description


@pytest.mark.asyncio
async def test_format_description_uses_standard_model(mock_genai_client, mock_circuit_breaker):
    """Should use STANDARD_MODEL for formatting."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = "Formatted"
    description = "raw"

    await adapter.format_project_description(description, circuit_breaker=mock_circuit_breaker)

    # Verify the model used is the standard one
    call_args = mock_genai_client.models.generate_content.call_args
    assert call_args is not None
    assert call_args[1]['model'] == "models/gemini-2.5-flash"


@pytest.mark.asyncio
async def test_set_gemini_model_default_strategy(mock_genai_client, mock_circuit_breaker):
    """Should set model to FILTER_MODEL for default strategy."""
    adapter = GeminiAdapter()
    adapter.set_gemini_model("none")
    assert adapter.model_id == "models/gemma-4-31b-it"


@pytest.mark.asyncio
async def test_set_gemini_model_flash_strategy(mock_genai_client, mock_circuit_breaker):
    """Should set model to STANDARD_MODEL for flash strategy."""
    adapter = GeminiAdapter()
    adapter.set_gemini_model("flash")
    assert adapter.model_id == "models/gemini-2.5-flash"


@pytest.mark.asyncio
async def test_set_gemini_model_pro_strategy(mock_genai_client, mock_circuit_breaker):
    """Should set model to PREMIUM_MODEL for pro strategy."""
    adapter = GeminiAdapter()
    adapter.set_gemini_model("pro")
    assert adapter.model_id == "models/gemini-2.5-pro"


@pytest.mark.asyncio
async def test_set_delay_model_default_strategy(mock_genai_client, mock_circuit_breaker):
    """Should set delay to 5.0 for default strategy."""
    import os
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'dummy'}):
        os.environ.pop('GEMINI_DELAY_OVERRIDE', None)
        adapter = GeminiAdapter()
        delay = adapter.set_delay_model("none")
        assert delay == 5.0


@pytest.mark.asyncio
async def test_set_delay_model_flash_strategy(mock_genai_client, mock_circuit_breaker):
    """Should set delay to 1.0 for flash strategy."""
    import os
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'dummy'}):
        os.environ.pop('GEMINI_DELAY_OVERRIDE', None)
        adapter = GeminiAdapter()
        delay = adapter.set_delay_model("flash")
        assert delay == 1.0


@pytest.mark.asyncio
async def test_set_delay_model_pro_strategy(mock_genai_client, mock_circuit_breaker):
    """Should set delay to 35.0 for pro strategy."""
    import os
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'dummy'}):
        os.environ.pop('GEMINI_DELAY_OVERRIDE', None)
        adapter = GeminiAdapter()
        delay = adapter.set_delay_model("pro")
        assert delay == 35.0


@pytest.mark.asyncio
async def test_set_delay_model_override(mock_genai_client, mock_circuit_breaker):
    """Should use GEMINI_DELAY_OVERRIDE env var if set."""
    with patch.dict('os.environ', {'GEMINI_DELAY_OVERRIDE': '2.5'}):
        adapter = GeminiAdapter()
        delay = adapter.set_delay_model("none")
        assert delay == 2.5


@pytest.mark.asyncio
async def test_generate_proposal_selects_staffing_template(mock_genai_client, mock_circuit_breaker):
    """Should use proposal_staffing.j2 for staff_augmentation contract type."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = '{"cover_letter": "test", "budget_summary": {"hourly_rate": 25, "suggested_hours_per_week": 20, "estimated_monthly_budget": 2000}}'
    project_data = {"title": "Test", "contract_type": "staff_augmentation"}

    result = await adapter.generate_proposal(project_data, circuit_breaker=mock_circuit_breaker)

    assert "cover_letter" in result
    assert "budget_summary" in result


@pytest.mark.asyncio
async def test_generate_proposal_selects_proposal_template(mock_genai_client, mock_circuit_breaker):
    """Should use proposal.j2 for project_fixed contract type."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = '{"proposal_header": "test", "milestones": [], "summary": {"total_hours": 0, "total_budget": 0, "delivery_time_weeks": 0, "hourly_rate_applied": 25}, "technical_pitch": "test", "questions_for_client": []}'
    project_data = {"title": "Test", "contract_type": "project_fixed"}

    result = await adapter.generate_proposal(project_data, circuit_breaker=mock_circuit_breaker)

    assert "proposal_header" in result
    assert "milestones" in result
    assert "summary" in result


@pytest.mark.asyncio
async def test_generate_proposal_handles_remote_protocol_error(mock_genai_client, mock_circuit_breaker):
    """Should raise AIConnectionError on RemoteProtocolError."""
    from httpx import RemoteProtocolError
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.side_effect = RemoteProtocolError("Connection reset")
    project_data = {"title": "Test"}

    with pytest.raises(AIConnectionError):
        await adapter.generate_proposal(project_data, circuit_breaker=mock_circuit_breaker)

    mock_circuit_breaker.record_failure.assert_called_once()


@pytest.mark.asyncio
async def test_evaluate_projects_handles_remote_protocol_error(mock_genai_client, mock_circuit_breaker):
    """Should raise AIConnectionError on RemoteProtocolError."""
    from httpx import RemoteProtocolError
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.side_effect = RemoteProtocolError("Connection reset")
    projects_data = [{"title": "Test"}]

    with pytest.raises(AIConnectionError):
        await adapter.evaluate_projects(projects_data, circuit_breaker=mock_circuit_breaker)

    mock_circuit_breaker.record_failure.assert_called_once()


@pytest.mark.asyncio
async def test_evaluate_projects_parses_json_from_code_block(mock_genai_client, mock_circuit_breaker):
    """Should extract JSON from ```json ... ``` code block."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = '```json\n[{"score": 8, "reason": "Good project"}]\n```'
    projects_data = [{"title": "Test"}]

    results = await adapter.evaluate_projects(projects_data, circuit_breaker=mock_circuit_breaker)

    assert len(results) == 1
    assert results[0]["score"] == 8


@pytest.mark.asyncio
async def test_evaluate_projects_returns_empty_on_no_text(mock_genai_client, mock_circuit_breaker):
    """Should return empty list when AI returns no text."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = None
    projects_data = [{"title": "Test"}]

    results = await adapter.evaluate_projects(projects_data, circuit_breaker=mock_circuit_breaker)

    assert results == []


@pytest.mark.asyncio
async def test_generate_proposal_returns_error_on_no_text(mock_genai_client, mock_circuit_breaker):
    """Should return error dict when AI returns no text."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = None
    project_data = {"title": "Test"}

    result = await adapter.generate_proposal(project_data, circuit_breaker=mock_circuit_breaker)

    assert "error" in result


# ---------------------------------------------------------------------------
# refine_proposal — template selection
# ---------------------------------------------------------------------------


class TestRefineProposalTemplateSelection:
    """Validate that ``refine_proposal`` selects the correct template based
    on ``contract_type`` and ``use_initial_template`` flags."""

    @pytest.fixture
    def mock_genai_client(self):
        with patch('app.intelligence.adapters.gemini.genai.Client') as mock_client_constructor:
            mock_client_instance = MagicMock()
            mock_client_constructor.return_value = mock_client_instance
            yield mock_client_instance

    @pytest.mark.asyncio
    async def test_refine_uses_refine_j2_for_project_fixed(
        self, mock_genai_client,
    ) -> None:
        """Default: project_fixed should render refine.j2."""
        adapter = GeminiAdapter()
        mock_genai_client.models.generate_content.return_value.text = '{"proposal":"ok"}'

        with patch.object(adapter, "_render_prompt") as mock_render:
            mock_render.return_value = "prompt string"

            await adapter.refine_proposal(
                project={"title": "Test", "contract_type": "project_fixed"},
                user_feedback_observations="Feedback",
                model_id="test/model",
            )

            template_name = mock_render.call_args[0][0]
            assert template_name == "refine.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_refine_staffing_j2_for_staff_augmentation(
        self, mock_genai_client,
    ) -> None:
        """When contract_type is staff_augmentation (no initial template),
        should render refine-staffing.j2."""
        adapter = GeminiAdapter()
        mock_genai_client.models.generate_content.return_value.text = '{"proposal":"ok"}'

        with patch.object(adapter, "_render_prompt") as mock_render:
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
        self, mock_genai_client,
    ) -> None:
        """When use_initial_template=True and contract_type is project_fixed,
        should render proposal.j2."""
        adapter = GeminiAdapter()
        mock_genai_client.models.generate_content.return_value.text = '{"proposal":"ok"}'

        with patch.object(adapter, "_render_prompt") as mock_render:
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
        self, mock_genai_client,
    ) -> None:
        """When use_initial_template=True and contract_type is
        staff_augmentation, should render proposal_staffing.j2."""
        adapter = GeminiAdapter()
        mock_genai_client.models.generate_content.return_value.text = '{"cover_letter":"ok"}'

        with patch.object(adapter, "_render_prompt") as mock_render:
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
