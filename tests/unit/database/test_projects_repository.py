import pytest
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock, ANY
from datetime import datetime, timedelta, timezone
from app.database.projects_repository import ProjectsRepository


# ---------------------------------------------------------------------------
# Helper to build a mock collection that returns the given cursor results
# ---------------------------------------------------------------------------
def _make_mock_collection():
    """Return a fresh AsyncMock collection with default async methods."""
    col = MagicMock()
    col.find = MagicMock()
    col.update_one = AsyncMock()
    col.update_many = AsyncMock()
    col.bulk_write = AsyncMock()
    col.count_documents = AsyncMock()
    col.create_index = AsyncMock()
    return col


# ---------------------------------------------------------------------------
# _build_hash
# ---------------------------------------------------------------------------
class TestBuildHash:
    def test_uses_link_when_present(self):
        repo = ProjectsRepository()
        project = {"link": "http://example.com/123"}
        expected = hashlib.sha256(b"http://example.com/123").hexdigest()
        assert repo._build_hash(project) == expected

    def test_falls_back_to_title_and_budget_when_no_link(self):
        repo = ProjectsRepository()
        project = {"title": "My Project", "budget": "$500"}
        raw = "My Project|$500"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert repo._build_hash(project) == expected

    def test_handles_empty_title_and_budget(self):
        repo = ProjectsRepository()
        project = {"title": "", "budget": ""}
        raw = "|"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert repo._build_hash(project) == expected


