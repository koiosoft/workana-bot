"""
Repository for the ``technical_estimates`` collection (Stage 2 / Etapa 2A-2B).

Every ``project_fixed`` run that reaches Stage 2 stores the accumulated
Etapa 1 + Etapa 2 JSON produced by ``estimate-full.j2`` (branch ``full``) or
``estimate-discovery.j2`` (branch ``discovery``) here: one document per
estimate, never mutated afterwards.

Lookup rule (plan §6.2 — "Sin versionado secuencial"): there is **no**
``version_number`` field and no auto-increment logic.  The effective estimate
for a project is always the most recently created document, i.e. the lookup is
strictly ``created_at`` DESC.  That is why only two operations exist here:
``insert`` (append) and ``get_latest_by_project_id`` (read the newest).

Document shape (plan §6.2).  The envelope is owned by this module; the payload
is owned by the Pydantic contract in ``app.models.estimate``:

    {
      "_id": ObjectId,
      "project_id": str,
      "link_hash": str,
      "estimate_type": "full" | "discovery",
      "analysis": { ... },              # nested Stage 1 subdocument (§6.2)
      # --- branch 'full' (2A) ---
      "milestones": [ {step, name, tasks, hours_with_overhead, subtotal} ],
      "summary": { total_hours, total_budget, delivery_time_weeks,
                   hourly_rate_applied },
      # --- branch 'discovery' (2B, Diseno B: estimacion parcial) ---
      "milestones": [ {step, name, tasks, hours_with_overhead, subtotal} ],
      "summary": { total_hours, total_budget, delivery_time_weeks,
                   hourly_rate_applied },
      "scope_matrix": { in_scope: [], out_of_scope: [] },
      "discovery_hours": int,
      "post_discovery_hourly_rate": float,
      "open_questions": [ str ],
      # --- common ---
      "model_used": str,
      "created_at": ISODate
    }

The two branches are mutually exclusive on ``estimate_type``: a ``full``
document never carries ``scope_matrix``/``discovery_hours``/…, and a
``discovery`` document (Diseno B) carries BOTH the estimable part
(``milestones``/``summary``) and the discovery fields.  That exclusivity is
``extra="forbid"`` contracts rather than with an if/else list of key names, so
the persisted shape cannot drift from ``TechnicalEstimateFull`` /
``TechnicalEstimateDiscovery`` without one of the two models changing first.

Idempotency/retry note (plan §10.4, INT006): when Stage 3 fails after Stages
1-2 succeeded, the retry reads the estimate back with
:meth:`get_latest_by_project_id` and feeds it to Stage 3 again instead of
re-billing two STANDARD calls.  Because the stored payload is a verbatim model
dump, reading it back and validating it again is loss-free.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

from loguru import logger
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from app.models.analysis import RequirementAnalysis
from app.models.estimate import ScopeMatrix, TechnicalEstimateFull
from app.models.project import Milestone, MilestoneProposalSummary

from .mongo import get_database


#: Values accepted by ``estimate_type`` — mirrors the ``Literal`` of the two
#: branch models and of ``RequirementAnalysis.branch``.
EstimateType = Literal["full", "discovery"]

_estimate_type_adapter: TypeAdapter = TypeAdapter(EstimateType)


class _EstimateEnvelope(BaseModel):
    """Fields every estimate document carries besides the branch payload.

    Declared private to this module on purpose: it is a *storage* contract, not
    part of the LLM output contract published by ``app.models.estimate``.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1)
    link_hash: str = Field(..., min_length=1)
    analysis: RequirementAnalysis
    model_used: str = Field(..., min_length=1)
    # Indicacion adicional usada al generar (traza de auditoria). Opcional:
    # los documentos previos no la tienen.
    extra_info: str = ""
    created_at: datetime


