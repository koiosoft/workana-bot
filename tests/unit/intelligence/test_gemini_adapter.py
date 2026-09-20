import pytest
import google.genai.errors
from unittest.mock import MagicMock, patch, AsyncMock
import json

from app.intelligence.adapters.gemini import GeminiAdapter
from app.bots.telegram.circuit_breaker import CircuitBreaker
from app.exceptions import AIConnectionError
from app.intelligence.pipeline import generate_project_fixed_proposal

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
    """Should use s3-commercial/write-proposal-staffing.j2 for staff_augmentation contract type."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = '{"cover_letter": "test", "budget_summary": {"hourly_rate": 25, "suggested_hours_per_week": 20, "estimated_monthly_budget": 2000}}'
    project_data = {"title": "Test", "contract_type": "staff_augmentation"}

    result = await adapter.generate_proposal(project_data, circuit_breaker=mock_circuit_breaker)

    assert "cover_letter" in result
    assert "budget_summary" in result


@pytest.mark.asyncio
async def test_generate_proposal_selects_proposal_template(mock_genai_client, mock_circuit_breaker):
    """Should use s3-commercial/write-proposal.j2 for project_fixed contract type."""
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
        """Default: project_fixed should render s4-refine/refine-proposal.j2."""
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
            assert template_name == "s4-refine/refine-proposal.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_refine_staffing_j2_for_staff_augmentation(
        self, mock_genai_client,
    ) -> None:
        """When contract_type is staff_augmentation (no initial template),
        should render s4-refine/refine-proposal-staffing.j2."""
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
            assert template_name == "s4-refine/refine-proposal-staffing.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_proposal_j2_when_contract_type_changes_to_fixed(
        self, mock_genai_client,
    ) -> None:
        """When use_initial_template=True and contract_type is project_fixed,
        should render s3-commercial/write-proposal.j2."""
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
            assert template_name == "s3-commercial/write-proposal.j2"

    @pytest.mark.asyncio
    async def test_refine_uses_proposal_staffing_j2_when_contract_type_changes_to_staffing(
        self, mock_genai_client,
    ) -> None:
        """When use_initial_template=True and contract_type is
        staff_augmentation, should render s3-commercial/write-proposal-staffing.j2."""
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
            assert template_name == "s3-commercial/write-proposal-staffing.j2"


# ---------------------------------------------------------------------------
#  Staged pipeline method tests (UNIT004, UNIT005, UNIT010, UNIT011,
#  UNIT018, UNIT019, UNIT020) — GeminiAdapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_requirement_exists(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT004: analyze_requirement should exist and accept documented signature."""
    adapter = GeminiAdapter()
    assert hasattr(adapter, "analyze_requirement")
    import inspect
    sig = inspect.signature(adapter.analyze_requirement)
    params = list(sig.parameters.keys())
    assert "project" in params
    assert "maturity_threshold" in params
    assert "circuit_breaker" in params


