"""Caso de uso: generar la propuesta por etapas y persistir las 3 colecciones.

Extraido del handler de Telegram para que el BOT y la API (`/refine`) compartan
la MISMA logica. Antes el bloque de persistencia vivia solo en el handler; ahora
hay un unico lugar (fin de la duplicacion bot/API).

Flujo:
  1. `generate_project_fixed_proposal(project, standard, premium, extra_info)`.
  2. Persistir `requirement_analyses`, `technical_estimates` y `proposal_versions`.
  3. Marcar el proyecto como `proposal_generated`.

`extra_info` (indicacion adicional) se persiste en cada artefacto para
trazabilidad: saber con que input se genero cada version.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from app.database.proposal_versions_repository import ProposalVersionsRepository
from app.database.projects_repository import ProjectsRepository
from app.database.requirement_analyses_repository import RequirementAnalysesRepository
from app.database.technical_estimates_repository import TechnicalEstimatesRepository
from app.intelligence.config import get_maturity_threshold
from app.intelligence.pipeline import generate_project_fixed_proposal

__all__ = ["generate_and_persist_proposal", "persist_pipeline_result"]


def _build_flat_proposal(estimate: dict, proposal: dict) -> dict:
    """Contrato plano `MilestoneProposal` que consume el dashboard de Workana.

    `milestones` y `summary` se copian VERBATIM desde la estimacion (Etapa 2);
    solo los textos (header/pitch/questions) vienen de la Etapa 3.
    """
    return {
        "proposal_header": proposal.get("proposal_header", ""),
        "milestones": estimate.get("milestones", proposal.get("milestones", [])),
        "summary": estimate.get("summary", proposal.get("summary", {})),
        "technical_pitch": proposal.get("technical_pitch", ""),
        "questions_for_client": proposal.get("questions_for_client", []),
    }


async def persist_pipeline_result(
    project: dict,
    accumulated: dict,
    extra_info: str = "",
    source_of_changes: str = "IA",
) -> str:
    """Persiste en las 3 colecciones el resultado del pipeline por etapas.

    Args:
        project: debe incluir `link_hash` (y opcionalmente `_id`).
        accumulated: `{"analysis", "estimate", "proposal"}` del orquestador.
        extra_info: indicacion adicional usada (traza de auditoria).
        source_of_changes: etiqueta para `proposal_versions` ("IA", "HUMAN"...).

    Returns:
        El `project_id` (str) usado como clave foranea.
    """
    link_hash = project.get("link_hash", "?")
    analysis = accumulated.get("analysis", {})
    estimate = accumulated.get("estimate", {})
    proposal = accumulated.get("proposal", {})

    projects_repository = ProjectsRepository()

    # Resolver el _id del proyecto (clave foranea). Fallback a link_hash.
    project_id = str(project.get("_id") or "")
    if not project_id or project_id == "None":
        doc = await projects_repository.collection.find_one(
            {"link_hash": link_hash}, {"_id": 1}
        )
        project_id = str(doc["_id"]) if doc else link_hash

    now_utc = datetime.now(timezone.utc)

    # 1) requirement_analyses (Etapa 1)
    await RequirementAnalysesRepository().insert(
        {
            "project_id": project_id,
            "link_hash": link_hash,
            "analysis": analysis,
            "maturity_threshold_used": get_maturity_threshold(),
            "model_used": estimate.get("model_used", "unknown"),
            "extra_info": extra_info,
            "created_at": now_utc,
        }
    )

    # 2) technical_estimates (Etapa 2)
    estimate_payload: dict[str, Any] = {
        "project_id": project_id,
        "link_hash": link_hash,
        "estimate_type": estimate.get("estimate_type", "full"),
        "analysis": analysis,
        "model_used": estimate.get("model_used", "unknown"),
        "extra_info": extra_info,
        "created_at": now_utc,
    }
    if estimate.get("estimate_type") == "full":
        estimate_payload["milestones"] = estimate.get("milestones", [])
        estimate_payload["summary"] = estimate.get("summary", {})
    else:
        estimate_payload["milestones"] = estimate.get("milestones", [])
        estimate_payload["summary"] = estimate.get("summary", {})
        estimate_payload["scope_matrix"] = estimate.get("scope_matrix", {})
        estimate_payload["discovery_hours"] = estimate.get("discovery_hours", 0)
        estimate_payload["post_discovery_hourly_rate"] = estimate.get(
            "post_discovery_hourly_rate", 0
        )
        estimate_payload["open_questions"] = estimate.get("open_questions", [])
    await TechnicalEstimatesRepository().insert(estimate_payload)

    # 3) proposal_versions (Etapa 3 -> contrato plano).
    #    `extra_info` va en `refinement_log` (campo ya soportado) para trazar
    #    con que indicacion se genero esta version.
    flat_proposal = _build_flat_proposal(estimate, proposal)
    refinement_log = (
        [{"extra_info": extra_info, "at": now_utc.isoformat()}] if extra_info else None
    )
    await ProposalVersionsRepository().insert_version(
        project_id=project_id,
        link_hash=link_hash,
        proposal_data=flat_proposal,
        source_of_changes=source_of_changes,
        refinement_log=refinement_log,
    )

    # 4) Marcar el proyecto como generado.
    await projects_repository.collection.update_one(
        {"link_hash": link_hash},
        {
            "$set": {
                "proposal_status": "proposal_generated",
                "proposal_at": now_utc.isoformat(),
                "updated_at": now_utc.isoformat(),
            }
        },
    )

    logger.info(f"✅ Pipeline persistido para link_hash={link_hash} (project_id={project_id})")
    return project_id


async def generate_and_persist_proposal(
    project: dict,
    adapters: dict,
    circuit_breaker: Optional[Any] = None,
    extra_info: str = "",
    source_of_changes: str = "IA",
) -> dict:
    """Orquesta el pipeline por etapas y persiste el resultado.

    Args:
        project: payload del proyecto.
        adapters: `{"STANDARD": ..., "PREMIUM": ...}` (de `create_intelligence_service`).
        circuit_breaker: estado compartido, si aplica.
        extra_info: indicacion adicional (vacio = generacion normal).
        source_of_changes: etiqueta para `proposal_versions`.

    Returns:
        El JSON acumulado `{"analysis", "estimate", "proposal"}`.
    """
    accumulated = await generate_project_fixed_proposal(
        project,
        standard_adapter=adapters["STANDARD"],
        premium_adapter=adapters["PREMIUM"],
        circuit_breaker=circuit_breaker,
        extra_info=extra_info,
    )
    await persist_pipeline_result(
        project,
        accumulated,
        extra_info=extra_info,
        source_of_changes=source_of_changes,
    )
    return accumulated
