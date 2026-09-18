"""Pydantic models for Stage 1 (requirement analysis) LLM output validation.

These models are the gatekeepers of the staged proposal pipeline (decision
"validacion estricta de salidas JSON", plan section 7.3): the Stage 1
`analyze-requirement` response is parsed and immediately run through
`RequirementAnalysis.model_validate`, and a `pydantic.ValidationError` there must
be converted into a `PipelineError` so the pipeline stops *before* any PREMIUM
model call is billed.

Schema source: plan section 6.1, `requirement_analyses.analysis` subdocument.
"""

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Entities(BaseModel):
    """Concrete entities extracted from the requirement description.

    Every list is a set of free-form strings produced by the STANDARD model:
      - technologies: stack items the requirement names or implies (Django, PostgreSQL)
      - deliverables: artifacts / outcomes expected (a documented REST API)
      - constraints: hard limits stated by the client (fixed budget, 3-month deadline)
    """

    model_config = ConfigDict(populate_by_name=True)

    technologies: List[str] = Field(default_factory=list)
    deliverables: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)


class RequirementAnalysis(BaseModel):
    """Validated Stage 1 output: maturity score + entities + gaps + branch decision.

    Validation rules:
      - maturity_score: int constrained to 1..10 inclusive (`ge`/`le`)
      - maturity_reason: str, non-empty (the justification text is required so an
        unexplained score can never pass the gate)
      - entities: nested `Entities` document
      - gaps: list of plain strings, each describing one void or uncertainty
      - branch: Literal['full', 'discovery'] — the Stage 2 routing decision
    """

    model_config = ConfigDict(populate_by_name=True)

    maturity_score: int = Field(..., ge=1, le=10)
    maturity_reason: str = Field(..., min_length=1)
    entities: Entities = Field(default_factory=Entities)
    gaps: List[str] = Field(default_factory=list)
    branch: Literal["full", "discovery"]

    @model_validator(mode="after")
    def validate_branch_consistency(self) -> "RequirementAnalysis":
        """Keep the two Stage 1 signals from contradicting each other.
        A 'discovery' branch exists precisely to resolve unknowns, so it must
        surface at least one gap for the Stage 2B clarification prompt.
        """
        if self.branch == "discovery" and not self.gaps:
            raise ValueError(
                "branch 'discovery' requires at least one entry in gaps "
                "(the discovery phase asks the client about them)"
            )
        return self
