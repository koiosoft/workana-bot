import os
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.main import app
from app.database.mongo import get_database

pytestmark = pytest.mark.skipif(
    not os.getenv("MONGO_URI"),
    reason="MONGO_URI not set"
)

@pytest.fixture(autouse=True)
def override_db_dependency(test_db: AsyncIOMotorDatabase):
    """
    Override the database dependency for FastAPI routes to use the function-scoped test_db.
    Also overrides the global cached instance to prevent 'Event loop is closed' errors
    in repositories that might not use FastAPI's Depends().
    """
    app.dependency_overrides[get_database] = lambda: test_db
    
    from app.database import mongo
    mongo._db = test_db
    
    yield
    
    app.dependency_overrides.clear()
    mongo._db = None

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


# ---------------------------------------------------------------------------
# Proposal population from proposal_versions (decoupling tests)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_project_populates_proposal_from_versions(
    test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]
) -> None:
    """
    GET /api/projects/{id} should populate the ``proposal`` field from the
    latest version in the ``proposal_versions`` collection.
    """
    # Insert a proposal version for the seeded project
    proposal_data = {"cover_letter": "Hello from version", "questions_for_client": []}
    await test_db.proposal_versions.insert_one({
        "project_id": seed_test_data["project_id"],
        "link_hash": "test-link-hash",
        "version_number": 1,
        "proposal_data": proposal_data,
        "created_at": datetime.now(timezone.utc),
    })

    # Also insert a second version (should be the one returned)
    proposal_data_v2 = {"cover_letter": "Latest version", "questions_for_client": []}
    await test_db.proposal_versions.insert_one({
        "project_id": seed_test_data["project_id"],
        "link_hash": "test-link-hash",
        "version_number": 2,
        "proposal_data": proposal_data_v2,
        "created_at": datetime.now(timezone.utc),
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/api/projects/{seed_test_data['project_id']}")

        assert response.status_code == 200
        data = response.json()
        assert "proposal" in data
        assert data["proposal"] == proposal_data_v2
        assert data.get("proposal_version_number") == 2


@pytest.mark.asyncio
async def test_get_project_handles_missing_versions_gracefully(
    test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]
) -> None:
    """
    GET /api/projects/{id} should not fail when no proposal_versions exist;
    ``proposal`` should be null.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/api/projects/{seed_test_data['project_id']}")

        assert response.status_code == 200
        data = response.json()
        assert data.get("proposal") is None


@pytest.mark.asyncio
async def test_list_projects_populates_proposals_from_versions(
    test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]
) -> None:
    """
    GET /api/projects (paginated) should populate ``proposal`` on each
    project from proposal_versions.
    """
    proposal_data = {"cover_letter": "Batch proposal", "questions_for_client": []}
    await test_db.proposal_versions.insert_one({
        "project_id": seed_test_data["project_id"],
        "link_hash": "test-link-hash",
        "version_number": 1,
        "proposal_data": proposal_data,
        "created_at": datetime.now(timezone.utc),
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/projects", params={"page": 1, "limit": 10})

        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) >= 1
        # The seeded project should have the proposal populated
        matching = [p for p in data["projects"] if p["_id"] == seed_test_data["project_id"]]
        assert len(matching) == 1
        assert matching[0]["proposal"] == proposal_data


@pytest.mark.asyncio
async def test_get_project_with_legacy_embedded_proposal(
    test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]
) -> None:
    """
    When a project still has an embedded ``proposal`` field (legacy data
    before migration) and no ``proposal_versions`` entry, the embedded
    proposal should be returned for backward compatibility.
    """
    legacy_proposal = {"proposal_header": "Legacy", "milestones": []}
    from bson import ObjectId
    await test_db.projects.update_one(
        {"_id": ObjectId(seed_test_data["project_id"])},
        {"$set": {"proposal": legacy_proposal}},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/api/projects/{seed_test_data['project_id']}")

        assert response.status_code == 200
        data = response.json()
        # Should still return the legacy embedded proposal
        assert data["proposal"] == legacy_proposal
