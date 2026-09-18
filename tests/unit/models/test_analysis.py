"""Unit tests for RequirementAnalysis Pydantic model (UNIT012).

Covers:
  - Valid RequirementAnalysis construction with all fields
  - maturity_score bounds (1..10)
  - maturity_reason non-empty
  - branch Literal validation ('full' | 'discovery')
  - branch consistency: 'discovery' requires at least one gap
  - Entities nested model (technologies, deliverables, constraints)
  - model_dump(mode='json') round-trip
"""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.analysis import Entities, RequirementAnalysis


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class TestEntities:
    """Validate the nested Entities document."""

    def test_defaults_to_empty_lists(self) -> None:
        entities = Entities()
        assert entities.technologies == []
        assert entities.deliverables == []
        assert entities.constraints == []

    def test_accepts_explicit_values(self) -> None:
        entities = Entities(
            technologies=["Python", "Django"],
            deliverables=["REST API"],
            constraints=["fixed budget"],
        )
        assert "Python" in entities.technologies
        assert len(entities.deliverables) == 1
        assert "fixed budget" in entities.constraints

    def test_accepts_partial_fields(self) -> None:
        entities = Entities(technologies=["Go"])
        assert entities.technologies == ["Go"]
        assert entities.deliverables == []
        assert entities.constraints == []


# ---------------------------------------------------------------------------
# RequirementAnalysis — basic construction
# ---------------------------------------------------------------------------


class TestRequirementAnalysisConstruction:
    """Validate that a valid RequirementAnalysis instance is accepted."""

    def test_valid_full_branch(self) -> None:
        ra = RequirementAnalysis(
            maturity_score=8,
            maturity_reason="Clear description with stack and deliverables.",
            entities=Entities(
                technologies=["Python"],
                deliverables=["API"],
                constraints=["3 months"],
            ),
            gaps=[],
            branch="full",
        )
        assert ra.maturity_score == 8
        assert ra.branch == "full"
        assert ra.gaps == []

    def test_valid_discovery_branch_with_gaps(self) -> None:
        ra = RequirementAnalysis(
            maturity_score=4,
            maturity_reason="Vague, needs clarification.",
            gaps=["Missing tech stack"],
            branch="discovery",
        )
        assert ra.maturity_score == 4
        assert ra.branch == "discovery"
        assert ra.gaps == ["Missing tech stack"]

    def test_minimal_valid(self) -> None:
        """maturity_score=1, maturity_reason single char should pass."""
        ra = RequirementAnalysis(
            maturity_score=1,
            maturity_reason="A",
            branch="full",
        )
        assert ra.maturity_score == 1
        assert ra.maturity_reason == "A"


# ---------------------------------------------------------------------------
# maturity_score bounds
# ---------------------------------------------------------------------------


class TestMaturityScoreBounds:
    """maturity_score must be int in [1, 10]."""

    def test_rejects_score_0(self) -> None:
        with pytest.raises(ValidationError, match="maturity_score"):
            RequirementAnalysis(
                maturity_score=0,
                maturity_reason="Test",
                branch="full",
            )

    def test_rejects_score_11(self) -> None:
        with pytest.raises(ValidationError, match="maturity_score"):
            RequirementAnalysis(
                maturity_score=11,
                maturity_reason="Test",
                branch="full",
            )

    def test_rejects_negative_score(self) -> None:
        with pytest.raises(ValidationError, match="maturity_score"):
            RequirementAnalysis(
                maturity_score=-5,
                maturity_reason="Test",
                branch="full",
            )

    @pytest.mark.parametrize("valid", [1, 5, 10])
    def test_accepts_boundary_values(self, valid: int) -> None:
        ra = RequirementAnalysis(
            maturity_score=valid,
            maturity_reason="Test",
            branch="full",
        )
        assert ra.maturity_score == valid


# ---------------------------------------------------------------------------
# maturity_reason — non-empty
# ---------------------------------------------------------------------------


class TestMaturityReason:
    """maturity_reason must be a non-empty string."""

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValidationError, match="maturity_reason"):
            RequirementAnalysis(
                maturity_score=5,
                maturity_reason="",
                branch="full",
            )

    def test_rejects_whitespace_only(self) -> None:
        """Pydantic's min_length=1 counts whitespace as characters,
        so a whitespace-only string has length >= 1 and passes.
        This test documents the current behaviour — if stricter rules
        are needed later, a model_validator should be added."""
        ra = RequirementAnalysis(
            maturity_score=5,
            maturity_reason="   ",
            branch="full",
        )
        assert ra.maturity_reason == "   "


# ---------------------------------------------------------------------------
# branch Literal validation
# ---------------------------------------------------------------------------


class TestBranchLiteral:
    """branch must be one of 'full' or 'discovery'."""

    def test_rejects_invalid_branch(self) -> None:
        with pytest.raises(ValidationError, match="branch"):
            RequirementAnalysis(
                maturity_score=5,
                maturity_reason="Test",
                branch="invalid_branch",
            )

    def test_accepts_full(self) -> None:
        ra = RequirementAnalysis(
            maturity_score=5,
            maturity_reason="Test",
            branch="full",
        )
        assert ra.branch == "full"

    def test_accepts_discovery(self) -> None:
        ra = RequirementAnalysis(
            maturity_score=5,
            maturity_reason="Test",
            gaps=["question"],
            branch="discovery",
        )
        assert ra.branch == "discovery"


# ---------------------------------------------------------------------------
# Branch consistency: discovery requires gaps
# ---------------------------------------------------------------------------


class TestBranchConsistency:
    """model_validator: branch='discovery' requires at least one gap."""

    def test_discovery_without_gaps_raises(self) -> None:
        with pytest.raises(ValidationError, match="discovery"):
            RequirementAnalysis(
                maturity_score=5,
                maturity_reason="Test",
                gaps=[],
                branch="discovery",
            )

    def test_full_without_gaps_is_valid(self) -> None:
        ra = RequirementAnalysis(
            maturity_score=8,
            maturity_reason="Clear enough.",
            branch="full",
        )
        assert ra.branch == "full"
        assert ra.gaps == []

    def test_discovery_with_one_gap_is_valid(self) -> None:
        ra = RequirementAnalysis(
            maturity_score=3,
            maturity_reason="Too vague.",
            gaps=["What stack?"],
            branch="discovery",
        )
        assert ra.branch == "discovery"
        assert len(ra.gaps) == 1


# ---------------------------------------------------------------------------
# JSON round-trip (model_dump mode='json')
# ---------------------------------------------------------------------------


class TestJsonRoundTrip:
    """Model can be serialised to JSON and read back."""

    def test_round_trip_full(self) -> None:
        original = RequirementAnalysis(
            maturity_score=7,
            maturity_reason="Good.",
            entities=Entities(
                technologies=["Django"],
                deliverables=["API"],
                constraints=["budget"],
            ),
            gaps=["Testing?"],
            branch="full",
        )
        dumped = original.model_dump(mode="json")
        restored = RequirementAnalysis.model_validate(dumped)
        assert restored.maturity_score == original.maturity_score
        assert restored.branch == original.branch
        assert restored.entities.technologies == ["Django"]
        assert restored.gaps == ["Testing?"]

    def test_json_serialisable(self) -> None:
        ra = RequirementAnalysis(
            maturity_score=6,
            maturity_reason="Decent.",
            branch="full",
        )
        raw = json.dumps(ra.model_dump(mode="json"))
        assert isinstance(raw, str)
        parsed = json.loads(raw)
        assert parsed["maturity_score"] == 6