# ---------------------------------------------------------------------------
# _calculate_estimated_published_at
# ---------------------------------------------------------------------------
class TestCalculateEstimatedPublishedAt:
    def test_returns_none_when_published_str_empty(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert repo._calculate_estimated_published_at("", now) is None

    def test_returns_none_when_published_str_none(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert repo._calculate_estimated_published_at(None, now) is None

    def test_returns_none_when_scraped_at_not_datetime(self):
        repo = ProjectsRepository()
        assert repo._calculate_estimated_published_at("hace 1 día", "not a datetime") is None

    def test_parses_ayer(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = repo._calculate_estimated_published_at("ayer", now)
        expected = now - timedelta(days=1)
        assert result == expected

    def test_parses_hace_1_dia(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = repo._calculate_estimated_published_at("hace 1 día", now)
        expected = now - timedelta(days=1)
        assert result == expected

    def test_parses_hace_3_dias(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = repo._calculate_estimated_published_at("hace 3 días", now)
        expected = now - timedelta(days=3)
        assert result == expected

    def test_parses_hace_2_horas(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = repo._calculate_estimated_published_at("hace 2 horas", now)
        expected = now - timedelta(hours=2)
        assert result == expected

    def test_parses_hace_30_minutos(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = repo._calculate_estimated_published_at("hace 30 minutos", now)
        expected = now - timedelta(minutes=30)
        assert result == expected

    def test_parses_hace_un_momento(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = repo._calculate_estimated_published_at("hace un momento", now)
        expected = now - timedelta(minutes=1)
        assert result == expected

    def test_parses_hace_menos_de_un_minuto(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = repo._calculate_estimated_published_at("hace menos de un minuto", now)
        expected = now - timedelta(minutes=1)
        assert result == expected

    def test_parses_hace_2_meses(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = repo._calculate_estimated_published_at("hace 2 meses", now)
        expected = now - timedelta(days=60)
        assert result == expected

    def test_returns_none_for_unparseable_string(self):
        repo = ProjectsRepository()
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = repo._calculate_estimated_published_at("some random text", now)
        assert result is None


# ---------------------------------------------------------------------------
# save_scraped_projects
# ---------------------------------------------------------------------------
class TestSaveScrapedProjects:
    @pytest.mark.asyncio
    async def test_returns_zero_when_empty_list(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            result = await repo.save_scraped_projects([])
            assert result == {"inserted": 0, "existing": 0}
            mock_col.bulk_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_inserts_new_project(self):
        repo = ProjectsRepository()

        project = {
            "title": "Test Project",
            "budget": "$1000",
            "link": "http://example.com/1",
            "published": "hace 1 día",
            "short_description": "A test",
            "bids": "5",
            "skills": ["Python"],
        }

        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.bulk_write.return_value.upserted_count = 1

            result = await repo.save_scraped_projects([project])

            assert result == {"inserted": 1, "existing": 0}
            mock_col.bulk_write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_existing_project(self):
        repo = ProjectsRepository()

        project = {
            "title": "Existing",
            "budget": "$500",
            "link": "http://example.com/2",
            "published": "hace 2 horas",
            "short_description": "",
            "bids": "0",
            "skills": [],
        }

        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.bulk_write.return_value.upserted_count = 0

            result = await repo.save_scraped_projects([project])

            assert result == {"inserted": 0, "existing": 1}


# ---------------------------------------------------------------------------
# get_pending_projects
# ---------------------------------------------------------------------------
class TestGetPendingProjects:
    @pytest.mark.asyncio
    async def test_returns_pending_not_deleted(self):
        repo = ProjectsRepository()
        expected = [{"link_hash": "abc", "title": "P1"}]

        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            cursor_mock = MagicMock()
            cursor_mock.sort.return_value = cursor_mock
            cursor_mock.limit.return_value = cursor_mock
            cursor_mock.to_list = AsyncMock(return_value=expected)
            mock_col.find.return_value = cursor_mock

            result = await repo.get_pending_projects(limit=10)

            assert result == expected
            mock_col.find.assert_called_once_with(
                {"proposal_status": "pending", "deleted_at": {"$exists": False}},
                {"_id": 0, "title": 1, "budget": 1, "link": 1, "published": 1, "link_hash": 1},
            )
            # verify sort and limit
            mock_col.find.return_value.sort.assert_called_once_with("scraped_at", 1)
            mock_col.find.return_value.sort.return_value.limit.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_returns_empty_when_none_pending(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            cursor_mock = MagicMock()
            cursor_mock.sort.return_value = cursor_mock
            cursor_mock.limit.return_value = cursor_mock
            cursor_mock.to_list = AsyncMock(return_value=[])
            mock_col.find.return_value = cursor_mock

            result = await repo.get_pending_projects(limit=5)
            assert result == []


# ---------------------------------------------------------------------------
# claim_pending_projects
# ---------------------------------------------------------------------------
class TestClaimPendingProjects:
    @pytest.mark.asyncio
    async def test_claims_and_returns_projects(self):
        repo = ProjectsRepository()
        now_dt = datetime(2026, 6, 4, 15, 8, 35, tzinfo=timezone.utc)
        now_iso = now_dt.isoformat()

        pending_item = {"link_hash": "hash123"}
        updated_project = {
            "link_hash": "hash123",
            "title": "P1",
            "budget": "$100",
            "link": "http://ex.com",
            "published": "hace 1 día",
            "short_description": "desc",
            "bids": "2",
            "skills": ["Python"],
        }

        with patch("app.database.projects_repository.get_database") as mock_get_db, \
             patch("app.database.projects_repository.datetime") as mock_datetime:
            mock_datetime.now.return_value = now_dt
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}

            # first find returns pending items
            first_cursor = MagicMock()
            first_cursor.to_list = AsyncMock(return_value=[pending_item])
            # second find returns updated projects
            second_cursor = MagicMock()
            second_cursor.to_list = AsyncMock(return_value=[updated_project])

            mock_col.find.side_effect = [first_cursor, second_cursor]
            mock_col.update_many.return_value.modified_count = 1

            result = await repo.claim_pending_projects(limit=2)

            assert result == [updated_project]
            # verify update_many call
            mock_col.update_many.assert_awaited_once_with(
                {
                    "link_hash": {"$in": ["hash123"]},
                    "proposal_status": "pending",
                },
                {
                    "$set": {
                        "proposal_status": "processing",
                        "processing_started_at": now_iso,
                        "updated_at": now_iso,
                    }
                },
            )

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_pending(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            cursor_mock = MagicMock()
            cursor_mock.to_list = AsyncMock(return_value=[])
            mock_col.find.return_value = cursor_mock

            result = await repo.claim_pending_projects(limit=5)
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_update_modified_zero(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            first_cursor = MagicMock()
            first_cursor.to_list = AsyncMock(return_value=[{"link_hash": "h1"}])
            mock_col.find.return_value = first_cursor
            mock_col.update_many.return_value.modified_count = 0

            result = await repo.claim_pending_projects(limit=5)
            assert result == []


# ---------------------------------------------------------------------------
# mark_projects_status
# ---------------------------------------------------------------------------
class TestMarkProjectsStatus:
    @pytest.mark.asyncio
    async def test_returns_zero_when_empty_list(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            result = await repo.mark_projects_status([], "done")
            assert result == 0
            mock_col.update_many.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_status(self):
        repo = ProjectsRepository()
        now_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        now_iso = now_dt.isoformat()

        with patch("app.database.projects_repository.get_database") as mock_get_db, \
             patch("app.database.projects_repository.datetime") as mock_datetime:
            mock_datetime.now.return_value = now_dt
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_many.return_value.modified_count = 2

            result = await repo.mark_projects_status(["h1", "h2"], "analyzed")

            assert result == 2
            mock_col.update_many.assert_awaited_once_with(
                {"link_hash": {"$in": ["h1", "h2"]}},
                {"$set": {"proposal_status": "analyzed", "updated_at": now_iso}},
            )


# ---------------------------------------------------------------------------
# update_project_analysis
# ---------------------------------------------------------------------------
class TestUpdateProjectAnalysis:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        repo = ProjectsRepository()
        now_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        now_iso = now_dt.isoformat()

        with patch("app.database.projects_repository.get_database") as mock_get_db, \
             patch("app.database.projects_repository.datetime") as mock_datetime:
            mock_datetime.now.return_value = now_dt
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_one.return_value.modified_count = 1

            result = await repo.update_project_analysis(
                link_hash="abc",
                score=8,
                reason="Good match",
                strategy="flash",
                status="analyzed",
                ai_summary="Summary",
                contract_type="staff_augmentation",
            )

            assert result is True
            mock_col.update_one.assert_awaited_once_with(
                {"link_hash": "abc"},
                {
                    "$set": {
                        "strategy": "flash",
                        "ai_score": 8,
                        "ai_reason": "Good match",
                        "ai_summary": "Summary",
                        "contract_type": "staff_augmentation",
                        "proposal_status": "analyzed",
                        "updated_at": now_iso,
                        "analyzed_at": now_iso,
                    }
                },
            )

    @pytest.mark.asyncio
    async def test_returns_false_when_no_match(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_one.return_value.modified_count = 0

            result = await repo.update_project_analysis(
                link_hash="nonexistent",
                score=5,
                reason="",
                contract_type="project_fixed",
            )
            assert result is False


# ---------------------------------------------------------------------------
# reset_orphaned_proposals
# ---------------------------------------------------------------------------
class TestResetOrphanedProposals:
    @pytest.mark.asyncio
    async def test_resets_orphaned_projects(self):
        repo = ProjectsRepository()
        now_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        now_iso = now_dt.isoformat()

        with patch("app.database.projects_repository.get_database") as mock_get_db, \
             patch("app.database.projects_repository.datetime") as mock_datetime:
            mock_datetime.now.return_value = now_dt
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_many.return_value.modified_count = 3

            result = await repo.reset_orphaned_proposals()

            assert result == 3
            mock_col.update_many.assert_awaited_once_with(
                {
                    "proposal_status": "ready_for_proposal",
                    "deleted_at": {"$exists": False},
                },
                {
                    "$set": {
                        "proposal_status": "analyzed",
                        "updated_at": now_iso,
                        "reset_at": now_iso,
                    },
                    "$unset": {
                        "full_description": "",
                        "budget_detail": "",
                        "proposal": "",
                        "proposal_at": "",
                        "temp_proposal_data": "",
                        "proposal_draft": "",
                    },
                },
            )

    @pytest.mark.asyncio
    async def test_returns_zero_when_none_orphaned(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_many.return_value.modified_count = 0

            result = await repo.reset_orphaned_proposals()
            assert result == 0


# ---------------------------------------------------------------------------
# get_projects_for_deep_analysis
# ---------------------------------------------------------------------------
class TestGetProjectsForDeepAnalysis:
    @pytest.mark.asyncio
    async def test_filters_by_score_and_missing_full_description(self):
        repo = ProjectsRepository()
        expected = [{"link_hash": "abc", "title": "P1", "ai_score": 7}]

        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            cursor_mock = MagicMock()
            cursor_mock.limit.return_value = cursor_mock
            cursor_mock.to_list = AsyncMock(return_value=expected)
            mock_col.find.return_value = cursor_mock

            result = await repo.get_projects_for_deep_analysis(min_score=5, limit=10)

            assert result == expected
            mock_col.find.assert_called_once_with(
                {
                    "proposal_status": "analyzed",
                    "ai_score": {"$gte": 5},
                    "full_description": {"$exists": False},
                },
                {
                    "_id": 0,
                    "title": 1,
                    "budget": 1,
                    "link": 1,
                    "link_hash": 1,
                    "strategy": 1,
                    "contract_type": 1,
                    "ai_score": 1,
                    "ai_summary": 1,
                },
            )
            mock_col.find.return_value.limit.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_returns_empty_when_none_qualify(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            cursor_mock = MagicMock()
            cursor_mock.limit.return_value = cursor_mock
            cursor_mock.to_list = AsyncMock(return_value=[])
            mock_col.find.return_value = cursor_mock

            result = await repo.get_projects_for_deep_analysis(min_score=10, limit=5)
            assert result == []


# ---------------------------------------------------------------------------
# update_full_details
# ---------------------------------------------------------------------------
class TestUpdateFullDetails:
    @pytest.mark.asyncio
    async def test_updates_and_returns_true(self):
        repo = ProjectsRepository()
        now_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        now_iso = now_dt.isoformat()

        details = {
            "full_description": "Long desc",
            "skills": ["Python"],
            "budget_detail": "$1000-$2000",
        }

        with patch("app.database.projects_repository.get_database") as mock_get_db, \
             patch("app.database.projects_repository.datetime") as mock_datetime:
            mock_datetime.now.return_value = now_dt
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_one.return_value.modified_count = 1

            result = await repo.update_full_details("hash1", details)

            assert result is True
            mock_col.update_one.assert_awaited_once_with(
                {"link_hash": "hash1"},
                {
                    "$set": {
                        "full_description": "Long desc",
                        "skills": ["Python"],
                        "budget_detail": "$1000-$2000",
                        "proposal_status": "ready_for_proposal",
                        "updated_at": now_iso,
                    }
                },
            )

    @pytest.mark.asyncio
    async def test_returns_false_when_no_match(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_one.return_value.modified_count = 0

            result = await repo.update_full_details("nonexistent", {"full_description": "x"})
            assert result is False


# ---------------------------------------------------------------------------
# update_project_proposal
# ---------------------------------------------------------------------------
class TestUpdateProjectProposal:
    @pytest.mark.asyncio
    async def test_saves_proposal_and_returns_true(self):
        repo = ProjectsRepository()
        now_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        now_iso = now_dt.isoformat()

        proposal = {"cover_letter": "Hello", "budget_summary": {"hourly_rate": 25}}

        with patch("app.database.projects_repository.get_database") as mock_get_db, \
             patch("app.database.projects_repository.datetime") as mock_datetime:
            mock_datetime.now.return_value = now_dt
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_one.return_value.modified_count = 1

            result = await repo.update_project_proposal("hash1", proposal)

            assert result is True
            mock_col.update_one.assert_awaited_once_with(
                {"link_hash": "hash1"},
                {
                    "$set": {
                        "proposal": proposal,
                        "proposal_status": "proposal_generated",
                        "proposal_at": now_iso,
                        "updated_at": now_iso,
                    }
                },
            )

    @pytest.mark.asyncio
    async def test_returns_false_when_no_match(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_one.return_value.modified_count = 0

            result = await repo.update_project_proposal("nonexistent", {})
            assert result is False


# ---------------------------------------------------------------------------
# get_project_by_hash
# ---------------------------------------------------------------------------
class TestGetProjectByHash:
    @pytest.mark.asyncio
    async def test_returns_project_when_found(self):
        repo = ProjectsRepository()
        expected = {"link_hash": "abc", "title": "P1"}

        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.find_one = AsyncMock(return_value=expected)

            result = await repo.get_project_by_hash("abc")
            assert result == expected
            mock_col.find_one.assert_awaited_once_with({"link_hash": "abc"})

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.find_one = AsyncMock(return_value=None)

            result = await repo.get_project_by_hash("nonexistent")
            assert result is None


# ---------------------------------------------------------------------------
# delete_projects
# ---------------------------------------------------------------------------
class TestDeleteProjects:
    @pytest.mark.asyncio
    async def test_delete_from_date(self):
        repo = ProjectsRepository()
        expected_from_dt = datetime(2024, 6, 1, tzinfo=timezone.utc)

        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_many.return_value.modified_count = 2

            result = await repo.delete_projects(from_date="2024-06-01")

            assert result == 2
            mock_col.update_many.assert_awaited_once_with(
                {
                    "deleted_at": {"$exists": False},
                    "estimated_published_at": {"$gte": expected_from_dt}
                },
                {"$set": {"deleted_at": ANY, "updated_at": ANY}}
            )

    @pytest.mark.asyncio
    async def test_delete_all_projects(self):
        repo = ProjectsRepository()

        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_many.return_value.modified_count = 5

            result = await repo.delete_projects()

            assert result == 5
            mock_col.update_many.assert_awaited_once_with(
                {"deleted_at": {"$exists": False}},
                {"$set": {"deleted_at": ANY, "updated_at": ANY}}
            )

    @pytest.mark.asyncio
    async def test_delete_returns_zero_when_no_match(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            mock_col.update_many.return_value.modified_count = 0

            result = await repo.delete_projects(from_date="2099-01-01")
            assert result == 0


# ---------------------------------------------------------------------------
# prune_projects
# ---------------------------------------------------------------------------
class TestPruneProjects:
    @pytest.mark.asyncio
    async def test_prunes_soft_deleted_projects(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            delete_result = MagicMock()
            delete_result.deleted_count = 7
            mock_col.delete_many = AsyncMock(return_value=delete_result)

            result = await repo.prune_projects()

            assert result == 7
            mock_col.delete_many.assert_awaited_once_with(
                {"deleted_at": {"$exists": True}}
            )

    @pytest.mark.asyncio
    async def test_prune_returns_zero_when_none_soft_deleted(self):
        repo = ProjectsRepository()
        with patch("app.database.projects_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"projects": mock_col}
            delete_result = MagicMock()
            delete_result.deleted_count = 0
            mock_col.delete_many = AsyncMock(return_value=delete_result)

            result = await repo.prune_projects()
            assert result == 0
