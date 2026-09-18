"""
INT007: Staff augmentation regression test.

Verifies that the ``generate_proposal`` path for ``staff_augmentation``
contract type remains unchanged from its original shape.

The staff_augmentation path must:
- Use the ``s3-commercial/write-proposal-staffing.j2`` template.
- Produce a proposal with ``cover_letter`` and ``budget_summary`` fields.
- Never use the project-fixed milestone/proposal-header shape.
"""

import os
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.intelligence.adapters.openrouter import OpenRouterAdapter
from app.bots.telegram.handlers import process_projects


pytestmark = pytest.mark.skipif(
    not os.getenv("MONGO_URI"),
    reason="MONGO_URI not set",
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_update():
    """Fixture to simulate Telegram Update object."""
    update = MagicMock()
    update.effective_user.id = "12345"
    update.message = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Fixture to simulate Telegram Context object."""
    return MagicMock()


@pytest.fixture
def mock_semaphore():
    """Fixture to simulate ProcessSemaphore."""
    semaphore = MagicMock()
    semaphore.is_locked = AsyncMock(return_value=False)
    semaphore.acquire = AsyncMock(return_value=True)
    semaphore.update_activity = AsyncMock()
    semaphore.release = AsyncMock()
    semaphore.get_status = AsyncMock()
    semaphore.calculate_remaining_projects = MagicMock(return_value=0)
    return semaphore


# ===========================================================================
# INT007: Staff augmentation regression — direct adapter test
# ===========================================================================

@pytest.mark.asyncio
async def test_staff_augmentation_generate_proposal_shape_unchanged() -> None:
    """INT007: The staff_augmentation generate_proposal path produces
    cover_letter and budget_summary (not milestones/proposal_header).

    This is a regression guard against accidental porting of the staffing
    path to the project-fixed shape.
    """
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
        adapter = OpenRouterAdapter()

    project = {
        "title": "Senior Python Developer Needed",
        "description": "We need a senior Python developer for 3 months.",
        "full_description": "Full-time remote senior Python developer for backend services.",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "budget_detail": "$3,000 - $5,000/month",
        "contract_type": "staff_augmentation",
        "link_hash": "intg-staff-regression-hash",
        "strategy": "pro",
    }

    mock_llm_response = (
        '```json\n{"cover_letter": "Estimado cliente, soy un desarrollador '
        'Python senior con amplia experiencia en FastAPI y PostgreSQL...", '
        '"budget_summary": {"hourly_rate": 25, '
        '"suggested_hours_per_week": 20, '
        '"estimated_monthly_budget": 2000}, '
        '"questions_for_client": ["What is the team size?"]}\n```'
    )

    with patch.object(
        adapter, "_chat_completion",
        AsyncMock(return_value=mock_llm_response),
    ), patch("asyncio.sleep", AsyncMock()):
        result = await adapter.generate_proposal(project)

    # Must have staff-augmentation-specific fields
    assert "cover_letter" in result, (
        "staff_augmentation proposal must contain 'cover_letter'"
    )
    assert "budget_summary" in result, (
        "staff_augmentation proposal must contain 'budget_summary'"
    )

    # Must NOT have project-fixed fields at the top level
    assert "proposal_header" not in result, (
        "staff_augmentation proposal must NOT contain 'proposal_header'"
    )
    assert "milestones" not in result, (
        "staff_augmentation proposal must NOT contain 'milestones'"
    )

    # Budget summary must have the expected sub-fields
    budget = result["budget_summary"]
    assert "hourly_rate" in budget
    assert "suggested_hours_per_week" in budget
    assert "estimated_monthly_budget" in budget


# ===========================================================================
# INT007: Staff augmentation — handler routing regression
# ===========================================================================

@pytest.mark.asyncio
@patch("app.bots.telegram.handlers.get_process_semaphore")
@patch("app.bots.telegram.handlers.is_admin", return_value=True)
@patch("app.bots.telegram.handlers.ScraperFactory")
@patch("app.bots.telegram.handlers.get_projects_repository")
async def test_staff_augmentation_handler_routes_to_generate_proposal(
    mock_get_repo, mock_scraper_factory, mock_is_admin, mock_get_semaphore,
    mock_update, mock_context, mock_semaphore,
) -> None:
    """INT007: The process_projects handler must route staff_augmentation
    projects to generate_proposal (legacy path), NOT to the staged
    project_fixed pipeline.
    """
    mock_semaphore.is_locked = AsyncMock(return_value=False)
    mock_semaphore.acquire = AsyncMock(return_value=True)
    mock_semaphore.update_activity = AsyncMock()
    mock_semaphore.release = AsyncMock()
    mock_get_semaphore.return_value = mock_semaphore

    mock_repo = MagicMock()
    mock_repo.reset_orphaned_proposals = AsyncMock(return_value=0)
    mock_repo.get_projects_for_deep_analysis = AsyncMock(
        return_value=[
            {
                "link": "http://example.com/staff",
                "link_hash": "staff-hash-intg",
                "title": "Staff Aug Project",
                "contract_type": "staff_augmentation",
            }
        ]
    )
    mock_repo.collection.find_one = AsyncMock(
        return_value={"_id": "staff-proj-id"}
    )
    mock_repo.collection.update_one = AsyncMock()
    mock_repo.mark_projects_status = AsyncMock()
    mock_repo.update_full_details = AsyncMock()
    mock_repo.update_project_proposal = AsyncMock()
    mock_get_repo.return_value = mock_repo

    mock_scraper = MagicMock()
    mock_scraper.fetch_full_detail = AsyncMock(
        return_value={"full_description": "Need Python developer"}
    )
    mock_scraper_factory.get_scraper.return_value = mock_scraper

    # Simulate the intelligence service with mocked adapters
    mock_standard = MagicMock()
    mock_standard.format_project_description = AsyncMock(
        return_value="Formatted description"
    )
    mock_premium = MagicMock()
    mock_premium.generate_proposal = AsyncMock(
        return_value={
            "cover_letter": "Dear client, I am a senior developer...",
            "budget_summary": {
                "hourly_rate": 25,
                "suggested_hours_per_week": 20,
                "estimated_monthly_budget": 2000,
            },
        }
    )
    # The project_fixed pipeline must NOT be called for staffing
    mock_premium.generate_project_fixed_proposal = AsyncMock()

    from app.database.requirement_analyses_repository import RequirementAnalysesRepository
    from app.database.technical_estimates_repository import TechnicalEstimatesRepository

    with patch(
        "app.bots.telegram.handlers.create_intelligence_service",
        AsyncMock(return_value={
            "STANDARD": mock_standard,
            "PREMIUM": mock_premium,
            "FILTER": mock_standard,
        }),
    ), patch.object(
        RequirementAnalysesRepository, "insert", AsyncMock(return_value="id1"),
    ), patch.object(
        TechnicalEstimatesRepository, "insert", AsyncMock(return_value="id2"),
    ):
        await process_projects(mock_update, mock_context)

    # Verify staff augmentation route was taken
    mock_premium.generate_proposal.assert_awaited_once()
    # Verify project_fixed pipeline was NOT called
    mock_premium.generate_project_fixed_proposal.assert_not_awaited()

    # Verify the proposal was persisted via update_project_proposal
    mock_repo.update_project_proposal.assert_called_once()


# ===========================================================================
# INT007: Staff augmentation template verification
# ===========================================================================

@pytest.mark.asyncio
async def test_staff_augmentation_uses_correct_template() -> None:
    """INT007: The staff_augmentation generate_proposal must render
    's3-commercial/write-proposal-staffing.j2' (not write-proposal.j2).
    """
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "dummy-key"}):
        adapter = OpenRouterAdapter()

    project = {
        "title": "Staff Aug Test",
        "contract_type": "staff_augmentation",
        "strategy": "pro",
    }

    mock_response = (
        '```json\n{"cover_letter": "Test", "budget_summary": {}}\n```'
    )

    with patch.object(
        adapter, "_chat_completion", AsyncMock(return_value=mock_response),
    ), patch.object(adapter, "_render_prompt") as mock_render, patch(
        "asyncio.sleep", AsyncMock()
    ):
        mock_render.return_value = "prompt string"
        await adapter.generate_proposal(project)

        template_name = mock_render.call_args[0][0]
        assert template_name == "s3-commercial/write-proposal-staffing.j2", (
            f"Staff augmentation must use staffing template, got {template_name}"
        )