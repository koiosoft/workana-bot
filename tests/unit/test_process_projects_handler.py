import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bots.telegram.handlers import process_projects
from app.exceptions import (
    AIConnectionError,
    CircuitBreakerWarning,
    CircuitBreakerSuspension,
    CircuitBreakerCritical,
    CircuitBreakerTrippedError,
)

# A dummy project list for testing
DUMMY_PROJECTS = [
    {"link": "http://test.com/1", "link_hash": "1", "title": "Project 1"},
    {"link": "http://test.com/2", "link_hash": "2", "title": "Project 2"},
]

@pytest.fixture
def mock_update():
    """Fixture for a mock Telegram Update object."""
    update = MagicMock()
    update.effective_user.id = "12345"
    update.message = AsyncMock()
    return update

@pytest.fixture
def mock_context():
    """Fixture for a mock Telegram Context object."""
    return MagicMock()

@pytest.fixture
def mock_repo():
    """Fixture for a mock ProjectsRepository."""
    repo = MagicMock()
    repo.reset_orphaned_proposals = AsyncMock(return_value=0)
    repo.get_projects_for_deep_analysis = AsyncMock(return_value=DUMMY_PROJECTS)
    repo.mark_projects_status = AsyncMock()
    repo.update_project_proposal = AsyncMock()
    repo.update_full_details = AsyncMock()
    return repo

@pytest.fixture
def mock_semaphore():
    """Fixture for a mock ProcessSemaphore."""
    semaphore = MagicMock()
    semaphore.is_locked = AsyncMock(return_value=False)
    semaphore.acquire = AsyncMock(return_value=True)
    semaphore.release = AsyncMock()
    semaphore.update_activity = AsyncMock()
    return semaphore

@pytest.fixture
def mock_ai_service():
    """Fixture for a mock IntelligenceService."""
    ai_service = MagicMock()
    ai_service.format_project_description = AsyncMock(return_value="Formatted description.")
    ai_service.generate_proposal = AsyncMock(return_value={"summary": "A great proposal."})
    return ai_service

@pytest.fixture
def mock_scraper():
    """Fixture for a mock Scraper."""
    scraper = MagicMock()
    scraper.fetch_full_detail = AsyncMock(return_value={"full_description": "details"})
    return scraper

@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
@patch("app.bots.telegram.handlers.get_projects_repository")
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.get_intelligence_service")
@patch("app.bots.telegram.handlers.ScraperFactory")
async def test_process_projects_happy_path(
    mock_scraper_factory, mock_get_ai, mock_get_semaphore, mock_get_repo, mock_is_admin,
    mock_update, mock_context, mock_repo, mock_semaphore, mock_ai_service, mock_scraper
):
    # Arrange
    mock_get_repo.return_value = mock_repo
    mock_get_semaphore.return_value = mock_semaphore
    mock_get_ai.return_value = mock_ai_service
    mock_scraper_factory.get_scraper.return_value = mock_scraper

    # Act
    await process_projects(mock_update, mock_context)

    # Assert
    assert mock_repo.get_projects_for_deep_analysis.call_count == 1
    assert mock_repo.update_full_details.call_count == len(DUMMY_PROJECTS)
    assert mock_ai_service.generate_proposal.call_count == len(DUMMY_PROJECTS)
    mock_semaphore.acquire.assert_called_once_with(total_projects=len(DUMMY_PROJECTS))
    mock_semaphore.release.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
@patch("app.bots.telegram.handlers.get_projects_repository")
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.get_intelligence_service")
@patch("app.bots.telegram.handlers.ScraperFactory")
async def test_process_projects_first_ai_failure(
    mock_scraper_factory, mock_get_ai, mock_get_semaphore, mock_get_repo, mock_is_admin, mock_sleep,
    mock_update, mock_context, mock_repo, mock_semaphore, mock_ai_service, mock_scraper
):
    # Arrange
    mock_get_repo.return_value = mock_repo
    mock_get_semaphore.return_value = mock_semaphore
    mock_get_ai.return_value = mock_ai_service
    mock_scraper_factory.get_scraper.return_value = mock_scraper
    # Simulate failure on the first project
    mock_ai_service.generate_proposal.side_effect = [AIConnectionError, {"summary": "A great proposal."}]

    # Act
    await process_projects(mock_update, mock_context)

    # Assert
    mock_sleep.assert_not_called()
    assert mock_semaphore.update_activity.call_count == 2
    # Check that the first call recorded 1 failure and the second recorded 1 success
    first_call_args = mock_semaphore.update_activity.call_args_list[0].args
    assert first_call_args == (0, 1, 0) # processed, failed, not_found
    second_call_args = mock_semaphore.update_activity.call_args_list[1].args
    assert second_call_args == (1, 1, 0)
    mock_semaphore.release.assert_called_once()

@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
@patch("app.bots.telegram.handlers.get_projects_repository")
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.get_intelligence_service")
@patch("app.bots.telegram.handlers.ScraperFactory")
async def test_process_projects_warning_backoff(
    mock_scraper_factory, mock_get_ai, mock_get_semaphore, mock_get_repo, mock_is_admin, mock_sleep,
    mock_update, mock_context, mock_repo, mock_semaphore, mock_ai_service, mock_scraper
):
    # Arrange
    mock_get_repo.return_value = mock_repo
    mock_get_semaphore.return_value = mock_semaphore
    mock_get_ai.return_value = mock_ai_service
    mock_scraper_factory.get_scraper.return_value = mock_scraper
    # This exception will be raised on the first call, and a normal dict on the second
    mock_ai_service.generate_proposal.side_effect = [
        CircuitBreakerWarning("Warning", failures=2, backoff=5),
        {"summary": "A great proposal."}
    ]

    # Act
    await process_projects(mock_update, mock_context)

    # Assert
    mock_sleep.assert_called_once_with(300) # 5 minutes
    mock_semaphore.release.assert_called_once() # The process should continue and release

@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
@patch("app.bots.telegram.handlers.get_projects_repository")
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.get_intelligence_service")
@patch("app.bots.telegram.handlers.ScraperFactory")
async def test_process_projects_shutdown_on_trip(
    mock_scraper_factory, mock_get_ai, mock_get_semaphore, mock_get_repo, mock_is_admin, mock_sleep,
    mock_update, mock_context, mock_repo, mock_semaphore, mock_ai_service, mock_scraper
):
    # Arrange
    mock_get_repo.return_value = mock_repo
    mock_get_semaphore.return_value = mock_semaphore
    mock_get_ai.return_value = mock_ai_service
    mock_scraper_factory.get_scraper.return_value = mock_scraper
    mock_ai_service.generate_proposal.side_effect = CircuitBreakerTrippedError("Tripped", failures=5)

    # Act
    await process_projects(mock_update, mock_context)

    # Assert
    mock_sleep.assert_not_called()
    mock_semaphore.release.assert_not_called() # CRITICAL: Semaphore should NOT be released
    # Check for the specific shutdown message
    final_message = mock_update.message.reply_text.call_args.args[0]
    assert "Bot apagado por inestabilidad persistente" in final_message
