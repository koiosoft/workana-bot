import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.bots.telegram.handlers import status, fetch_projects

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
