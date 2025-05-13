from fastapi import APIRouter, Depends, HTTPException, status, Path
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime, timedelta
import logging
from decimal import Decimal

from app.models.commit import Commit # Assuming Commit model exists
from app.models.daily_report import DailyReport, AiAnalysis # Assuming DailyReport model exists
from app.models.user import User # Assuming User model exists
from app.dependencies import get_current_user, get_commit_repository, get_daily_report_repository
from app.repositories.commit_repository import CommitRepository
from app.repositories.daily_report_repository import DailyReportRepository
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Response Models ---

class CommitSummary(BaseModel):
    commit_hash: str
    commit_message: Optional[str] = None
    ai_estimated_hours: Optional[Decimal] = None
    seniority_score: Optional[int] = None
    commit_timestamp: datetime
    
    class Config:
        from_attributes = True

class DeveloperDailySummary(BaseModel):
    user_id: UUID
    report_date: date
    total_estimated_hours: Decimal = Field(decimal_places=1, default=Decimal(0.0))
    commit_estimated_hours: Decimal = Field(decimal_places=1, default=Decimal(0.0))
    eod_estimated_hours: Decimal = Field(decimal_places=1, default=Decimal(0.0))
    average_seniority_score: Optional[float] = None
    commit_count: int = 0
    individual_commits: List[CommitSummary] = []
    eod_summary: Optional[str] = None
    low_seniority_flag: bool = False
    
    class Config:
        from_attributes = True
        json_encoders = {
            # Handles Decimal serialization
            Decimal: lambda v: float(round(v, 1)) if v is not None else None,
            # Handles date serialization
            date: lambda v: v.isoformat() if v is not None else None,
        }

# --- API Endpoint ---

@router.get(
    "/developer/{user_id}/daily_summary/{report_date_str}",
    response_model=DeveloperDailySummary,
    summary="Get Developer Daily Summary",
    description="Retrieves aggregated commit and EOD report data for a specific developer and date."
)
async def get_developer_daily_summary(
    user_id: UUID = Path(..., description="The ID of the user to retrieve the summary for."),
    report_date_str: str = Path(..., description="The date for the summary in YYYY-MM-DD format."),
    current_user: User = Depends(get_current_user),
    commit_repo: CommitRepository = Depends(get_commit_repository),
    report_repo: DailyReportRepository = Depends(get_daily_report_repository)
) -> DeveloperDailySummary:
    """
    Calculates and returns a daily summary for a developer, combining commit analysis
    and EOD report data.
    """
    # Authorization check: Ensure the current user is the requested user or an admin/manager
    # TODO: Implement proper role-based access control
    if current_user.id != user_id and current_user.role not in ["admin", "manager"]:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Not authorized to view this user's summary."
         )

    try:
        report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use YYYY-MM-DD.")

    # Define the date range for the query (start of day to end of day UTC)
    start_datetime = datetime.combine(report_date, datetime.min.time())
    # Add almost one full day to include everything on the report_date
    end_datetime = start_datetime + timedelta(days=1, microseconds=-1) 
    
    logger.info(f"Fetching data for user {user_id} on {report_date_str} ({start_datetime} to {end_datetime})")

    # 1. Fetch Commits for the user and date range
    commits: List[Commit] = await commit_repo.get_commits_by_user_and_date_range(user_id, start_datetime, end_datetime)
    
    # 2. Fetch EOD Report for the user and date
    # Assuming get_daily_reports_by_user_and_date expects a datetime object for the specific day
    eod_report: Optional[DailyReport] = await report_repo.get_daily_reports_by_user_and_date(user_id, start_datetime) 
    
    # --- Calculations ---
    commit_hours = Decimal(0.0)
    total_seniority = 0
    valid_seniority_commits = 0
    commit_summaries: List[CommitSummary] = []

    for commit in commits:
        commit_hours += commit.ai_estimated_hours if commit.ai_estimated_hours else Decimal(0.0)
        if commit.seniority_score is not None:
            total_seniority += commit.seniority_score
            valid_seniority_commits += 1
        commit_summaries.append(CommitSummary.model_validate(commit)) # Use Pydantic v2 validation

    avg_seniority = round(total_seniority / valid_seniority_commits, 1) if valid_seniority_commits > 0 else None
    
    eod_hours = Decimal(0.0)
    eod_summary = None
    if eod_report and eod_report.ai_analysis:
        # Use final_estimated_hours if available and non-null, otherwise fallback to ai_analysis.estimated_hours
        eod_hours_source = eod_report.final_estimated_hours if eod_report.final_estimated_hours is not None else \
                         eod_report.ai_analysis.estimated_hours
        eod_hours = Decimal(str(eod_hours_source)) if eod_hours_source is not None else Decimal(0.0)
        eod_summary = eod_report.ai_analysis.summary
        
    elif eod_report: # EOD report exists but no AI analysis
        eod_summary = eod_report.raw_text_input[:200] + ("..." if len(eod_report.raw_text_input) > 200 else "") # Show raw input snippet

    total_hours = commit_hours + eod_hours
    
    # Determine low seniority flag (e.g., average score < 4)
    low_seniority_flag = avg_seniority is not None and avg_seniority < 4.0

    summary = DeveloperDailySummary(
        user_id=user_id,
        report_date=report_date,
        total_estimated_hours=total_hours,
        commit_estimated_hours=commit_hours,
        eod_estimated_hours=eod_hours,
        average_seniority_score=avg_seniority,
        commit_count=len(commits),
        individual_commits=sorted(commit_summaries, key=lambda c: c.commit_timestamp, reverse=True), # Sort by time
        eod_summary=eod_summary,
        low_seniority_flag=low_seniority_flag
    )

    return summary

# TODO: Add this router to the main FastAPI app (e.g., in main.py or api/v1/api.py)
# Example: app.include_router(developer_insights_endpoints.router, prefix="/api/v1/insights", tags=["Developer Insights"]) 