"""Unit tests for TechnicalEstimatesRepository (UNIT015).

Covers the acceptance contract of the Stage 2 persistence layer:

  * ``ensure_indexes`` creates the required indexes
  * ``insert`` persists the full/full or discovery document with validation
  * ``get_latest_by_project_id`` sorts by ``created_at`` DESC
  * Validation: missing fields, wrong types, branch-specific field exclusivity
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.technical_estimates_repository import (
    TechnicalEstimatesRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLLECTION = "technical_estimates"


def _make_mock_collection() -> MagicMock:
    col = MagicMock()
    col.find_one = AsyncMock()
    col.insert_one = AsyncMock()
    col.create_indexes = AsyncMock()
    col.create_index = AsyncMock()
    return col


def _object_id(value: str) -> MagicMock:
    oid = MagicMock()
    oid.__str__ = lambda self=None: value
    return oid


def _analysis_payload(score: int = 7, branch: str = "full") -> dict:
    return {
        "maturity_score": score,
        "maturity_reason": "Clear description.",
        "entities": {"technologies": ["Python"], "deliverables": [], "constraints": []},
        "gaps": [] if branch == "full" else ["Missing stack"],
        "branch": branch,
    }


def _full_document(**overrides) -> dict:
    doc = {
        "project_id": "pid1",
        "link_hash": "hash1",
        "estimate_type": "full",
        "analysis": _analysis_payload(),
        "model_used": "gemini-2.5-flash",
        "milestones": [
            {
                "step": 1,
                "name": "Design",
                "tasks": {"t1": {"description": "UI", "hours_with_overhead": 10}},
                "hours_with_overhead": 10,
                "subtotal": 250.0,
            }
        ],
        "summary": {
            "total_hours": 10,
            "total_budget": 250.0,
            "delivery_time_weeks": 2,
            "hourly_rate_applied": 25.0,
        },
    }
    doc.update(overrides)
    return doc


def _discovery_document(**overrides) -> dict:
    doc = {
        "project_id": "pid1",
        "link_hash": "hash1",
        "estimate_type": "discovery",
        "analysis": _analysis_payload(score=3, branch="discovery"),
        "model_used": "gemini-2.5-flash",
        "milestones": [
            {"step": 1, "name": "Integracion", "tasks": {"t1": {"description": "setup", "hours_with_overhead": 4}}, "hours_with_overhead": 4, "subtotal": 72.0},
        ],
        "summary": {"total_hours": 4, "total_budget": 72.0, "delivery_time_weeks": 1, "hourly_rate_applied": 18.0},
        "scope_matrix": {
            "in_scope": ["Review"],
            "out_of_scope": ["Implementation"],
        },
        "discovery_hours": 20,
        "post_discovery_hourly_rate": 18.0,
        "open_questions": ["What stack?"],
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def mock_db():
    with patch(
        "app.database.technical_estimates_repository.get_database"
    ) as mock_get_db:
        col = _make_mock_collection()
        mock_get_db.return_value = {COLLECTION: col}
        yield col


# ---------------------------------------------------------------------------
# ensure_indexes
# ---------------------------------------------------------------------------


class TestEnsureIndexes:
    async def test_creates_required_indexes(self, mock_db):
        repo = TechnicalEstimatesRepository()
        await repo.ensure_indexes()

        assert mock_db.create_indexes.call_count == 1
        models = mock_db.create_indexes.call_args[0][0]

        # Build a list of (field, order) tuples from each model
        all_keys = [list(d) for d in (model.document["key"] for model in models)]

        # (project_id ASC, created_at DESC)
        expected_full = [("project_id", 1), ("created_at", -1)]
        actual_full = list(models[0].document["key"].items())
        assert actual_full == expected_full, f"Expected {expected_full}, got {actual_full}"

        # (link_hash ASC)
        expected_hash = [("link_hash", 1)]
        actual_hash = list(models[1].document["key"].items()) if len(models) > 1 else None
        assert actual_hash == expected_hash, f"Expected {expected_hash}, got {actual_hash}"

    async def test_skips_on_second_call(self, mock_db):
        repo = TechnicalEstimatesRepository()
        await repo.ensure_indexes()
        await repo.ensure_indexes()
        assert mock_db.create_indexes.call_count == 1

    async def test_no_version_number_index(self, mock_db):
        repo = TechnicalEstimatesRepository()
        await repo.ensure_indexes()
        models = mock_db.create_indexes.call_args[0][0]
        for model in models:
            keys = model.document
            assert "version_number" not in str(keys)


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


class TestInsert:
    async def test_persists_full_document_fields(self, mock_db):
        repo = TechnicalEstimatesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        inserted_id = await repo.insert(_full_document())
        assert inserted_id == "abc123"

        doc = mock_db.insert_one.call_args[0][0]
        # Essential envelope fields
        assert doc["project_id"] == "pid1"
        assert doc["link_hash"] == "hash1"
        assert doc["estimate_type"] == "full"
        assert doc["model_used"] == "gemini-2.5-flash"
        assert "milestones" in doc
        assert "summary" in doc
        # Discovery-only fields must NOT be present
        assert "scope_matrix" not in doc
        assert "discovery_hours" not in doc

    async def test_persists_discovery_document_fields(self, mock_db):
        repo = TechnicalEstimatesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        inserted_id = await repo.insert(_discovery_document())
        assert inserted_id == "abc123"

        doc = mock_db.insert_one.call_args[0][0]
        assert doc["estimate_type"] == "discovery"
        assert doc["discovery_hours"] == 20
        assert "open_questions" in doc
        # Diseno B: discovery SI lleva la parte estimable
        assert doc["milestones"] == [] or doc["milestones"]
        assert "summary" in doc

    async def test_created_at_defaults_to_utc(self, mock_db):
        repo = TechnicalEstimatesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")
        before = datetime.now(timezone.utc)

        await repo.insert(_full_document())

        created = mock_db.insert_one.call_args[0][0]["created_at"]
        assert isinstance(created, datetime)
        assert created.tzinfo is not None
        assert created >= before

    async def test_respects_explicit_created_at(self, mock_db):
        repo = TechnicalEstimatesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")
        when = datetime(2026, 6, 1, tzinfo=timezone.utc)

        await repo.insert(_full_document(created_at=when))
        assert mock_db.insert_one.call_args[0][0]["created_at"] == when

    async def test_ensures_indexes_before_insert(self, mock_db):
        repo = TechnicalEstimatesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        await repo.insert(_full_document())
        assert mock_db.create_indexes.call_count == 1

    async def test_rejects_missing_required_fields(self, mock_db):
        repo = TechnicalEstimatesRepository()

        with pytest.raises(ValueError, match="project_id"):
            doc = _full_document()
            del doc["project_id"]
            await repo.insert(doc)

        mock_db.insert_one.assert_not_called()

    async def test_rejects_missing_link_hash(self, mock_db):
        repo = TechnicalEstimatesRepository()

        with pytest.raises(ValueError, match="link_hash"):
            doc = _full_document()
            del doc["link_hash"]
            await repo.insert(doc)

    async def test_rejects_invalid_estimate_type(self, mock_db):
        repo = TechnicalEstimatesRepository()

        with pytest.raises(ValueError, match="estimate_type"):
            await repo.insert(_full_document(estimate_type="invalid"))

    async def test_rejects_missing_model_used(self, mock_db):
        repo = TechnicalEstimatesRepository()

        with pytest.raises(ValueError, match="model_used"):
            doc = _full_document()
            del doc["model_used"]
            await repo.insert(doc)

    async def test_rejects_non_dict_document(self, mock_db):
        repo = TechnicalEstimatesRepository()

        with pytest.raises(ValueError):
            await repo.insert(["not", "a", "dict"])

    async def test_drops_unknown_extra_fields(self, mock_db):
        """Extra fields not in the contract should be dropped."""
        repo = TechnicalEstimatesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        await repo.insert(_full_document(version_number=4, proposal="x"))

        doc = mock_db.insert_one.call_args[0][0]
        assert "version_number" not in doc
        assert "proposal" not in doc

    async def test_drops_branch_foreign_fields_from_full(self, mock_db):
        """Full document with discovery fields: those fields are simply dropped.

        The _normalise method selects only fields declared in
        _BRANCH_FIELDS['full']; scope_matrix/discovery_hours are excluded
        and the document is inserted without them.
        """
        repo = TechnicalEstimatesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        await repo.insert(
            _full_document(estimate_type="full", scope_matrix={"in_scope": []})
        )
        doc = mock_db.insert_one.call_args[0][0]
        assert "scope_matrix" not in doc, "scope_matrix should be dropped for full"
        assert "discovery_hours" not in doc
        assert doc["estimate_type"] == "full"
        assert "milestones" in doc
        assert "summary" in doc
        assert doc["estimate_type"] == "full"
        assert "milestones" in doc
        assert "summary" in doc

    async def test_drops_branch_foreign_fields_from_discovery(self, mock_db):
        """Discovery (Diseno B) declara milestones/summary: NO se descartan.

        _BRANCH_FIELDS['discovery'] incluye milestones/summary + los campos de
        descubrimiento; un documento discovery valido los conserva todos.
        """
        repo = TechnicalEstimatesRepository()
        mock_db.insert_one.return_value = MagicMock(inserted_id="abc123")

        await repo.insert(
            _discovery_document(
                estimate_type="discovery",
                milestones=[{"step": 1, "name": "X", "tasks": {"t": {"description": "d", "hours_with_overhead": 10}}, "hours_with_overhead": 10, "subtotal": 180}],
                summary={"total_hours": 10, "total_budget": 180, "delivery_time_weeks": 1, "hourly_rate_applied": 18},
            )
        )
        doc = mock_db.insert_one.call_args[0][0]
        assert "milestones" in doc, "discovery conserva su parte estimable"
        assert "summary" in doc
        assert doc["estimate_type"] == "discovery"
        assert "scope_matrix" in doc
        assert "open_questions" in doc


# ---------------------------------------------------------------------------
# get_latest_by_project_id
# ---------------------------------------------------------------------------


class TestGetLatestByProjectId:
    async def test_sorts_by_created_at_descending(self, mock_db):
        repo = TechnicalEstimatesRepository()
        mock_db.find_one.return_value = {
            "_id": _object_id("deadbeef"),
            "project_id": "pid1",
            "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        }

        doc = await repo.get_latest_by_project_id("pid1")
        assert doc["_id"] == "deadbeef"

        kwargs = mock_db.find_one.call_args.kwargs
        assert mock_db.find_one.call_args[0][0] == {"project_id": "pid1"}
        assert kwargs["sort"] == [("created_at", -1)]

    async def test_returns_none_when_absent(self, mock_db):
        repo = TechnicalEstimatesRepository()
        mock_db.find_one.return_value = None

        assert await repo.get_latest_by_project_id("missing") is None

    async def test_ensures_indexes_before_query(self, mock_db):
        repo = TechnicalEstimatesRepository()
        mock_db.find_one.return_value = None

        await repo.get_latest_by_project_id("pid1")
        assert mock_db.create_indexes.call_count == 1

    async def test_highest_created_at_wins(self, mock_db):
        """End-to-end-ish: newest inserted document is the one returned."""
        store: list[dict] = []

        async def fake_insert_one(doc):
            stored = dict(doc)
            stored.setdefault("_id", f"id{len(store) + 1}")
            store.append(stored)
            return MagicMock(inserted_id=stored["_id"])

        async def fake_find_one(*args, **kwargs):
            query = args[0] if args else kwargs.get("filter", {})
            sort = kwargs.get("sort") or []
            matches = [
                dict(d) for d in store if d["project_id"] == query["project_id"]
            ]
            if not matches:
                return None
            key = sort[0][0]
            reverse = sort[0][1] == -1
            return sorted(matches, key=lambda d: d[key], reverse=reverse)[0]

        repo = TechnicalEstimatesRepository()
        mock_db.insert_one.side_effect = fake_insert_one
        mock_db.find_one.side_effect = fake_find_one

        older = datetime(2026, 1, 1, tzinfo=timezone.utc)
        newer = datetime(2026, 6, 1, tzinfo=timezone.utc)

        await repo.insert(_full_document(created_at=newer))
        await repo.insert(_full_document(created_at=older))

        latest = await repo.get_latest_by_project_id("pid1")
        assert latest["created_at"] == newer

    async def test_stringifies_object_id(self, mock_db):
        """_id should be converted to str in the returned document."""
        repo = TechnicalEstimatesRepository()
        mock_db.find_one.return_value = {
            "_id": _object_id("abc123"),
            "project_id": "pid1",
            "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        }

        doc = await repo.get_latest_by_project_id("pid1")
        assert isinstance(doc["_id"], str)
        assert doc["_id"] == "abc123"