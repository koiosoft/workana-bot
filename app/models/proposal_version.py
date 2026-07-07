"""
ProposalVersion model – decouples proposal data from the projects collection.

Enables full version history, audit trails, and AI-driven refinements
while maintaining backward compatibility with all existing API responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# Re-use the same proposal union type from project.py to keep the schema aligned.
from app.models.project import AnyProposal


class RefinementEntry(BaseModel):
    """Log entry recording what changed during a proposal refinement."""

    refined_by: Optional[str] = Field(None, description="User or system that triggered the refinement")
    reason: Optional[str] = Field(None, description="Why the refinement was performed")
    changes_summary: Optional[str] = Field(None, description="Brief summary of what changed")
    refined_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the refinement")


class ProposalVersion(BaseModel):
    """A versioned snapshot of a project proposal.

    Each generation or refinement creates a new document.  The latest version
    (highest ``version_number``) is what the API surface exposes as the
    effective proposal for a given project.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(None, alias="_id", description="MongoDB ObjectId")
    project_id: str = Field(..., description="MongoDB _id of the parent project (as string)")
    # NOTE: link_hash is stored alongside project_id so that existing code paths
    # that identify a project by link_hash can still locate proposal versions
    # without joining on _id first.
    link_hash: str = Field(..., description="Unique link_hash of the parent project")
    version_number: int = Field(..., ge=1, description="Monotonically increasing version number")
    proposal_data: AnyProposal = Field(..., description="The proposal content (MilestoneProposal or StaffAugmentationProposal)")
    refinement_log: Optional[List[RefinementEntry]] = Field(None, description="Log of previous refinements applied to this version")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When this version was created")
    source_of_changes: Optional[str] = Field(None, description="Source of changes: 'IA' or 'HUMAN'")