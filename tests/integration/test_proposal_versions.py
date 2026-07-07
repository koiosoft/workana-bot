"""
Integration tests for source_of_changes tracking in proposal_versions.

Verifies that:
- source_of_changes is "IA" when a proposal version is inserted via the bot.
- source_of_changes is "HUMAN" when a project is updated through the API.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.main import app
from app.database.mongo import get_database
from app.database.proposal_versions_repository import ProposalVersionsRepository

pytestmark = pytest.mark.skipif(
    not os.getenv("MONGO_URI"),
    reason="MONGO_URI not set"
)


@pytest.fixture(autouse=True)
def override_db_dependency(test_db: AsyncIOMotorDatabase):
    """
    Override the database dependency for FastAPI routes to use the function-scoped test_db.
    Also overrides the global cached instance to prevent 'Event loop is closed' errors.
    """
    app.dependency_overrides[get_database] = lambda: test_db

    from app.database import mongo
    mongo._db = test_db

    yield

    app.dependency_overrides.clear()
    mongo._db = None


# ---------------------------------------------------------------------------
# source_of_changes = "IA" via repository (bot path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_version_sets_source_of_changes_to_ia(
    test_db: AsyncIOMotorDatabase,
) -> None:
    """
    When a proposal version is inserted via the repository (as the Telegram
    bot does), the ``source_of_changes`` field must be ``"IA"``.
    """
    repo = ProposalVersionsRepository()

    proposal_data = {
        "cover_letter": "Bot-generated proposal",
        "questions_for_client": [],
    }

    inserted_id = await repo.insert_version(
        project_id="proj-bot-1",
        link_hash="bot-test-hash",
        proposal_data=proposal_data,
    )

    # Verify the document was stored with source_of_changes="IA"
    doc = await test_db.proposal_versions.find_one(
        {"_id": ObjectId(inserted_id)}
    )

    assert doc is not None
    assert doc["source_of_changes"] == "IA"
    assert doc["project_id"] == "proj-bot-1"
    assert doc["proposal_data"] == proposal_data


@pytest.mark.asyncio
async def test_insert_version_source_of_changes_persists_across_versions(
    test_db: AsyncIOMotorDatabase,
) -> None:
    """
    Every version inserted via the bot should independently carry
    ``source_of_changes = "IA"``.
    """
    repo = ProposalVersionsRepository()

    # Insert two versions for the same project
    await repo.insert_version(
        project_id="proj-multi",
        link_hash="multi-hash",
        proposal_data={"cover_letter": "v1"},
    )
    await repo.insert_version(
        project_id="proj-multi",
        link_hash="multi-hash",
        proposal_data={"cover_letter": "v2"},
    )

    # Both documents should have source_of_changes="IA"
    cursor = test_db.proposal_versions.find({"project_id": "proj-multi"})
    docs = await cursor.to_list(length=None)

    assert len(docs) == 2
    for doc in docs:
        assert doc["source_of_changes"] == "IA", (
            f"Version {doc['version_number']} should have source_of_changes='IA'"
        )


# ---------------------------------------------------------------------------
# source_of_changes = "HUMAN" via PATCH /api/projects/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_project_sets_source_of_changes_to_human(
    test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]
) -> None:
    """
    When a project is updated through the PATCH endpoint, the latest
    proposal version's ``source_of_changes`` should be set to ``"HUMAN"``.
    """
    project_id = seed_test_data["project_id"]

    # First, insert a proposal version as if the bot had created it
    await test_db.proposal_versions.insert_one({
        "project_id": project_id,
        "link_hash": "human-test-hash",
        "version_number": 1,
        "proposal_data": {"cover_letter": "Bot proposal", "questions_for_client": []},
        "created_at": datetime.now(timezone.utc),
        "source_of_changes": "IA",
    })

    # Now update the project through the API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.patch(
            f"/api/projects/{project_id}",
            json={
                "proposal_status": "proposal_generated",
                "title": "Human-Updated Title",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Project updated successfully"

    # Verify source_of_changes was changed to "HUMAN"
    latest = await test_db.proposal_versions.find_one(
        {"project_id": project_id},
        sort=[("version_number", -1)],
    )
    assert latest is not None
    assert latest["source_of_changes"] == "HUMAN", (
        f"Expected 'HUMAN' but got '{latest.get('source_of_changes')}'"
    )
    assert latest["version_number"] == 1  # still the same version, just updated


@pytest.mark.asyncio
async def test_update_project_without_existing_version_handles_gracefully(
    test_db: AsyncIOMotorDatabase, seed_test_data: Dict[str, Any]
) -> None:
    """
    Updating a project that has no proposal_versions should not crash.
    The endpoint should still return 200.
    """
    project_id = seed_test_data["project_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.patch(
            f"/api/projects/{project_id}",
            json={
                "proposal_status": "proposal_generated",
                "title": "Updated Without Versions",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Project updated successfully"

    # No proposal_versions document should have been created by the update
    count = await test_db.proposal_versions.count_documents(
        {"project_id": project_id}
    )
    assert count == 0