class _FullContract(_EstimateEnvelope):
    """Persistable form of :class:`app.models.estimate.TechnicalEstimateFull`.

    ``milestones`` / ``summary`` / ``estimate_type`` are re-declared with the
    same types the Stage 2 model uses (imported, not duplicated — decision #6 /
    plan §9.2), so the numbers written here are the numbers Stage 3 may copy
    verbatim into ``MilestoneProposal``.
    """

    estimate_type: Literal["full"]
    milestones: List[Milestone] = Field(..., min_length=1)
    summary: MilestoneProposalSummary


class _DiscoveryContract(_EstimateEnvelope):
    """Persistable form of :class:`app.models.estimate.TechnicalEstimateDiscovery`.

    Diseno B: lleva la parte estimable (`milestones` + `summary`) ademas de la
    parte de discovery (`scope_matrix`, `discovery_hours`, tarifa, preguntas).
    """

    estimate_type: Literal["discovery"]
    milestones: List[Milestone] = Field(default_factory=list)
    summary: MilestoneProposalSummary
    scope_matrix: ScopeMatrix = Field(default_factory=ScopeMatrix)
    discovery_hours: int = Field(..., ge=1)
    post_discovery_hourly_rate: float = Field(..., gt=0)
    open_questions: List[str] = Field(..., min_length=1)


#: ``extra="forbid"`` on both sides makes the union self-exclusive: a payload
#: carrying keys from the wrong branch fails instead of silently persisting a
#: hybrid document.
_contract_adapter: TypeAdapter = TypeAdapter(Union[_FullContract, _DiscoveryContract])


