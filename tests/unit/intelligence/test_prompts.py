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
    """UNIT022: estimate-full.j2 renders a non-empty PROMPT with the data injected.

    La plantilla ya NO es un generador de JSON (eso lo hace la IA): es un prompt
    que pide a la IA estimar en Horas de IA Supervisada. El test verifica que
    renderiza texto no vacio, menciona la mentalidad y inyecta el analysis."""
    template = jinja_env.get_template("s2-estimation/estimate-full.j2")
    analysis = _sample_analysis()
    output = template.render(analysis_json=json.dumps(analysis, indent=2), hourly_rate=18, post_discovery_hourly_rate=18)
    assert len(output) > 0, "Template rendered empty string"
    # Es un prompt, no un JSON: no debe empezar con '{'.
    assert not output.strip().startswith("{"), "estimate-full.j2 must render a prompt, not JSON"
    # Menciona la mentalidad de estimacion nueva.
    assert "IA Supervisada" in output or "IA supervisada" in output
    # Inyecta los datos del Stage 1.
    assert "maturity_score" in output
    # Inyecta la tarifa configurable.
    assert "18" in output


def test_estimate_discovery_renders(jinja_env: Environment) -> None:
    """UNIT022: estimate-discovery.j2 renders a non-empty PROMPT (Diseño B).

    La plantilla es un prompt (la IA estima); debe renderizar texto no vacio,
    describir la estimabilidad minima y el descubrimiento, e inyectar datos."""
    template = jinja_env.get_template("s2-estimation/estimate-discovery.j2")
    analysis = _sample_analysis()
    output = template.render(analysis_json=json.dumps(analysis, indent=2), hourly_rate=18, post_discovery_hourly_rate=18)
    assert output.strip(), (
        "estimate-discovery.j2 rendered empty — the Stage 2B prompt would be "
        "rejected upstream as 'Input must have at least 1 token'"
    )
    assert not output.strip().startswith("{"), "estimate-discovery.j2 must render a prompt, not JSON"
    assert "ESTIMABILIDAD MÍNIMA" in output or "estimable" in output.lower()
    assert "discovery_hours" in output
    assert "maturity_score" in output