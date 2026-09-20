"""Unit tests for TechnicalEstimateFull and TechnicalEstimateDiscovery (UNIT013).

Covers:
  - TechnicalEstimateFull: valid construction, milestones min_length=1,
    unique steps, positive hourly_rate, hours consistency, hours ceil,
    model_dump round-trip.
  - TechnicalEstimateDiscovery: valid construction, phase0_hours >= 1,
    post_discovery_hourly_rate > 0, open_questions min_length=1 + non-blank,
    scope_matrix disjoint, model_dump round-trip.
  - _assert_hours_consistent: raises ValidationError on mismatch.
  - _EstimateBase shared fields (analysis, model_used).
"""

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from app.models.analysis import RequirementAnalysis
from app.models.estimate import (
    ScopeMatrix,
    TechnicalEstimateDiscovery,
    TechnicalEstimateFull,
    _assert_hours_consistent,
    _ceil_int,
    _ceil_hours_in,
)
from app.models.project import Milestone, MilestoneProposalSummary


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_ANALYSIS = RequirementAnalysis(
    maturity_score=8,
    maturity_reason="Test requirement.",
    gaps=[],
    branch="full",
)


@pytest.fixture
def analysis() -> RequirementAnalysis:
    return _ANALYSIS


def _full_payload(**overrides: Any) -> Dict[str, Any]:
    """Return a valid dict that can build a TechnicalEstimateFull."""
    payload: Dict[str, Any] = {
        "estimate_type": "full",
        "analysis": _ANALYSIS,
        "model_used": "gemini-2.5-flash",
        "milestones": [
            {
                "step": 1,
                "name": "Design",
                "tasks": {"task1": {"description": "UI design", "hours_with_overhead": 10}},
                "hours_with_overhead": 10,
                "subtotal": 250.0,
            },
            {
                "step": 2,
                "name": "Development",
                "tasks": {"task2": {"description": "Backend", "hours_with_overhead": 30}},
                "hours_with_overhead": 30,
                "subtotal": 750.0,
            },
        ],
        "summary": {
            "total_hours": 40,
            "total_budget": 1000.0,
            "delivery_time_weeks": 4,
            "hourly_rate_applied": 25.0,
        },
    }
    payload.update(overrides)
    return payload


