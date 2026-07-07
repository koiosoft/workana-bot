import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from app.bots.telegram.handlers import fetch_projects

@pytest.fixture
def mock_dependencies():
    with patch("app.bots.telegram.handlers.is_admin", return_value=True), \
         patch("app.bots.telegram.handlers.get_process_semaphore") as mock_sem, \
         patch("app.bots.telegram.handlers.get_projects_repository") as mock_repo, \
         patch("app.bots.telegram.handlers.ScraperFactory") as mock_scraper, \
         patch("app.bots.telegram.handlers.create_intelligence_service") as mock_ai, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        
        # is_locked is an async method -> must be AsyncMock
        mock_sem.return_value.is_locked = AsyncMock(return_value=False)
        
        # Make async methods AsyncMock
        mock_repo.return_value.collection = AsyncMock()
        mock_repo.return_value.collection.count_documents = AsyncMock(return_value=1)
        mock_repo.return_value.claim_pending_projects = AsyncMock()
        mock_repo.return_value.mark_projects_status = AsyncMock()
        mock_repo.return_value.update_project_analysis = AsyncMock()
        mock_repo.return_value.save_scraped_projects = AsyncMock(return_value={"inserted": 0, "existing": 0})
        
        mock_scraper.get_scraper.return_value.get_projects = AsyncMock()
        
        mock_filter = MagicMock()
        mock_filter.evaluate_projects = AsyncMock()
        mock_ai.return_value = {"FILTER": mock_filter, "STANDARD": MagicMock(), "PREMIUM": MagicMock()}
        
        yield mock_repo, mock_scraper, mock_filter

@pytest.mark.asyncio
async def test_notifies_when_no_relevant_projects_found(mock_dependencies):
    mock_repo, mock_scraper, mock_filter = mock_dependencies
    
    mock_scraper.get_scraper.return_value.get_projects.return_value = [{"link_hash": "1"}]
    mock_repo.return_value.collection.count_documents.return_value = 1
    mock_repo.return_value.claim_pending_projects.side_effect = [[{"link_hash": "1"}], []]
    mock_filter.evaluate_projects.return_value = [{"score": 2}]

    mock_update = AsyncMock()
    await fetch_projects(update=mock_update, context=AsyncMock())
    
    # Verify the final message sent via reply_text
    calls = mock_update.message.reply_text.call_args_list
    assert any("No se encontraron oportunidades destacadas" in call[0][0] for call in calls)

@pytest.mark.asyncio
async def test_notifies_when_relevant_projects_found(mock_dependencies):
    mock_repo, mock_scraper, mock_filter = mock_dependencies
    
    mock_scraper.get_scraper.return_value.get_projects.return_value = [{"link_hash": "1"}]
    mock_repo.return_value.collection.count_documents.return_value = 1
    mock_repo.return_value.claim_pending_projects.side_effect = [[{"link_hash": "1"}], []]
    mock_filter.evaluate_projects.return_value = [{"score": 8, "title": "Great Project"}]

    with patch("app.bots.telegram.handlers.send_long_message") as mock_send:
        mock_update = AsyncMock()
        await fetch_projects(update=mock_update, context=AsyncMock())
        
        mock_send.assert_awaited_once()
        assert "1 Oportunidades encontradas" in mock_send.call_args[0][1]

@pytest.mark.asyncio
async def test_notifies_when_no_pending_projects_exist(mock_dependencies):
    mock_repo, mock_scraper, mock_filter = mock_dependencies
    
    mock_scraper.get_scraper.return_value.get_projects.return_value = []

    mock_update = AsyncMock()
    await fetch_projects(update=mock_update, context=AsyncMock())
    
    calls = mock_update.message.reply_text.call_args_list
    assert any("No se encontraron proyectos nuevos" in call[0][0] for call in calls)
