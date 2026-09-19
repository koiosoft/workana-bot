"""Unit tests for the staged prompt templates (UNIT022).

Verifies the three staged prompt templates exist at their subfolder paths,
extend ``base/base-role.j2``, and render without error when given their
documented context variables.
"""

import json
import os
from typing import Any

import pytest
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# Path to the prompts directory relative to this file
PROMPTS_DIR = os.path.join(
    os.path.dirname(__file__), "../../../app/intelligence/prompts"
)


@pytest.fixture(scope="module")
def jinja_env() -> Environment:
    """Create a Jinja2 environment pointed at the prompts directory.

    ``fromjson`` is registered here because both production adapters do the same
    (``OpenRouterAdapter.__init__`` / ``GeminiAdapter.__init__``): the Stage 2
    templates normalise ``analysis_json``, which callers pass as a JSON *string*,
    via ``| fromjson``. A fixture without the filter cannot render either template
    and would report a false failure.
    """
    env = Environment(loader=FileSystemLoader(PROMPTS_DIR))
    env.filters["fromjson"] = json.loads
    return env


# ── Template existence tests ────────────────────────────────────────────────


def test_analyze_requirement_template_exists(jinja_env: Environment) -> None:
    """UNIT022: s2-estimation/analyze-requirement.j2 must exist."""
    try:
        jinja_env.get_template("s2-estimation/analyze-requirement.j2")
    except TemplateNotFound:
        pytest.fail("Template s2-estimation/analyze-requirement.j2 not found")


def test_estimate_full_template_exists(jinja_env: Environment) -> None:
    """UNIT022: s2-estimation/estimate-full.j2 must exist."""
    try:
        jinja_env.get_template("s2-estimation/estimate-full.j2")
    except TemplateNotFound:
        pytest.fail("Template s2-estimation/estimate-full.j2 not found")


def test_estimate_discovery_template_exists(jinja_env: Environment) -> None:
    """UNIT022: s2-estimation/estimate-discovery.j2 must exist."""
    try:
        jinja_env.get_template("s2-estimation/estimate-discovery.j2")
    except TemplateNotFound:
        pytest.fail("Template s2-estimation/estimate-discovery.j2 not found")


# ── Template inheritance tests ──────────────────────────────────────────────


def test_analyze_requirement_extends_base_role(jinja_env: Environment) -> None:
    """UNIT022: analyze-requirement.j2 must extend base/base-role.j2."""
    template_source = jinja_env.loader.get_source(
        jinja_env, "s2-estimation/analyze-requirement.j2"
    )[0]
    assert "{% extends 'base/base-role.j2' %}" in template_source, (
        "analyze-requirement.j2 must extend base/base-role.j2"
    )


def test_estimate_full_does_not_extend_base_role(jinja_env: Environment) -> None:
    """UNIT022: estimate-full.j2 does NOT need to extend base/base-role.j2.
    It's a self-contained numerical template with no prose sections."""
    template_source = jinja_env.loader.get_source(
        jinja_env, "s2-estimation/estimate-full.j2"
    )[0]
    # Self-contained template — no extends directive
    assert "{% extends" not in template_source, (
        "estimate-full.j2 unexpectedly extends a base template"
    )


def test_estimate_discovery_does_not_extend_base_role(jinja_env: Environment) -> None:
    """UNIT022: estimate-discovery.j2 does NOT extend base/base-role.j2.
    It is a macro-based template, not a prose/render template."""
    template_source = jinja_env.loader.get_source(
        jinja_env, "s2-estimation/estimate-discovery.j2"
    )[0]
    # Macro-based template — no extends directive
    assert "{% extends" not in template_source, (
        "estimate-discovery.j2 unexpectedly extends a base template"
    )


# ── Template rendering tests ────────────────────────────────────────────────


def _sample_analysis() -> dict[str, Any]:
    """Return a minimal RequirementAnalysis-like dict for template rendering."""
    return {
        "maturity_score": 7,
        "maturity_reason": "Good detail level with some gaps",
        "entities": {
            "technologies": ["Python", "FastAPI"],
            "deliverables": ["API endpoints", "Database schema"],
            "constraints": ["Must be done in 4 weeks"],
        },
        "gaps": ["No mention of testing strategy"],
        "branch": "full",
        "requirements": [
            {
                "name": "User authentication",
                "description": "JWT-based auth with refresh tokens",
            },
            {
                "name": "Data export",
                "description": "CSV export of user data",
            },
        ],
        "complexity": "medium",
        "delivery_pace": "standard",
    }


