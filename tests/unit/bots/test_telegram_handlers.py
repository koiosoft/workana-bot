import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.bots.telegram.handlers import status, fetch_projects, unlock_semaphore, process_projects
from app.database.requirement_analyses_repository import RequirementAnalysesRepository
from app.database.technical_estimates_repository import TechnicalEstimatesRepository

# Correr con: pytest tests/unit/test_telegram_handlers.py

@pytest.fixture
def mock_update():
    """Fixture para simular el objeto Update de Telegram."""
    update = MagicMock()
    update.effective_user.id = "12345" # Simula un ID de usuario
    update.message = AsyncMock()
    return update

@pytest.fixture
def mock_context():
    """Fixture para simular el objeto Context de Telegram."""
    return MagicMock()

@pytest.fixture
def mock_semaphore():
    """Fixture para simular el ProcessSemaphore."""
    semaphore = MagicMock()
    semaphore.is_locked = AsyncMock()
    semaphore.get_status = AsyncMock()
    semaphore.calculate_remaining_projects = MagicMock()
    semaphore.force_release = AsyncMock()
    return semaphore

@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
async def test_status_when_semaphore_is_unlocked(mock_is_admin, mock_get_semaphore, mock_update, mock_context, mock_semaphore):
    # Condición: Semáforo desbloqueado
    mock_semaphore.is_locked.return_value = False
    mock_get_semaphore.return_value = mock_semaphore

    # Acción
    await status(mock_update, mock_context)

    # Resultado esperado
    mock_update.message.reply_text.assert_called_once()
    call_args, _ = mock_update.message.reply_text.call_args
    assert "📊 **Resumen actual:**" in call_args[0]
    mock_semaphore.get_status.assert_not_called()

@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
async def test_status_when_semaphore_is_locked(mock_is_admin, mock_get_semaphore, mock_update, mock_context, mock_semaphore):
    # Condición: Semáforo bloqueado
    mock_semaphore.is_locked.return_value = True
    status_data = {
        "locked_at": datetime(2026, 5, 29, 10, 0, 0, tzinfo=timezone.utc),
        "last_activity_at": datetime(2026, 5, 29, 10, 5, 30, tzinfo=timezone.utc)
    }
    mock_semaphore.get_status.return_value = status_data
    mock_semaphore.calculate_remaining_projects.return_value = 5
    mock_get_semaphore.return_value = mock_semaphore

    # Acción
    await status(mock_update, mock_context)

    # Resultado esperado
    mock_update.message.reply_text.assert_called_once()
    call_args, _ = mock_update.message.reply_text.call_args
    assert "🚫 **Acción Denegada: Sistema Ocupado**" in call_args[0]
    assert "El comando `/status` no puede ejecutarse" in call_args[0]
    assert "📦 **Proyectos Restantes en la Cola:** 5" in call_args[0]

@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
async def test_status_when_semaphore_check_fails(mock_is_admin, mock_get_semaphore, mock_update, mock_context, mock_semaphore):
    # Condición: Falla al consultar el semáforo
    mock_semaphore.is_locked.side_effect = Exception("DB connection error")
    mock_get_semaphore.return_value = mock_semaphore

    # Acción
    await status(mock_update, mock_context)

    # Resultado esperado
    mock_update.message.reply_text.assert_called_once_with(
        "⚠️ No se pudo verificar el estado del sistema. Por seguridad, la operación ha sido cancelada."
    )

@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.ScraperFactory")
@patch("app.bots.telegram.handlers.get_projects_repository")
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
async def test_fetch_projects_when_semaphore_is_unlocked(mock_is_admin, mock_get_semaphore, mock_get_repo, mock_scraper_factory, mock_update, mock_context, mock_semaphore):
    # Condición: Semáforo desbloqueado
    mock_semaphore.is_locked.return_value = False
    mock_get_semaphore.return_value = mock_semaphore

    # Simulamos que el scraper no devuelve proyectos para no ejecutar toda la función
    mock_scraper = MagicMock()
    # El handler llama get_projects_fresh_context() cuando el scraper lo expone
    # (hasattr -> True en MagicMock), por eso se mockea ese metodo.
    mock_scraper.get_projects_fresh_context = AsyncMock(return_value=[])
    mock_scraper.get_projects = AsyncMock(return_value=[])
    mock_scraper_factory.get_scraper.return_value = mock_scraper
    
    # Acción
    await fetch_projects(mock_update, mock_context)

    # Resultado esperado
    # Verificamos que se llamó para consultar y luego para decir que no hay proyectos
    assert mock_update.message.reply_text.call_count == 2
    first_call_args, _ = mock_update.message.reply_text.call_args_list[0]
    assert "🔍 Consultando nuevos proyectos..." in first_call_args[0]

