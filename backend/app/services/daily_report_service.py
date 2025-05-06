from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import logging

from app.models.daily_report import DailyReport, DailyReportCreate, DailyReportUpdate, AiAnalysis, ClarificationRequest
from app.repositories.daily_report_repository import DailyReportRepository
# from app.services.ai_integration_service import AiIntegrationService # To be created/enhanced
# from app.services.user_service import UserService # Assuming a user service exists to validate user_id

logger = logging.getLogger(__name__)

class DailyReportService:
    def __init__(self):
        self.report_repository = DailyReportRepository()
        # self.ai_service = AiIntegrationService() # Placeholder
        # self.user_service = UserService() # Placeholder

    async def submit_daily_report(self, report_data: DailyReportCreate, current_user_id: UUID) -> DailyReport:
        """
        Handles the submission of a new daily report.
        This includes initial AI processing for clarification, estimation.
        """
        # TODO: Validate user_id using UserService if report_data.user_id is from payload
        # For now, assume current_user_id is validated and authoritative
        report_create_with_user = DailyReportCreate(
            user_id=current_user_id, 
            raw_text_input=report_data.raw_text_input
        )

        # Check if a report for this user and date already exists
        existing_report = await self.report_repository.get_daily_reports_by_user_and_date(
            current_user_id, datetime.utcnow()
        )
        if existing_report:
            # Optionally, update the existing report or raise an error
            # For now, let's update
            logger.info(f"Updating existing daily report for user {current_user_id} on {datetime.utcnow().date()}")
            update_payload = DailyReportUpdate(raw_text_input=report_data.raw_text_input)
            updated_report = await self.report_repository.update_daily_report(existing_report.id, update_payload)
            if not updated_report: # Should not happen with in-memory repo if get succeeded
                 raise Exception("Failed to update existing report") # Or a more specific HTTP error
            new_report = updated_report
        else:
            new_report = await self.report_repository.create_daily_report(report_create_with_user)

        # --- AI Processing Placeholder ---
        try:
            # ai_processed_data: AiAnalysis = await self.ai_service.analyze_eod_report(new_report.raw_text_input)
            # For now, create a dummy AiAnalysis object
            dummy_ai_analysis = AiAnalysis(
                estimated_hours=None, # AI will fill this
                estimated_difficulty=None, # AI will fill this
                summary="AI processing pending for: " + new_report.raw_text_input[:50] + "...",
                clarification_requests=[] # AI might add clarification questions here
            )
            update_with_ai_data = DailyReportUpdate(
                ai_analysis=dummy_ai_analysis,
                clarified_tasks_summary=new_report.raw_text_input # Initially same, AI can refine
            )
            processed_report = await self.report_repository.update_daily_report(new_report.id, update_with_ai_data)
            if processed_report:
                return processed_report
            else: # Should not happen with in-memory store if ID is valid
                logger.error(f"Failed to update report {new_report.id} with AI data.")
                return new_report # Return the report without AI data if update fails

        except Exception as e:
            logger.error(f"Error during AI processing for report {new_report.id}: {e}")
            # Return the report without AI data if an error occurs
            return new_report
        # --- End AI Processing Placeholder ---

    async def get_report_by_id(self, report_id: UUID) -> Optional[DailyReport]:
        return await self.report_repository.get_daily_report_by_id(report_id)

    async def get_reports_for_user(self, user_id: UUID) -> List[DailyReport]:
        # TODO: Add pagination
        return await self.report_repository.get_daily_reports_by_user_id(user_id)

    async def get_user_report_for_date(self, user_id: UUID, report_date: datetime) -> Optional[DailyReport]:
        return await self.report_repository.get_daily_reports_by_user_and_date(user_id, report_date)

    async def update_report_assessment(self, report_id: UUID, assessment_notes: str, final_hours: float) -> Optional[DailyReport]:
        """Allows a manager or system to add overall assessment and final hours."""
        update_data = DailyReportUpdate(
            overall_assessment_notes=assessment_notes,
            final_estimated_hours=final_hours
        )
        return await self.report_repository.update_daily_report(report_id, update_data)

    async def link_commits_to_report(self, report_id: UUID, commit_ids: List[str]) -> Optional[DailyReport]:
        """Links commit IDs to a daily report."""
        report = await self.report_repository.get_daily_report_by_id(report_id)
        if not report:
            return None
        
        # Append new, unique commit_ids
        existing_commit_ids = set(report.linked_commit_ids or [])
        for cid in commit_ids:
            existing_commit_ids.add(cid)
        
        update_data = DailyReportUpdate(linked_commit_ids=list(existing_commit_ids))
        return await self.report_repository.update_daily_report(report_id, update_data)
    
    # TODO: Add method for AI to request clarification and for user to respond to clarifications.
    # This would involve updating the ClarificationRequest status and answer within the AiAnalysis field.