def test_analyze_requirement_renders(jinja_env: Environment) -> None:
    """UNIT022: analyze-requirement.j2 renders with documented context."""
    template = jinja_env.get_template("s2-estimation/analyze-requirement.j2")
    output = template.render(
        full_description="Build a web app with user management and reporting.",
        threshold=8,
    )
    # Should produce valid JSON parseable output (or at least not crash)
    assert len(output) > 0, "Template rendered empty string"
    assert "maturity_score" in output or "maturity" in output.lower(), (
        "Output should reference maturity analysis"
    )


def test_estimate_full_renders(jinja_env: Environment) -> None:
    """UNIT022: estimate-full.j2 renders to parseable JSON with consistent hours.

    The previous version of this test wrapped the render in a bare
    ``except Exception: pass``, so it stayed green while the template crashed in
    production with ``TypeError: type str doesn't define __round__ method``. A
    prompt template that does not render is never acceptable, so the render is
    now asserted unconditionally.
    """
    template = jinja_env.get_template("s2-estimation/estimate-full.j2")
    analysis = _sample_analysis()
    output = template.render(analysis_json=json.dumps(analysis, indent=2))
    assert len(output) > 0, "Template rendered empty string"

    payload = json.loads(output)
    assert payload["estimate_type"] == "full", (
        "TechnicalEstimateFull requires estimate_type: Literal['full']"
    )
    # Hours invariant asserted by TechnicalEstimateFull.validate_hours_consistency.
    total = payload["summary"]["total_hours"]
    milestones = payload["milestones"]
    assert milestones, "an empty plan has nothing for Stage 3 to sell"
    assert abs(total - sum(m["hours_with_overhead"] for m in milestones)) <= 0.5, (
        "summary.total_hours must equal the sum of the milestone hours"
    )
    for milestone in milestones:
        rollup = sum(t["hours_with_overhead"] for t in milestone["tasks"].values())
        assert abs(rollup - milestone["hours_with_overhead"]) <= 0.5, (
            f"milestone step {milestone['step']} disagrees with its own tasks"
        )


def test_estimate_discovery_renders(jinja_env: Environment) -> None:
    """UNIT022: estimate-discovery.j2 renders to parseable JSON at top level.

    This template used to be a bag of never-invoked ``{% macro %}`` definitions,
    so ``render()`` returned ``''`` for every input and OpenRouter rejected the
    blank prompt with ``400 — Input must have at least 1 token``. The body is now
    inline; both the emptiness and the JSON shape are asserted.
    """
    template = jinja_env.get_template("s2-estimation/estimate-discovery.j2")
    analysis = _sample_analysis()
    output = template.render(analysis_json=json.dumps(analysis, indent=2))
    assert output.strip(), (
        "estimate-discovery.j2 rendered empty — the Stage 2B prompt would be "
        "rejected upstream as 'Input must have at least 1 token'"
    )

    payload = json.loads(output)
    assert payload["estimate_type"] == "discovery"
    assert isinstance(payload["phase0_hours"], int) and payload["phase0_hours"] >= 1
    assert payload["post_discovery_hourly_rate"] > 0
    # open_questions must be a real JSON array, not the Python repr of one
    # (the old ``{{ questions }}`` emitted "['g1', 'g2']").
    assert isinstance(payload["open_questions"], list), (
        "open_questions must serialise via | tojson, not via Python repr"
    )
    assert len(payload["open_questions"]) >= 1, (
        "TechnicalEstimateDiscovery requires at least one open question"
    )
    for question in payload["open_questions"]:
        assert question.strip(), "open_questions must not contain blank strings"

    scope = payload["scope_matrix"]
    assert set(scope["in_scope"]).isdisjoint(scope["out_of_scope"]), (
        "validate_scope_disjoint rejects items present in both scope branches"
    )