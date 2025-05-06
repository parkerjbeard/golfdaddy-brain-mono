from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

class ClarificationRequest(BaseModel):
    question: str
    original_text: str
    status: str = "pending" # pending, answered, resolved
    answer: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    answered_at: Optional[datetime] = None

class AiAnalysis(BaseModel):
    estimated_hours: Optional[float] = None
    estimated_difficulty: Optional[str] = None # e.g., low, medium, high
    clarification_requests: List[ClarificationRequest] = []
    sentiment: Optional[str] = None # e.g., positive, neutral, negative
    key_achievements: List[str] = []
    potential_blockers: List[str] = []
    summary: Optional[str] = None

class DailyReport(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    report_date: datetime = Field(default_factory=datetime.utcnow)
    raw_text_input: str = Field(..., description="Raw bullet points submitted by the employee")
    
    # AI Processed Data
    clarified_tasks_summary: Optional[str] = Field(None, description="Summary of tasks after AI clarification (if any)")
    ai_analysis: Optional[AiAnalysis] = None
    
    # Links to other data
    linked_commit_ids: List[str] = [] # List of commit SHAs or IDs
    
    # Overall Assessment (potentially filled by manager or further AI analysis)
    overall_assessment_notes: Optional[str] = None
    final_estimated_hours: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True # if we use SQLAlchemy later
        # For older Pydantic versions, it might be `orm_mode = True` directly in the class.
        # For Pydantic v2, orm_mode is handled by model_config
        # model_config = {
        #     "from_attributes": True 
        # }


class DailyReportCreate(BaseModel):
    user_id: UUID # Should likely be inferred from authenticated user
    raw_text_input: str

class DailyReportUpdate(BaseModel):
    raw_text_input: Optional[str] = None
    clarified_tasks_summary: Optional[str] = None
    ai_analysis: Optional[AiAnalysis] = None
    linked_commit_ids: Optional[List[str]] = None
    overall_assessment_notes: Optional[str] = None
    final_estimated_hours: Optional[float] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow) 