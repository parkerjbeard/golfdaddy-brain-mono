from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
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
                 logger.error(f"Failed to update existing report {existing_report.id} for user {current_user_id} which was previously found.")
                 raise DatabaseError(f"Failed to update existing report {existing_report.id} after it was found.")
            new_report = updated_report
        else:
            new_report = await self.report_repository.create_daily_report(report_create_with_user)

        # --- AI Processing ---
        try:
            logger.info(f"Performing AI analysis on EOD report {new_report.id} for user {current_user_id}")
            ai_analysis_dict = await self.ai_integration.analyze_eod_report_text(new_report.raw_text_input)
            
            if ai_analysis_dict.get("error"):
                logger.error(f"AI analysis for EOD report {new_report.id} returned an error: {ai_analysis_dict.get('error')}")
                # Create a default AiAnalysis object with the error message
                ai_analysis_obj = AiAnalysis(
                    summary=f"AI analysis failed: {ai_analysis_dict.get('error')}",
                    clarification_requests=[],
                    estimated_hours=0.0
                )
                clarified_summary_for_update = f"AI analysis failed: {ai_analysis_dict.get('error')}"
                final_hours_for_update = 0.0
            else:
                # Convert clarification request dicts to ClarificationRequest objects
                parsed_clarification_requests = []
                for req_data in ai_analysis_dict.get("clarification_requests", []):
                    try:
                        parsed_clarification_requests.append(ClarificationRequest(**req_data))
                    except Exception as p_err:
                        logger.warning(f"Could not parse clarification request item for report {new_report.id}: {req_data}. Error: {p_err}", exc_info=True)
                
                ai_analysis_obj = AiAnalysis(
                    estimated_hours=ai_analysis_dict.get('estimated_hours', 0.0),
                    estimated_difficulty=ai_analysis_dict.get('estimated_difficulty'),
                    summary=ai_analysis_dict.get('summary'),
                    sentiment=ai_analysis_dict.get('sentiment'),
                    key_achievements=ai_analysis_dict.get('key_achievements', []),
                    potential_blockers=ai_analysis_dict.get('potential_blockers', []),
                    clarification_requests=parsed_clarification_requests
                )
                clarified_summary_for_update = ai_analysis_obj.summary
                final_hours_for_update = ai_analysis_obj.estimated_hours

            update_with_ai_data = DailyReportUpdate(
                ai_analysis=ai_analysis_obj,
                clarified_tasks_summary=clarified_summary_for_update, # Initially AI summary, can be refined
                final_estimated_hours=final_hours_for_update # Set final_estimated_hours from AI analysis
            )
            
            processed_report = await self.report_repository.update_daily_report(new_report.id, update_with_ai_data)
            if processed_report:
                logger.info(f"Successfully processed and updated EOD report {new_report.id} with AI analysis.")
                
                # --- Deduplication Processing ---
                try:
                    # Get user's commits from the same day
                    report_date = processed_report.report_date or datetime.utcnow().date()
                    start_of_day = datetime.combine(report_date, datetime.min.time())
                    end_of_day = start_of_day + timedelta(days=1)
                    
                    user_commits = await self.commit_repository.get_commits_by_user_id(
                        current_user_id,
                        start_date=start_of_day,
                        end_date=end_of_day
                    )
                    
                    # Run deduplication
                    logger.info(f"Running deduplication for report {processed_report.id} with {len(user_commits)} commits")
                    deduplicated_report = await self.deduplication_service.deduplicate_daily_report(
                        processed_report, 
                        user_commits
                    )
                    
                    # Update report with deduplication results
                    dedup_update = DailyReportUpdate(
                        deduplication_results=deduplicated_report.deduplication_results,
                        confidence_scores=deduplicated_report.confidence_scores,
                        commit_hours=deduplicated_report.commit_hours,
                        additional_hours=deduplicated_report.additional_hours,
                        linked_commit_ids=[c.sha for c in user_commits] if user_commits else []
                    )
                    
                    final_report = await self.report_repository.update_daily_report(processed_report.id, dedup_update)
                    if final_report:
                        logger.info(f"Successfully deduplicated report {processed_report.id}. "
                                  f"Commit hours: {final_report.commit_hours}, "
                                  f"Additional hours: {final_report.additional_hours}")
                        
                        # --- Daily Commit Analysis ---
                        try:
                            if self.daily_commit_analysis_service:
                                logger.info(f"Triggering daily commit analysis for report {final_report.id}")
                                daily_analysis = await self.daily_commit_analysis_service.analyze_for_report(
                                    user_id=current_user_id,
                                    report_date=report_date,
                                    daily_report=final_report
                                )
                                logger.info(f"Daily commit analysis completed: {daily_analysis.total_estimated_hours} hours")
                            else:
                                # Import here to avoid circular dependency
                                from app.services.daily_commit_analysis_service import DailyCommitAnalysisService
                                analysis_service = DailyCommitAnalysisService()
                                logger.info(f"Triggering daily commit analysis for report {final_report.id}")
                                daily_analysis = await analysis_service.analyze_for_report(
                                    user_id=current_user_id,
                                    report_date=report_date,
                                    daily_report=final_report
                                )
                                logger.info(f"Daily commit analysis completed: {daily_analysis.total_estimated_hours} hours")
                        except Exception as analysis_error:
                            logger.error(f"Error during daily commit analysis: {analysis_error}", exc_info=True)
                            # Continue without daily analysis if it fails
                        # --- End Daily Commit Analysis ---
                        
                        return final_report
                    else:
                        logger.error(f"Failed to update report {processed_report.id} with deduplication results")
                        return processed_report
                        
                except Exception as dedup_error:
                    logger.error(f"Error during deduplication for report {processed_report.id}: {dedup_error}", exc_info=True)
                    # Continue without deduplication if it fails
                    return processed_report
                # --- End Deduplication Processing ---
                
            else: 
                logger.error(f"Failed to update report {new_report.id} with AI data after successful AI analysis. Returning report without this AI update.", exc_info=True)
                # Fallback: return the report as it was before this update attempt, but with AI data attached if possible
                # This situation implies a repository save error, so the original new_report is more accurate to DB state.
                # However, the AI analysis *was* done. For now, log and return original to reflect DB.
                return new_report 

        except Exception as e:
            logger.error(f"Error during AI processing or update for report {new_report.id}: {e}", exc_info=True)
            # Return the report without AI data if a broader error occurs
            return new_report
        # --- End AI Processing ---

    async def get_report_by_id(self, report_id: UUID) -> Optional[DailyReport]:
        return await self.report_repository.get_daily_report_by_id(report_id)

    async def get_reports_for_user(self, user_id: UUID) -> List[DailyReport]:
        # TODO: Add pagination
        return await self.report_repository.get_daily_reports_by_user_id(user_id)

    async def get_user_report_for_date(self, user_id: UUID, report_date: datetime) -> Optional[DailyReport]:
        return await self.report_repository.get_daily_reports_by_user_and_date(user_id, report_date)

    async def get_all_reports(self) -> List[DailyReport]:
        """Retrieves all daily reports. For admin use."""
        # TODO: Add pagination for admin view
        return await self.report_repository.get_all_daily_reports()

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