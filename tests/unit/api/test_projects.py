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
        mock_instance.get_project_by_id = AsyncMock()
        mock_instance.update_project_by_id = AsyncMock()
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

def test_get_project_found(mock_repo):
    """Prueba que GET /api/projects/{id} devuelve un proyecto cuando existe."""
    mock_project = {
        "_id": "6a034f37d8e430e05690091b",
        "title": "Test Project",
        "budget": "$500",
        "link": "https://workana.com/project/123",
        "published": "hace 2 horas",
        "short_description": "A test project",
        "bids": "5",
        "source": "workana",
        "proposal_status": "pending",
        "scraped_at": "2024-01-01T00:00:00",
        "link_hash": "abc123",
        "skills": ["Python", "React"]
    }
    mock_repo.get_project_by_id.return_value = mock_project

    response = client.get("/api/projects/6a034f37d8e430e05690091b")
    assert response.status_code == 200
    data = response.json()
    assert data["_id"] == "6a034f37d8e430e05690091b"
    assert data["title"] == "Test Project"
    assert data["budget"] == "$500"

def test_get_project_not_found(mock_repo):
    """Prueba que GET /api/projects/{id} devuelve 404 cuando no existe."""
    mock_repo.get_project_by_id.return_value = None

    response = client.get("/api/projects/6a034f37d8e430e05690091b")
    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}

def test_update_project_success(mock_repo):
    """Prueba que PATCH /api/projects/{id} actualiza y devuelve mensaje de éxito."""
    # Simular que la actualización es exitosa
    mock_repo.update_project_by_id.return_value = True

    response = client.patch(
        "/api/projects/6a034f37d8e430e05690091b",
        json={"title": "New Title"}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Project updated successfully"}

def test_update_project_not_found(mock_repo):
    """Prueba que PATCH /api/projects/{id} devuelve 404 cuando el proyecto no existe."""
    # Simular que la actualización falla (proyecto no encontrado)
    mock_repo.update_project_by_id.return_value = False

    response = client.patch(
        "/api/projects/6a034f37d8e430e05690091b",
        json={"title": "New Title"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found or invalid ID"}

def test_update_project_internal_error(mock_repo):
    """Prueba que PATCH /api/projects/{id} devuelve 500 cuando ocurre un error inesperado."""
    # Simular una excepción inesperada en el repositorio
    mock_repo.update_project_by_id.side_effect = Exception("DB connection lost")

    response = client.patch(
        "/api/projects/6a034f37d8e430e05690091b",
        json={"title": "New Title"}
    )
    assert response.status_code == 500
    data = response.json()
    assert data["detail"]["error"] == "Internal Server Error"

def test_get_project_invalid_id(mock_repo):
    """Prueba que GET /api/projects/{id} devuelve 400 con un ObjectId inválido."""
    response = client.get("/api/projects/not-a-valid-objectid")
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"] == "Bad Request"

def test_update_project_invalid_id(mock_repo):
    """Prueba que PATCH /api/projects/{id} devuelve 400 con un ObjectId inválido."""
    response = client.patch(
        "/api/projects/not-a-valid-objectid",
        json={"title": "New Title"}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"] == "Bad Request"
