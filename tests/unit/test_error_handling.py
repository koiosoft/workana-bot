"""
Tests unitarios para el manejo de errores en el procesamiento de proyectos.
Verifica la lógica de reintentos, circuit breaker y reporte de errores.
Ejecutar con: pytest tests/unit/test_error_handling.py -v
"""
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch, call
from google.genai.errors import ServerError as GeminiServerError
from app.bots.telegram.handlers import process_projects

# Constantes del manejador que estamos probando
MAX_RETRY_ATTEMPTS = 3
CIRCUIT_BREAKER_THRESHOLD = 5

@pytest.fixture
def mock_update():
    """Fixture para un mock de telegram.Update con un message mockeado."""
    update = MagicMock()
    update.effective_user.id = os.getenv("MY_TELEGRAM_ID", "12345")
    update.message = AsyncMock()
    return update

@pytest.fixture
def mock_context():
    """Fixture para un mock de telegram.ext.ContextTypes.DEFAULT_TYPE."""
    return MagicMock()

@pytest.fixture
def mock_project():
    """Fixture que devuelve un proyecto de ejemplo."""
    return {
        "link": "http://example.com/project/1",
        "link_hash": "hash1",
        "title": "Proyecto de Prueba 1",
        "contract_type": "project_fixed"
    }

@pytest.mark.asyncio
class TestProcessProjectsErrorHandling:
    
    # Mockearemos todos los helpers/factorías a nivel de clase
    @pytest.fixture(autouse=True)
    def patch_dependencies(self, mocker):
        mocker.patch('app.bots.telegram.handlers.get_projects_repository', return_value=AsyncMock())
        mocker.patch('app.bots.telegram.handlers.get_process_semaphore', return_value=AsyncMock())
        mocker.patch('app.bots.telegram.handlers.get_intelligence_service', return_value=AsyncMock())
        mocker.patch('app.bots.telegram.handlers.ScraperFactory.get_scraper', return_value=AsyncMock())
        mocker.patch('app.bots.telegram.handlers.is_admin', return_value=True)

    async def test_retries_on_gemini_server_error_and_succeeds(self, mock_update, mock_context, mock_project, mocker):
        """
        Verifica que el sistema reintenta al recibir un GeminiServerError
        y eventualmente procesa el proyecto si un reintento es exitoso.
        """
        # --- Configuración de Mocks ---
        mock_repo = mocker.patch('app.bots.telegram.handlers.get_projects_repository', return_value=AsyncMock()).return_value
        mock_repo.get_projects_for_deep_analysis.return_value = [mock_project]
        mock_repo.reset_orphaned_proposals.return_value = 0

        mock_semaphore = mocker.patch('app.bots.telegram.handlers.get_process_semaphore', return_value=AsyncMock()).return_value
        mock_semaphore.is_locked.return_value = False
        mock_semaphore.acquire.return_value = True

        mock_ai_service = mocker.patch('app.bots.telegram.handlers.get_intelligence_service', return_value=AsyncMock()).return_value
        mock_ai_service.format_project_description.return_value = "Formatted description."
        mock_ai_service.generate_proposal.side_effect = [
            GeminiServerError(503, response_json={'error': 'dummy'}, response=None),
            {"summary": {"total_budget": 100, "total_hours": 10}}
        ]
        
        mock_scraper = mocker.patch('app.bots.telegram.handlers.ScraperFactory.get_scraper', return_value=AsyncMock()).return_value
        mock_scraper.fetch_full_detail.return_value = {"full_description": "details"}

        # --- Ejecución ---
        await process_projects(mock_update, mock_context)

        # --- Aserciones ---
        # 1. Se llamó a generate_proposal dos veces (1 original + 1 reintento)
        assert mock_ai_service.generate_proposal.call_count == 2
        
        # 2. Se actualizó la propuesta en el repo (señal de éxito)
        mock_repo.update_project_proposal.assert_called_once()
        
        # 3. Se enviaron los mensajes correctos a Telegram
        reply_calls = mock_update.message.reply_text.call_args_list
        
        # Convertir llamadas a texto para facilitar la búsqueda
        reply_texts = [call[0][0] if call[0] else call.kwargs.get('text', '') for call in reply_calls]
        
        assert any("Generando propuesta IA para: Proyecto de Prueba 1" in text for text in reply_texts)
        assert any("✅ (1/1) Propuesta Generada" in text for text in reply_texts)
        assert not any("⚠️" in text for text in reply_texts) # No debería haber mensajes de advertencia de omisión
        # No debería haber mensajes de error crítico (solo el resumen final puede tener ❌ Fallidos: 0)
        assert not any("❌ (1/1)" in text or "Error" in text and "❌" in text for text in reply_texts)

        # 4. El semáforo se liberó al final
        mock_semaphore.release.assert_called_once()