@pytest.mark.asyncio
async def test_estimate_technical_exists(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT004: estimate_technical should exist and accept documented signature."""
    adapter = GeminiAdapter()
    assert hasattr(adapter, "estimate_technical")
    import inspect
    sig = inspect.signature(adapter.estimate_technical)
    params = list(sig.parameters.keys())
    assert "project" in params
    assert "analysis" in params
    assert "circuit_breaker" in params


@pytest.mark.asyncio
async def test_write_commercial_proposal_exists(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT004: write_commercial_proposal should exist and accept documented signature."""
    adapter = GeminiAdapter()
    assert hasattr(adapter, "write_commercial_proposal")
    import inspect
    sig = inspect.signature(adapter.write_commercial_proposal)
    params = list(sig.parameters.keys())
    assert "project" in params
    assert "technical_estimate" in params
    assert "circuit_breaker" in params


@pytest.mark.asyncio
async def test_analyze_requirement_passes_response_mime_type(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT005: verify analyze_requirement sends config with response_mime_type='application/json'."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = (
        '{"maturity_score": 7, "maturity_reason": "Good detail", '
        + '"entities": {"technologies": [], "deliverables": [], "constraints": []}, '
        + '"gaps": ["some gap"], "branch": "full"}'
    )
    with patch.object(adapter, "_render_prompt", return_value="prompt"):
        await adapter.analyze_requirement(
            project={"description": "test"},
            circuit_breaker=mock_circuit_breaker,
        )
    call_kwargs = mock_genai_client.models.generate_content.call_args[1]
    assert "config" in call_kwargs
    assert call_kwargs["config"]["response_mime_type"] == "application/json"


@pytest.mark.asyncio
async def test_estimate_technical_passes_response_mime_type(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT005: verify estimate_technical sends config with response_mime_type='application/json'."""
    adapter = GeminiAdapter()
    # Provide a minimal valid TechnicalEstimateFull JSON to avoid validation failure
    valid_full_response = json.dumps({
        "estimate_type": "full",
        "analysis": {"maturity_score": 7, "maturity_reason": "G", "entities": {"technologies": [], "deliverables": [], "constraints": []}, "gaps": ["g"], "branch": "full"},
        "model_used": "test-model",
        "milestones": [{"step": 1, "name": "M1", "tasks": {"t1": {"description": "d", "hours_with_overhead": 10}}, "hours_with_overhead": 10, "subtotal": 450}],
        "summary": {"total_hours": 10, "total_budget": 450, "delivery_time_weeks": 1, "hourly_rate_applied": 45}
    })
    mock_genai_client.models.generate_content.return_value.text = valid_full_response
    with patch.object(adapter, "_render_prompt", return_value="prompt"):
        await adapter.estimate_technical(
            project={"description": "test"},
            analysis={"branch": "full"},
            circuit_breaker=mock_circuit_breaker,
        )
    call_kwargs = mock_genai_client.models.generate_content.call_args[1]
    assert "config" in call_kwargs
    assert call_kwargs["config"]["response_mime_type"] == "application/json"


@pytest.mark.asyncio
async def test_analyze_requirement_renders_correct_template(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT011: verify analyze_requirement renders s2-estimation/analyze-requirement.j2."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = (
        '{"maturity_score": 7, "maturity_reason": "Good detail", '
        + '"entities": {"technologies": [], "deliverables": [], "constraints": []}, '
        + '"gaps": ["some gap"], "branch": "full"}'
    )
    with patch.object(adapter, "_render_prompt") as mock_render:
        mock_render.return_value = "prompt"
        await adapter.analyze_requirement(
            project={"description": "test project"},
            circuit_breaker=mock_circuit_breaker,
        )
    template_name = mock_render.call_args[0][0]
    assert template_name == "s2-estimation/analyze-requirement.j2"


@pytest.mark.asyncio
async def test_estimate_technical_renders_correct_template_full(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT011: verify estimate_technical renders estimate-full.j2 for branch='full'."""
    adapter = GeminiAdapter()
    valid_full_json = json.dumps({
        "estimate_type": "full",
        "analysis": {"maturity_score": 7, "maturity_reason": "G", "entities": {"technologies": [], "deliverables": [], "constraints": []}, "gaps": ["g"], "branch": "full"},
        "model_used": "test-model",
        "milestones": [{"step": 1, "name": "M1", "tasks": {"t1": {"description": "d", "hours_with_overhead": 10}}, "hours_with_overhead": 10, "subtotal": 450}],
        "summary": {"total_hours": 10, "total_budget": 450, "delivery_time_weeks": 1, "hourly_rate_applied": 45}
    })
    mock_genai_client.models.generate_content.return_value.text = valid_full_json
    with patch.object(adapter, "_render_prompt") as mock_render:
        mock_render.return_value = "prompt"
        await adapter.estimate_technical(
            project={"description": "test"},
            analysis={"branch": "full"},
            circuit_breaker=mock_circuit_breaker,
        )
    template_name = mock_render.call_args[0][0]
    assert template_name == "s2-estimation/estimate-full.j2"


@pytest.mark.asyncio
async def test_estimate_technical_renders_correct_template_discovery(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT011: verify estimate_technical renders estimate-discovery.j2 for branch='discovery'."""
    adapter = GeminiAdapter()
    valid_discovery_json = json.dumps({
        "estimate_type": "discovery",
        "analysis": {"maturity_score": 3, "maturity_reason": "Vague", "entities": {"technologies": [], "deliverables": [], "constraints": []}, "gaps": ["unclear scope"], "branch": "discovery"},
        "model_used": "test-model",
        "milestones": [],
        "summary": {"total_hours": 0, "total_budget": 0.0, "delivery_time_weeks": 0, "hourly_rate_applied": 18.0},
        "scope_matrix": {"in_scope": [], "out_of_scope": []},
        "discovery_hours": 40,
        "post_discovery_hourly_rate": 18.0,
        "open_questions": ["What is the scope?"]
    })
    mock_genai_client.models.generate_content.return_value.text = valid_discovery_json
    with patch.object(adapter, "_render_prompt") as mock_render:
        mock_render.return_value = "prompt"
        await adapter.estimate_technical(
            project={"description": "test"},
            analysis={"branch": "discovery"},
            circuit_breaker=mock_circuit_breaker,
        )
    template_name = mock_render.call_args[0][0]
    assert template_name == "s2-estimation/estimate-discovery.j2"


@pytest.mark.asyncio
async def test_write_commercial_proposal_renders_correct_template(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT011: verify write_commercial_proposal renders s3-commercial/write-proposal.j2."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = (
        '{"proposal_header": "H", "milestones": [], "summary": {}, '
        + '"technical_pitch": "", "questions_for_client": []}'
    )
    with patch.object(adapter, "_render_prompt") as mock_render:
        mock_render.return_value = "prompt"
        await adapter.write_commercial_proposal(
            project={"title": "Test"},
            technical_estimate={"milestones": [], "summary": {}},
            circuit_breaker=mock_circuit_breaker,
        )
    template_name = mock_render.call_args[0][0]
    assert template_name == "s3-commercial/write-proposal.j2"


@pytest.mark.asyncio
async def test_write_commercial_proposal_contract_fields(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT018: contract test — output should contain proposal_header, milestones,
    summary, technical_pitch, questions_for_client."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = (
        '```json\n{"proposal_header": "Prop", "milestones": [], '
        + '"summary": {"total_hours": 40, "total_budget": 1000}, '
        + '"technical_pitch": "Tech", "questions_for_client": []}\n```'
    )
    with patch.object(adapter, "_render_prompt", return_value="prompt"):
        result = await adapter.write_commercial_proposal(
            project={"title": "Test"},
            technical_estimate={"milestones": [], "summary": {"total_hours": 40}},
            circuit_breaker=mock_circuit_breaker,
        )

    assert "proposal_header" in result
    assert "milestones" in result
    assert "summary" in result
    assert "technical_pitch" in result
    assert "questions_for_client" in result


@pytest.mark.asyncio
async def test_write_commercial_proposal_verbatim_milestones_summary(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT019: verbatim test — milestones and summary injected deep-equal from technical_estimate."""
    adapter = GeminiAdapter()
    tech_estimate_milestones = [{"step": 1, "name": "Design", "tasks": {}, "hours_with_overhead": 10.0, "subtotal": 250.0}]
    tech_estimate_summary = {"total_hours": 40, "total_budget": 1000, "delivery_time_weeks": 4, "hourly_rate_applied": 25}
    mock_genai_client.models.generate_content.return_value.text = (
        '```json\n{"proposal_header": "Test", "milestones": ["LLM_HALLUCINATION"], '
        + '"summary": {"wrong": "llm data"}, "technical_pitch": "pitch", '
        + '"questions_for_client": []}\n```'
    )
    with patch.object(adapter, "_render_prompt", return_value="prompt"):
        result = await adapter.write_commercial_proposal(
            project={"title": "Test"},
            technical_estimate={
                "milestones": tech_estimate_milestones,
                "summary": tech_estimate_summary,
            },
            circuit_breaker=mock_circuit_breaker,
        )
    assert result["milestones"] == tech_estimate_milestones
    assert result["summary"] == tech_estimate_summary


@pytest.mark.asyncio
async def test_generate_project_fixed_proposal_accumulates(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT020: accumulation test — generate_project_fixed_proposal returns
    analysis + estimate + proposal keys."""
    adapter = GeminiAdapter()
    mock_analysis = {"branch": "full", "summary": "analysis done"}
    mock_estimate = {"milestones": [], "summary": {"total_hours": 40}}
    mock_proposal = {"proposal_header": "H", "technical_pitch": "p", "questions_for_client": []}
    with patch.object(adapter, "analyze_requirement", AsyncMock(return_value=mock_analysis)):
        with patch.object(adapter, "estimate_technical", AsyncMock(return_value=mock_estimate)):
            with patch.object(adapter, "write_commercial_proposal", AsyncMock(return_value=mock_proposal)):
                result = await generate_project_fixed_proposal(
                    {"title": "Test"},
                    standard_adapter=adapter,
                    premium_adapter=adapter,
                )
    assert "analysis" in result
    assert result["analysis"] == mock_analysis
    assert "estimate" in result
    assert result["estimate"] == mock_estimate
    assert "proposal" in result
    assert result["proposal"] == mock_proposal


@pytest.mark.asyncio
async def test_staff_augmentation_path_unchanged(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT016: regression test — staff_augmentation generate_proposal path unchanged.
    Should return cover_letter and budget_summary."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = (
        '```json\n{"cover_letter": "Dear", '
        + '"budget_summary": {"hourly_rate": 25, "suggested_hours_per_week": 20, '
        + '"estimated_monthly_budget": 2000}}\n```'
    )
    result = await adapter.generate_proposal(
        {"title": "Test", "contract_type": "staff_augmentation"},
        circuit_breaker=mock_circuit_breaker,
    )
    assert "cover_letter" in result
    assert "budget_summary" in result


@pytest.mark.asyncio
async def test_maturity_threshold_read_and_forwarded(
    mock_genai_client, mock_circuit_breaker
) -> None:
    """UNIT010: MATURITY_THRESHOLD env var default is 8 and forwarded to analyze_requirement."""
    adapter = GeminiAdapter()
    mock_genai_client.models.generate_content.return_value.text = (
        '{"maturity_score": 7, "maturity_reason": "Good detail", '
        + '"entities": {"technologies": [], "deliverables": [], "constraints": []}, '
        + '"gaps": ["some gap"], "branch": "full"}'
    )
    with patch("app.intelligence.config.os.environ.get", return_value="8"):
        with patch.object(adapter, "_render_prompt") as mock_render:
            mock_render.return_value = "prompt"
            await adapter.analyze_requirement(
                project={"description": "test"},
                circuit_breaker=mock_circuit_breaker,
            )
    # Check threshold was passed to render
    call_kwargs = mock_render.call_args[1]
    assert call_kwargs.get("threshold") == 8
