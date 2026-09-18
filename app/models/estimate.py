"""Pydantic models for Stage 2 (technical estimation) LLM output validation.

These are the second gatekeeper of the staged proposal pipeline (plan section
7.3, "validacion estricta de salidas JSON").  The Stage 2 `estimate_technical`
response is parsed and immediately run through `TechnicalEstimateFull.model_validate`
or `TechnicalEstimateDiscovery.model_validate` (routed by `analysis['branch']`),
and a `pydantic.ValidationError` there must be converted into a `PipelineError`
so the pipeline stops *before* the PREMIUM Stage 3 write is billed.

Which class applies is decided by the caller, not by this module: the two
branches come from two different prompts (`s2-estimation/estimate-full.j2` vs
`s2-estimation/estimate-discovery.j2`) and therefore from two different
provider calls, so a discriminated union over `estimate_type` would buy nothing
here — see the scope note in `TechnicalEstimateFull` below.

Schema source: plan section 6.2, `technical_estimates` document.  The persisted
document also carries `_id`, `project_id`, `link_hash`, `created_at` and (for
the 'full' branch bookkeeping) the accumulated Stage 1 payload; those envelope
fields belong to `TechnicalEstimatesRepository` (TASK005/TASK006), not to the
LLM output contract validated here.

Reuse policy (decision #6 / plan section 9.2): `Milestone`, `Task` and
`MilestoneProposalSummary` are imported from `app.models.project` rather than
redefined, so the numbers the dashboard consumes cannot drift between the
intermediate estimate and the final `MilestoneProposal`.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.analysis import RequirementAnalysis
from app.models.project import (
    Milestone,
    MilestoneProposalSummary,
    Task,
)

__all__ = [
    "ScopeMatrix",
    "TechnicalEstimateFull",
    "TechnicalEstimateDiscovery",
]

_T = TypeVar("_T")

# The Workana contract only ever renders integer hours (the prompt asks the
# model for `integer` and tells it to apply `ceiling`), but `Task` /
# `Milestone` / `MilestoneProposalSummary` declare `float` because that is what
# `projects.proposal` already stores.  Coerce on the way in instead of narrowing
# those shared models — narrowing them would silently reject legacy documents
# that legitimately hold e.g. 12.5.
_HOURS_FIELDS = ("hours_with_overhead", "total_hours")


def _ceil_int(value: Any) -> Any:
    """Ceil a numeric hours value to `int`; leave non-numbers for Pydantic.

    Returns the input untouched when it is not an int/float (a string, `None`,
    a dict) so the declared field type still produces the canonical
    `int_parsing` / `int_type` error instead of a bespoke one.  `bool` is
    excluded on purpose: `True` is an `int` subclass in Python but is not a
    quantity of hours.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    from math import ceil

    return int(ceil(value))


class ScopeMatrix(BaseModel):
    """Plan §6.2 `scope_matrix`: what Stage 2B commits to and what it excludes.

    Two parallel string lists produced by `estimate-discovery.j2`.  An empty
    list is meaningful (nothing declared in scope yet is a real discovery
    outcome), so no `min_length` is imposed on either side; the *model* level
    check that the two branches are not conflated lives in
    `TechnicalEstimateDiscovery.validate_scope_disjoint`.
    """

    model_config = ConfigDict(populate_by_name=True)

    in_scope: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)


