import os
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("MONGODB_URI"),
    reason="MONGODB_URI not set"
)

@pytest.mark.asyncio
async def test_get_projects_success_structure(test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]) -> None:
    """
    Test successful retrieval of projects with valid structure.
    Asserts 200 status code and response body containing 'projects' array and 'total' count.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/projects",
            params={"page": 1, "limit": 10}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert "projects" in data
        assert isinstance(data["projects"], list)
        assert "total" in data
        assert isinstance(data["total"], int)

@pytest.mark.asyncio
async def test_get_projects_success_filters(test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]) -> None:
    """
    Test successful retrieval of projects with filtering query parameters.
    Asserts 200 status code and response body containing 'projects' array.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/projects",
            params={
                "status": "proposal_generated",
                "staffAugmentationOnly": "true",
                "searchTerm": "test"
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert "projects" in data
        assert isinstance(data["projects"], list)

@pytest.mark.asyncio
async def test_update_project_success(test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]) -> None:
    """
    Test successful update of a project.
    Asserts 200 status code and a success message in the response body.
    """
    transport = ASGITransport(app=app)
    project_id = seed_test_data["project_id"]
    
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.patch(
            f"/api/projects/{project_id}",
            json={
                "proposal_status": "proposal_generated",
                "title": "Updated Project Title"
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert data["message"] == "Project updated successfully"

@pytest.mark.asyncio
async def test_update_project_invalid_id(test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]) -> None:
    """
    Test update project with invalid ID format.
    Asserts 400 Bad Request status code.
    """
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.patch(
            "/api/projects/invalid_id_format",
            json={
                "proposal_status": "proposal_generated",
                "title": "Updated Project Title"
            }
        )
        
        assert response.status_code == 400
