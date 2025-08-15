import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

# Added for the new UserWidgetSummary model
from pydantic import BaseModel

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.commit import Commit
from app.models.user import User, UserRole
from app.repositories.commit_repository import CommitRepository
from app.repositories.daily_report_repository import DailyReportRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


# New Pydantic Model for Widget Summary
class UserWidgetSummary(BaseModel):
    user_id: UUID
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    total_ai_estimated_commit_hours: float


class KpiService:
    """Service for calculating performance metrics."""

    def __init__(self):
        self.user_repo = UserRepository()
        self.commit_repo = CommitRepository()
        self.daily_report_repo = DailyReportRepository()

    def calculate_commit_metrics_for_user(
        self, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Calculates commit-based KPIs for a specific user in a date range."""
        commits = self.commit_repo.get_commits_by_user_in_range(user_id, start_date, end_date)

        total_commits = len(commits)
        total_hours = sum(float(c.ai_estimated_hours or 0) for c in commits)

        return {
            "user_id": user_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_commits": total_commits,
            "total_ai_estimated_hours": round(total_hours, 2),
        }

    def generate_weekly_kpis_for_user(self, user_id: UUID) -> Dict[str, Any]:
        """Generates a consolidated weekly KPI report for a user."""
        today = datetime.today()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        end_of_week = start_of_week + timedelta(days=6)  # Sunday

        commit_metrics = self.calculate_commit_metrics_for_user(user_id, start_of_week, end_of_week)

        # Combine metrics
        kpis = {
            "user_id": user_id,
            "week_start": start_of_week.isoformat(),
            "week_end": end_of_week.isoformat(),
            "commit_metrics": commit_metrics,
            # Add burndown or other KPIs as needed
        }
        logger.info(f"Generated weekly KPIs for user {user_id}")
        return kpis

    async def get_user_performance_summary(self, user_id: UUID, period_days: int = 7) -> Dict[str, Any]:
        """Generates a performance summary for a user over a specified period."""

        # Check if user exists first
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User with ID {user_id} not found. Cannot generate KPI summary.")
            raise ResourceNotFoundError(resource_name="User", resource_id=str(user_id))

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)

        logger.info(
            f"Generating performance summary for user {user_id} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}."
        )

        # 1. Fetch Daily Reports and sum final_estimated_hours
        daily_reports = await self.daily_report_repo.get_reports_by_user_and_date_range(user_id, start_date, end_date)

        total_eod_reported_hours = sum(dr.final_estimated_hours or 0.0 for dr in daily_reports)
        eod_report_details = [
            {
                "report_date": dr.report_date.strftime("%Y-%m-%d"),
                "reported_hours": dr.final_estimated_hours or 0.0,
                "ai_summary": dr.ai_analysis.summary if dr.ai_analysis else "N/A",
                "ai_estimated_hours": (
                    dr.ai_analysis.estimated_hours
                    if dr.ai_analysis and dr.ai_analysis.estimated_hours is not None
                    else 0.0
                ),
                "clarification_requests_count": len(dr.ai_analysis.clarification_requests) if dr.ai_analysis else 0,
            }
            for dr in daily_reports
        ]

        # 2. Fetch Commit-based metrics
        # Note: calculate_commit_metrics_for_user is synchronous, adjust if KpiService methods become async
        # For now, let's assume it's okay to call sync from async, or adapt it. Let's make it callable.
        # To call it, we need to pass datetime objects, not date objects if original method expects datetime.
        # The existing calculate_commit_metrics_for_user takes datetime. We have datetime for start_date and end_date.

        commits_in_period = await self.commit_repo.get_commits_by_user_in_range(
            user_id, start_date.date(), end_date.date()
        )

        total_commit_ai_estimated_hours = sum(float(c.ai_estimated_hours or 0.0) for c in commits_in_period)
        total_commits = len(commits_in_period)

        seniority_scores = [c.seniority_score for c in commits_in_period if c.seniority_score is not None]
        average_seniority_score = sum(seniority_scores) / len(seniority_scores) if seniority_scores else 0.0

        all_comparison_notes = []
        for commit in commits_in_period:
            if commit.comparison_notes:
                all_comparison_notes.append(
                    {
                        "commit_hash": commit.commit_hash,
                        "commit_timestamp": commit.commit_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "notes": commit.comparison_notes,
                    }
                )

        return {
            "user_id": str(user_id),
            "period_start_date": start_date.isoformat(),
            "period_end_date": end_date.isoformat(),
            "total_eod_reported_hours": round(total_eod_reported_hours, 2),
            "eod_report_details": eod_report_details,
            "total_commits_in_period": total_commits,
            "total_commit_ai_estimated_hours": round(total_commit_ai_estimated_hours, 2),
            "average_commit_seniority_score": round(average_seniority_score, 2),
            "commit_comparison_insights": all_comparison_notes,
            # Could add task velocity here too if desired by calling self.calculate_task_velocity
        }

    async def get_bulk_widget_summaries(
        self, start_date_dt: datetime, end_date_dt: datetime
    ) -> List[UserWidgetSummary]:
        """
        Generates widget summaries (total AI estimated commit hours) for relevant users
        within a specified date range.
        """
        # Fetch users (e.g., developers). Adjust role or fetching logic as needed.
        # Consider if this should fetch users managed by a specific manager if auth context is available.
        # For simplicity, fetching all users with EMPLOYEE role.
        try:
            # Assuming user_repo is UserRepository instance
            relevant_users: List[User] = await self.user_repo.list_users_by_role(UserRole.EMPLOYEE)
            if not relevant_users:
                logger.info("No users found for bulk widget summaries.")
                return []
        except Exception as e:
            logger.error(f"Error fetching users for bulk summaries: {e}", exc_info=True)
            # Depending on desired behavior, could raise or return empty. Let's return empty.
            return []

        widget_summaries: List[UserWidgetSummary] = []

        # Convert datetimes to date objects for commit_repo if it expects dates
        # The existing get_user_performance_summary passes .date() to commit_repo
        query_start_date: date = start_date_dt.date()
        query_end_date: date = end_date_dt.date()

        for user in relevant_users:
            try:
                # Fetch commits for the user within the date range
                # Assuming commit_repo.get_commits_by_user_in_range is synchronous
                # If it becomes async, use 'await'
                # If it's CPU-bound or blocking I/O, consider asyncio.to_thread
                commits: List[Commit] = await self.commit_repo.get_commits_by_user_in_range(
                    user.id, query_start_date, query_end_date
                )

                total_hours = sum(float(c.ai_estimated_hours or 0.0) for c in commits)

                widget_summaries.append(
                    UserWidgetSummary(
                        user_id=user.id,
                        name=user.name,
                        avatar_url=user.avatar_url,
                        total_ai_estimated_commit_hours=round(total_hours, 2),
                    )
                )
            except Exception as e:
                logger.error(f"Error processing widget summary for user {user.id}: {e}", exc_info=True)
                # Optionally, append a summary with an error or default values, or skip this user
                # For now, skipping the user if an error occurs for them.
                continue  # Skip to the next user

        logger.info(f"Generated {len(widget_summaries)} bulk widget summaries.")
        return widget_summaries

    # Add methods for team KPIs, burndown charts, etc.
