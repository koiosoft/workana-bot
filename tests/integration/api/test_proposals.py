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
import json
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.main import app
from app.database.mongo import get_database, ensure_models_collection
from app.intelligence.adapters.openrouter import OpenRouterAdapter

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

@pytest_asyncio.fixture(scope="function", autouse=False)
async def seed_models_for_refine(test_db: AsyncIOMotorDatabase) -> None:
    """Seed the models collection with the model used by refine tests.

    The refine endpoint resolves ``llm_model_id`` against the ``models``
    collection to determine which provider/adapter to use.  Without this
    seed the lookup fails and the factory falls back to the STANDARD
    adapter, which may be incompatible with the requested model_id.
    """
    await ensure_models_collection()

    # Clean up from previous runs first
    await test_db["models"].delete_many(
        {"model_id": {"$in": ["deepseek/deepseek-v4-pro"]}}
    )
    await test_db["providers"].delete_many({"key": "openrouter"})

    await test_db["providers"].insert_one({
        "key": "openrouter",
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1",
    })

    await test_db["models"].insert_one({
        "model_id": "deepseek/deepseek-v4-pro",
        "provider_key": "openrouter",
        "name": "DeepSeek V4 Pro",
        "is_default": False,
        "is_premium": False,
    })

    yield

    await test_db["models"].delete_many(
        {"model_id": {"$in": ["deepseek/deepseek-v4-pro"]}}
    )
    await test_db["providers"].delete_many({"key": "openrouter"})


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
    @pytest.mark.usefixtures("seed_models_for_refine")
    async def test_refine_endpoint_success(
        self,
        test_db: AsyncIOMotorDatabase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Full refinement flow with a FAKE LLM response (deterministic):
        1. POST /api/proposals/{id}/refine with valid feedback + model.
        2. Assert 200 and response includes project fields.
        3. Assert new version inserted in proposal_versions with
           source_of_changes="IA".
        4. Assert proposal_data does NOT contain refinement_justification.
        5. Assert refinement_justification is stored as a top-level field.

        The HTTP call to OpenRouter is stubbed at ``_chat_completion`` so the
        adapter's real prompt-rendering and JSON-parsing logic still runs.
        A live provider call lives in
        ``TestRefineProposalLive::test_refine_endpoint_live_llm``.
        """
        seeds = await _seed_project_with_proposal(test_db)
        project_id = seeds["project_id"]

        llm_payload = {
            "refinement_justification": (
                "Alcance reducido a backend API segun el feedback. "
                "Se eliminaron tareas de frontend y se ajustaron las horas."
            ),
            "proposal": {
                "proposal_header": "Hola, soy Arquitecto Senior con 24+ anos.",
                "milestones": [
                    {
                        "step": 1,
                        "name": "Backend API",
                        "tasks": {
                            "API Endpoints": {
                                "description": "Endpoints REST con FastAPI.",
                                "hours_with_overhead": 24,
                            }
                        },
                        "hours_with_overhead": 24,
                        "subtotal": 600.0,
                    }
                ],
                "summary": {
                    "total_hours": 24,
                    "total_budget": 600.0,
                    "delivery_time_weeks": 0.8,
                    "hourly_rate_applied": 25,
                },
                "technical_pitch": "Cierre tecnico enfocado en backend puro.",
                "questions_for_client": ["¿Que proveedor de base de datos usan?"],
            },
        }

        async def fake_chat_completion(self, prompt, circuit_breaker=None):
            # Devolver el JSON tal cual lo haria el LLM
            return json.dumps(llm_payload, ensure_ascii=False)

        monkeypatch.setattr(
            OpenRouterAdapter, "_chat_completion", fake_chat_completion
        )

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


class TestRefineProposalLive:
    """Smoke test against the real provider.

    This is the only refine test that hits OpenRouter, so it is inherently
    flaky (the model occasionally returns malformed JSON or drops the
    connection).  It asserts only what must hold for a live call: the route
    completes and either stores a well-formed version or fails cleanly with
    502.  Behavioural assertions belong to TestRefineProposalIntegration.
    """

    @pytest.mark.asyncio
    @pytest.mark.live
    @_skip_no_openrouter
    @pytest.mark.skip(reason="LLAMADA REAL AL PROVEEDOR (lenta ~40-85s). Desactivado temporalmente; ver plans/current/pendientes-post-rediseno.md (T15). Correr con: pytest -m live")
    @pytest.mark.usefixtures("seed_models_for_refine")
    async def test_refine_endpoint_live_llm(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        seeds = await _seed_project_with_proposal(test_db)
        project_id = seeds["project_id"]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={
                    "llm_model_id": "deepseek/deepseek-v4-pro",
                    "user_feedback_observations": (
                        "Reduce the total budget to under $1,500 and focus "
                        "only on the backend API, no frontend."
                    ),
                },
            )

        versions = await test_db.proposal_versions.find(
            {"project_id": project_id}
        ).sort("version_number", -1).to_list(length=None)

        if response.status_code == 200:
            assert len(versions) >= 2
            latest = versions[0]
            assert latest["source_of_changes"] == "IA"
            assert "refinement_justification" not in latest["proposal_data"]
            assert isinstance(latest.get("refinement_justification"), str)
        else:
            # Provider failed (malformed JSON / dropped connection): the
            # route must fail cleanly and never store an empty version.
            assert response.status_code == 502
            assert len(versions) == 1


class TestRefineProposalContractType:
    """Integration tests for the contract_type field in the refine endpoint."""

    @pytest.mark.asyncio
    async def test_refine_invalid_contract_type_returns_422(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Providing an unsupported contract_type value must return 422."""
        seeds = await _seed_project_with_proposal(test_db)
        project_id = seeds["project_id"]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={
                    "llm_model_id": "any/model",
                    "user_feedback_observations": "Feedback",
                    "contract_type": "invalid_type",
                },
            )

        assert response.status_code == 422
        data = response.json()
        # The error should mention the invalid value
        assert "invalid_type" in str(data).lower() or "contract_type" in str(data).lower()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="LLAMADA REAL AL PROVEEDOR (lenta ~27s, sin mock). Desactivado temporalmente; ver plans/current/pendientes-post-rediseno.md (T15).")
    async def test_refine_contract_type_change_deletes_existing_versions(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """When contract_type changes, all existing proposal versions must be
        deleted BEFORE the AI call.

        The AI call may succeed (200) if a valid fallback model is available,
        or fail (502) if not.  In either case the original versions must be
        deleted first."""
        seeds = await _seed_project_with_proposal(test_db)
        project_id = seeds["project_id"]

        # Verify we have at least one version before the request
        count_before = await test_db.proposal_versions.count_documents(
            {"project_id": project_id}
        )
        assert count_before == 1, "Seed must create one proposal version"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={
                    "llm_model_id": "nonexistent/model",
                    "user_feedback_observations": "Switch to staffing",
                    "contract_type": "staff_augmentation",
                },
            )

        count_after = await test_db.proposal_versions.count_documents(
            {"project_id": project_id}
        )

        if response.status_code == 200:
            # AI call succeeded via fallback adapter → a new refined version
            # was inserted after the original was deleted.
            assert count_after == 1, (
                f"Expected 1 refined version after successful AI call, "
                f"found {count_after}"
            )
        else:
            assert response.status_code == 502
            assert count_after == 0, (
                f"Expected 0 versions after failed AI call, found {count_after}"
            )

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("seed_models_for_refine")
    async def test_refine_staff_augmentation_uses_refine_staffing_template(
        self,
        test_db: AsyncIOMotorDatabase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When refining a staff_augmentation project with the same
        contract_type, the s4-refine/refine-proposal-staffing.j2 template must be used AND the
        stored proposal_data must keep the staffing shape (cover_letter +
        budget_summary), never the milestone/project-fixed shape.

        The prompt itself is asserted directly (deterministic); the HTTP call
        to the provider is stubbed with a spec-compliant response so the
        storage path is still exercised end to end.
        """
        # Create a project with staff_augmentation contract_type
        project_doc = {
            "title": "Staff Aug Project",
            "budget": "$1,000 – $2,500",
            "link": "https://www.workana.com/job/staff-integration-test",
            "published": "hace 2 horas",
            "short_description": "Need a senior Python dev for staff augmentation",
            "bids": "3",
            "source": "workana",
            "proposal_status": "proposal_generated",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "link_hash": "intg-refine-staff-hash-001",
            "skills": ["Python", "Django", "PostgreSQL"],
            "ai_score": 8,
            "contract_type": "staff_augmentation",
        }
        result = await test_db.projects.insert_one(project_doc)
        project_id = str(result.inserted_id)

        # Insert an existing staffing proposal version
        current_proposal = {
            "cover_letter": "Dear client, I am a senior Python dev...",
            "budget_summary": {
                "hourly_rate": 25,
                "suggested_hours_per_week": 20,
                "estimated_monthly_budget": 2000,
            },
            "questions_for_client": ["What's the team size?"],
        }
        await test_db.proposal_versions.insert_one({
            "project_id": project_id,
            "link_hash": "intg-refine-staff-hash-001",
            "version_number": 1,
            "proposal_data": current_proposal,
            "created_at": datetime.now(timezone.utc),
            "source_of_changes": "IA",
        })

        # --- 1. Deterministic check: the refine-staffing prompt must ask for
        # the staffing shape, never the project-fixed (milestones) shape.
        from jinja2 import Environment, FileSystemLoader
        prompts_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "app", "intelligence", "prompts",
        )
        rendered = Environment(
            loader=FileSystemLoader(prompts_dir)
        ).get_template("s4-refine/refine-proposal-staffing.j2").render(
            my_profile_skills=["Python"],
            hourly_rate=25,
            suggested_hours_per_week=30,
            project_payload_json="{}",
            current_proposal_json=json.dumps(current_proposal),
            user_feedback_observations="Increase hours to 30",
        )
        output_contract = rendered[rendered.index("**FORMATO DE SALIDA"):]
        assert '"cover_letter"' in output_contract
        assert '"budget_summary"' in output_contract
        for forbidden in ('"milestones"', '"proposal_header"', '"technical_pitch"'):
            assert forbidden not in output_contract, (
                f"s4-refine/refine-proposal-staffing.j2 output contract must not declare {forbidden}"
            )

        # --- 2. Stub the provider call with a spec-compliant staffing answer
        # so the storage path runs end to end without depending on the LLM.
        llm_payload = {
            "refinement_justification": (
                "Se ajusto la carga horaria a 30 horas semanales y se reforzo "
                "el enfasis en React Native dentro de la carta."
            ),
            "proposal": {
                "cover_letter": "Hola, perfil senior para dedicacion exclusiva...",
                "budget_summary": {
                    "hourly_rate": 25,
                    "suggested_hours_per_week": 30,
                    "estimated_monthly_budget": 3000.0,
                },
                "questions_for_client": ["Cual es la duracion estimada del rol?"],
            },
        }

        captured_prompt: dict = {}

        async def fake_chat_completion(self, prompt, circuit_breaker=None):
            captured_prompt["value"] = prompt
            return json.dumps(llm_payload, ensure_ascii=False)

        monkeypatch.setattr(
            OpenRouterAdapter, "_chat_completion", fake_chat_completion
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={
                    "llm_model_id": "deepseek/deepseek-v4-pro",
                    "user_feedback_observations": (
                        "Increase the suggested hours per week to 30 "
                        "and emphasise React Native experience."
                    ),
                    "contract_type": "staff_augmentation",
                },
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["_id"] == project_id

        # Verify a new version was created
        versions = await (
            test_db.proposal_versions.find({"project_id": project_id})
            .sort("version_number", -1)
            .to_list(length=None)
        )
        assert len(versions) >= 2
        latest = versions[0]
        assert latest["source_of_changes"] == "IA"

        # Verify the proposal_data has staffing-specific fields
        proposal_data = latest["proposal_data"]
        assert "cover_letter" in proposal_data, (
            "Staff augmentation refinement must produce a cover_letter field"
        )
        assert "budget_summary" in proposal_data, (
            "Staff augmentation refinement must produce a budget_summary field"
        )
        assert "refinement_justification" in latest, (
            "refinement_justification must be stored as top-level field"
        )

        # The staffing template (not the project-fixed one) was actually sent
        assert "cover_letter" in captured_prompt.get("value", ""), (
            "s4-refine/refine-proposal-staffing.j2 was not the prompt sent to the model"
        )



# ---------------------------------------------------------------------------
# INT001: Template path assertions — factory functions return subfolder paths
# ---------------------------------------------------------------------------


class TestProposalTemplatePaths:
    """INT001: Validate that factory template-path functions return subfolder-
    prefixed paths compatible with the Jinja FileSystemLoader."""

    def _import_select_initial_template(self):
        from app.intelligence.factory import select_initial_proposal_template
        return select_initial_proposal_template

    def _import_select_estimation_template(self):
        from app.intelligence.factory import select_estimation_template
        return select_estimation_template


    def test_select_initial_proposal_template_project_fixed(self) -> None:
        """project_fixed contract type → 's3-commercial/write-proposal.j2'"""
        fn = self._import_select_initial_template()
        path = fn("project_fixed")
        assert path == "s3-commercial/write-proposal.j2", (
            f"Expected s3-commercial subfolder path, got {path}"
        )
        # Verify the template file actually exists at that path
        import os
        template_file = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "app", "intelligence", "prompts", path,
        )
        assert os.path.exists(template_file), (
            f"Template file not found at {template_file}"
        )

    def test_select_initial_proposal_template_staff_augmentation(self) -> None:
        """staff_augmentation contract type →
        's3-commercial/write-proposal-staffing.j2'"""
        fn = self._import_select_initial_template()
        path = fn("staff_augmentation")
        assert path == "s3-commercial/write-proposal-staffing.j2", (
            f"Expected s3-commercial subfolder path, got {path}"
        )

    def test_select_estimation_template_full(self) -> None:
        """maturity_score >= threshold → 's2-estimation/estimate-full.j2'"""
        from app.intelligence.config import get_maturity_threshold
        fn = self._import_select_estimation_template()
        path = fn(9.0, get_maturity_threshold())
        assert path == "s2-estimation/estimate-full.j2", (
            f"Expected s2-estimation subfolder path, got {path}"
        )
    def test_select_estimation_template_discovery(self) -> None:
        """maturity_score < threshold → 's2-estimation/estimate-discovery.j2'"""
        from app.intelligence.config import get_maturity_threshold
        fn = self._import_select_estimation_template()
        path = fn(4.0, get_maturity_threshold())
        assert path == "s2-estimation/estimate-discovery.j2", (
            f"Expected s2-estimation subfolder path, got {path}"
        )
    def test_select_estimation_template_at_threshold(self) -> None:
        """maturity_score == threshold → full template (>= threshold)"""
        from app.intelligence.config import get_maturity_threshold
        fn = self._import_select_estimation_template()
        path = fn(8.0, get_maturity_threshold())
        assert path == "s2-estimation/estimate-full.j2"
# ---------------------------------------------------------------------------
# INT002: GET/POST endpoints expose proposal in same format,
#          no intermediate artifacts
# ---------------------------------------------------------------------------


class TestProposalGetPostConsistency:
    """INT002: Verify that GET /api/projects/{id} and POST /api/proposals/{id}/refine
    return the project with the same proposal structure and no intermediate
    fields leaking into the response."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="LLAMADA REAL AL PROVEEDOR (lenta ~85s). Desactivado temporalmente; ver plans/current/pendientes-post-rediseno.md (T15).")
    async def test_refine_response_has_same_fields_as_get_project(
        self,
        test_db: AsyncIOMotorDatabase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        After refinement, the POST response must have the same shape as a
        subsequent GET /api/projects/{id} response: both must include
        ``proposal``, ``proposal_version_number`` and omit intermediate
        internal fields like ``proposal_data`` or ``refinement_justification``.
        """
        seeds = await _seed_project_with_proposal(test_db)
        project_id = seeds["project_id"]

        llm_payload = {
            "refinement_justification": "Simplified scope.",
            "proposal": {
                "proposal_header": "Hola, soy Arquitecto Senior.",
                "milestones": [
                    {
                        "step": 1,
                        "name": "API Core",
                        "tasks": {
                            "Endpoints": {
                                "description": "REST endpoints.",
                                "hours_with_overhead": 20,
                            }
                        },
                        "hours_with_overhead": 20,
                        "subtotal": 500.0,
                    }
                ],
                "summary": {
                    "total_hours": 20,
                    "total_budget": 500.0,
                    "delivery_time_weeks": 1.0,
                    "hourly_rate_applied": 25,
                },
                "technical_pitch": "Backend API.",
                "questions_for_client": ["Auth method?"],
            },
        }

        async def fake_chat_completion(self, prompt, circuit_breaker=None):
            return json.dumps(llm_payload, ensure_ascii=False)

        monkeypatch.setattr(
            OpenRouterAdapter, "_chat_completion", fake_chat_completion
        )

        # 1. POST to refine
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            post_resp = await ac.post(
                f"/api/proposals/{project_id}/refine",
                json={
                    "llm_model_id": "deepseek/deepseek-v4-pro",
                    "user_feedback_observations": "Simplify.",
                },
            )

        assert post_resp.status_code == 200, post_resp.text
        post_data = post_resp.json()

        # 2. GET the same project
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            get_resp = await ac.get(f"/api/projects/{project_id}")

        assert get_resp.status_code == 200, get_resp.text
        get_data = get_resp.json()

        # 3. Compare proposal structure and values
        for key in ("proposal", "proposal_version_number"):
            assert key in post_data, (
                f"POST response missing '{key}' — intermediate artifacts may be leaking"
            )
            assert key in get_data, (
                f"GET response missing '{key}'"
            )

        # The proposal_data must be identical (same version)
        assert post_data["proposal"] == get_data["proposal"], (
            "POST and GET must return the same proposal data"
        )
        assert post_data["proposal_version_number"] == get_data["proposal_version_number"], (
            "POST and GET must return the same version number"
        )

        # No internal / intermediate fields should leak into the response
        forbidden_keys = {"proposal_data", "refinement_justification", "source_of_changes"}
        for key in forbidden_keys:
            assert key not in post_data, (
                f"POST response must not contain internal field '{key}'"
            )
            assert key not in get_data, (
                f"GET response must not contain internal field '{key}'"
            )


# ---------------------------------------------------------------------------
# INT009: External contract — proposal_versions validates against
#          MilestoneProposal; GET exposes correct structure
# ---------------------------------------------------------------------------


class TestProposalExternalContract:
    """INT009: Verify that proposal_versions documents conform to the
    MilestoneProposal contract expected by the external dashboard.
    The proposal_data stored must carry the fields that the frontend
    dashboard expects: proposal_header, milestones, summary, technical_pitch,
    questions_for_client."""

    @pytest.mark.asyncio
    async def test_proposal_version_milestone_proposal_contract(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """The proposal_data stored in proposal_versions must include all
        fields of the MilestoneProposal contract."""
        seeds = await _seed_project_with_proposal(test_db)
        project_id = seeds["project_id"]

        # Read the proposal version that was seeded
        version = await test_db.proposal_versions.find_one(
            {"project_id": project_id},
            sort=[("version_number", -1)],
        )
        assert version is not None, "Seed should have created a proposal version"

        proposal_data = version["proposal_data"]

        # The MilestoneProposal contract requires all of these top-level fields
        contract_fields = [
            "proposal_header",
            "milestones",
            "summary",
            "technical_pitch",
            "questions_for_client",
        ]
        for field in contract_fields:
            assert field in proposal_data, (
                f"MilestoneProposal contract requires '{field}' in proposal_data, "
                f"but it's missing. Available: {list(proposal_data.keys())}"
            )

        # Validate structure of milestones entries
        assert isinstance(proposal_data["milestones"], list), (
            "milestones must be a list"
        )
        if len(proposal_data["milestones"]) > 0:
            milestone = proposal_data["milestones"][0]
            for mfield in ("step", "name", "tasks", "hours_with_overhead", "subtotal"):
                assert mfield in milestone, (
                    f"Each milestone must contain '{mfield}'"
                )

        # Validate structure of summary
        summary = proposal_data["summary"]
        for sfield in ("total_hours", "total_budget", "delivery_time_weeks", "hourly_rate_applied"):
            assert sfield in summary, (
                f"Summary must contain '{sfield}'"
            )

    @pytest.mark.asyncio
    async def test_get_exposes_correct_proposal_structure(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """GET /api/projects/{id} must expose the proposal with the
        MilestoneProposal shape from proposal_versions."""
        seeds = await _seed_project_with_proposal(test_db)
        project_id = seeds["project_id"]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(f"/api/projects/{project_id}")

        assert response.status_code == 200, response.text
        data = response.json()

        # The response must include proposal as a nested object
        assert "proposal" in data, "GET response must include 'proposal' field"
        proposal = data["proposal"]
        assert proposal is not None, "Proposal must not be null"

        # Must have full MilestoneProposal shape
        for field in ("proposal_header", "milestones", "summary", "technical_pitch", "questions_for_client"):
            assert field in proposal, (
                f"Proposal must contain '{field}', got keys: {list(proposal.keys())}"
            )

        # Response must carry version metadata
        assert "proposal_version_number" in data, (
            "GET response must include proposal_version_number"
        )
        assert isinstance(data["proposal_version_number"], int), (
            "proposal_version_number must be an integer"
        )