"""Orquestador del pipeline de propuestas por etapas (`project_fixed`).

Este módulo vive **fuera** de los adapters a propósito. Un adapter está atado a
un único provider (Gemini u OpenRouter, decidido por su ``model_id``), así que un
orquestador alojado dentro de un adapter fuerza que las tres etapas corran con el
mismo provider/modelo. Ese era el bug original: el handler llamaba a
``adapters["PREMIUM"].generate_project_fixed_proposal(...)`` y, como la fábrica
fija los tres overrides al mismo ``model_id``, las Etapas 1 y 2 terminaban
ejecutándose con el modelo PREMIUM —contra lo que exige el plan §7.2.

Aquí la asignación es explícita y por etapa, de modo que cada etapa puede usar un
provider distinto:

    Etapa 1 (analyze_requirement)        -> ``standard_adapter``
    Etapa 2 (estimate_technical)         -> ``standard_adapter``
    Etapa 3 (write_commercial_proposal)  -> ``premium_adapter``

Hoy ambos adapters son OpenRouter, pero basta con pasar, p. ej., un
``GeminiAdapter`` como ``standard_adapter`` y un ``OpenRouterAdapter`` como
``premium_adapter`` para repartir las etapas entre providers sin tocar más código.

El guard rail del plan §7.3 se conserva intacto: un ``PipelineError`` en la
Etapa 1 o 2 aborta **antes** de invocar la Etapa 3 (PREMIUM, 2 RPM / 35 s), de
modo que nunca se factura el modelo caro con datos corruptos.

La persistencia en ``requirement_analyses``, ``technical_estimates`` y
``proposal_versions`` NO es responsabilidad de este orquestador: la realiza el
handler de Telegram, que es el único punto con acceso a ``project_id`` y
``link_hash``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from app.exceptions import PipelineError
from app.intelligence.config import get_maturity_threshold
from app.intelligence.port import IntelligencePort

if TYPE_CHECKING:
    from app.bots.telegram.circuit_breaker import CircuitBreaker

__all__ = ["generate_project_fixed_proposal"]


async def generate_project_fixed_proposal(
    project: dict,
    standard_adapter: IntelligencePort,
    premium_adapter: IntelligencePort,
    circuit_breaker: Optional["CircuitBreaker"] = None,
) -> dict[str, Any]:
    """Orquesta Etapa 1 -> 2 -> 3 para ``project_fixed``.

    Args:
        project: payload del proyecto (debe incluir ``link_hash`` y ``title``
            para la trazabilidad de las trazas ``[PIPELINE]``).
        standard_adapter: adapter que sirve las Etapas 1 y 2 (modelo STANDARD).
            Puede ser de un provider distinto al de ``premium_adapter``.
        premium_adapter: adapter que sirve la Etapa 3 (modelo PREMIUM).
        circuit_breaker: estado compartido del circuit breaker, si aplica.

    Returns:
        JSON acumulado ``{"analysis": ..., "estimate": ..., "proposal": ...}``.

    Raises:
        PipelineError: si la Etapa 1 o 2 no superan su validación Pydantic. En
            ese caso la Etapa 3 nunca se invoca.
    """
    threshold = get_maturity_threshold()
    link_hash = project.get("link_hash", "?")
    title = project.get("title", "?")

    logger.info(f"🚀 Pipeline project_fixed con maturity_threshold={threshold}")
    logger.debug(
        f"[PIPELINE][link_hash={link_hash}][START] title={title!r} "
        f"threshold={threshold} contract_type={project.get('contract_type')!r} "
        f"standard={type(standard_adapter).__name__} "
        f"premium={type(premium_adapter).__name__}"
    )

    # Etapa 1 (STANDARD) — un PipelineError propaga y corta aquí.
    try:
        analysis = await standard_adapter.analyze_requirement(
            project=project,
            maturity_threshold=threshold,
            circuit_breaker=circuit_breaker,
        )
    except PipelineError as e:
        logger.error(
            f"[PIPELINE][link_hash={link_hash}][STAGE_FAILED] etapa=1 error={e}"
        )
        raise
    logger.success("✅ Etapa 1 completa — análisis de requerimientos.")
    logger.debug(
        f"[PIPELINE][link_hash={link_hash}][STAGE_DONE] etapa=1 "
        f"branch={analysis.get('branch')!r} "
        f"maturity_score={analysis.get('maturity_score')!r}"
    )

    # Etapa 2 (STANDARD) — PipelineError => nunca se llega a Etapa 3.
    try:
        estimate = await standard_adapter.estimate_technical(
            project=project,
            analysis=analysis,
            circuit_breaker=circuit_breaker,
        )
    except PipelineError as e:
        logger.error(
            f"[PIPELINE][link_hash={link_hash}][STAGE_FAILED] etapa=2 error={e}"
        )
        raise
    logger.success("✅ Etapa 2 completa — estimación técnica.")
    logger.debug(
        f"[PIPELINE][link_hash={link_hash}][STAGE_DONE] etapa=2 "
        f"estimate_type={estimate.get('estimate_type')!r}"
    )

    # Etapa 3 (PREMIUM) — puede usar un provider distinto al de las Etapas 1-2.
    try:
        proposal = await premium_adapter.write_commercial_proposal(
            project=project,
            technical_estimate=estimate,
            circuit_breaker=circuit_breaker,
        )
    except PipelineError as e:
        logger.error(
            f"[PIPELINE][link_hash={link_hash}][STAGE_FAILED] etapa=3 error={e}"
        )
        raise
    logger.success("✅ Etapa 3 completa — propuesta comercial.")
    logger.debug(f"[PIPELINE][link_hash={link_hash}][STAGE_DONE] etapa=3")

    return {
        "analysis": analysis,
        "estimate": estimate,
        "proposal": proposal,
    }
