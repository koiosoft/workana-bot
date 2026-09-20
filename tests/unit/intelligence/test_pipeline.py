"""Tests Pareto del orquestador del pipeline por etapas (`app.intelligence.pipeline`).

Cubren lo esencial del rediseno: la asignacion de adapters por etapa y el guard
rail que evita facturar la Etapa 3 (PREMIUM) cuando una etapa previa falla.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import PipelineError
from app.intelligence.pipeline import generate_project_fixed_proposal


PROJECT = {"link_hash": "h1", "title": "Demo", "contract_type": "project_fixed"}


def _adapter(name: str, **returns) -> MagicMock:
    """Adapter mock con sus tres metodos de etapa como AsyncMock."""
    a = MagicMock()
    a.__class__.__name__ = name
    a.analyze_requirement = AsyncMock(return_value=returns.get("analysis", {"branch": "full", "maturity_score": 9}))
    a.estimate_technical = AsyncMock(return_value=returns.get("estimate", {"estimate_type": "full"}))
    a.write_commercial_proposal = AsyncMock(return_value=returns.get("proposal", {"proposal_header": "x"}))
    return a


@pytest.mark.asyncio
async def test_stages_1_2_use_standard_and_stage_3_uses_premium() -> None:
    """El core del rediseno: cada etapa llama al adapter correcto.

    Esto es lo que permite un provider distinto por etapa (STANDARD para 1-2,
    PREMIUM para 3), que era el requisito central.
    """
    standard = _adapter("Standard")
    premium = _adapter("Premium")

    result = await generate_project_fixed_proposal(PROJECT, standard, premium)

    assert standard.analyze_requirement.await_count == 1
    assert standard.estimate_technical.await_count == 1
    assert premium.write_commercial_proposal.await_count == 1
    # El premium NO hace las etapas baratas, y el standard NO redacta.
    assert premium.analyze_requirement.await_count == 0
    assert standard.write_commercial_proposal.await_count == 0
    assert sorted(result.keys()) == ["analysis", "estimate", "proposal"]


@pytest.mark.asyncio
async def test_guard_rail_stage2_failure_skips_stage3() -> None:
    """Si la Etapa 2 falla, la Etapa 3 (PREMIUM) NUNCA se invoca (plan §7.3)."""
    standard = _adapter("Standard")
    standard.estimate_technical = AsyncMock(side_effect=PipelineError("boom"))
    premium = _adapter("Premium")

    with pytest.raises(PipelineError):
        await generate_project_fixed_proposal(PROJECT, standard, premium)

    premium.write_commercial_proposal.assert_not_awaited()


@pytest.mark.asyncio
async def test_guard_rail_stage1_failure_skips_all() -> None:
    """Si la Etapa 1 falla, ni Etapa 2 ni Etapa 3 se invocan."""
    standard = _adapter("Standard")
    standard.analyze_requirement = AsyncMock(side_effect=PipelineError("boom"))
    premium = _adapter("Premium")

    with pytest.raises(PipelineError):
        await generate_project_fixed_proposal(PROJECT, standard, premium)

    standard.estimate_technical.assert_not_awaited()
    premium.write_commercial_proposal.assert_not_awaited()


@pytest.mark.asyncio
async def test_supports_mixed_providers_per_stage() -> None:
    """Adapters de providers distintos (nombres distintos) se usan por etapa."""
    gemini_like = _adapter("GeminiAdapter")
    openrouter_like = _adapter("OpenRouterAdapter")

    await generate_project_fixed_proposal(PROJECT, gemini_like, openrouter_like)

    # Etapas 1-2 en el primer adapter; Etapa 3 en el segundo.
    assert gemini_like.analyze_requirement.await_count == 1
    assert gemini_like.estimate_technical.await_count == 1
    assert openrouter_like.write_commercial_proposal.await_count == 1
