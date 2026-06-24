import pytest
from unittest.mock import AsyncMock, patch
from app.database.projects_repository import ProjectsRepository
from datetime import datetime, timezone

class TestDatabaseIntegration:
    @pytest.fixture(autouse=True)
    def setup_database(self):
        with patch("app.database.projects_repository.get_database") as mock_get_db, \
             patch("app.database.projects_repository.datetime") as mock_datetime:

            # Set a fixed datetime for deterministic testing
            fixed_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
            mock_datetime.now.return_value = fixed_now

            # Mock the database collection
            mock_collection = AsyncMock()
            mock_collection.update_one = AsyncMock()
            mock_collection.find_one = AsyncMock()

            # Create a mock result object with modified_count = 1
            mock_result = AsyncMock()
            mock_result.modified_count = 1
            mock_collection.update_one.return_value = mock_result

            # Set up find_one to return a sample project document
            mock_collection.find_one.return_value = {
                "title": "Proyecto de MVP",
                "link_hash": "hash123",
                "contract_type": "project_fixed"
            }

            # Configure get_database to return the mocked collection
            mock_get_db.return_value = {"projects": mock_collection}
            yield

    @pytest.mark.asyncio
    async def test_contract_type_saved_in_analysis(self):
        repo = ProjectsRepository()
        project = {
            "title": "Proyecto de MVP",
            "link_hash": "hash123"
        }

        result = await repo.update_project_analysis(
            link_hash="hash123",
            score=5,
            reason="",
            contract_type="project_fixed"
        )

        assert result is True
        repo.collection.update_one.assert_awaited_once_with(
            {"link_hash": "hash123"},
            {
                "$set": {
                    "strategy": "none",
                    "ai_score": 5,
                    "ai_reason": "",
                    "ai_summary": "No summary available",
                    "contract_type": "project_fixed",
                    "proposal_status": "analyzed",
                    "updated_at": "2025-01-01T00:00:00+00:00",
                    "analyzed_at": "2025-01-01T00:00:00+00:00"
                }
            }
        )

    @pytest.mark.asyncio
    async def test_contract_type_retrieved_for_proposal(self):
        repo = ProjectsRepository()
        project = {
            "title": "Proyecto de MVP",
            "link_hash": "hash123",
            "contract_type": "project_fixed"
        }

        repo.collection.find_one.return_value = project

        result = await repo.get_project_by_hash("hash123")

        assert result is not None
        assert result["contract_type"] == "project_fixed"
