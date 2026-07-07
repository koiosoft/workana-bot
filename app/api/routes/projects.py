from fastapi import APIRouter, Query, Path, Body, HTTPException
from typing import Optional, Dict, Any
from bson import ObjectId
from bson.errors import InvalidId
from app.database.projects_repository import ProjectsRepository
from app.database.proposal_versions_repository import ProposalVersionsRepository
from loguru import logger

router = APIRouter(tags=["projects"])

@router.get("")
async def list_projects(
    status: str = Query("all", description="Filter by proposal status"),
    searchTerm: Optional[str] = Query(None, description="Search in title and description"),
    staffAugmentationOnly: bool = Query(False, description="Filter by staff augmentation contract type"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
):
    repo = ProjectsRepository()
    result = await repo.get_projects(
        status=status,
        search_term=searchTerm,
        staff_augmentation_only=staffAugmentationOnly,
        page=page,
        limit=limit
    )
    # Populate proposals from proposal_versions (two-step: fetch metadata, hydrate)
    result["projects"] = await repo.populate_proposals_for_projects(result["projects"])
    return result

@router.get("/{id}")
async def get_project(
    id: str = Path(..., description="The MongoDB ObjectId of the project"),
):
    try:
        ObjectId(id)
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Bad Request",
                "message": "Invalid project ID format. Must be a valid MongoDB ObjectId."
            }
        )
    
    repo = ProjectsRepository()
    project = await repo.get_project_by_id(id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    # Convert ObjectId to string for JSON serialization
    project["_id"] = str(project["_id"])
    # Populate proposal from proposal_versions (latest version, newest first)
    project = await repo.populate_proposal_for_project(project)
    return project

@router.patch("/{id}")
async def update_project(
    id: str = Path(..., description="The MongoDB ObjectId of the project"),
    update_data: Dict[str, Any] = Body(..., description="Fields to update")
):
    try:
        ObjectId(id)
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Bad Request",
                "message": "Invalid project ID format. Must be a valid MongoDB ObjectId."
            }
        )

    repo = ProjectsRepository()
    try:
        # Extract proposal data before passing to update_project_by_id,
        # so it never lands in the projects collection.
        proposal_data = update_data.pop("proposal", None)

        success = await repo.update_project_by_id(id, update_data)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found or invalid ID")

        proposals_repo = ProposalVersionsRepository()

        if proposal_data is not None:
            # Create a new proposal version with HUMAN as the source of changes
            project = await repo.get_project_by_id(id)
            link_hash = project.get("link_hash") if project else None

            if not link_hash:
                logger.error(
                    f"Cannot insert proposal version – project {id} has no link_hash."
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "Internal Server Error",
                        "message": "Project is missing link_hash; cannot store proposal version.",
                    },
                )

            await proposals_repo.insert_version(
                project_id=id,
                link_hash=link_hash,
                proposal_data=proposal_data,
                source_of_changes="HUMAN",
            )
            logger.info(
                f"Created new proposal version for project {id} "
                f"with source_of_changes=HUMAN"
            )
        else:
            # No proposal payload – just mark the latest version as human-edited
            await proposals_repo.update_source_of_changes(id, source="HUMAN")

        return {"message": "Project updated successfully"}
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating project {id}: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Bad Request",
                "message": "Invalid data provided for project update.",
                "details": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error updating project {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred while updating the project.",
                "details": str(e)
            }
        )
