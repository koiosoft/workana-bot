"""Unit tests for RequirementAnalysesRepository (TASK005).

Covers the acceptance contract of the Stage 1 persistence layer:

  * ``insert`` persists the Etapa 1 accumulated JSON with the documented fields.
  * ``get_latest_by_project_id`` resolves "latest" strictly by ``created_at``
    DESC — no ``version_number`` exists anywhere in this repository.
  * The ``(project_id, created_at DESC)`` and ``link_hash`` indexes are declared.
  * No new external API surface is introduced (repository-level module only).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.requirement_analyses_repository import RequirementAnalysesRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLLECTION = "requirement_analyses"


def _make_mock_collection() -> MagicMock:
    """Return a fresh MagicMock collection with async defaults."""
    col = MagicMock()
    col.find_one = AsyncMock()
    col.insert_one = AsyncMock()
    col.create_index = AsyncMock()
    return col


def _object_id(value: str) -> MagicMock:
    """Mock ObjectId whose ``str()`` is *value* (motor returns ObjectId docs)."""
    oid = MagicMock()
    oid.__str__ = lambda self=None: value
    return oid


def _analysis_payload(score: int = 7, branch: str = "full") -> dict:
    """Full nested Stage 1 analysis object (mirrors RequirementAnalysis)."""
    return {
        "maturity_score": score,
        "maturity_reason": "La descripción define stack y entregables.",
        "entities": {
            "technologies": ["Django", "PostgreSQL"],
            "deliverables": ["API REST documentada"],
            "constraints": ["presupuesto fijo"],
        },
        "gaps": [] if branch == "full" else ["¿Hosting incluido?"],
        "branch": branch,
    }


def _document(**overrides) -> dict:
    doc = {
        "project_id": "pid1",
        "link_hash": "hash1",
        "analysis": _analysis_payload(),
        "maturity_threshold_used": 8,
        "model_used": "gemini-2.5-flash",
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def mock_db():
    """Patch get_database and expose the mock collection to tests."""
    with patch(
        "app.database.requirement_analyses_repository.get_database"
    ) as mock_get_db:
        col = _make_mock_collection()
        mock_get_db.return_value = {COLLECTION: col}
        yield col


# ---------------------------------------------------------------------------
# ensure_indexes
# ---------------------------------------------------------------------------


class TestEnsureIndexes:
    async def test_creates_required_indexes(self, mock_db):
        repo = RequirementAnalysesRepository()
        await repo.ensure_indexes()

        assert mock_db.create_index.call_count == 2
        calls = [c[0][0] for c in mock_db.create_index.call_args_list]
        # Compound (project_id ASC, created_at DESC) for latest lookups
        assert [("project_id", 1), ("created_at", -1)] in calls
        # link_hash for hash-keyed lookups
        assert [("link_hash", 1)] in calls

    async def test_no_unique_version_index_declared(self, mock_db):
        """Sin versionado secuencial: version_number must never be indexed."""
        repo = RequirementAnalysesRepository()
        await repo.ensure_indexes()

        for call in mock_db.create_index.call_args_list:
            assert "version_number" not in str(call)

    async def test_skips_on_second_call(self, mock_db):
        repo = RequirementAnalysesRepository()
        await repo.ensure_indexes()
        await repo.ensure_indexes()
        assert mock_db.create_index.call_count == 2


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


class TestInsert:
    async def test_persists_document_fields(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        inserted_id = await repo.insert(_document())

        assert inserted_id == "abc123"
        doc = mock_db.insert_one.call_args[0][0]
        assert set(doc) == {
            "project_id",
            "link_hash",
            "analysis",
            "maturity_threshold_used",
            "model_used",
            "created_at",
        }
        assert doc["project_id"] == "pid1"
        assert doc["link_hash"] == "hash1"
        assert doc["model_used"] == "gemini-2.5-flash"
        assert doc["maturity_threshold_used"] == 8

    async def test_stores_full_nested_analysis(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")
        payload = _analysis_payload(score=3, branch="discovery")

        await repo.insert(_document(analysis=payload))

        stored = mock_db.insert_one.call_args[0][0]["analysis"]
        assert stored == payload
        assert set(stored) == {
            "maturity_score",
            "maturity_reason",
            "entities",
            "gaps",
            "branch",
        }
        assert stored["entities"]["technologies"] == ["Django", "PostgreSQL"]

    async def test_created_at_defaults_to_utc_datetime(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")
        before = datetime.now(timezone.utc)

        await repo.insert(_document())

        created = mock_db.insert_one.call_args[0][0]["created_at"]
        assert isinstance(created, datetime)
        assert created.tzinfo is not None
        assert created >= before

    async def test_respects_explicit_created_at(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")
        when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

        await repo.insert(_document(created_at=when))

        assert mock_db.insert_one.call_args[0][0]["created_at"] == when

    async def test_ensures_indexes_before_insert(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        await repo.insert(_document())

        assert mock_db.create_index.call_count == 2

    async def test_coerces_string_threshold_to_int(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        await repo.insert(_document(maturity_threshold_used="7"))

        stored = mock_db.insert_one.call_args[0][0]["maturity_threshold_used"]
        assert stored == 7 and isinstance(stored, int)

    async def test_rejects_non_int_threshold(self, mock_db):
        repo = RequirementAnalysesRepository()

        with pytest.raises(ValueError, match="maturity_threshold_used"):
            await repo.insert(_document(maturity_threshold_used="alto"))

    @pytest.mark.parametrize(
        "overrides",
        [
            {"project_id": ""},
            {"link_hash": ""},
            {"analysis": None},
            {"model_used": ""},
            {"maturity_threshold_used": None},
        ],
    )
    async def test_rejects_invalid_payloads(self, mock_db, overrides):
        repo = RequirementAnalysesRepository()

        with pytest.raises(ValueError):
            await repo.insert(_document(**overrides))

        mock_db.insert_one.assert_not_called()

    async def test_rejects_empty_analysis_dict(self, mock_db):
        repo = RequirementAnalysesRepository()

        with pytest.raises(ValueError, match="analysis"):
            await repo.insert(_document(analysis={}))

    async def test_rejects_non_dict_document(self, mock_db):
        repo = RequirementAnalysesRepository()

        with pytest.raises(ValueError):
            await repo.insert(["not", "a", "dict"])

    async def test_drops_unknown_extra_fields(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        await repo.insert(_document(version_number=4, proposal="x"))

        doc = mock_db.insert_one.call_args[0][0]
        assert "version_number" not in doc
        assert "proposal" not in doc


# ---------------------------------------------------------------------------
# get_latest_by_project_id
# ---------------------------------------------------------------------------


class TestGetLatestByProjectId:
    async def test_sorts_by_created_at_descending(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.find_one.return_value = {
            "_id": _object_id("deadbeef"),
            "project_id": "pid1",
            "created_at": datetime(2026, 5, 5, tzinfo=timezone.utc),
        }

        doc = await repo.get_latest_by_project_id("pid1")

        kwargs = mock_db.find_one.call_args.kwargs
        assert mock_db.find_one.call_args[0][0] == {"project_id": "pid1"}
        assert kwargs["sort"] == [("created_at", -1)]
        assert "version_number" not in str(kwargs)
        assert doc["_id"] == "deadbeef"

    async def test_returns_none_when_absent(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.find_one.return_value = None

        assert await repo.get_latest_by_project_id("missing") is None

    async def test_ensures_indexes_before_query(self, mock_db):
        repo = RequirementAnalysesRepository()
        mock_db.find_one.return_value = None

        await repo.get_latest_by_project_id("pid1")

        assert mock_db.create_index.call_count == 2

    async def test_highest_created_at_wins_with_fake_store(self, mock_db):
        """End-to-end-ish check: newest inserted document is the one returned."""
        store: list[dict] = []

        async def fake_insert_one(doc):
            # motor adds an _id; mirror it so the fake matches real behaviour.
            stored = dict(doc)
            stored.setdefault("_id", f"id{len(store) + 1}")
            store.append(stored)
            return MagicMock(inserted_id=stored["_id"])

        async def fake_find_one(*args, **kwargs):
            query = args[0] if args else kwargs.get("filter", {})
            sort = kwargs.get("sort") or (args[1] if len(args) > 1 else None)
            # Return a copy: the repository mutates _id on the document it gets back.
            matches = [dict(d) for d in store if d["project_id"] == query["project_id"]]
            if not matches:
                return None
            key = sort[0][0]
            reverse = sort[0][1] == -1
            return sorted(matches, key=lambda d: d[key], reverse=reverse)[0]

        repo = RequirementAnalysesRepository()
        mock_db.insert_one.side_effect = fake_insert_one
        mock_db.find_one.side_effect = fake_find_one

        older = datetime(2026, 1, 1, tzinfo=timezone.utc)
        newer = datetime(2026, 6, 1, tzinfo=timezone.utc)
        await repo.insert(_document(analysis=_analysis_payload(score=4), created_at=newer))
        await repo.insert(_document(analysis=_analysis_payload(score=9), created_at=older))

        latest = await repo.get_latest_by_project_id("pid1")
        assert latest["created_at"] == newer
        assert latest["analysis"]["maturity_score"] == 4
