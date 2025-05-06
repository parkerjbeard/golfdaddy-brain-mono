from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime

from app.models.daily_report import DailyReport, DailyReportCreate, DailyReportUpdate

# In-memory storage for now
_daily_reports_db: Dict[UUID, DailyReport] = {}

class DailyReportRepository:
    async def create_daily_report(self, report_create: DailyReportCreate) -> DailyReport:
        """Creates a new daily report and stores it."""
        report = DailyReport(**report_create.model_dump(), report_date=datetime.utcnow()) # Pydantic v2 uses model_dump()
        _daily_reports_db[report.id] = report
        return report

    async def get_daily_report_by_id(self, report_id: UUID) -> Optional[DailyReport]:
        """Retrieves a daily report by its ID."""
        return _daily_reports_db.get(report_id)

    async def get_daily_reports_by_user_id(self, user_id: UUID) -> List[DailyReport]:
        """Retrieves all daily reports for a specific user."""
        return [report for report in _daily_reports_db.values() if report.user_id == user_id]
    
    async def get_daily_reports_by_user_and_date(
        self, user_id: UUID, report_date: datetime
    ) -> Optional[DailyReport]:
        """Retrieves a daily report for a specific user and date."""
        for report in _daily_reports_db.values():
            if report.user_id == user_id and report.report_date.date() == report_date.date():
                return report
        return None

    async def update_daily_report(self, report_id: UUID, report_update: DailyReportUpdate) -> Optional[DailyReport]:
        """Updates an existing daily report."""
        report = await self.get_daily_report_by_id(report_id)
        if not report:
            return None
        
        update_data = report_update.model_dump(exclude_unset=True) # Pydantic v2 uses model_dump()
        for key, value in update_data.items():
            setattr(report, key, value)
        report.updated_at = datetime.utcnow()
        _daily_reports_db[report.id] = report
        return report

    async def delete_daily_report(self, report_id: UUID) -> bool:
        """Deletes a daily report by its ID."""
        if report_id in _daily_reports_db:
            del _daily_reports_db[report_id]
            return True
        return False

    async def get_all_daily_reports(self) -> List[DailyReport]:
        """Retrieves all daily reports (for admin/debugging purposes)."""
        return list(_daily_reports_db.values()) 