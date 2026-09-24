"""
Repository for the ``requirement_analyses`` collection (Stage 1 / Etapa 1).

Every ``project_fixed`` run of the staged pipeline stores the accumulated
requirement-analysis JSON produced by Stage 1 here: one document per analysis,
never mutated afterwards.

Lookup rule (plan §6.1 — "Sin versionado secuencial"): there is **no**
``version_number`` field and no auto-increment logic.  The effective analysis
for a project is always the most recently created document, i.e. the lookup is
strictly ``created_at`` DESC.  That is why only two operations exist here:
``insert`` (append) and ``get_latest_by_project_id`` (read the newest).

The persisted document doubles as the audit record required by plan §6.3: it
carries the threshold that was in force (``maturity_threshold_used``) and the
model that produced the output (``model_used``) alongside the nested
``analysis`` payload validated by ``app.models.analysis.RequirementAnalysis``.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from loguru import logger
from pymongo import ASCENDING, DESCENDING

from .mongo import get_database


class RequirementAnalysesRepository:
    """Data-access layer for Stage 1 requirement analyses (no sequential versioning)."""

    COLLECTION_NAME = "requirement_analyses"

    #: Fields the caller is expected to provide on :meth:`insert`.
    REQUIRED_FIELDS = ("project_id", "link_hash", "analysis")

    def __init__(self) -> None:
        self._indexes_ready = False

    @property
    def collection(self):
        """Obtiene la colección de forma dinámica asegurando que la DB ya inició."""
        return get_database()[self.COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        """Create the indexes declared by plan §6.1 if they don't exist yet.

        - ``(project_id ASC, created_at DESC)`` serves ``get_latest_by_project_id``
          so the newest-document lookup is an index seek instead of a scan+sort.
        - ``(link_hash)`` serves lookups performed before the project ``_id`` is
          known (the Telegram/scraping layer keys projects by ``link_hash``).
        """
        if self._indexes_ready:
            return
        await self.collection.create_index(
            [("project_id", ASCENDING), ("created_at", DESCENDING)],
            name="project_id_created_at_desc",
        )
        await self.collection.create_index(
            [("link_hash", ASCENDING)], name="link_hash_asc"
        )
        self._indexes_ready = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _as_int(value: Any, field: str) -> int:
        """Coerce *value* to ``int`` or raise ``ValueError`` naming *field``.

        ``maturity_threshold_used`` must be stored as a BSON int (not a float or
        a stringified number) so the persisted threshold stays comparable with
        ``MATURITY_THRESHOLD`` at review time (TASK017).
        """
        if isinstance(value, bool) or value is None:
            raise ValueError(
                f"{field} must be an int, got {type(value).__name__}: {value!r}"
            )
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                pass
        raise ValueError(
            f"{field} must be an int, got {type(value).__name__}: {value!r}"
        )

    @classmethod
    def _normalise(cls, document: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the incoming payload and return the document to persist.

        Unknown extra keys are dropped rather than rejected: the caller may pass
        the whole accumulated pipeline context and this repository owns only the
        Stage 1 envelope.
        """
        if not isinstance(document, dict) or not document:
            raise ValueError(
                f"document must be a non-empty dict, got "
                f"{type(document).__name__}: {document!r}"
            )

        missing = [f for f in cls.REQUIRED_FIELDS if not document.get(f)]
        if missing:
            raise ValueError(
                f"document is missing required field(s): {', '.join(missing)}"
            )

        analysis = document["analysis"]
        if not isinstance(analysis, dict) or not analysis:
            raise ValueError(
                f"analysis must be a non-empty dict (the full nested Stage 1 "
                f"object: maturity_score, maturity_reason, entities, gaps, "
                f"branch), got {type(analysis).__name__}: {analysis!r}"
            )

        model_used = document.get("model_used")
        if not isinstance(model_used, str) or not model_used.strip():
            raise ValueError(
                f"model_used must be a non-empty str, got {model_used!r}"
            )

        created_at = document.get("created_at")
        if created_at is None:
            created_at = datetime.now(timezone.utc)
        elif not isinstance(created_at, datetime):
            raise ValueError(
                f"created_at must be a datetime or None, got "
                f"{type(created_at).__name__}: {created_at!r}"
            )

        return {
            "project_id": str(document["project_id"]),
            "link_hash": str(document["link_hash"]),
            "analysis": analysis,
            "maturity_threshold_used": cls._as_int(
                document.get("maturity_threshold_used"), "maturity_threshold_used"
            ),
            "model_used": model_used,
            # Indicacion adicional usada al generar (traza de auditoria).
            "extra_info": document.get("extra_info", "") or "",
            "created_at": created_at,
        }

    # ------------------------------------------------------------------
    # Insert
    # ------------------------------------------------------------------

    async def insert(self, document: Dict[str, Any]) -> str:
        """Persist one Stage 1 analysis document.

        Args:
            document: mapping with ``project_id``, ``link_hash``, ``analysis``
                (the full nested Stage 1 object), ``maturity_threshold_used``,
                ``model_used`` and an optional ``created_at`` (UTC ``datetime``;
                defaults to now).

        Returns:
            String representation of the inserted document's ``_id``.

        Raises:
            ValueError: if required fields are missing or mistyped.  Failures
                are raised instead of logged-and-ignored so the pipeline cannot
                silently deliver a proposal whose analysis was never persisted.
        """
        await self.ensure_indexes()
        doc = self._normalise(document)

        result = await self.collection.insert_one(doc)
        inserted_id = str(result.inserted_id)
        logger.info(
            f"Inserted requirement analysis (id={inserted_id}) for "
            f"project_id={doc['project_id']} "
            f"(score={doc['analysis'].get('maturity_score')}, "
            f"branch={doc['analysis'].get('branch')}, "
            f"model={doc['model_used']})"
        )
        return inserted_id

    # ------------------------------------------------------------------
    # Query – latest analysis
    # ------------------------------------------------------------------

    async def get_latest_by_project_id(
        self, project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent analysis for *project_id*, or ``None``.

        "Most recent" is decided exclusively by ``created_at`` DESC — there is no
        version counter to consult (plan §6.1).  ``_id`` is stringified so the
        caller can serialise the document without a custom encoder.
        """
        await self.ensure_indexes()
        doc = await self.collection.find_one(
            {"project_id": str(project_id)},
            sort=[("created_at", DESCENDING)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