class TechnicalEstimatesRepository:
    """Data-access layer for Stage 2 technical estimates (no sequential versioning)."""

    COLLECTION_NAME = "technical_estimates"

    #: Fields the caller is expected to provide on :meth:`insert`.  Everything
    #: else is either branch-specific (validated by the contracts above) or
    #: defaulted (``created_at``).
    REQUIRED_FIELDS = ("project_id", "link_hash", "estimate_type", "analysis")

    def __init__(self) -> None:
        self._indexes_ready = False

    @property
    def collection(self):
        """Obtiene la colección de forma dinámica asegurando que la DB ya inició."""
        return get_database()[self.COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        """Create the indexes declared by plan §6.2 if they don't exist yet.

        - ``(project_id ASC, created_at DESC)`` serves ``get_latest_by_project_id``
          so the newest-document lookup is an index seek instead of a scan+sort.
        - ``(link_hash)`` serves lookups performed before the project ``_id`` is
          known (the Telegram/scraping layer keys projects by ``link_hash``).

        Both are idempotent server-side, and ``create_indexes`` sends them in a
        single round trip.
        """
        if self._indexes_ready:
            return
        await self.collection.create_indexes(
            [
                IndexModel(
                    [("project_id", ASCENDING), ("created_at", DESCENDING)],
                    name="project_id_created_at_desc",
                ),
                IndexModel(
                    [("link_hash", ASCENDING)], name="link_hash_asc"
                ),
            ]
        )
        self._indexes_ready = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(document: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the incoming payload and return the document to persist.

        Two stages, mirroring how the pipeline itself validates:

        1. Cheap structural guards over the *envelope* (``project_id``,
           ``link_hash``, ``estimate_type``, ``model_used``, ``created_at``) so
           the error message names the offending field instead of dumping a
           Pydantic tree about a missing ``project_id``.
        2. Branch validation through :data:`_contract_adapter`, which enforces
           §6.2's shape for the branch that was actually taken.

        Unknown extra keys are dropped rather than rejected: the caller may pass
        the whole accumulated pipeline context (including the Stage 1 audit
        fields such as ``maturity_threshold_used``) and this repository owns
        only the Stage 2 envelope + payload.
        """
        if not isinstance(document, dict) or not document:
            raise ValueError(
                f"document must be a non-empty dict, got "
                f"{type(document).__name__}: {document!r}"
            )

        missing = [f for f in TechnicalEstimatesRepository.REQUIRED_FIELDS if not document.get(f)]
        if missing:
            raise ValueError(
                f"document is missing required field(s): {', '.join(missing)}"
            )

        try:
            estimate_type = _estimate_type_adapter.validate_python(
                document["estimate_type"]
            )
        except ValidationError as exc:
            raise ValueError(
                f"estimate_type must be 'full' or 'discovery', got "
                f"{document['estimate_type']!r}"
            ) from exc

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

        payload = {
            "project_id": str(document["project_id"]),
            "link_hash": str(document["link_hash"]),
            "estimate_type": estimate_type,
            "analysis": document["analysis"],
            "model_used": model_used,
            "extra_info": document.get("extra_info", "") or "",
            "created_at": created_at,
        }
        # Only the branch keys present in the input participate in validation;
        # absent ones surface as `missing` errors naming exactly that field.
        for key in _BRANCH_FIELDS[estimate_type]:
            if key in document:
                payload[key] = document[key]

        try:
            validated = _contract_adapter.validate_python(payload)
        except ValidationError as exc:
            raise ValueError(
                f"technical estimate payload for estimate_type="
                f"{estimate_type!r} is invalid: {_describe(exc)}"
            ) from exc

        return validated.model_dump()

    # ------------------------------------------------------------------
    # Insert
    # ------------------------------------------------------------------

    async def insert(self, document: Dict[str, Any]) -> str:
        """Persist one Stage 2 estimate document.

        Args:
            document: mapping with ``project_id``, ``link_hash``,
                ``estimate_type`` ('full' | 'discovery'), ``analysis`` (the full
                nested Stage 1 object), ``model_used`` and an optional
                ``created_at`` (UTC ``datetime``; defaults to now), plus the
                branch payload: ``milestones`` + ``summary`` for 'full'; for
                'discovery' (Diseno B) ``milestones`` + ``summary`` (parte
                estimable, puede ir vacia) + ``scope_matrix`` +
                ``discovery_hours`` + ``post_discovery_hourly_rate`` +
                ``open_questions``.

        Returns:
            String representation of the inserted document's ``_id``.

        Raises:
            ValueError: if required fields are missing or mistyped, if
                ``estimate_type`` contradicts the supplied branch payload, or if
                the Stage 2 consistency checks fail (e.g. ``summary.total_hours``
                disagreeing with the milestone hours).  Failures are raised
                instead of logged-and-ignored so the pipeline cannot silently
                deliver a proposal whose estimate was never persisted — that
                record is what makes an Etapa 3 retry skip Etapas 1-2 (§10.4).
        """
        await self.ensure_indexes()
        doc = self._normalise(document)

        result = await self.collection.insert_one(doc)
        inserted_id = str(result.inserted_id)
        logger.info(
            f"Inserted technical estimate (id={inserted_id}) for "
            f"project_id={doc['project_id']} "
            f"(estimate_type={doc['estimate_type']}, "
            f"branch={doc['analysis'].get('branch')}, "
            f"model={doc['model_used']})"
        )
        return inserted_id

    # ------------------------------------------------------------------
    # Query – latest estimate
    # ------------------------------------------------------------------

    async def get_latest_by_project_id(
        self, project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent estimate for *project_id*, or ``None``.

        "Most recent" is decided exclusively by ``created_at`` DESC — there is no
        version counter to consult (plan §6.2).  ``_id`` is stringified so the
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


#: Branch → payload keys, kept next to the contracts that declare them so a
#: future field addition has exactly one place to change.
_BRANCH_FIELDS: Dict[str, tuple] = {
    "full": ("milestones", "summary"),
    "discovery": (
        "milestones",
        "summary",
        "scope_matrix",
        "discovery_hours",
        "post_discovery_hourly_rate",
        "open_questions",
    ),
}


def _describe(exc: ValidationError) -> str:
    """Render a ValidationError as ``field: message`` pairs (root field only).

    A Pydantic union failure reports one error per candidate branch, which is
    noise for a log line; the caller already knows the branch it asked for, so
    keep the distinct messages and drop the duplicates.
    """
    seen: List[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"] if part != "union")
        text = f"{loc or '<root>'}: {err['msg']}"
        if text not in seen:
            seen.append(text)
    return "; ".join(seen) or "invalid payload"
