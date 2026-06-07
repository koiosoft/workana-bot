import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.api.main import app

# Cliente de pruebas de FastAPI
client = TestClient(app)

@pytest.fixture
def mock_repo():
    """Fixture para mockear el ProjectsRepository y evitar llamadas a la BD real."""
    with patch("app.api.routes.projects.ProjectsRepository") as MockRepo:
        mock_instance = MockRepo.return_value
        mock_instance.get_projects = AsyncMock()
        yield mock_instance

def test_list_projects_default_params(mock_repo):
    """Prueba que el endpoint responde correctamente con los parámetros por defecto."""
    # Configurar el mock para devolver una respuesta simulada
    mock_repo.get_projects.return_value = {"projects": [], "total": 0}
    
    response = client.get("/api/projects")
    
    assert response.status_code == 200
    assert response.json() == {"projects": [], "total": 0}
    
    # Verificar que el repositorio fue llamado con los valores por defecto
    mock_repo.get_projects.assert_called_once_with(
        status="all",
        search_term=None,
        staff_augmentation_only=False,
        page=1,
        limit=10
    )

def test_list_projects_with_custom_params(mock_repo):
    """Prueba que el endpoint pasa correctamente los query parameters al repositorio."""
    mock_data = {
        "projects": [{"_id": "123", "title": "Proyecto React"}], 
        "total": 1
    }
    mock_repo.get_projects.return_value = mock_data
    
    response = client.get(
        "/api/projects", 
        params={
            "status": "discarded",
            "searchTerm": "react",
            "staffAugmentationOnly": "true",
            "page": 2,
            "limit": 5
        }
    )
    
    assert response.status_code == 200
    assert response.json() == mock_data
    
    # Verificar que los parámetros se parsearon y enviaron correctamente
    mock_repo.get_projects.assert_called_once_with(
        status="discarded",
        search_term="react",
        staff_augmentation_only=True,
        page=2,
        limit=5
    )

def test_list_projects_invalid_pagination(mock_repo):
    """Prueba que FastAPI valide correctamente los límites de paginación."""
    # Intentar pedir la página 0 (inválido, ge=1)
    response = client.get("/api/projects", params={"page": 0})
    assert response.status_code == 422 # Unprocessable Entity (Error de validación)
    
    # Intentar pedir un límite mayor a 100 (inválido, le=100)
    response = client.get("/api/projects", params={"limit": 101})
    assert response.status_code == 422