@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
async def test_fetch_projects_when_semaphore_is_locked(mock_is_admin, mock_get_semaphore, mock_update, mock_context, mock_semaphore):
    # Condición: Semáforo bloqueado
    mock_semaphore.is_locked.return_value = True
    status_data = {
        "locked_at": datetime(2026, 5, 29, 10, 0, 0, tzinfo=timezone.utc),
        "last_activity_at": datetime(2026, 5, 29, 10, 5, 30, tzinfo=timezone.utc)
    }
    mock_semaphore.get_status.return_value = status_data
    mock_semaphore.calculate_remaining_projects.return_value = 10
    mock_get_semaphore.return_value = mock_semaphore

    # Acción
    await fetch_projects(mock_update, mock_context)

    # Resultado esperado
    mock_update.message.reply_text.assert_called_once()
    call_args, _ = mock_update.message.reply_text.call_args
    assert "🚫 **Acción Denegada: Sistema Ocupado**" in call_args[0]
    assert "El comando `/listar` no puede ejecutarse" in call_args[0]
    assert "📦 **Proyectos Restantes en la Cola:** 10" in call_args[0]
    
@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
async def test_fetch_projects_when_semaphore_check_fails(mock_is_admin, mock_get_semaphore, mock_update, mock_context, mock_semaphore):
    # Condición: Falla al consultar el semáforo
    mock_semaphore.is_locked.side_effect = Exception("DB connection error")
    mock_get_semaphore.return_value = mock_semaphore

    # Acción
    await fetch_projects(mock_update, mock_context)

    # Resultado esperado
    mock_update.message.reply_text.assert_called_once_with(
        "⚠️ No se pudo verificar el estado del sistema. Por seguridad, la operación ha sido cancelada."
    )


# ========== NEW TESTS ==========

@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
async def test_unlock_semaphore_when_locked(mock_is_admin, mock_get_semaphore, mock_update, mock_context, mock_semaphore):
    """Should release semaphore and notify when it was locked."""
    mock_semaphore.get_status.return_value = {"is_locked": True}
    mock_get_semaphore.return_value = mock_semaphore

    await unlock_semaphore(mock_update, mock_context)

    mock_semaphore.force_release.assert_called_once()
    mock_update.message.reply_text.assert_called_once()
    call_args, _ = mock_update.message.reply_text.call_args
    assert "🔓 **Semáforo Global liberado manualmente**" in call_args[0]


@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
async def test_unlock_semaphore_when_already_unlocked(mock_is_admin, mock_get_semaphore, mock_update, mock_context, mock_semaphore):
    """Should notify that semaphore was already unlocked."""
    mock_semaphore.get_status.return_value = {"is_locked": False}
    mock_get_semaphore.return_value = mock_semaphore

    await unlock_semaphore(mock_update, mock_context)

    mock_semaphore.force_release.assert_called_once()
    mock_update.message.reply_text.assert_called_once()
    call_args, _ = mock_update.message.reply_text.call_args
    assert "El semáforo ya estaba liberado" in call_args[0]


@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
async def test_unlock_semaphore_when_status_none(mock_is_admin, mock_get_semaphore, mock_update, mock_context, mock_semaphore):
    """Should handle None status gracefully."""
    mock_semaphore.get_status.return_value = None
    mock_get_semaphore.return_value = mock_semaphore

    await unlock_semaphore(mock_update, mock_context)

    mock_semaphore.force_release.assert_called_once()
    mock_update.message.reply_text.assert_called_once()
    call_args, _ = mock_update.message.reply_text.call_args
    assert "El semáforo ya estaba liberado" in call_args[0]


# ========== UNIT017 TESTS: contract_type routing ==========
#
# These tests verify that process_projects correctly routes to
# project_fixed staged pipeline vs staff_augmentation generate_proposal
# based on the project's contract_type field.


