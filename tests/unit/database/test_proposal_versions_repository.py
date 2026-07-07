"""Unit tests for ProposalVersionsRepository."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId

from app.database.proposal_versions_repository import ProposalVersionsRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_collection() -> MagicMock:
    """Return a fresh MagicMock collection with async defaults."""
    col = MagicMock()
    col.find = MagicMock()
    col.find_one = AsyncMock()
    col.insert_one = AsyncMock()
    col.update_one = AsyncMock()
    col.delete_many = AsyncMock()
    col.count_documents = AsyncMock()
    col.create_index = AsyncMock()
    col.aggregate = MagicMock()
    return col


# ---------------------------------------------------------------------------
# ensure_indexes
# ---------------------------------------------------------------------------

class TestEnsureIndexes:
    @pytest.mark.asyncio
    async def test_creates_expected_indexes(self):
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            await repo.ensure_indexes()

            assert mock_col.create_index.call_count == 3
            # Gather all index specs
            calls = [call[0][0] for call in mock_col.create_index.call_args_list]
            # Compound index (project_id, version_number DESC)
            assert ([("project_id", 1), ("version_number", -1)] in calls)
            # Single-field project_id index
            assert ([("project_id", 1)] in calls)
            # link_hash index
            assert ([("link_hash", 1)] in calls)

    @pytest.mark.asyncio
    async def test_skips_on_second_call(self):
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            await repo.ensure_indexes()
            await repo.ensure_indexes()
            # Only called once because of the flag
            assert mock_col.create_index.call_count == 3


# ---------------------------------------------------------------------------
# insert_version
# ---------------------------------------------------------------------------

class TestInsertVersion:
    @pytest.mark.asyncio
    async def test_inserts_first_version(self):
        repo = ProposalVersionsRepository()
        proposal = {"cover_letter": "Hello"}

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.find_one.return_value = None  # No existing versions
            mock_col.insert_one.return_value = MagicMock(
                inserted_id="abc123"
            )

            inserted_id = await repo.insert_version(
                project_id="pid1",
                link_hash="hash1",
                proposal_data=proposal,
            )

            assert inserted_id == "abc123"
            # Verify the doc shape
            doc = mock_col.insert_one.call_args[0][0]
            assert doc["project_id"] == "pid1"
            assert doc["link_hash"] == "hash1"
            assert doc["version_number"] == 1
            assert doc["proposal_data"] == proposal
            assert "created_at" in doc

    @pytest.mark.asyncio
    async def test_increments_version_number(self):
        repo = ProposalVersionsRepository()
        proposal = {"cover_letter": "Hello"}

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.find_one.return_value = {"version_number": 3}
            mock_col.insert_one.return_value = MagicMock(
                inserted_id="abc124"
            )

            inserted_id = await repo.insert_version(
                project_id="pid1",
                link_hash="hash1",
                proposal_data=proposal,
            )

            assert inserted_id == "abc124"
            doc = mock_col.insert_one.call_args[0][0]
            assert doc["version_number"] == 4

    @pytest.mark.asyncio
    async def test_includes_refinement_log_when_provided(self):
        repo = ProposalVersionsRepository()
        proposal = {"cover_letter": "Hello"}
        refinement = [{"refined_by": "user1", "reason": "test"}]

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.find_one.return_value = None
            mock_col.insert_one.return_value = MagicMock(
                inserted_id="xyz"
            )

            await repo.insert_version(
                project_id="pid1",
                link_hash="hash1",
                proposal_data=proposal,
                refinement_log=refinement,
            )

            doc = mock_col.insert_one.call_args[0][0]
            assert doc["refinement_log"] == refinement

    @pytest.mark.asyncio
    async def test_insert_version_sets_source_of_changes_to_ia(self):
        """Verify that source_of_changes is always set to 'IA' on insert."""
        repo = ProposalVersionsRepository()
        proposal = {"cover_letter": "Hello"}

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.find_one.return_value = None
            mock_col.insert_one.return_value = MagicMock(inserted_id="abc-ia")

            await repo.insert_version(
                project_id="pid-ia",
                link_hash="hash-ia",
                proposal_data=proposal,
            )

            doc = mock_col.insert_one.call_args[0][0]
            assert doc["source_of_changes"] == "IA"


# ---------------------------------------------------------------------------
# update_source_of_changes
# ---------------------------------------------------------------------------

class TestUpdateSourceOfChanges:
    @pytest.mark.asyncio
    async def test_updates_source_to_human(self):
        """update_source_of_changes should set source_of_changes to 'HUMAN'."""
        repo = ProposalVersionsRepository()

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            # Simulate a latest version existing
            valid_oid = ObjectId()
            mock_col.find_one.return_value = {
                "_id": str(valid_oid),
                "project_id": "pid-1",
                "version_number": 3,
                "source_of_changes": "IA",
            }
            mock_col.update_one.return_value = MagicMock(modified_count=1)

            result = await repo.update_source_of_changes("pid-1")

            assert result is True
            mock_col.update_one.assert_awaited_once()
            # Verify the $set operation targets source_of_changes
            call_args = mock_col.update_one.call_args
            assert call_args[0][0] == {"_id": valid_oid}
            assert call_args[0][1] == {"$set": {"source_of_changes": "HUMAN"}}

    @pytest.mark.asyncio
    async def test_returns_false_when_no_version_exists(self):
        """Should return False when no proposal version exists for the project."""
        repo = ProposalVersionsRepository()

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.find_one.return_value = None  # No version found

            result = await repo.update_source_of_changes("nonexistent")

            assert result is False
            mock_col.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_custom_source_value(self):
        """Should accept a custom source value."""
        repo = ProposalVersionsRepository()

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            valid_oid = ObjectId()
            mock_col.find_one.return_value = {
                "_id": str(valid_oid),
                "project_id": "pid-custom",
            }
            mock_col.update_one.return_value = MagicMock(modified_count=1)

            result = await repo.update_source_of_changes(
                "pid-custom", source="CUSTOM"
            )

            assert result is True
            assert mock_col.update_one.call_args[0][1] == {
                "$set": {"source_of_changes": "CUSTOM"}
            }


# ---------------------------------------------------------------------------
# get_latest_version
# ---------------------------------------------------------------------------

class TestGetLatestVersion:
    @pytest.mark.asyncio
    async def test_returns_latest_version(self):
        repo = ProposalVersionsRepository()
        version_doc = {
            "_id": "v1",
            "project_id": "pid1",
            "version_number": 2,
            "proposal_data": {"cover_letter": "v2"},
        }

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.find_one.return_value = version_doc.copy()

            result = await repo.get_latest_version("pid1")

            assert result is not None
            assert result["_id"] == "v1"
            assert result["version_number"] == 2
            # Verify sort order
            mock_col.find_one.assert_awaited_once_with(
                {"project_id": "pid1"},
                sort=[("version_number", -1)],
            )

    @pytest.mark.asyncio
    async def test_returns_none_when_no_versions(self):
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.find_one.return_value = None

            result = await repo.get_latest_version("nonexistent")
            assert result is None


# ---------------------------------------------------------------------------
# get_latest_version_by_link_hash
# ---------------------------------------------------------------------------

class TestGetLatestVersionByLinkHash:
    @pytest.mark.asyncio
    async def test_returns_latest_by_link_hash(self):
        repo = ProposalVersionsRepository()
        version_doc = {
            "_id": "v2",
            "project_id": "pid2",
            "link_hash": "lh1",
            "version_number": 3,
        }

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.find_one.return_value = version_doc.copy()

            result = await repo.get_latest_version_by_link_hash("lh1")

            assert result["_id"] == "v2"
            mock_col.find_one.assert_awaited_once_with(
                {"link_hash": "lh1"},
                sort=[("version_number", -1)],
            )


# ---------------------------------------------------------------------------
# get_version_history
# ---------------------------------------------------------------------------

class TestGetVersionHistory:
    @pytest.mark.asyncio
    async def test_returns_all_versions_newest_first(self):
        repo = ProposalVersionsRepository()
        docs = [
            {"_id": "v3", "version_number": 3},
            {"_id": "v2", "version_number": 2},
            {"_id": "v1", "version_number": 1},
        ]

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            cursor_mock = MagicMock()
            cursor_mock.sort.return_value = cursor_mock
            cursor_mock.to_list = AsyncMock(return_value=docs)
            mock_col.find.return_value = cursor_mock

            result = await repo.get_version_history("pid1")

            assert len(result) == 3
            assert result[0]["_id"] == "v3"
            assert result[2]["_id"] == "v1"
            mock_col.find.assert_called_once_with({"project_id": "pid1"})
            cursor_mock.sort.assert_called_once_with([("version_number", -1)])

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_versions(self):
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            cursor_mock = MagicMock()
            cursor_mock.sort.return_value = cursor_mock
            cursor_mock.to_list = AsyncMock(return_value=[])
            mock_col.find.return_value = cursor_mock

            result = await repo.get_version_history("pid1")
            assert result == []


# ---------------------------------------------------------------------------
# get_latest_versions_for_projects (aggregation)
# ---------------------------------------------------------------------------

class TestGetLatestVersionsForProjects:
    @pytest.mark.asyncio
    async def test_returns_mapping_of_latest_versions(self):
        repo = ProposalVersionsRepository()
        agg_results = [
            {
                "_id": "pid1",
                "latest": {
                    "_id": "v10",
                    "project_id": "pid1",
                    "version_number": 3,
                    "proposal_data": {"cover_letter": "latest"},
                },
            },
            {
                "_id": "pid2",
                "latest": {
                    "_id": "v20",
                    "project_id": "pid2",
                    "version_number": 1,
                    "proposal_data": {"cover_letter": "first"},
                },
            },
        ]

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            # mock aggregate to return an async iterable
            async def _async_gen():
                for doc in agg_results:
                    yield doc

            mock_col.aggregate.return_value = _async_gen()

            result = await repo.get_latest_versions_for_projects(["pid1", "pid2"])

            assert "pid1" in result
            assert result["pid1"]["_id"] == "v10"
            assert result["pid1"]["version_number"] == 3
            assert "pid2" in result
            assert result["pid2"]["_id"] == "v20"

            # Verify pipeline structure
            pipeline = mock_col.aggregate.call_args[0][0]
            assert pipeline[0] == {"$match": {"project_id": {"$in": ["pid1", "pid2"]}}}
            assert pipeline[1] == {"$sort": {"version_number": -1}}
            assert pipeline[2]["$group"]["_id"] == "$project_id"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_ids(self):
        repo = ProposalVersionsRepository()
        result = await repo.get_latest_versions_for_projects([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_versions_found(self):
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            # mock aggregate to return an async iterable (empty)
            async def _async_gen():
                if False:  # never yields – empty
                    yield

            mock_col.aggregate.return_value = _async_gen()

            result = await repo.get_latest_versions_for_projects(["nonexistent"])
            assert result == {}


# ---------------------------------------------------------------------------
# count_versions
# ---------------------------------------------------------------------------

class TestCountVersions:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.count_documents.return_value = 5

            result = await repo.count_versions("pid1")
            assert result == 5
            mock_col.count_documents.assert_awaited_once_with({"project_id": "pid1"})


# ---------------------------------------------------------------------------
# delete_versions_for_project
# ---------------------------------------------------------------------------

class TestDeleteVersionsForProject:
    @pytest.mark.asyncio
    async def test_deletes_and_returns_count(self):
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.delete_many.return_value = MagicMock(deleted_count=3)

            result = await repo.delete_versions_for_project("pid1")
            assert result == 3
            mock_col.delete_many.assert_awaited_once_with({"project_id": "pid1"})

    @pytest.mark.asyncio
    async def test_returns_zero_when_nothing_deleted(self):
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}
            mock_col.delete_many.return_value = MagicMock(deleted_count=0)

            result = await repo.delete_versions_for_project("nonexistent")
            assert result == 0


# ---------------------------------------------------------------------------
# Compound index validation (Task 10)
# ---------------------------------------------------------------------------

class TestCompoundIndexValidation:
    """Verify that the repository creates the exact compound indexes required
    by the decoupling strategy."""

    @pytest.mark.asyncio
    async def test_compound_index_project_id_version_number_desc(self):
        """
        Compound index ``(project_id ASC, version_number DESC)`` must be
        present for efficient latest-version lookups.
        """
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            await repo.ensure_indexes()

            # Collect every create_index call's positional arg (the index spec)
            specs = [
                call[0][0]
                for call in mock_col.create_index.call_args_list
            ]
            # The compound index must be present
            assert [("project_id", 1), ("version_number", -1)] in specs

    @pytest.mark.asyncio
    async def test_single_field_project_id_index(self):
        """
        Single-field index ``(project_id ASC)`` must be present for
        aggregation ``$group`` performance.
        """
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            await repo.ensure_indexes()

            specs = [
                call[0][0]
                for call in mock_col.create_index.call_args_list
            ]
            assert [("project_id", 1)] in specs

    @pytest.mark.asyncio
    async def test_link_hash_index(self):
        """
        Single-field index ``(link_hash ASC)`` must be present for queries
        that identify a project by its link_hash.
        """
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            await repo.ensure_indexes()

            specs = [
                call[0][0]
                for call in mock_col.create_index.call_args_list
            ]
            assert [("link_hash", 1)] in specs

    @pytest.mark.asyncio
    async def test_exactly_three_indexes_created(self):
        """
        No more, no less than the three indexes required by the
        decoupling strategy.
        """
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            await repo.ensure_indexes()

            assert mock_col.create_index.call_count == 3


# ---------------------------------------------------------------------------
# Aggregation pipeline accuracy (Task 10)
# ---------------------------------------------------------------------------

class TestAggregationPipelineAccuracy:
    """Verify that the aggregation pipeline used by
    ``get_latest_versions_for_projects`` produces correct results."""

    @pytest.mark.asyncio
    async def test_pipeline_stages_in_correct_order(self):
        """
        The aggregation pipeline must execute: $match → $sort → $group
        in that exact order to guarantee the latest version is selected.
        """
        repo = ProposalVersionsRepository()
        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            # Return empty async iterable
            async def _empty():
                if False:
                    yield
            mock_col.aggregate.return_value = _empty()

            await repo.get_latest_versions_for_projects(["pid1"])

            pipeline = mock_col.aggregate.call_args[0][0]
            assert len(pipeline) == 3
            assert pipeline[0] == {"$match": {"project_id": {"$in": ["pid1"]}}}
            assert pipeline[1] == {"$sort": {"version_number": -1}}
            assert pipeline[2] == {
                "$group": {
                    "_id": "$project_id",
                    "latest": {"$first": "$$ROOT"},
                }
            }

    @pytest.mark.asyncio
    async def test_latest_version_selected_from_multiple(self):
        """
        When a project has versions [1, 3, 2], the aggregation must return
        version 3 as the latest.
        """
        repo = ProposalVersionsRepository()
        agg_results = [
            {
                "_id": "pid1",
                "latest": {
                    "_id": "v3",
                    "project_id": "pid1",
                    "version_number": 3,
                    "proposal_data": {"cover_letter": "v3"},
                },
            }
        ]

        with patch(
            "app.database.proposal_versions_repository.get_database"
        ) as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"proposal_versions": mock_col}

            async def _gen():
                for doc in agg_results:
                    yield doc
            mock_col.aggregate.return_value = _gen()

            result = await repo.get_latest_versions_for_projects(["pid1"])

            assert result["pid1"]["version_number"] == 3
            assert result["pid1"]["proposal_data"]["cover_letter"] == "v3"