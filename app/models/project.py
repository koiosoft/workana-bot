from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from datetime import datetime

# Literals for statuses and strategies
ProjectStatus = Literal['BACKLOG', 'DRAFT', 'READY_TO_PUBLISH', 'PUBLISHED', 'REJECTED']
ProjectStrategy = Literal['PRO', 'FLASH', 'NONE']
ContractType = Literal['staff_augmentation', 'project_fixed']
ProposalStatus = Literal[
    'all', 
    'proposal_generated', 
    'submited_to_workana', 
    'ready_for_proposal', 
    'discarded', 
    'rejected',
    'not_found'
]

class Task(BaseModel):
    description: str
    hours_with_overhead: float

class Milestone(BaseModel):
    step: int
    name: str
    tasks: Dict[str, Task]
    hours_with_overhead: float
    subtotal: float

class MilestoneProposalSummary(BaseModel):
    total_hours: float
    total_budget: float
    delivery_time_weeks: int
    hourly_rate_applied: float

class MilestoneProposal(BaseModel):
    proposal_header: str
    milestones: List[Milestone]
    summary: MilestoneProposalSummary
    technical_pitch: str
    questions_for_client: Optional[List[str]] = None

class BudgetSummary(BaseModel):
    hourly_rate: float
    suggested_hours_per_week: int
    estimated_monthly_budget: float

class StaffAugmentationProposal(BaseModel):
    cover_letter: str
    budget_summary: BudgetSummary
    questions_for_client: Optional[List[str]] = None

# Union of the two proposal types
AnyProposal = Union[MilestoneProposal, StaffAugmentationProposal]

class Project(BaseModel):
    # Pydantic v2 configuration
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(None, alias="_id")
    link_hash: str
    title: str
    description: str
    full_description: str
    generated_proposal: Optional[str] = None
    status: ProjectStatus
    updated_at: datetime
    scraped_at: datetime
    estimated_published_at: datetime
    proposal_at: Optional[datetime] = None
    url: HttpUrl
    country: str
    payment: str
    skills: List[str]
    proposal: AnyProposal
    link: HttpUrl
    budget: str
    strategy: ProjectStrategy
    ai_reason: str
    ai_score: float
    proposal_status: str
    previous_status: Optional[str] = None
    contract_type: ContractType
    deleted_at: Optional[datetime] = None
