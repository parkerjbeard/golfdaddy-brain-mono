from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PullRequest(BaseModel):
    """Represents a pull request analyzed for manager dashboards."""

    id: Optional[UUID] = Field(default=None, description="Primary key for the pull request record")
    pr_number: int = Field(..., description="Repository-specific pull request number")
    title: Optional[str] = Field(default=None, description="Title of the pull request")
    description: Optional[str] = Field(default=None, description="Body/description text for the pull request")
    author_id: Optional[UUID] = Field(default=None, description="User ID of the author in our system")
    author_github_username: Optional[str] = Field(default=None, description="GitHub username of the author")
    author_email: Optional[str] = Field(default=None, description="Email associated with the PR author")
    repository_name: Optional[str] = Field(default=None, description="Repository where the PR lives")
    repository_url: Optional[str] = Field(default=None, description="Repository URL")
    url: Optional[str] = Field(default=None, description="Direct URL to the pull request")
    status: str = Field(default="open", description="Lifecycle status (open, merged, closed)")
    opened_at: Optional[datetime] = Field(default=None, description="Timestamp when the PR was opened")
    closed_at: Optional[datetime] = Field(default=None, description="Timestamp when the PR was closed")
    merged_at: Optional[datetime] = Field(default=None, description="Timestamp when the PR was merged")
    activity_timestamp: Optional[datetime] = Field(
        default=None,
        description="Primary timestamp used for activity rollups (defaults to merged_at or opened_at)",
    )
    ai_estimated_hours: Optional[Decimal] = Field(default=None, description="AI estimated hours associated with the PR")
    ai_summary: Optional[str] = Field(default=None, description="AI generated summary for the PR")
    ai_prompts: Optional[List[str]] = Field(
        default=None, description="Prompts or manager nudges associated with this PR"
    )
    ai_analysis_notes: Optional[Dict[str, Any]] = Field(
        default=None, description="Structured AI analysis payload for the PR"
    )
    impact_score: Optional[float] = Field(default=None, description="Business impact score for the PR")
    impact_category: Optional[str] = Field(default=None, description="Impact category for normalization")
    review_comments: Optional[int] = Field(default=None, description="Count of review comments addressed")
    created_at: Optional[datetime] = Field(default=None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Record update timestamp")

    class Config:
        from_attributes = True
