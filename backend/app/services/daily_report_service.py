from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, timezone
import logging

from app.models.daily_report import DailyReport, DailyReportCreate, DailyReportUpdate, AiAnalysis, ClarificationRequest
from app.models.commit import Commit
from app.repositories.daily_report_repository import DailyReportRepository
from app.repositories.commit_repository import CommitRepository
from app.integrations.ai_integration import AIIntegration # Added
from app.services.deduplication_service import DeduplicationService
# Removed circular import - will be injected
from app.core.exceptions import (
    DatabaseError, # For repository/DB issues
    AIIntegrationError, # If AI service fails explicitly
    ResourceNotFoundError, # If a report/user is not found when expected
    PermissionDeniedError, # For auth issues (though mostly handled by API layer)
    BadRequestError # For bad input data if not caught by Pydantic
) # New imports
# from app.services.user_service import UserService # Assuming a user service exists to validate user_id

logger = logging.getLogger(__name__)

class DailyReportService:
    def __init__(self):
        self.report_repository = DailyReportRepository()
        self.commit_repository = CommitRepository()
        self.ai_integration = AIIntegration() # Instantiate AIIntegration
        self.deduplication_service = DeduplicationService()
        self.daily_commit_analysis_service = None  # Will be injected to avoid circular import
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
        now = datetime.now(timezone.utc)
        existing_report = await self.report_repository.get_daily_reports_by_user_and_date(
            current_user_id, now
        )
        if existing_report:
            # For new submissions on the same day, return error
            # Updates should go through update_daily_report method
            raise BadRequestError(
                "A report for today already exists. Use the update functionality to add more details."
            )
        else:
            # Try to create the report with race condition handling
            try:
                new_report = await self.report_repository.create_daily_report(report_create_with_user)
            except DatabaseError as e:
                # Check if this is a unique constraint violation (race condition)
                error_msg = str(e).lower()
                if "duplicate key" in error_msg or "unique constraint" in error_msg or "unique_violation" in error_msg:
                    # Another request created the report at the same time
                    logger.warning(f"Race condition detected for user {current_user_id}, fetching existing report")
                    existing_report = await self.report_repository.get_daily_reports_by_user_and_date(
                        current_user_id, now
                    )
                    if existing_report:
                        # Return the existing report
                        return existing_report
                    else:
                        # Shouldn't happen, but handle gracefully
                        logger.error(f"Could not find report after unique constraint violation for user {current_user_id}")
                        raise DatabaseError("Failed to create or retrieve daily report due to concurrent access")
                else:
                    # Not a race condition, re-raise the error
                    raise

        # --- AI Processing ---
        # Process the new report with AI
        new_report = await self.process_report_with_ai(new_report)
        
        # Return the processed report
        return new_report

    async def get_report_by_id(self, report_id: UUID) -> Optional[DailyReport]:
        return await self.report_repository.get_daily_report_by_id(report_id)

    async def get_reports_for_user(self, user_id: UUID) -> List[DailyReport]:
        # TODO: Add pagination
        return await self.report_repository.get_daily_reports_by_user_id(user_id)
    
    async def get_reports_for_user_paginated(self, user_id: UUID, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """Get paginated daily reports for a specific user."""
        offset = (page - 1) * page_size
        
        # Get total count
        total_count = await self.report_repository.get_user_reports_count(user_id)
        
        # Get paginated reports
        reports = await self.report_repository.get_daily_reports_by_user_id_paginated(
            user_id=user_id,
            offset=offset,
            limit=page_size
        )
        
        # Calculate pagination metadata
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_previous = page > 1
        
        return {
            "items": reports,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_previous": has_previous
        }

    async def get_user_report_for_date(self, user_id: UUID, report_date: datetime, user_timezone: Optional[str] = None) -> Optional[DailyReport]:
        """
        Get a user's report for a specific date.
        
        Args:
            user_id: User's ID
            report_date: Date to check (should be timezone-aware)
            user_timezone: User's timezone string (e.g., 'America/Los_Angeles')
                         If provided, will convert the date to user's local date
        """
        if user_timezone:
            try:
                from zoneinfo import ZoneInfo
                # Convert to user's timezone to get the correct date
                user_tz = ZoneInfo(user_timezone)
                local_date = report_date.astimezone(user_tz)
                # Use the local date for lookup
                return await self.report_repository.get_daily_reports_by_user_and_date(user_id, local_date)
            except Exception as e:
                logger.warning(f"Failed to convert to user timezone {user_timezone}: {e}")
        
        return await self.report_repository.get_daily_reports_by_user_and_date(user_id, report_date)

    async def get_all_reports(self) -> List[DailyReport]:
        """Retrieves all daily reports. For admin use."""
        # TODO: Add pagination for admin view
        return await self.report_repository.get_all_daily_reports()
    
    async def get_all_reports_paginated(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """Get all daily reports with pagination. For admin use."""
        offset = (page - 1) * page_size
        
        # Get total count
        total_count = await self.report_repository.get_total_reports_count()
        
        # Get paginated reports
        reports = await self.report_repository.get_all_daily_reports_paginated(
            offset=offset,
            limit=page_size
        )
        
        # Calculate pagination metadata
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_previous = page > 1
        
        return {
            "items": reports,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_previous": has_previous
        }
    
    async def process_report_with_ai(self, report: DailyReport) -> DailyReport:
        """
        Process or re-process a report with AI analysis.
        Used for both new reports and updates.
        """
        try:
            logger.info(f"Performing AI analysis on EOD report {report.id}")
            ai_analysis_dict = await self.ai_integration.analyze_eod_report_text(report.raw_text_input)
            
            if ai_analysis_dict.get("error"):
                logger.error(f"AI analysis for EOD report {report.id} returned an error: {ai_analysis_dict.get('error')}")
                # Continue without AI analysis rather than failing
                return report
            
            # Convert AI response to our AiAnalysis model
            ai_analysis = AiAnalysis(
                estimated_hours=ai_analysis_dict.get("estimated_hours", 0),
                difficulty_level=ai_analysis_dict.get("difficulty_level", "medium"),
                key_achievements=ai_analysis_dict.get("key_achievements", []),
                blockers_challenges=ai_analysis_dict.get("blockers_challenges", []),
                sentiment_score=ai_analysis_dict.get("sentiment_score", 0.5),
                clarification_requests=ai_analysis_dict.get("clarification_requests", []),
                summary=ai_analysis_dict.get("summary", "")
            )
            
            # Update the report with AI analysis
            update_data = DailyReportUpdate(
                ai_analysis=ai_analysis,
                clarified_tasks_summary=ai_analysis_dict.get("summary", report.raw_text_input[:200]),
                final_estimated_hours=ai_analysis.estimated_hours
            )
            
            updated_report = await self.report_repository.update_daily_report(report.id, update_data)
            if not updated_report:
                logger.error(f"Failed to update report {report.id} with AI analysis")
                return report
            
            return updated_report
            
        except Exception as e:
            logger.error(f"AI analysis failed for report {report.id}: {e}", exc_info=True)
            # Return original report on failure
            return report

    async def update_daily_report(self, report_id: UUID, report_data: DailyReportUpdate, user_id: UUID) -> Optional[DailyReport]:
        """
        Updates an existing daily report. Ensures the user owns the report.
        Called by user-facing update endpoint.
        """
        report_to_update = await self.report_repository.get_daily_report_by_id(report_id)
        if not report_to_update:
            return None # Report not found
        if report_to_update.user_id != user_id:
            # This check is also in the endpoint, but good for service layer integrity
            logger.warning(f"User {user_id} attempted to update report {report_id} owned by {report_to_update.user_id}")
            return None # Or raise an authorization error
        
        # Ensure updated_at is set
        if report_data.updated_at is None:
            report_data.updated_at = datetime.utcnow()
            
        return await self.report_repository.update_daily_report(report_id, report_data)

    async def delete_daily_report(self, report_id: UUID, user_id: UUID) -> bool:
        """
        Deletes a daily report. Ensures the user owns the report.
        Returns True if deletion was successful, False otherwise.
        """
        report_to_delete = await self.report_repository.get_daily_report_by_id(report_id)
        if not report_to_delete:
            return False # Report not found
        if report_to_delete.user_id != user_id:
            # Also checked in endpoint
            logger.warning(f"User {user_id} attempted to delete report {report_id} owned by {report_to_delete.user_id}")
            return False # Or raise an authorization error

        return await self.report_repository.delete_daily_report(report_id)

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
    
    async def get_weekly_hours_summary(self, user_id: UUID, week_start: datetime) -> Dict[str, Any]:
        """
        Get a comprehensive weekly hours summary for a user, combining commits and daily reports.
        Uses the deduplication service to ensure accurate hour counting.
        """
        week_end = week_start + timedelta(days=7)
        
        # Get all daily reports for the week
        daily_reports = []
        for day_offset in range(7):
            date = week_start + timedelta(days=day_offset)
            report = await self.report_repository.get_daily_reports_by_user_and_date(user_id, date)
            if report:
                daily_reports.append(report)
        
        # Get all commits for the week
        commits = await self.commit_repository.get_commits_by_user_id(
            user_id,
            start_date=week_start,
            end_date=week_end
        )
        
        # Use deduplication service to get weekly aggregate
        return await self.deduplication_service.get_weekly_aggregate(
            user_id,
            week_start,
            week_end,
            daily_reports,
            commits
        )
    
    async def get_reports_with_pending_clarifications(self) -> List[DailyReport]:
        """
        Get all reports that have pending clarification requests.
        """
        # This would ideally be a database query, but for now we'll filter in memory
        all_reports = await self.report_repository.get_all_daily_reports(limit=1000)
        
        pending_reports = []
        for report in all_reports:
            if report.conversation_state:
                status = report.conversation_state.get("status")
                if status == "awaiting_clarification":
                    pending_reports.append(report)
                    
        return pending_reports
    
    async def handle_slack_conversation(self, report_id: UUID, user_message: str, slack_thread_ts: str) -> Dict[str, Any]:
        """
        Handle ongoing Slack conversation for daily report clarification.
        Returns response to send back to Slack.
        """
        report = await self.get_report_by_id(report_id)
        if not report:
            return {
                "error": "Report not found",
                "message": "I couldn't find the report you're referring to."
            }
        
        # Update conversation state
        conversation_state = report.conversation_state or {}
        conversation_state["last_user_message"] = user_message
        conversation_state["last_interaction"] = datetime.utcnow().isoformat()
        
        # Process with AI
        try:
            ai_response = await self.ai_integration.process_eod_clarification(
                original_report=report.raw_text_input,
                user_message=user_message,
                conversation_history=conversation_state.get("history", [])
            )
            
            # Update conversation history
            if "history" not in conversation_state:
                conversation_state["history"] = []
            conversation_state["history"].append({
                "user": user_message,
                "ai": ai_response.get("response", ""),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Update report with new conversation state and any extracted information
            update_data = DailyReportUpdate(
                conversation_state=conversation_state,
                slack_thread_ts=slack_thread_ts
            )
            
            # If AI extracted new information, update the report
            if ai_response.get("updated_summary"):
                update_data.clarified_tasks_summary = ai_response["updated_summary"]
            if ai_response.get("updated_hours") is not None:
                update_data.final_estimated_hours = ai_response["updated_hours"]
                
            await self.report_repository.update_daily_report(report_id, update_data)
            
            return {
                "response": ai_response.get("response", "I understand. Let me update your report."),
                "needs_more_info": ai_response.get("needs_clarification", False),
                "conversation_complete": ai_response.get("conversation_complete", False)
            }
            
        except Exception as e:
            logger.error(f"Error processing Slack conversation for report {report_id}: {e}", exc_info=True)
            return {
                "error": "Processing error",
                "message": "I had trouble understanding that. Could you please rephrase?"
            }