"""
SCS Case Management Models
These models represent the operational case management layer
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class PriorityLevel(str, Enum):
    """Priority levels for cases"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CaseStatus(str, Enum):
    """Case status"""
    UNASSIGNED = "unassigned"
    ASSIGNED = "assigned"

class WorkStatus(str, Enum):
    """Workflow status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    TO_REVIEW = "to_review"
    COMPLETED = "completed"

class SCSCaseModel(BaseModel):
    """
    Operational case record for youth workers
    One case per monitored youth
    """
    case_id: str = Field(..., description="Unique case ID: CASE_{year}_{sequence}")
    user_id: str = Field(..., description="Social media handle of the youth")
    assigned_to: Optional[str] = Field(None, description="Staff user_id (null = unassigned)")
    
    # AI-generated fields (updated each run)
    current_risk_score: float = Field(..., ge=0, le=100, description="0-100 risk score")
    category: str = Field(..., description="AI-determined category")
    ai_explanation: Dict[str, Any] = Field(..., description="Detailed AI reasoning")
    priority: PriorityLevel = Field(..., description="Priority level for case workers")
    
    # Workflow fields (preserved across runs)
    case_status: CaseStatus = Field(default=CaseStatus.UNASSIGNED)
    work_status: WorkStatus = Field(default=WorkStatus.NOT_STARTED)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SCSCaseHistoryModel(BaseModel):
    """
    Historical snapshots of risk assessments
    One entry per case per ingestion cycle (append-only)
    """
    history_id: int = Field(..., description="Auto-incrementing ID per case")
    case_id: str = Field(..., description="Reference to scs_cases.case_id")
    
    # Snapshot of AI assessment at this point in time
    risk_score: float = Field(..., ge=0, le=100)
    category: str = Field(...)
    ai_explanation: Dict[str, Any] = Field(...)
    
    # Metadata
    ingestion_date: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = Field(..., description="Version of analytics pipeline")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SCSChecklistItemModel(BaseModel):
    """
    Checklist items for youth workers to complete
    Created from templates when case is first created
    """
    checklist_item_id: int = Field(..., description="Auto-incrementing ID per case")
    case_id: str = Field(..., description="Reference to scs_cases.case_id")
    template_id: Optional[int] = Field(None, description="Template ID if from template")
    
    # Item details
    label: str = Field(..., description="Description of task")
    is_mandatory: bool = Field(default=True)
    completed: bool = Field(default=False)
    
    # Comments/notes from youth worker
    comments: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Completion tracking
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    
    # Display order
    display_order: int = Field(default=0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SCSChecklistTemplateModel(BaseModel):
    """
    Templates for checklist items
    Used to initialize checklists for new cases
    """
    template_id: int = Field(..., description="Unique template ID")
    label: str = Field(..., description="Task description")
    is_mandatory: bool = Field(default=True)
    display_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SCSUserModel(BaseModel):
    """
    Staff users (youth workers)
    """
    user_id: str = Field(..., description="Unique staff ID")
    name: str = Field(...)
    email: str = Field(...)
    role: str = Field(...)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)