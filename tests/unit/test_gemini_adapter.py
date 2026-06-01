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
