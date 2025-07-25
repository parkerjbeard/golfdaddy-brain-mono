from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum

class ClarificationStatus(str, Enum):
    PENDING = "pending"
    ANSWERED = "answered"
    RESOLVED = "resolved"

class ConversationState(str, Enum):
    INITIATED = "initiated"
    AWAITING_REPORT = "awaiting_report"
    CLARIFYING = "clarifying"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ClarificationRequest(BaseModel):
    question: str
    original_text: str
    status: ClarificationStatus = Field(default=ClarificationStatus.PENDING, description="Status of the clarification request")
    answer: Optional[str] = None
    requested_by_ai: bool = Field(default=False, description="Indicates if the AI generated this clarification request")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    answered_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AiAnalysis(BaseModel):
    estimated_hours: Optional[float] = None
    estimated_difficulty: Optional[str] = None # e.g., low, medium, high
    clarification_requests: List[ClarificationRequest] = []
    sentiment: Optional[str] = None # e.g., positive, neutral, negative
    key_achievements: List[str] = []
    potential_blockers: List[str] = []
    summary: Optional[str] = None

    class Config:
        from_attributes = True

class DailyReport(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    report_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_text_input: str = Field(..., description="Raw bullet points submitted by the employee")
    
    # Slack Integration
    slack_thread_ts: Optional[str] = Field(None, description="Slack thread timestamp for conversation tracking")
    slack_channel_id: Optional[str] = Field(None, description="Slack channel/DM ID where report was submitted")
    conversation_state: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Slack conversation context")
    
    # AI Processed Data
    clarified_tasks_summary: Optional[str] = Field(None, description="Summary of tasks after AI clarification (if any)")
    ai_analysis: Optional[AiAnalysis] = None
    
    # Deduplication Data
    deduplication_results: Optional[Dict[str, Any]] = Field(None, description="Results of commit/report deduplication")
    confidence_scores: Optional[Dict[str, float]] = Field(None, description="AI confidence scores for deduplication")
    commit_hours: Optional[float] = Field(None, description="Hours already accounted for in commits")
    additional_hours: Optional[float] = Field(None, description="Hours from report not in commits")
    
    # Links to other data
    linked_commit_ids: List[str] = [] # List of commit SHAs or IDs
    
    # Overall Assessment (potentially filled by manager or further AI analysis)
    overall_assessment_notes: Optional[str] = None
    final_estimated_hours: Optional[float] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        from_attributes = True
        # use_enum_values = True # Implicit with Pydantic V2 when enums are used as types


class DailyReportCreate(BaseModel):
    user_id: UUID # Should likely be inferred from authenticated user
    raw_text_input: str

class DailyReportUpdate(BaseModel):
    raw_text_input: Optional[str] = None
    clarified_tasks_summary: Optional[str] = None
    ai_analysis: Optional[AiAnalysis] = None
    linked_commit_ids: Optional[List[str]] = None # Or List[UUID] if they are commit table PKs
    overall_assessment_notes: Optional[str] = None
    final_estimated_hours: Optional[float] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Timezone-aware
    # Config class removed as it's often not needed for Update models unless specific features are used