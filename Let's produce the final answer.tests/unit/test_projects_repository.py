import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.database.projects_repository import ProjectsRepository
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_claim_pending_projects():
    repo = ProjectsRepository()

    active_project = {
        "link_hash": "hash123",
        "proposal_status": "pending",
        "title": "Proyecto Activo",
        "budget": "$1000",
        "link": "http://example.com",
        "published": "hace 1 día",
        "bids": "0",
        "skills": [],
    }

    # Set a fixed timestamp for the test
    fixed_now = datetime(2026, 6, 4, 15, 8, 35, tzinfo=timezone.utc).isoformat()

    # Mock the first find to return only the active project
    first_cursor_mock = MagicMock()
    first_cursor_mock.to_list = AsyncMock(return_value=[active_project])

    # Mock the second find to return the updated project
    second_cursor_mock = MagicMock()
    second_cursor_mock.to_list = AsyncMock(return_value=[active_project])

    # Mock the update result
    update_result = AsyncMock()
    update_result.modified_count = 1

    with patch("app.database.projects_repository.get_database") as mock_get_db, \
         patch("app.database.projects_repository.datetime") as mock_datetime:

        # Set the fixed timestamp for the test
        mock_datetime.now.return_value = datetime(2026, 6, 4, 15, 8, 35, tzinfo=timezone.utc)

        mock_collection = MagicMock()
        mock_collection.find = MagicMock()
        mock_collection.update_many = AsyncMock()

        # First find call returns the first cursor
        mock_collection.find.side_effect = [
            first_cursor_mock,
            second_cursor_mock
        ]
        mock_collection.update_many.return_value = update_result

        mock_get_db.return_value = {"projects": mock_collection}

        result = await repo.claim_pending_projects(limit=2)

    assert active_project in result
    assert len(result) == 1

    # Ensure the update was called with the correct parameters
    mock_collection.update_many.assert_awaited_once_with(
        {
            "link_hash": {"$in": ["hash123"]},
            "proposal_status": "pending"
        },
        {
            "$set": {
                "proposal_status": "processing",
                "processing_started_at": fixed_now,
                "updated_at": fixed_now
            }
        }
    )

    # Ensure the second find was called with the correct parameters
    mock_collection.find.assert_has_calls([
        # First find: get pending projects
        mock_collection.find.call_args_list[0],
        # Second find: get updated projects
        mock_collection.find.call_args_list[1]
    ])

    # Verify the second find call has the correct parameters
    second_call_args = mock_collection.find.call_args_list[1]
    assert second_call_args[0][0] == {
        "link_hash": {"$in": ["hash123"]},
        "proposal_status": "processing",
        "processing_started_at": fixed_now
    }
    assert second_call_args[0][1] == {
        "_id": 0, "title": 1, "budget": 1, "link": 1,
        "published": 1, "short_description": 1, "link_hash": 1, "bids": 1,
        "skills": 1
    }
    assert second_call_args[1] == {"sort": [("scraped_at", 1)]}
