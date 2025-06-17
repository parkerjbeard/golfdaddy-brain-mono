"""
Slack Conversation Handler for Daily Report interactions.

This service manages the conversational flow between the Slack bot and users
for daily report submission and clarification.
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta
import logging
import json

from app.services.slack_service import SlackService
from app.services.slack_message_templates import SlackMessageTemplates
from app.services.daily_report_service import DailyReportService
from app.services.user_service import UserService
from app.models.daily_report import DailyReportCreate, DailyReport
from app.models.user import User
from app.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class SlackConversationHandler:
    """Handles Slack conversation flows for daily reports."""
    
    def __init__(self):
        self.slack_service = SlackService()
        self.daily_report_service = DailyReportService()
        self.user_service = UserService()
        self.templates = SlackMessageTemplates()
        
    async def handle_eod_command(self, slack_user_id: str, channel_id: str, trigger_id: str) -> Dict[str, Any]:
        """
        Handle the /eod slash command.
        Opens a modal for report submission or shows existing report.
        """
        try:
            # Get user by Slack ID
            user = await self.user_service.get_user_by_slack_id(slack_user_id)
            if not user:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ Your Slack account is not linked to a GolfDaddy account. Please contact your administrator."
                }
            
            # Check if report already exists for today
            today_report = await self.daily_report_service.get_user_report_for_date(
                user.id, 
                datetime.utcnow()
            )
            
            if today_report:
                # Show existing report with option to update
                return {
                    "response_type": "ephemeral",
                    "blocks": self._build_existing_report_blocks(today_report, user)
                }
            
            # Open modal for new report
            modal_view = self._build_eod_modal(user)
            await self.slack_service.open_modal(trigger_id, modal_view)
            
            return {"response_type": "ephemeral", "text": "Opening EOD report form..."}
            
        except Exception as e:
            logger.error(f"Error handling /eod command: {e}", exc_info=True)
            return {
                "response_type": "ephemeral",
                "text": "❌ An error occurred. Please try again later."
            }
    
    async def handle_modal_submission(self, slack_user_id: str, view_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle EOD report modal submission.
        Creates the daily report and initiates AI processing.
        """
        try:
            # Extract report text from modal
            report_text = view_data["state"]["values"]["report_block"]["report_input"]["value"]
            
            # Get user
            user = await self.user_service.get_user_by_slack_id(slack_user_id)
            if not user:
                raise ResourceNotFoundError("User not found")
            
            # Create daily report
            report_create = DailyReportCreate(
                user_id=user.id,
                raw_text_input=report_text
            )
            
            # Submit report (includes AI analysis and deduplication)
            report = await self.daily_report_service.submit_daily_report(
                report_create,
                user.id
            )
            
            # Send DM with report summary
            dm_channel = await self.slack_service.open_dm(slack_user_id)
            if dm_channel:
                # Check if clarification is needed
                needs_clarification = bool(
                    report.ai_analysis and 
                    report.ai_analysis.clarification_requests
                )
                
                if needs_clarification:
                    # Send clarification request
                    clarification_message = self.templates.eod_clarification(
                        user_name=user.name,
                        report_id=str(report.id),
                        clarification_requests=report.ai_analysis.clarification_requests,
                        original_summary=report.ai_analysis.summary
                    )
                    
                    response = await self.slack_service.post_message(
                        channel=dm_channel,
                        **clarification_message
                    )
                    
                    # Store thread timestamp for conversation tracking
                    if response and response.get("ts"):
                        await self.daily_report_service.update_daily_report(
                            report.id,
                            {"slack_thread_ts": response["ts"], "slack_channel_id": dm_channel},
                            user.id
                        )
                else:
                    # Send summary without clarification
                    summary_message = self.templates.eod_summary(
                        user_name=user.name,
                        report_id=str(report.id),
                        summary=report.clarified_tasks_summary or report.raw_text_input[:200] + "...",
                        estimated_hours=report.final_estimated_hours or 0,
                        commit_hours=report.commit_hours or 0,
                        additional_hours=report.additional_hours or 0,
                        linked_commits=len(report.linked_commit_ids) if report.linked_commit_ids else 0
                    )
                    
                    await self.slack_service.post_message(
                        channel=dm_channel,
                        **summary_message
                    )
            
            return {"response_action": "clear"}
            
        except Exception as e:
            logger.error(f"Error handling modal submission: {e}", exc_info=True)
            return {
                "response_action": "errors",
                "errors": {
                    "report_block": "Failed to submit report. Please try again."
                }
            }
    
    async def handle_dm_message(self, slack_user_id: str, channel_id: str, message_text: str, thread_ts: Optional[str] = None) -> None:
        """
        Handle direct message from user for report clarification.
        """
        try:
            # Get user
            user = await self.user_service.get_user_by_slack_id(slack_user_id)
            if not user:
                await self.slack_service.post_message(
                    channel=channel_id,
                    text="I don't recognize your account. Please contact your administrator.",
                    thread_ts=thread_ts
                )
                return
            
            # Find report associated with this thread
            if thread_ts:
                # Look for report with this thread timestamp
                today_report = await self.daily_report_service.get_user_report_for_date(
                    user.id,
                    datetime.utcnow()
                )
                
                if today_report and today_report.slack_thread_ts == thread_ts:
                    # Handle clarification conversation
                    response = await self.daily_report_service.handle_slack_conversation(
                        today_report.id,
                        message_text,
                        thread_ts
                    )
                    
                    # Send response
                    await self.slack_service.post_message(
                        channel=channel_id,
                        text=response.get("response", "I understand. Let me update your report."),
                        thread_ts=thread_ts
                    )
                    
                    # If conversation is complete, send final summary
                    if response.get("conversation_complete"):
                        await self._send_final_summary(user, today_report, channel_id, thread_ts)
                    
                    return
            
            # No thread context - check if this is a new report submission
            if not thread_ts and len(message_text) > 50:  # Arbitrary length check
                # Treat as new report submission
                report_create = DailyReportCreate(
                    user_id=user.id,
                    raw_text_input=message_text
                )
                
                report = await self.daily_report_service.submit_daily_report(
                    report_create,
                    user.id
                )
                
                # Send acknowledgment
                await self.slack_service.post_message(
                    channel=channel_id,
                    text=f"✅ I've recorded your EOD report for today. "
                         f"Estimated hours: {report.final_estimated_hours or 0:.1f}"
                )
            else:
                # General help message
                await self.slack_service.post_message(
                    channel=channel_id,
                    text="Hi! You can submit your EOD report by:\n"
                         "• Using the `/eod` command\n"
                         "• Sending me a detailed message about what you worked on today\n"
                         "• Replying to my daily reminder"
                )
                
        except Exception as e:
            logger.error(f"Error handling DM message: {e}", exc_info=True)
            await self.slack_service.post_message(
                channel=channel_id,
                text="I encountered an error processing your message. Please try again.",
                thread_ts=thread_ts
            )
    
    async def handle_button_interaction(self, slack_user_id: str, action: Dict[str, Any], response_url: str) -> Dict[str, Any]:
        """
        Handle button interactions from Slack messages.
        """
        action_id = action.get("action_id", "")
        value = action.get("value", "")
        
        if action_id == "submit_eod":
            # Trigger EOD modal
            trigger_id = action.get("trigger_id")
            if trigger_id:
                return await self.handle_eod_command(slack_user_id, "", trigger_id)
                
        elif action_id == "update_report":
            # Handle report update
            report_id = value
            # Implementation for updating existing report
            pass
            
        return {"text": "Action received"}
    
    def _build_eod_modal(self, user: User) -> Dict[str, Any]:
        """Build the EOD report submission modal."""
        return {
            "type": "modal",
            "callback_id": "eod_report_submission",
            "title": {
                "type": "plain_text",
                "text": "End of Day Report"
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Hi {user.name}! Please share what you worked on today."
                    }
                },
                {
                    "type": "input",
                    "block_id": "report_block",
                    "label": {
                        "type": "plain_text",
                        "text": "What did you accomplish today?"
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "report_input",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "E.g., Completed user authentication feature, fixed bug in payment processing, attended team meeting..."
                        }
                    }
                }
            ],
            "submit": {
                "type": "plain_text",
                "text": "Submit Report"
            }
        }
    
    def _build_existing_report_blocks(self, report: DailyReport, user: User) -> List[Dict[str, Any]]:
        """Build blocks showing existing report with update option."""
        summary = report.clarified_tasks_summary or report.raw_text_input[:200] + "..."
        hours = report.final_estimated_hours or 0
        
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*You've already submitted a report for today:*\n\n{summary}\n\n"
                           f"*Estimated hours:* {hours:.1f}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Update Report"
                        },
                        "action_id": "update_report",
                        "value": str(report.id)
                    }
                ]
            }
        ]
    
    async def _send_final_summary(self, user: User, report: DailyReport, channel_id: str, thread_ts: str) -> None:
        """Send final summary after clarification conversation."""
        summary_message = self.templates.eod_summary(
            user_name=user.name,
            report_id=str(report.id),
            summary=report.clarified_tasks_summary or report.raw_text_input[:200] + "...",
            estimated_hours=report.final_estimated_hours or 0,
            commit_hours=report.commit_hours or 0,
            additional_hours=report.additional_hours or 0,
            linked_commits=len(report.linked_commit_ids) if report.linked_commit_ids else 0
        )
        
        # Add thread timestamp to keep in conversation
        summary_message["thread_ts"] = thread_ts
        
        await self.slack_service.post_message(
            channel=channel_id,
            **summary_message
        )