from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DailyCommitAnalysisBase(BaseModel):
    """Base model for daily commit analysis"""

    user_id: UUID
    analysis_date: date
    total_estimated_hours: Decimal = Field(..., decimal_places=2, max_digits=4)
    commit_count: int = Field(default=0, ge=0)
    daily_report_id: Optional[UUID] = None
    analysis_type: str = Field(..., pattern="^(with_report|automatic)$")

    # AI Analysis Results
    ai_analysis: Dict = Field(default_factory=dict)
    complexity_score: Optional[int] = Field(None, ge=1, le=10)
    seniority_score: Optional[int] = Field(None, ge=1, le=10)

    # Metadata
    repositories_analyzed: List[str] = Field(default_factory=list)
    total_lines_added: int = Field(default=0, ge=0)
    total_lines_deleted: int = Field(default=0, ge=0)

    model_config = ConfigDict(from_attributes=True)


class DailyCommitAnalysisCreate(DailyCommitAnalysisBase):
    """Model for creating a new daily commit analysis"""


class DailyCommitAnalysisUpdate(BaseModel):
    """Model for updating daily commit analysis"""

    total_estimated_hours: Optional[Decimal] = Field(None, decimal_places=2, max_digits=4)
    ai_analysis: Optional[Dict] = None
    complexity_score: Optional[int] = Field(None, ge=1, le=10)
    seniority_score: Optional[int] = Field(None, ge=1, le=10)

    model_config = ConfigDict(from_attributes=True)


class DailyCommitAnalysis(DailyCommitAnalysisBase):
    """Model representing a daily commit analysis in the database"""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyCommitAnalysisWithDetails(DailyCommitAnalysis):
    """Extended model with additional details for API responses"""

    user_name: Optional[str] = None
    daily_report_summary: Optional[str] = None
    commit_hashes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
