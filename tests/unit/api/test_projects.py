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
        mock_instance.populate_proposal_for_project = AsyncMock(
            side_effect=lambda p: p  # identity – returns project as-is
        )
        mock_instance.populate_proposals_for_projects = AsyncMock(
            side_effect=lambda projects: projects
        )
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


# ---------------------------------------------------------------------------
# PATCH: proposal_versions creation (decoupling from projects.proposal)
# ---------------------------------------------------------------------------

class TestUpdateProjectProposalVersion:
    """Verify that PATCH /api/projects/{id} creates proposal versions
    correctly and never stores proposal data in the projects collection."""

    def test_with_proposal_creates_version_not_stored_in_projects(self, mock_repo) -> None:
        """When proposal data is included in the payload, it must create a new
        version in proposal_versions with source_of_changes='HUMAN' and NOT
        end up in the projects collection."""
        mock_repo.update_project_by_id.return_value = True
        mock_repo.get_project_by_id.return_value = {
            "_id": "6a034f37d8e430e05690091b",
            "link_hash": "abc123hash",
        }

        proposal_payload = {"cover_letter": "Hello", "milestones": []}

        with patch(
            "app.api.routes.projects.ProposalVersionsRepository"
        ) as MockProposalsRepo:
            mock_proposals = MockProposalsRepo.return_value
            mock_proposals.insert_version = AsyncMock()

            response = client.patch(
                "/api/projects/6a034f37d8e430e05690091b",
                json={"title": "New Title", "proposal": proposal_payload},
            )

            assert response.status_code == 200
            assert response.json() == {"message": "Project updated successfully"}

            # Must call insert_version with HUMAN source
            mock_proposals.insert_version.assert_awaited_once_with(
                project_id="6a034f37d8e430e05690091b",
                link_hash="abc123hash",
                proposal_data=proposal_payload,
                source_of_changes="HUMAN",
            )

            # Must NOT call update_source_of_changes (no double-marking)
            mock_proposals.update_source_of_changes.assert_not_called()

            # Proposal field must be stripped before update_project_by_id
            call_args = mock_repo.update_project_by_id.call_args
            passed_data = call_args[0][1]
            assert "proposal" not in passed_data
            assert passed_data == {"title": "New Title"}

    def test_without_proposal_marks_latest_as_human(self, mock_repo) -> None:
        """When no proposal is in the payload, fall back to marking the latest
        version's source_of_changes as 'HUMAN' without creating a version."""
        mock_repo.update_project_by_id.return_value = True

        with patch(
            "app.api.routes.projects.ProposalVersionsRepository"
        ) as MockProposalsRepo:
            mock_proposals = MockProposalsRepo.return_value
            mock_proposals.update_source_of_changes = AsyncMock()

            response = client.patch(
                "/api/projects/6a034f37d8e430e05690091b",
                json={"title": "Only Title"},
            )

            assert response.status_code == 200

            mock_proposals.update_source_of_changes.assert_awaited_once_with(
                "6a034f37d8e430e05690091b", source="HUMAN"
            )
            mock_proposals.insert_version.assert_not_called()

    def test_proposal_missing_link_hash_returns_500(self, mock_repo) -> None:
        """When proposal data is sent but the project has no link_hash,
        the endpoint must return a 500 error."""
        mock_repo.update_project_by_id.return_value = True
        mock_repo.get_project_by_id.return_value = {
            "_id": "6a034f37d8e430e05690091b",
            # deliberately no link_hash
        }

        with patch(
            "app.api.routes.projects.ProposalVersionsRepository"
        ) as MockProposalsRepo:
            MockProposalsRepo.return_value

            response = client.patch(
                "/api/projects/6a034f37d8e430e05690091b",
                json={"proposal": {"cover_letter": "Test"}},
            )

            assert response.status_code == 500
            data = response.json()
            assert data["detail"]["error"] == "Internal Server Error"
            assert "link_hash" in data["detail"]["message"]
