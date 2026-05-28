"""
Tests unitarios para las notificaciones del comando /lista (fetch_projects).
Verifica que siempre se envíe una notificación al finalizar el proceso.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
import os


@pytest.fixture
def mock_update():
    """Fixture para un mock de telegram.Update."""
    update = MagicMock()
    update.effective_user.id = os.getenv("MY_TELEGRAM_ID", "12345")
    update.message = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Fixture para un mock de telegram.ext.ContextTypes.DEFAULT_TYPE."""
    return MagicMock()


@pytest.mark.asyncio
class TestFetchProjectsNotifications:
    
    @pytest.fixture(autouse=True)
    def patch_dependencies(self, mocker):
        """Mockear todas las dependencias externas."""
        mocker.patch('app.bots.telegram.handlers.get_projects_repository', return_value=AsyncMock())
        mocker.patch('app.bots.telegram.handlers.ScraperFactory.get_scraper', return_value=AsyncMock())
        mocker.patch('app.bots.telegram.handlers.get_intelligence_service', return_value=AsyncMock())
        mocker.patch('app.bots.telegram.handlers.is_admin', return_value=True)
        mocker.patch('app.bots.telegram.handlers.send_long_message', new_callable=AsyncMock)
    
    async def test_notifies_when_no_relevant_projects_found(self, mock_update, mock_context, mocker):
        """
        Verifica que se envíe notificación cuando NO se encuentran oportunidades.
        """
        from app.bots.telegram.handlers import fetch_projects
        
        # --- Configuración ---
        mock_repo = mocker.patch('app.bots.telegram.handlers.get_projects_repository', return_value=AsyncMock()).return_value
        mock_repo.collection.count_documents.return_value = 10
        mock_repo.claim_pending_projects.side_effect = [
            [{"link_hash": f"hash{i}", "title": f"Project {i}"} for i in range(10)],
            None  # Segunda llamada retorna None (no más proyectos)
        ]
        
        mock_scraper = mocker.patch('app.bots.telegram.handlers.ScraperFactory.get_scraper', return_value=AsyncMock()).return_value
        mock_scraper.get_projects.return_value = [{"title": "Test Project"}]
        
        mock_ai = mocker.patch('app.bots.telegram.handlers.get_intelligence_service', return_value=AsyncMock()).return_value
        # Todos los proyectos tienen score bajo (≤4)
        mock_ai.evaluate_projects.return_value = [
            {"score": i % 4, "strategy": "none", "summary": "test", "contract_type": "project_fixed", "reason": "test"}
            for i in range(10)
        ]
        
        # --- Ejecución ---
        await fetch_projects(mock_update, mock_context)
        
        # --- Aserciones ---
        reply_calls = mock_update.message.reply_text.call_args_list
        reply_texts = [call[0][0] if call[0] else call.kwargs.get('text', '') for call in reply_calls]
        
        # Debe haber un mensaje de finalización
        assert any("Análisis Completado" in text for text in reply_texts), \
            "Debe notificar que el análisis completó"
        assert any("Proyectos analizados: 10" in text for text in reply_texts), \
            "Debe indicar cuántos proyectos se analizaron"
        assert any("No se encontraron oportunidades" in text for text in reply_texts), \
            "Debe indicar que no hubo oportunidades destacadas"
    
    async def test_notifies_when_relevant_projects_found(self, mock_update, mock_context, mocker):
        """
        Verifica que se envíe notificación cuando SÍ se encuentran oportunidades.
        """
        from app.bots.telegram.handlers import fetch_projects
        
        # --- Configuración ---
        mock_repo = mocker.patch('app.bots.telegram.handlers.get_projects_repository', return_value=AsyncMock()).return_value
        mock_repo.collection.count_documents.return_value = 5
        mock_repo.claim_pending_projects.side_effect = [
            [{"link_hash": f"hash{i}", "title": f"Project {i}", "budget": "$1000", "link": f"http://test.com/{i}"} for i in range(5)],
            None
        ]
        
        mock_scraper = mocker.patch('app.bots.telegram.handlers.ScraperFactory.get_scraper', return_value=AsyncMock()).return_value
        mock_scraper.get_projects.return_value = [{"title": "Test Project"}]
        
        mock_ai = mocker.patch('app.bots.telegram.handlers.get_intelligence_service', return_value=AsyncMock()).return_value
        # Algunos proyectos con score alto (>4)
        mock_ai.evaluate_projects.return_value = [
            {"score": 8, "strategy": "none", "summary": "Good project", "contract_type": "project_fixed", "reason": "Excellent match"},
            {"score": 9, "strategy": "none", "summary": "Great project", "contract_type": "staff_augmentation", "reason": "Perfect fit"},
            {"score": 7, "strategy": "none", "summary": "Nice project", "contract_type": "project_fixed", "reason": "Good"},
            {"score": 3, "strategy": "none", "summary": "Poor project", "contract_type": "project_fixed", "reason": "Not suitable"},
            {"score": 2, "strategy": "none", "summary": "Bad project", "contract_type": "project_fixed", "reason": "Not good"},
        ]
        
        mock_send_long = mocker.patch('app.bots.telegram.handlers.send_long_message', new_callable=AsyncMock)
        
        # --- Ejecución ---
        await fetch_projects(mock_update, mock_context)
        
        # --- Aserciones ---
        # Debe enviar el mensaje largo con las oportunidades
        mock_send_long.assert_called_once()
        call_args = mock_send_long.call_args
        message_text = call_args[0][1]  # Segundo argumento es el mensaje
        
        assert "3 Oportunidades encontradas (de 5 analizados)" in message_text, \
            "Debe indicar cuántas oportunidades se encontraron"

        assert "Score: 8/10" in message_text, \
            "Debe mostrar los proyectos con score alto"
    
    async def test_notifies_when_no_pending_projects_exist(self, mock_update, mock_context, mocker):
        """
        Verifica que se envíe notificación cuando no hay proyectos pendientes desde el inicio.
        """
        from app.bots.telegram.handlers import fetch_projects
        
        # --- Configuración ---
        mock_repo = mocker.patch('app.bots.telegram.handlers.get_projects_repository', return_value=AsyncMock()).return_value
        mock_repo.collection.count_documents.return_value = 0
        mock_repo.claim_pending_projects.return_value = None  # No hay proyectos pendientes
        
        mock_scraper = mocker.patch('app.bots.telegram.handlers.ScraperFactory.get_scraper', return_value=AsyncMock()).return_value
        mock_scraper.get_projects.return_value = [{"title": "Test Project"}]
        
        # --- Ejecución ---
        await fetch_projects(mock_update, mock_context)
        
        # --- Aserciones ---
        reply_calls = mock_update.message.reply_text.call_args_list
        reply_texts = [call[0][0] if call[0] else call.kwargs.get('text', '') for call in reply_calls]
        
        # Debe haber notificado que hay 0 proyectos pendientes
        assert any("0 proyectos pendientes" in text for text in reply_texts), \
            "Debe notificar que hay 0 proyectos pendientes"
