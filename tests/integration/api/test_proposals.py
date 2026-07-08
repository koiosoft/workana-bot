"""
Integration tests for ``POST /api/proposals/{proposalId}/refine``.

Verifies that the refinement endpoint:
- Interacts correctly with the database (projects + proposal_versions).
- Calls the real LLM via OpenRouter when ``OPENROUTER_API_KEY`` is set.
- Stores the result with ``source_of_changes="IA"``.
- Separates ``refinement_justification`` from ``proposal_data``.

Requires ``MONGO_URI`` and ``OPENROUTER_API_KEY`` environment variables.
Tests are skipped if either is not set.
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

pytestmark = pytest.mark.skipif(
    not os.getenv("MONGO_URI"),
    reason="MONGO_URI not set",
)

# Marker applied per-test when OPENROUTER_API_KEY is unavailable
_skip_no_openrouter = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)


@pytest.fixture(autouse=True)
def override_db_dependency(test_db: AsyncIOMotorDatabase) -> None:
    """Override the database dependency so routes use the test database."""
    app.dependency_overrides[get_database] = lambda: test_db

    from app.database import mongo
    mongo._db = test_db

    yield

    app.dependency_overrides.clear()
    mongo._db = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_project_with_proposal(
    test_db: AsyncIOMotorDatabase,
) -> Dict[str, str]:
    """Insert a project + a current proposal version and return their IDs.

    The project includes ``link_hash`` so the refine endpoint can store a
    new version.
    """
    project_doc = {
        "title": "Integration Test Project",
        "budget": "$1,000 – $2,500",
        "link": "https://www.workana.com/job/integration-test",
        "published": "hace 2 horas",
        "short_description": "Build a REST API with FastAPI and PostgreSQL.",
        "bids": "3",
        "source": "workana",
        "proposal_status": "proposal_generated",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "link_hash": "intg-refine-hash-001",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "ai_score": 8,
        "contract_type": "project_fixed",
    }
    result = await test_db.projects.insert_one(project_doc)
    project_id = str(result.inserted_id)

    # Insert an existing proposal version (as if the bot already generated it)
    current_proposal = {
        "proposal_header": "Hello, I'm a Senior Architect...",
        "milestones": [
            {
                "step": 1,
                "name": "Discovery & Architecture",
                "tasks": {
                    "Database Design": {
                        "description": "Design the PostgreSQL schema.",
                        "hours_with_overhead": 20,
                    },
                },
                "hours_with_overhead": 20,
                "subtotal": 500.0,
            },
        ],
        "summary": {
            "total_hours": 80,
            "total_budget": 2000.0,
            "delivery_time_weeks": 4.0,
            "hourly_rate_applied": 25,
        },
        "technical_pitch": "We will deliver...",
        "questions_for_client": ["What is the preferred auth method?"],
    }
    await test_db.proposal_versions.insert_one({
        "project_id": project_id,
        "link_hash": "intg-refine-hash-001",
        "version_number": 1,
        "proposal_data": current_proposal,
        "created_at": datetime.now(timezone.utc),
        "source_of_changes": "IA",
    })

    return {"project_id": project_id, "link_hash": "intg-refine-hash-001"}


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestRefineProposalIntegration:
    """End-to-end tests that exercise the full refinement pipeline."""

    @pytest.mark.asyncio
    @_skip_no_openrouter
    async def test_refine_endpoint_success(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """
        Full refinement flow with real OpenRouter call:
        1. POST /api/proposals/{id}/refine with valid feedback + model.
        2. Assert 200 and response includes project fields.
        3. Assert new version inserted in proposal_versions with
           source_of_changes="IA".
        4. Assert proposal_data does NOT contain refinement_justification.
        5. Assert refinement_justification is stored as a top-level field.
        """
        seeds = await _seed_project_with_proposal(test_db)
        project_id = seeds["project_id"]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={
                    "llm_model_id": "deepseek/deepseek-v4-pro",
                    "user_feedback_observations": (
                        "Please reduce the total budget to under $1,500 "
                        "and focus only on the backend API, no frontend."
                    ),
                },
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        data = response.json()
        # Response should have project fields (same format as GET /api/projects/{id})
        assert data["_id"] == project_id
        assert data["title"] == "Integration Test Project"

        # Verify a new version was stored in proposal_versions
        versions = await (
            test_db.proposal_versions.find({"project_id": project_id})
            .sort("version_number", -1)
            .to_list(length=None)
        )
        assert len(versions) >= 2, (
            f"Expected at least 2 versions (original + refinement), "
            f"found {len(versions)}"
        )

        latest = versions[0]
        assert latest["source_of_changes"] == "IA"
        assert latest["version_number"] >= 2

        # proposal_data must be the inner proposal (NOT contain refinement_justification)
        proposal_data = latest["proposal_data"]
        assert "refinement_justification" not in proposal_data, (
            "proposal_data must not contain refinement_justification"
        )
        # It must have the expected proposal fields
        for key in ("proposal_header", "milestones", "summary", "technical_pitch"):
            assert key in proposal_data, (
                f"proposal_data missing expected key '{key}'"
            )

        # refinement_justification must be a top-level field on the version doc
        assert "refinement_justification" in latest, (
            "refinement_justification must be a top-level field on the version doc"
        )
        assert isinstance(latest["refinement_justification"], str)
        assert len(latest["refinement_justification"]) > 0

    @pytest.mark.asyncio
    async def test_refine_invalid_id_returns_400(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Invalid ObjectId → 400 regardless of API key presence."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/proposals/not-a-valid-id/refine",
                json={
                    "llm_model_id": "any/model",
                    "user_feedback_observations": "Feedback",
                },
            )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "Bad Request"

    @pytest.mark.asyncio
    async def test_refine_project_not_found_returns_404(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Valid ObjectId but no matching project → 404."""
        fake_id = str(ObjectId())  # Valid ObjectId that doesn't exist

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                f"/api/proposals/{fake_id}/refine",
                json={
                    "llm_model_id": "any/model",
                    "user_feedback_observations": "Feedback",
                },
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

    @pytest.mark.asyncio
    async def test_refine_missing_link_hash_returns_500(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Project exists but has no link_hash → 500."""
        project_doc = {
            "title": "No Hash Project",
            "link": "https://example.com",
            # deliberately no link_hash
        }
        result = await test_db.projects.insert_one(project_doc)
        project_id = str(result.inserted_id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={
                    "llm_model_id": "any/model",
                    "user_feedback_observations": "Feedback",
                },
            )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "Internal Server Error"
        assert "link_hash" in data["detail"]["message"]

    @pytest.mark.asyncio
    async def test_refine_request_validation_requires_fields(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Missing required body fields → 422 Unprocessable Entity."""
        seeds = await _seed_project_with_proposal(test_db)
        project_id = seeds["project_id"]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Missing llm_model_id
            response = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={"user_feedback_observations": "Feedback"},
            )
            assert response.status_code == 422

            # Missing user_feedback_observations
            response = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={"llm_model_id": "any/model"},
            )
            assert response.status_code == 422

            # Empty body
            response = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={},
            )
            assert response.status_code == 422