from fastapi import APIRouter, Query, Path, Body, HTTPException
from typing import Optional, Dict, Any
from app.database.projects_repository import ProjectsRepository

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
    return result

@router.get("/{id}")
async def get_project(
    id: str = Path(..., description="The MongoDB ObjectId of the project"),
):
    repo = ProjectsRepository()
    project = await repo.get_project_by_id(id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    # Convert ObjectId to string for JSON serialization
    project["_id"] = str(project["_id"])
    return project

@router.patch("/{id}")
async def update_project(
    id: str = Path(..., description="The MongoDB ObjectId of the project"),
    update_data: Dict[str, Any] = Body(..., description="Fields to update")
):
    repo = ProjectsRepository()
    try:
        success = await repo.update_project_by_id(id, update_data)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found or invalid ID")
        return {"message": "Project updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")
