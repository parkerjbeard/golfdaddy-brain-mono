from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class CommitAnalysisBase(BaseModel):
    """Base model for commit analysis"""
    commit_hash: str = Field(..., max_length=40)
    repository: str = Field(..., max_length=255)
    author_email: str = Field(..., max_length=255)
    author_name: Optional[str] = Field(None, max_length=255)
    commit_date: Optional[datetime] = None
    
    # Analysis results
    complexity_score: int = Field(..., ge=1, le=10)
    estimated_hours: float = Field(..., gt=0)
    risk_level: str = Field(..., pattern="^(low|medium|high)$")
    seniority_score: int = Field(..., ge=1, le=10)
    seniority_rationale: str
    key_changes: List[str] = Field(default_factory=list)
    
    # Files and changes
    files_changed: List[str] = Field(default_factory=list)
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    
    # Metadata
    analyzed_at: datetime
    model_used: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class CommitAnalysisCreate(CommitAnalysisBase):
    """Model for creating a new commit analysis"""
    pass


class CommitAnalysisUpdate(BaseModel):
    """Model for updating commit analysis"""
    complexity_score: Optional[int] = Field(None, ge=1, le=10)
    estimated_hours: Optional[float] = Field(None, gt=0)
    risk_level: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    seniority_score: Optional[int] = Field(None, ge=1, le=10)
    seniority_rationale: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class CommitAnalysis(CommitAnalysisBase):
    """Model representing a commit analysis in the database"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CommitAnalysisWithStats(CommitAnalysis):
    """Extended model with statistics for API responses"""
    total_complexity: Optional[float] = None
    average_hours_per_file: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)