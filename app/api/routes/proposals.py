from fastapi import APIRouter, Path, Body, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId
from bson.errors import InvalidId
from app.database.projects_repository import ProjectsRepository
from app.database.proposal_versions_repository import ProposalVersionsRepository
from app.intelligence.factory import (
    refine_proposal as refine_proposal_intel,
    create_intelligence_service,
)
from app.services.proposal_pipeline_service import generate_and_persist_proposal
from loguru import logger

router = APIRouter(tags=["proposals"])


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

ALLOWED_CONTRACT_TYPES = {"project_fixed", "staff_augmentation"}


class RefineProposalRequest(BaseModel):
    llm_model_id: str = Field(..., description="The LLM model ID to use for refinement")
    user_feedback_observations: str = Field(
        ..., description="User feedback/observations to guide the refinement"
    )
    contract_type: Optional[str] = Field(
        None,
        description="Optional contract type override: 'project_fixed' or 'staff_augmentation'",
    )

    @field_validator("contract_type")
    @classmethod
    def validate_contract_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_CONTRACT_TYPES:
            raise ValueError(
                f"Invalid contract_type '{v}'. "
                f"Allowed values: {', '.join(sorted(ALLOWED_CONTRACT_TYPES))}"
            )
        return v


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/{projectId}/refine")
async def refine_proposal(
    projectId: str = Path(..., description="The MongoDB ObjectId of the project"),
    body: RefineProposalRequest = Body(...),
):
    """
    Refine an existing proposal using an LLM.

    Accepts an ``llm_model_id`` and ``user_feedback_observations``, processes
    the refinement through the intelligence layer, stores the result as a new
    version in ``proposal_versions`` with ``source_of_changes="IA"``, and
    returns the updated project in the same format as ``GET /api/projects/{id}``.
    """
    # -- Validate project ID -------------------------------------------------
    try:
        ObjectId(projectId)
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Bad Request",
                "message": "Invalid project ID format. Must be a valid MongoDB ObjectId.",
            },
        )

    # -- Look up the project -------------------------------------------------
    projects_repo = ProjectsRepository()
    project = await projects_repo.get_project_by_id(projectId)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Convert ObjectId for JSON serialisation
    project["_id"] = str(project["_id"])

    # Populate the latest proposal so the project dict carries the current
    # proposal data that the LLM needs as context for refinement
    project = await projects_repo.populate_proposal_for_project(project)

    # -- Validate link_hash exists before calling AI (fail fast) ------------
    link_hash = project.get("link_hash")
    if not link_hash:
        logger.error(
            f"Cannot insert refined proposal – project {projectId} has no link_hash."
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "Project is missing link_hash; cannot store proposal version.",
            },
        )

    # -- Determine effective contract type ----------------------------------
    requested_contract_type = body.contract_type
    existing_contract_type = project.get("contract_type", "project_fixed")
    effective_contract_type = (
        requested_contract_type
        if requested_contract_type is not None
        else existing_contract_type
    )
    contract_type_changed = (
        requested_contract_type is not None
        and requested_contract_type != existing_contract_type
    )

    # -- project_fixed: correr el PIPELINE COMPLETO -------------------------
    #    Reestimar como proyecto usa el MISMO workflow que el bot
    #    (/procesar): Etapa 1 (analisis) -> 2 (estimacion) -> 3 (comercial).
    #    El feedback del usuario viaja como `extra_info` y reorienta las tres
    #    etapas. Antes se usaba ``refine_proposal`` con el template inicial,
    #    que NO recibe ``technical_estimate_json`` y devolvia milestones=[]
    #    (0 tareas) y aplicaba $25 en vez de HOURLY_RATE_PROJECT_FIXED.
    if effective_contract_type == "project_fixed":
        try:
            # Persistir el cambio de tipo de contrato ANTES de generar, para
            # que la propuesta y el documento queden coherentes (el Dashboard
            # decide como renderizar segun `contract_type`).
            if existing_contract_type != "project_fixed":
                await projects_repo.collection.update_one(
                    {"_id": ObjectId(projectId)},
                    {"$set": {"contract_type": "project_fixed"}},
                )
                project["contract_type"] = "project_fixed"
            adapters = await create_intelligence_service()
            await generate_and_persist_proposal(
                project,
                adapters,
                extra_info=body.user_feedback_observations,
                source_of_changes="IA",
            )
        except Exception as e:
            logger.error(f"Pipeline refinement failed for project {projectId}: {e}")
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "AI Service Error",
                    "message": "The pipeline failed to regenerate the proposal.",
                    "details": str(e),
                },
            )
        # El pipeline ya persistio la version y marco el proyecto.
        project = await projects_repo.populate_proposal_for_project(project)
        return project

    # -- staff_augmentation: se mantiene el refine existente ----------------
    #    Simetria con project_fixed: si el contrato cambio a staff, se refleja
    #    en el documento para que el Dashboard renderice la propuesta correcta.
    if contract_type_changed:
        await projects_repo.collection.update_one(
            {"_id": ObjectId(projectId)},
            {"$set": {"contract_type": "staff_augmentation"}},
        )
        project["contract_type"] = "staff_augmentation"
        logger.info(
            f"Contract type changed from '{existing_contract_type}' to "
            f"'{requested_contract_type}' for project {projectId}."
        )

    try:
        refined = await refine_proposal_intel(
            project=project,
            user_feedback_observations=body.user_feedback_observations,
            model_id=body.llm_model_id,
            contract_type=requested_contract_type,
        )
        if isinstance(refined, dict) and "error" in refined:
            logger.error(
                f"Intelligence service returned an error for project {projectId}: "
                f"{refined['error']}"
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "AI Service Error",
                    "message": "The intelligence service failed to refine the proposal.",
                    "details": refined["error"],
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refinement failed for project {projectId}: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "AI Service Error",
                "message": "The intelligence service failed to refine the proposal.",
                "details": str(e),
            },
        )
    # -- Extract refinement_justification and inner proposal -----------------
    # The LLM returns a dict with top-level "refinement_justification" and
    # "proposal" keys.  They must be stored separately: justification as a
    # top-level field on the proposal_versions document, and the inner
    # proposal object as proposal_data (without the justification inside it).
    logger.debug(
        f"[DEBUG refine] Raw refined keys: {list(refined.keys()) if isinstance(refined, dict) else type(refined).__name__} | "
        f"has_error_key={'error' in refined if isinstance(refined, dict) else 'N/A'} | "
        f"type={type(refined).__name__}"
    )
    refinement_justification = refined.pop("refinement_justification", None)
    inner_proposal = refined.pop("proposal", refined)
    logger.debug(
        f"[DEBUG refine] inner_proposal keys: {list(inner_proposal.keys()) if isinstance(inner_proposal, dict) else type(inner_proposal).__name__} | "
        f"is_empty={not inner_proposal if isinstance(inner_proposal, dict) else 'N/A'} | "
        f"refinement_justification_len={len(refinement_justification) if refinement_justification else 0}"
    )

    # Guard: the LLM sometimes returns only refinement_justification
    # without the "proposal" key, leaving inner_proposal as an empty dict.
    # Reject early so we never store empty proposal_data.
    if not isinstance(inner_proposal, dict) or not inner_proposal:
        logger.error(
            f"Refined proposal data is empty for project {projectId}. "
            f"LLM returned keys: {list(refined.keys()) if isinstance(refined, dict) else 'N/A'} "
            f"after popping refinement_justification."
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "AI Service Error",
                "message": (
                    "The intelligence service returned a response without proposal content. "
                    "Please retry the refinement."
                ),
            },
        )

    # -- Store the refined proposal as a new version -------------------------
    proposals_repo = ProposalVersionsRepository()
    await proposals_repo.insert_version(
        project_id=projectId,
        link_hash=link_hash,
        proposal_data=inner_proposal,
        source_of_changes="IA",
        refinement_justification=refinement_justification,
    )
    logger.info(
        f"Created new proposal version for project {projectId} "
        f"with source_of_changes=IA"
    )

    # Re-populate and return the project in the same format as get_project
    project = await projects_repo.populate_proposal_for_project(project)
    return project