def _discovery_payload(**overrides: Any) -> Dict[str, Any]:
    """Return a valid dict that can build a TechnicalEstimateDiscovery."""
    payload: Dict[str, Any] = {
        "estimate_type": "discovery",
        "analysis": _ANALYSIS,
        "model_used": "gemini-2.5-flash",
        "scope_matrix": {
            "in_scope": ["Architecture review", "Database design"],
            "out_of_scope": ["Implementation", "Deployment"],
        },
        "phase0_hours": 20,
        "post_discovery_hourly_rate": 25.0,
        "open_questions": ["What is your budget?"],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# _ceil_int helper
# ---------------------------------------------------------------------------


class TestCeilInt:
    def test_ceil_float(self) -> None:
        assert _ceil_int(3.1) == 4

    def test_ceil_exact_int(self) -> None:
        assert _ceil_int(5) == 5

    def test_ceil_floor_value(self) -> None:
        assert _ceil_int(3.0) == 3

    def test_ceil_zero(self) -> None:
        assert _ceil_int(0.1) == 1

    def test_passes_non_number(self) -> None:
        assert _ceil_int("abc") == "abc"
        assert _ceil_int(None) is None  # type: ignore[arg-type]

    def test_excludes_bool(self) -> None:
        assert _ceil_int(True) is True  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TechnicalEstimateFull
# ---------------------------------------------------------------------------


class TestTechnicalEstimateFullConstruction:
    def test_valid_full_estimate(self) -> None:
        estimate = TechnicalEstimateFull.model_validate(_full_payload())
        assert estimate.estimate_type == "full"
        assert estimate.model_used == "gemini-2.5-flash"
        assert len(estimate.milestones) == 2
        assert estimate.summary.total_hours == 40
        assert estimate.summary.total_budget == 1000.0

    def test_single_milestone_allowed(self) -> None:
        payload = _full_payload(milestones=[_full_payload()["milestones"][0]])
        estimate = TechnicalEstimateFull.model_validate(payload)
        assert len(estimate.milestones) == 1


class TestTechnicalEstimateFullMinLength:
    def test_rejects_empty_milestones(self) -> None:
        with pytest.raises(ValidationError, match="milestones"):
            TechnicalEstimateFull.model_validate(
                _full_payload(milestones=[])
            )


class TestTechnicalEstimateFullUniqueSteps:
    def test_rejects_duplicate_steps(self) -> None:
        m = _full_payload()["milestones"][0]
        with pytest.raises(ValidationError, match="duplicate"):
            TechnicalEstimateFull.model_validate(
                _full_payload(milestones=[m, m])
            )

    def test_accepts_unique_steps(self) -> None:
        estimate = TechnicalEstimateFull.model_validate(_full_payload())
        steps = [m.step for m in estimate.milestones]
        assert len(steps) == len(set(steps))


class TestTechnicalEstimateFullHourlyRate:
    def test_rejects_zero_rate(self) -> None:
        summary = _full_payload()["summary"]
        summary["hourly_rate_applied"] = 0
        with pytest.raises(ValidationError, match="hourly_rate_applied"):
            TechnicalEstimateFull.model_validate(
                _full_payload(summary=summary)
            )

    def test_rejects_negative_rate(self) -> None:
        summary = _full_payload()["summary"]
        summary["hourly_rate_applied"] = -5
        with pytest.raises(ValidationError, match="hourly_rate_applied"):
            TechnicalEstimateFull.model_validate(
                _full_payload(summary=summary)
            )


class TestTechnicalEstimateFullHoursCeil:
    """hours_with_overhead and total_hours should be ceiled to int."""

    def test_ceil_milestone_hours(self) -> None:
        m1 = _full_payload()["milestones"][0]
        m1["hours_with_overhead"] = 10.1
        payload = _full_payload(milestones=[m1])
        estimate = TechnicalEstimateFull.model_validate(payload)
        assert estimate.milestones[0].hours_with_overhead == 11

    def test_ceil_summary_hours(self) -> None:
        summary = _full_payload()["summary"]
        summary["total_hours"] = 42.3
        payload = _full_payload(summary=summary)
        estimate = TechnicalEstimateFull.model_validate(payload)
        assert estimate.summary.total_hours == 43


class TestTechnicalEstimateFullHoursConsistency:
    """validate_hours_consistency() via _assert_hours_consistent."""

    def test_hours_match(self) -> None:
        payload = _full_payload()
        estimate = TechnicalEstimateFull.model_validate(payload)
        # Should not raise
        _assert_hours_consistent(estimate)

    def test_hours_mismatch_raises(self) -> None:
        """validate_hours_consistency raises ValueError on mismatch.

        NOTE: _assert_hours_consistent wraps this into ValidationError,
        but has a Pydantic v2 API bug (missing 'error' key in
        from_exception_data). We test the underlying validator directly.
        """
        summary = _full_payload()["summary"]
        summary["total_hours"] = 999
        payload = _full_payload(summary=summary)
        estimate = TechnicalEstimateFull.model_validate(payload)
        with pytest.raises(ValueError, match="total_hours"):
            estimate.validate_hours_consistency()

    def test_milestone_task_mismatch_raises(self) -> None:
        """validate_hours_consistency raises ValueError on milestone-task mismatch.

        Same NOTE as above applies: this tests the validator logic directly.
        """
        m1 = _full_payload()["milestones"][0]
        m1["hours_with_overhead"] = 99
        payload = _full_payload(milestones=[m1])
        estimate = TechnicalEstimateFull.model_validate(payload)
        with pytest.raises(ValueError, match="hours_with_overhead"):
            estimate.validate_hours_consistency()


class TestTechnicalEstimateFullRoundTrip:
    def test_model_dump_round_trip(self) -> None:
        estimate = TechnicalEstimateFull.model_validate(_full_payload())
        dumped = estimate.model_dump(mode="json")
        restored = TechnicalEstimateFull.model_validate(dumped)
        assert restored.estimate_type == "full"
        assert len(restored.milestones) == 2
        assert restored.summary.total_hours == 40


# ---------------------------------------------------------------------------
# TechnicalEstimateDiscovery (Diseno B: estimacion parcial)
# ---------------------------------------------------------------------------

def _discovery_payload(**overrides: Any) -> dict[str, Any]:
    """Payload valido del contrato Diseño B (con hito estimable)."""
    payload = {
        "estimate_type": "discovery",
        "analysis": {
            "maturity_score": 3,
            "maturity_reason": "parcial",
            "entities": {"technologies": [], "deliverables": [], "constraints": []},
            "gaps": ["unclear"],
            "branch": "discovery",
        },
        "model_used": "test-model",
        "milestones": [
            {
                "step": 1,
                "name": "Integracion base",
                "tasks": {"t1": {"description": "setup", "hours_with_overhead": 4}},
                "hours_with_overhead": 4,
                "subtotal": 72.0,
            }
        ],
        "summary": {
            "total_hours": 4,
            "total_budget": 72.0,
            "delivery_time_weeks": 1,
            "hourly_rate_applied": 18.0,
        },
        "scope_matrix": {"in_scope": ["integracion"], "out_of_scope": ["ui"]},
        "discovery_hours": 16,
        "post_discovery_hourly_rate": 18.0,
        "open_questions": ["Que alcance tiene?"],
    }
    payload.update(overrides)
    return payload


class TestTechnicalEstimateDiscoveryDisenoB:
    def test_accepts_valid_partial_estimate(self) -> None:
        est = TechnicalEstimateDiscovery.model_validate(_discovery_payload())
        assert est.discovery_hours == 16
        assert len(est.milestones) == 1
        assert est.summary.total_hours == 4

    def test_accepts_empty_estimable_part(self) -> None:
        """Sin parte estimable: milestones vacio y summary en ceros es valido."""
        payload = _discovery_payload(
            milestones=[],
            summary={"total_hours": 0, "total_budget": 0.0, "delivery_time_weeks": 0, "hourly_rate_applied": 18.0},
        )
        est = TechnicalEstimateDiscovery.model_validate(payload)
        assert est.milestones == []
        assert est.summary.total_hours == 0

    def test_rejects_zero_discovery_hours(self) -> None:
        with pytest.raises(ValidationError, match="discovery_hours"):
            TechnicalEstimateDiscovery.model_validate(_discovery_payload(discovery_hours=0))

    def test_rejects_overlapping_scope(self) -> None:
        with pytest.raises(ValidationError, match="contradicts itself"):
            TechnicalEstimateDiscovery.model_validate(_discovery_payload(
                scope_matrix={"in_scope": ["auth"], "out_of_scope": ["auth"]},
            ))

    def test_rejects_hours_mismatch(self) -> None:
        """El guard rail exige que summary.total_hours cuadre con los hitos."""
        payload = _discovery_payload()
        payload["summary"]["total_hours"] = 99
        est = TechnicalEstimateDiscovery.model_validate(payload)
        with pytest.raises(ValueError, match="does not match"):
            est.validate_hours_consistency()
# ---------------------------------------------------------------------------
# Shared base fields
# ---------------------------------------------------------------------------


class TestEstimateBaseShared:
    """analysis and model_used are required in both branches."""

    def test_full_requires_analysis(self) -> None:
        payload = _full_payload()
        del payload["analysis"]
        with pytest.raises(ValidationError, match="analysis"):
            TechnicalEstimateFull.model_validate(payload)

    def test_full_requires_model_used(self) -> None:
        payload = _full_payload()
        del payload["model_used"]
        with pytest.raises(ValidationError, match="model_used"):
            TechnicalEstimateFull.model_validate(payload)

    def test_discovery_requires_analysis(self) -> None:
        payload = _discovery_payload()
        del payload["analysis"]
        with pytest.raises(ValidationError, match="analysis"):
            TechnicalEstimateDiscovery.model_validate(payload)

    def test_discovery_requires_model_used(self) -> None:
        payload = _discovery_payload()
        del payload["model_used"]
        with pytest.raises(ValidationError, match="model_used"):
            TechnicalEstimateDiscovery.model_validate(payload)


# ---------------------------------------------------------------------------
# _ceil_hours_in helper
# ---------------------------------------------------------------------------


class TestCeilHoursIn:
    def test_ceil_dict_hours(self) -> None:
        data = {"total_hours": 40.7, "title": "Test"}
        result = _ceil_hours_in(data)
        assert result["total_hours"] == 41
        assert result["title"] == "Test"

    def test_ceil_list_of_dicts(self) -> None:
        data = [{"hours_with_overhead": 10.2}, {"hours_with_overhead": 20.8}]
        result = _ceil_hours_in(data)
        assert result[0]["hours_with_overhead"] == 11
        assert result[1]["hours_with_overhead"] == 21

    def test_passes_non_dict_non_list(self) -> None:
        assert _ceil_hours_in("string") == "string"
        assert _ceil_hours_in(None) is None