@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
@patch("app.bots.telegram.handlers.ScraperFactory")
@patch("app.bots.telegram.handlers.get_projects_repository")
async def test_process_project_fixed_routes_to_staged_pipeline(
    mock_get_repo, mock_scraper_factory, mock_is_admin, mock_get_semaphore, 
    mock_update, mock_context, mock_semaphore
):
    """UNIT017: project_fixed contract type routes to generate_project_fixed_proposal.

    The handler should call the PREMIUM adapter's
    generate_project_fixed_proposal for project_fixed projects.
    """
    mock_semaphore.is_locked = AsyncMock(return_value=False)
    mock_semaphore.acquire = AsyncMock(return_value=True)
    mock_semaphore.update_activity = AsyncMock()
    mock_semaphore.release = AsyncMock()
    mock_get_semaphore.return_value = mock_semaphore

    mock_repo = MagicMock()
    mock_repo.reset_orphaned_proposals = AsyncMock(return_value=0)
    mock_repo.get_projects_for_deep_analysis = AsyncMock(
        return_value=[
            {"link": "http://example.com/1", "link_hash": "hash1", 
             "title": "Project 1", "contract_type": "project_fixed"}
        ]
    )
    mock_repo.collection.find_one = AsyncMock(
        return_value={"_id": "proj123"}
    )
    mock_repo.collection.update_one = AsyncMock()
    mock_repo._proposal_versions = MagicMock()
    mock_repo._proposal_versions.insert_version = AsyncMock()
    mock_repo.mark_projects_status = AsyncMock()
    mock_repo.update_full_details = AsyncMock()
    mock_get_repo.return_value = mock_repo

    mock_scraper = MagicMock()
    mock_scraper.fetch_full_detail = AsyncMock(
        return_value={"full_description": "A good project"}
    )
    mock_scraper_factory.get_scraper.return_value = mock_scraper

    # Simulate the intelligence service with mocked adapters
    mock_standard = MagicMock()
    mock_standard.format_project_description = AsyncMock(
        return_value="Formatted description"
    )
    mock_premium = MagicMock()
    mock_premium.generate_project_fixed_proposal = AsyncMock(
        return_value={
            "analysis": {"branch": "full", "maturity_score": 8},
            "estimate": {"estimate_type": "full", "milestones": [], "summary": {}},
            "proposal": {"proposal_header": "Test"}
        }
    )

    with patch(
        "app.bots.telegram.handlers.create_intelligence_service",
        AsyncMock(return_value={
            "STANDARD": mock_standard,
            "PREMIUM": mock_premium,
            "FILTER": mock_standard,
        })
    ), patch.object(
        RequirementAnalysesRepository, "insert", AsyncMock(return_value="id1")
    ), patch.object(
        TechnicalEstimatesRepository, "insert", AsyncMock(return_value="id2")
    ):
        from app.bots.telegram.handlers import process_projects
        await process_projects(mock_update, mock_context)

    # Verify the staged pipeline was called
    mock_premium.generate_project_fixed_proposal.assert_awaited_once()
    # The project dict should have contract_type and full_description
    call_arg = mock_premium.generate_project_fixed_proposal.call_args[0][0]
    assert call_arg.get("contract_type") == "project_fixed"
    assert "full_description" in call_arg


@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
@patch("app.bots.telegram.handlers.ScraperFactory")
@patch("app.bots.telegram.handlers.get_projects_repository")
async def test_process_staff_augmentation_routes_to_generate_proposal(
    mock_get_repo, mock_scraper_factory, mock_is_admin, mock_get_semaphore, 
    mock_update, mock_context, mock_semaphore
):
    """UNIT017: staff_augmentation contract type routes to generate_proposal.

    The handler should call the PREMIUM adapter's generate_proposal
    (the legacy path) for staff_augmentation projects, not the staged pipeline.
    """
    mock_semaphore.is_locked = AsyncMock(return_value=False)
    mock_semaphore.acquire = AsyncMock(return_value=True)
    mock_semaphore.update_activity = AsyncMock()
    mock_semaphore.release = AsyncMock()
    mock_get_semaphore.return_value = mock_semaphore

    mock_repo = MagicMock()
    mock_repo.reset_orphaned_proposals = AsyncMock(return_value=0)
    mock_repo.get_projects_for_deep_analysis = AsyncMock(
        return_value=[
            {"link": "http://example.com/2", "link_hash": "hash2", 
             "title": "Staff Project", "contract_type": "staff_augmentation"}
        ]
    )
    mock_repo.collection.find_one = AsyncMock(
        return_value={"_id": "proj456"}
    )
    mock_repo.collection.update_one = AsyncMock()
    mock_repo.mark_projects_status = AsyncMock()
    mock_repo.update_full_details = AsyncMock()
    mock_repo.update_project_proposal = AsyncMock()
    mock_get_repo.return_value = mock_repo
    mock_repo.mark_projects_status = AsyncMock()
    mock_repo.update_full_details = AsyncMock()
    mock_repo.update_project_proposal = AsyncMock()
    mock_get_repo.return_value = mock_repo

    mock_scraper = MagicMock()
    mock_scraper.fetch_full_detail = AsyncMock(
        return_value={"full_description": "Need developers"}
    )
    mock_scraper_factory.get_scraper.return_value = mock_scraper

    # Simulate the intelligence service with mocked adapters
    mock_standard = MagicMock()
    mock_standard.format_project_description = AsyncMock(
        return_value="Formatted"
    )
    mock_premium = MagicMock()
    mock_premium.generate_proposal = AsyncMock(
        return_value={"cover_letter": "Dear client", "budget_summary": {}}
    )

    with patch(
        "app.bots.telegram.handlers.create_intelligence_service",
        AsyncMock(return_value={
            "STANDARD": mock_standard,
            "PREMIUM": mock_premium,
            "FILTER": mock_standard,
        })
    ):
        from app.bots.telegram.handlers import process_projects
        await process_projects(mock_update, mock_context)

    # Verify the legacy generate_proposal was called (staffing path)
    mock_premium.generate_proposal.assert_awaited_once()
    # Verify project_fixed pipeline was NOT called
    assert mock_premium.generate_project_fixed_proposal.call_count == 0
