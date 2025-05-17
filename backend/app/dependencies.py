from app.auth.dependencies import get_current_user
from app.repositories.commit_repository import CommitRepository
from app.repositories.daily_report_repository import DailyReportRepository


def get_commit_repository() -> CommitRepository:
    """Dependency to provide a CommitRepository instance."""
    return CommitRepository()


def get_daily_report_repository() -> DailyReportRepository:
    """Dependency to provide a DailyReportRepository instance."""
    return DailyReportRepository()

__all__ = [
    "get_current_user",
    "get_commit_repository",
    "get_daily_report_repository",
]
