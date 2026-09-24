"""Tests del normalizador determinista de estimaciones.

El normalizador es la capa que "no confia en el LLM": reescribe claves, calcula
horas/subtotales y CONSTRUYE el `summary` (el prompt le dice al LLM que no lo
emita). Estos tests fijan ese contrato, en especial el caso que tumbo produccion:

    discovery con `milestones: []` (proyecto vacio / todo por descubrir)
    => `summary` DEBE existir (en ceros), no ausente.
"""

from app.intelligence.estimate_normalizer import normalize_estimate_hours
from app.models.estimate import (
    TechnicalEstimateDiscovery,
    TechnicalEstimateFull,
)


FULL_ANALYSIS = {
    "maturity_score": 8,
    "maturity_reason": "claro",
    "entities": {
        "technologies": ["Python"],
        "deliverables": ["API"],
        "constraints": [],
    },
    "gaps": ["x"],
    "branch": "full",
}


def _discovery_raw(milestones):
    return {
        "estimate_type": "discovery",
        "milestones": milestones,
        "scope_matrix": {"in_scope": [], "out_of_scope": ["a"]},
        "discovery_hours": 40,
        "post_discovery_hourly_rate": 18.0,
        "open_questions": ["¿objetivo?"],
        "analysis": {**{k: v for k, v in FULL_ANALYSIS.items()}, "branch": "discovery"},
        "model_used": "deepseek/deepseek-v4-flash",
    }


# ---------------------------------------------------------------------------
# REGRESION: summary SIEMPRE presente (bug "summary Field required")
# ---------------------------------------------------------------------------

def test_discovery_with_empty_milestones_gets_zero_summary_and_validates():
    """El caso que rompio prod: discovery con 0 hitos -> summary en ceros.

    El prompt instruye al LLM a NO emitir `summary`. Si el normalizador lo
    omite cuando no hay horas, Pydantic falla ("summary Field required") y la
    etapa 2 se cae. Debe existir SIEMPRE.
    """
    raw = _discovery_raw(milestones=[])
    normalize_estimate_hours(raw, "discovery")

    assert "summary" in raw, "el normalizador debe emitir summary siempre"
    assert raw["summary"]["total_hours"] == 0
    assert raw["summary"]["total_budget"] == 0
    assert raw["summary"]["delivery_time_weeks"] == 1  # minimo 1 semana

    validated = TechnicalEstimateDiscovery.model_validate(raw)
    assert validated.summary.total_hours == 0


def test_discovery_with_milestone_tasks_builds_summary_from_hours():
    """Con hitos: summary.total_hours == suma de horas de los hitos."""
    ms = [{"tasks": {"disenar_bd": {"description": "x", "hours_with_overhead": 10}}},
          {"tasks": {"implementar_api": {"description": "y", "hours_with_overhead": 6}}}]
    raw = _discovery_raw(milestones=ms)
    normalize_estimate_hours(raw, "discovery")

    assert raw["summary"]["total_hours"] == 16
    assert raw["summary"]["total_budget"] == round(16 * raw["summary"]["hourly_rate_applied"], 2)


def test_full_with_empty_milestones_still_gets_summary():
    """La rama `full` tambien usaba el mismo `if` condicionado a horas."""
    raw = {
        "estimate_type": "full",
        "milestones": [],
        "analysis": FULL_ANALYSIS,
        "model_used": "m",
    }
    normalize_estimate_hours(raw, "full")
    assert "summary" in raw
    assert raw["summary"]["total_hours"] == 0


# ---------------------------------------------------------------------------
# Normalizacion de tareas / horas
# ---------------------------------------------------------------------------

def test_task_key_is_preserved_as_visible_title():
    """La clave es el TITULO visible: se preserva tal cual (con tildes)."""
    raw = _discovery_raw(
        milestones=[{"tasks": {"Diseñar esquema de BD": {"description": "x", "hours_with_overhead": 5}}}]
    )
    normalize_estimate_hours(raw, "discovery")
    keys = list(raw["milestones"][0]["tasks"].keys())
    assert keys == ["Diseñar esquema de BD"]


def test_whitespace_only_difference_collides_and_is_disambiguated():
    """Tras `strip()`, claves que solo difieren en espacios colisionan -> (2)."""
    ms = [{"tasks": {"Diseñar BD": {"description": "a", "hours_with_overhead": 1},
                     "  Diseñar BD  ": {"description": "b", "hours_with_overhead": 2}}}]
    raw = _discovery_raw(milestones=ms)
    normalize_estimate_hours(raw, "discovery")
    keys = sorted(raw["milestones"][0]["tasks"].keys())
    assert keys == ["Diseñar BD", "Diseñar BD (2)"]
    assert raw["milestones"][0]["hours_with_overhead"] == 3


def test_different_titles_with_same_slug_are_NOT_merged():
    """Dos titulos distintos ya NO colapsan (el slug desaparecio)."""
    ms = [{"tasks": {"Diseñar BD": {"description": "a", "hours_with_overhead": 1},
                     "Disenar  Bd": {"description": "b", "hours_with_overhead": 2}}}]
    raw = _discovery_raw(milestones=ms)
    normalize_estimate_hours(raw, "discovery")
    assert len(raw["milestones"][0]["tasks"]) == 2


def test_full_hours_consistent_passes_assert():
    raw = {
        "estimate_type": "full",
        "milestones": [
            {"step": 1, "name": "Backend",
             "tasks": {"a": {"description": "", "hours_with_overhead": 20}}}
        ],
        "analysis": FULL_ANALYSIS,
        "model_used": "m",
    }
    normalize_estimate_hours(raw, "full")
    validated = TechnicalEstimateFull.model_validate(raw)
    assert validated.summary.total_hours == 20


def test_non_dict_input_is_returned_untouched():
    """Guard: si el LLM devuelve algo que no es dict, no explotamos aqui."""
    assert normalize_estimate_hours("no soy un dict", "full") == "no soy un dict"
    assert normalize_estimate_hours(None, "full") is None