class _EstimateBase(BaseModel):
    """Fields shared by both Stage 2 branches.

    Deliberately *not* exported as part of the public contract: it exists so the
    two branch models declare `analysis`, `model_used` and the hours coercion
    once.  `estimate_type` is declared in each subclass with its own `Literal`,
    never here — a base declaring it would let a subclass forget to override and
    still validate.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Accumulated Stage 1 output, nested verbatim (§6.2 "Subdocumento anidado:
    # analysis de la Etapa 1").  Required: the estimate is meaningless without
    # the maturity score and gaps that produced it, and persisting it here is
    # what makes a retry idempotent (INT006).
    analysis: RequirementAnalysis

    # Audit trail (§6.3 "cada documento lleva created_at e model_used").
    model_used: str = Field(..., min_length=1)

    @field_validator(*_HOURS_FIELDS, mode="before", check_fields=False)
    @classmethod
    def _coerce_hours(cls, value: Any) -> Any:
        return _ceil_int(value)


class TechnicalEstimateFull(_EstimateBase):
    """Validated Stage 2A output (`branch == 'full'`): milestones + summary.

    Pure engineering numbers and structure — no commercial prose.  Stage 3
    (`write-proposal.j2`, TASK010) copies `milestones` and `summary` verbatim
    into the final `MilestoneProposal`, which is exactly why these two fields
    are typed with the classes imported from `app.models.project`: the type
    check performed on the intermediate estimate *is* the type check performed
    on the delivered proposal.

    Cross-field rules enforced beyond the declared types:
      - at least one milestone (an empty plan has nothing for Stage 3 to sell);
      - milestone steps unique (duplicate `step` values make the dashboard's
        ordering ambiguous);
      - `summary.total_hours` equals the sum of the milestone hours within a
        0.5-hour rounding tolerance.
    """

    estimate_type: Literal["full"]

    milestones: List[Milestone] = Field(..., min_length=1)
    summary: MilestoneProposalSummary

    @field_validator("milestones", mode="before")
    @classmethod
    def _coerce_milestone_hours(cls, value: Any) -> Any:
        return _ceil_hours_in(value)

    @field_validator("summary", mode="before")
    @classmethod
    def _coerce_summary_hours(cls, value: Any) -> Any:
        return _ceil_hours_in(value)

    @field_validator("milestones")
    @classmethod
    def validate_unique_steps(cls, milestones: List[Milestone]) -> List[Milestone]:
        steps = [m.step for m in milestones]
        if len(set(steps)) != len(steps):
            duplicates = sorted({s for s in steps if steps.count(s) > 1})
            raise ValueError(
                f"milestones carry duplicate 'step' values {duplicates}; each "
                "hitos must be uniquely numbered for the dashboard to order them"
            )
        return milestones

    @field_validator("summary")
    @classmethod
    def validate_positive_rate(cls, summary: MilestoneProposalSummary) -> MilestoneProposalSummary:
        if summary.hourly_rate_applied <= 0:
            raise ValueError(
                "summary.hourly_rate_applied must be greater than 0; a zero or "
                "negative rate means the estimate was not priced"
            )
        return summary

    def validate_hours_consistency(self) -> None:
        """Check `summary.total_hours` against the milestone hours.

        Runs as an explicit post-load step (see `_assert_hours_consistent`)
        rather than as an `after` model validator, so the rejection surfaces as
        a `pydantic.ValidationError` carrying the offending numbers — the
        adapters catch `ValidationError` and turn it into `PipelineError`, and
        a bare `ValueError` raised outside `model_validate` would escape that
        handler as an unclassified crash.
        """
        milestone_hours = sum(m.hours_with_overhead for m in self.milestones)
        task_hours = sum(
            t.hours_with_overhead for m in self.milestones for t in m.tasks.values()
        )
        total = self.summary.total_hours
        if abs(total - milestone_hours) > 0.5:
            raise ValueError(
                f"summary.total_hours ({total}) does not match the sum of the "
                f"milestone hours_with_overhead ({milestone_hours})"
            )
        # A milestone that disagrees with its own tasks is the classic symptom of
        # a model that recomputed the rollup but edited the tasks afterwards.
        for milestone in self.milestones:
            rollup = sum(t.hours_with_overhead for t in milestone.tasks.values())
            if abs(rollup - milestone.hours_with_overhead) > 0.5:
                raise ValueError(
                    f"milestone step {milestone.step} ({milestone.name!r}) reports "
                    f"hours_with_overhead={milestone.hours_with_overhead} but its "
                    f"tasks sum to {rollup}"
                )
        del task_hours  # documented above; only used for the message-free audit


class TechnicalEstimateDiscovery(_EstimateBase):
    """Validated Stage 2B output (`branch == 'discovery'`).

    Phase 0 is a paid discovery slice, not a project plan: it prices a bounded
    clarification phase and defers the rest, so there are no milestones and no
    budget.  The three numeric/list fields mirror `estimate-discovery.j2`
    (TASK009) one-to-one.

    Cross-field rules enforced beyond the declared types:
      - `phase0_hours` >= 1;
      - `post_discovery_hourly_rate` > 0;
      - at least one open question (Stage 2B exists to ask them);
      - `in_scope` and `out_of_scope` disjoint.
    """

    estimate_type: Literal["discovery"]

    scope_matrix: ScopeMatrix = Field(default_factory=ScopeMatrix)
    phase0_hours: int = Field(..., ge=1)
    post_discovery_hourly_rate: float = Field(..., gt=0)
    open_questions: List[str] = Field(..., min_length=1)

    @field_validator("open_questions")
    @classmethod
    def validate_open_questions_text(cls, questions: List[str]) -> List[str]:
        blank = [q for q in questions if not q.strip()]
        if blank:
            raise ValueError(
                "open_questions must not contain empty strings; "
                f"{len(blank)} entr(ies) are whitespace-only"
            )
        return questions

    @field_validator("scope_matrix")
    @classmethod
    def validate_scope_disjoint(cls, scope: ScopeMatrix) -> ScopeMatrix:
        overlap = {i.strip() for i in scope.in_scope} & {
            o.strip() for o in scope.out_of_scope
        }
        if overlap:
            raise ValueError(
                "scope_matrix contradicts itself: these items appear in both "
                f"in_scope and out_of_scope: {sorted(overlap)}"
            )
        return scope


def _ceil_hours_in(value: Any) -> Any:
    """Apply `_ceil_int` to the hour keys of a nested dict / list of dicts.

    Tolerates every shape it is not asked to fix: non-dict entries pass through
    untouched so the field's own type validation reports them.
    """
    if isinstance(value, dict):
        return {k: (_ceil_int(v) if k in _HOURS_FIELDS else v) for k, v in value.items()}
    if isinstance(value, list):
        return [_ceil_hours_in(item) for item in value]
    return value


def _assert_hours_consistent(model: _T) -> _T:
    """Post-load hook: run `validate_hours_consistency` under ValidationError."""
    check = getattr(model, "validate_hours_consistency", None)
    if callable(check):
        try:
            check()
        except Exception as exc:  # noqa: BLE001 - re-wrapped as ValidationError
            from pydantic import ValidationError

            errors: List[Dict[str, Any]] = [
                {
                    "type": "value_error",
                    "loc": ("summary", "total_hours"),
                    "msg": f"Value error, {exc}",
                    "input": None,
                }
            ]
            raise ValidationError.from_exception_data(
                type(model).__name__, errors  # type: ignore[arg-type]
            ) from exc
    return model
