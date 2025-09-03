from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkItem(BaseModel):
    id: Optional[UUID] = None
    daily_analysis_id: Optional[UUID] = None
    item_type: str
    source: str
    source_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    loc_added: int = 0
    loc_removed: int = 0
    files_changed: int = 0
    estimated_hours: float = 0.0
    item_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_duplicate: Optional[bool] = None
    duplicate_of_id: Optional[UUID] = None
    ai_summary: Optional[str] = None
    ai_tags: Optional[List[str]] = None


class DeduplicationResult(BaseModel):
    id: Optional[UUID] = None
    daily_analysis_id: UUID
    item1_id: str
    item1_type: str
    item1_source: str
    item2_id: str
    item2_type: str
    item2_source: str
    is_duplicate: bool
    confidence_score: Optional[float] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None


class DailyWorkAnalysis(BaseModel):
    id: Optional[UUID] = None
    user_id: UUID
    analysis_date: date

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    total_work_items: int = 0
    total_commits: int = 0
    total_tickets: int = 0
    total_prs: int = 0

    total_loc_added: int = 0
    total_loc_removed: int = 0
    total_files_changed: int = 0

    total_estimated_hours: float = 0.0

    daily_summary: Optional[str] = None
    key_achievements: Optional[List[str]] = None
    technical_highlights: Optional[List[str]] = None
    work_items: Optional[List[Dict[str, Any]]] = None
    deduplication_results: Optional[List[Dict[str, Any]]] = None
    processing_status: Optional[str] = None
    processing_error: Optional[str] = None
    last_processed_at: Optional[datetime] = None
    data_sources: Optional[List[str]] = None

