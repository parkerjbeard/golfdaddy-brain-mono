"""
Slack Conversation Handler for Daily Report interactions.

This service manages the conversational flow between the Slack bot and users
for daily report submission and clarification.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.config.settings import settings
from app.core.exceptions import ResourceNotFoundError
from app.core.validators import DateValidator, ReportValidator
from app.models.daily_report import DailyReport, DailyReportCreate
from app.models.user import User
from app.services.daily_report_service import DailyReportService
from app.services.slack_message_templates import SlackMessageTemplates
from app.services.slack_service import SlackService
from app.services.unified_daily_analysis_service import UnifiedDailyAnalysisService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """Tracks the state of an active Slack conversation."""
    
    report_id: Optional[UUID]
    user_id: UUID
    thread_ts: str
    channel_id: str
    state: str
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class SlackConversationHandler:
    """Handles Slack conversation flows for daily reports."""

    def __init__(self):
        self.slack_service = SlackService()
        self.daily_report_service = DailyReportService()
        self.user_service = UserService()
        self.unified_analysis_service = UnifiedDailyAnalysisService()
        self.templates = SlackMessageTemplates()
        self.active_conversations: Dict[str, ConversationState] = {}

    async def _safe_send_message(
        self, channel: str, text: str, blocks: Optional[List[Dict[str, Any]]] = None, thread_ts: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Safely send a message with error handling.
        Returns None if sending fails.
        """
        try:
            return await self.slack_service.post_message(channel=channel, text=text, blocks=blocks, thread_ts=thread_ts)
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return None

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
                    "text": "❌ Your Slack account is not linked to a GolfDaddy account. Please contact your administrator.",
                }

            # Get user's timezone (default to EOD reminder timezone)
            user_timezone = self._get_user_timezone(user)

            # Check if report already exists for today (in user's timezone)
            today_report = await self.daily_report_service.get_user_report_for_date(
                user.id, datetime.now(timezone.utc), user_timezone
            )

            if today_report:
                # Show existing report with option to update
                # Check if we're still before midnight in user's timezone
                user_midnight = DateValidator.get_user_midnight_utc(
                    datetime.now(timezone.utc), user_timezone
                ) + timedelta(
                    days=1
                )  # Next midnight

                if datetime.now(timezone.utc) < user_midnight:
                    return {
                        "response_type": "ephemeral",
                        "blocks": self._build_existing_report_blocks(today_report, user, can_update=True),
                    }
                else:
                    return {
                        "response_type": "ephemeral",
                        "blocks": self._build_existing_report_blocks(today_report, user, can_update=False),
                    }

            # Open modal for new report
            modal_view = self._build_eod_modal(user)
            result = await self.slack_service.open_modal(trigger_id, modal_view)

            if result:
                return {"response_type": "ephemeral", "text": "Opening EOD report form..."}
            else:
                logger.error("Failed to open EOD modal")
                return {
                    "response_type": "ephemeral",
                    "text": "❌ Failed to open the report form. Please try again or send your report as a direct message.",
                }

        except Exception as e:
            logger.error(f"Error handling /eod command: {e}", exc_info=True)
            return {"response_type": "ephemeral", "text": "❌ An error occurred. Please try again later."}

    async def handle_modal_submission(self, slack_user_id: str, view_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle EOD report modal submission.
        Creates the daily report and initiates AI processing.
        """
        try:
            # Extract report text from modal
            report_text = view_data["state"]["values"]["report_block"]["report_input"]["value"]
            callback_id = view_data.get("callback_id", "")

            # Get user
            user = await self.user_service.get_user_by_slack_id(slack_user_id)
            if not user:
                raise ResourceNotFoundError("User not found")

            # Validate report content
            is_valid, errors = ReportValidator.validate_report_content(report_text)
            if not is_valid:
                return {"response_action": "errors", "errors": {"report_block": "\n".join(errors)}}

            # Sanitize content for AI processing
            sanitized_text = ReportValidator.sanitize_for_ai(report_text)

            # Handle update vs new report
            if callback_id == "eod_report_update":
                # Update existing report
                report_id = UUID(view_data.get("private_metadata", ""))

                # Get existing report and append new content
                existing_report = await self.daily_report_service.get_daily_report(report_id, user.id)

                if existing_report:
                    # Append new content with timestamp
                    timestamp = datetime.now(timezone.utc).strftime("%I:%M %p")
                    updated_text = f"{existing_report.raw_text_input}\n\n[Update {timestamp}]\n{sanitized_text}"

                    report = await self.daily_report_service.update_daily_report(
                        report_id, {"raw_text_input": updated_text}, user.id
                    )

                    # Re-process the report with AI
                    report = await self.daily_report_service.process_report_with_ai(report)
                else:
                    raise ResourceNotFoundError("Report not found")

            else:
                # Create new daily report
                report_create = DailyReportCreate(user_id=user.id, raw_text_input=sanitized_text)

                # Submit report (includes AI analysis and deduplication)
                report = await self.daily_report_service.submit_daily_report(report_create, user.id)

            # Trigger unified daily analysis after report submission
            try:
                analysis_date = (
                    report.report_date.date() if isinstance(report.report_date, datetime) else report.report_date
                )
                unified_analysis = await self.unified_analysis_service.analyze_daily_work(
                    user_id=user.id,
                    analysis_date=analysis_date,
                    force_reanalysis=True,  # Force reanalysis to include the new report
                )
                logger.info(
                    f"Unified analysis completed for user {user.id} with {unified_analysis.total_estimated_hours} total hours"
                )
            except Exception as e:
                logger.error(f"Failed to run unified analysis: {e}", exc_info=True)
                # Don't fail the report submission if analysis fails
                unified_analysis = None

            # Send DM with report summary
            dm_channel = await self.slack_service.open_dm(slack_user_id)
            if not dm_channel:
                logger.error(f"Failed to open DM channel for user {slack_user_id}")
                # Report was saved successfully, so still return success
                return {"response_action": "clear"}

            if dm_channel:
                # Send initial confirmation message
                confirm_message = await self._safe_send_message(
                    channel=dm_channel, text=f"✅ I've received your EOD report for today, {user.name}!"
                )

                if not confirm_message or not confirm_message.get("ts"):
                    logger.error(f"Failed to send confirmation message to user {slack_user_id}")
                    return {"response_action": "clear"}

                # Store the thread timestamp for all subsequent messages
                thread_ts = confirm_message["ts"]

                # Update report with Slack info
                await self.daily_report_service.update_daily_report(
                    report.id,
                    {
                        "slack_thread_ts": thread_ts,
                        "slack_channel_id": dm_channel,
                        "conversation_state": {
                            "status": "initiated",
                            "initiated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    },
                    user.id,
                )

                # Check if clarification is needed using AI integration
                clarification_check = await self.daily_report_service.ai_integration.check_if_clarification_needed(
                    report.raw_text_input, report.ai_analysis.model_dump() if report.ai_analysis else {}
                )

                if clarification_check.get("needs_clarification"):
                    # Send single clarification request in the same thread
                    clarification_text = (
                        f"I have one quick question about your report:\n\n"
                        f"_{clarification_check['clarification_question']}_\n\n"
                        f"Please reply in this thread with your clarification."
                    )

                    await self._safe_send_message(channel=dm_channel, text=clarification_text, thread_ts=thread_ts)

                    # Update conversation state
                    await self.daily_report_service.update_daily_report(
                        report.id,
                        {
                            "conversation_state": {
                                "status": "awaiting_clarification",
                                "initiated_at": datetime.now(timezone.utc).isoformat(),
                                "clarification_question": clarification_check["clarification_question"],
                                "original_text": clarification_check.get("original_text", ""),
                                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(),
                            }
                        },
                        user.id,
                    )
                else:
                    # No clarification needed - send summary in thread
                    # Include unified analysis results if available
                    if unified_analysis:
                        # Use unified analysis hours for more accurate total
                        total_hours = float(unified_analysis.total_estimated_hours)
                        # Calculate deduplicated hours (difference between simple sum and unified total)
                        simple_sum = (report.commit_hours or 0) + (report.additional_hours or 0)
                        deduplication_savings = max(0, simple_sum - total_hours)

                        summary_message = self.templates.eod_summary(
                            user_name=user.name,
                            report_id=str(report.id),
                            summary=report.clarified_tasks_summary or report.raw_text_input[:200] + "...",
                            estimated_hours=total_hours,  # Use unified analysis total
                            commit_hours=report.commit_hours or 0,
                            additional_hours=report.additional_hours or 0,
                            linked_commits=len(report.linked_commit_ids) if report.linked_commit_ids else 0,
                        )

                        # Add unified analysis block if there was deduplication
                        if deduplication_savings > 0:
                            summary_message["blocks"].append({"type": "divider"})
                            summary_message["blocks"].append(
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": f"📊 *Unified Analysis:*\n• Total deduplicated hours: {total_hours:.1f}\n• Hours saved from deduplication: {deduplication_savings:.1f}\n• Work appears in both commits and report",
                                    },
                                }
                            )
                    else:
                        # Fallback to original calculation if unified analysis failed
                        summary_message = self.templates.eod_summary(
                            user_name=user.name,
                            report_id=str(report.id),
                            summary=report.clarified_tasks_summary or report.raw_text_input[:200] + "...",
                            estimated_hours=report.final_estimated_hours or 0,
                            commit_hours=report.commit_hours or 0,
                            additional_hours=report.additional_hours or 0,
                            linked_commits=len(report.linked_commit_ids) if report.linked_commit_ids else 0,
                        )

                    # Add thread_ts to keep in same thread
                    summary_message["thread_ts"] = thread_ts

                    await self.slack_service.post_message(channel=dm_channel, **summary_message)

                    # Update conversation state to completed
                    await self.daily_report_service.update_daily_report(
                        report.id,
                        {
                            "conversation_state": {
                                "status": "completed",
                                "completed_at": datetime.now(timezone.utc).isoformat(),
                            }
                        },
                        user.id,
                    )

            return {"response_action": "clear"}

        except Exception as e:
            logger.error(f"Error handling modal submission: {e}", exc_info=True)
            return {
                "response_action": "errors",
                "errors": {"report_block": "Failed to submit report. Please try again."},
            }

    async def handle_dm_message(
        self, slack_user_id: str, channel_id: str, message_text: str, thread_ts: Optional[str] = None
    ) -> None:
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
                    thread_ts=thread_ts,
                )
                return

            # Find report associated with this thread
            if thread_ts:
                # Look for report with this thread timestamp
                today_report = await self.daily_report_service.get_user_report_for_date(
                    user.id, datetime.now(timezone.utc), self._get_user_timezone(user)
                )

                if today_report and today_report.slack_thread_ts == thread_ts:
                    # Check if clarification has expired (48 hours)
                    conv_state = today_report.conversation_state or {}
                    expires_at_str = conv_state.get("expires_at")

                    if expires_at_str:
                        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                        if datetime.now(timezone.utc) > expires_at:
                            await self._safe_send_message(
                                channel=channel_id,
                                text="This clarification request has expired. Your report has been submitted as-is.",
                                thread_ts=thread_ts,
                            )
                            return

                    # Check if we're awaiting clarification
                    if conv_state.get("status") == "awaiting_clarification":
                        # Process the clarification
                        logger.info(f"Processing clarification for report {today_report.id}")

                        # Update report with clarification
                        clarified_text = (
                            f"{today_report.raw_text_input}\n\n"
                            f"[Clarification]\n"
                            f"Q: {conv_state.get('clarification_question', 'N/A')}\n"
                            f"A: {message_text}"
                        )

                        # Update report and re-process with AI
                        updated_report = await self.daily_report_service.update_daily_report(
                            today_report.id,
                            {
                                "raw_text_input": clarified_text,
                                "conversation_state": {
                                    "status": "completed",
                                    "completed_at": datetime.now(timezone.utc).isoformat(),
                                    "clarification_received": message_text,
                                },
                            },
                            user.id,
                        )

                        # Re-process with AI to get updated analysis
                        updated_report = await self.daily_report_service.process_report_with_ai(updated_report)

                        # Send confirmation
                        await self._safe_send_message(
                            channel=channel_id,
                            text="✅ Thank you for the clarification! I've updated your report.",
                            thread_ts=thread_ts,
                        )

                        # Send final summary in thread
                        await self._send_final_summary(user, updated_report, channel_id, thread_ts)
                    else:
                        # Not expecting clarification - treat as update if before midnight
                        await self._safe_send_message(
                            channel=channel_id,
                            text="I've already processed your report for today. If you need to add more details, please send them as a new message (not in this thread).",
                            thread_ts=thread_ts,
                        )

                    return

            # No thread context - check if this is a new report submission
            # Validate the message content first
            is_valid, validation_errors = ReportValidator.validate_report_content(message_text)

            if is_valid:
                # Get user's timezone
                user_timezone = self._get_user_timezone(user)

                # Check if user already has a report for today
                existing_report = await self.daily_report_service.get_user_report_for_date(
                    user.id, datetime.now(timezone.utc), user_timezone
                )

                # Sanitize content
                sanitized_text = ReportValidator.sanitize_for_ai(message_text)

                if existing_report:
                    # Check if we're still before midnight
                    user_midnight = DateValidator.get_user_midnight_utc(
                        datetime.now(timezone.utc), user_timezone
                    ) + timedelta(days=1)

                    if datetime.now(timezone.utc) < user_midnight:
                        # Append to existing report
                        timestamp = datetime.now(timezone.utc).strftime("%I:%M %p")
                        updated_text = f"{existing_report.raw_text_input}\n\n[Update {timestamp}]\n{sanitized_text}"

                        report = await self.daily_report_service.update_daily_report(
                            existing_report.id, {"raw_text_input": updated_text}, user.id
                        )

                        # Re-process with AI
                        report = await self.daily_report_service.process_report_with_ai(report)

                        # Trigger unified analysis after update
                        try:
                            analysis_date = (
                                report.report_date.date()
                                if isinstance(report.report_date, datetime)
                                else report.report_date
                            )
                            unified_analysis = await self.unified_analysis_service.analyze_daily_work(
                                user_id=user.id, analysis_date=analysis_date, force_reanalysis=True
                            )
                            total_hours = float(unified_analysis.total_estimated_hours)
                            simple_sum = (report.commit_hours or 0) + (report.additional_hours or 0)
                            deduplication_savings = max(0, simple_sum - total_hours)

                            if deduplication_savings > 0:
                                await self._safe_send_message(
                                    channel=channel_id,
                                    text=f"✅ I've updated your EOD report for today.\n"
                                    f"📊 Unified Analysis: {total_hours:.1f} total hours "
                                    f"({deduplication_savings:.1f} hours deduplicated)",
                                )
                            else:
                                await self._safe_send_message(
                                    channel=channel_id,
                                    text=f"✅ I've updated your EOD report for today. "
                                    f"Total estimated hours: {total_hours:.1f}",
                                )
                        except Exception as e:
                            logger.error(f"Failed to run unified analysis after DM update: {e}")
                            await self._safe_send_message(
                                channel=channel_id,
                                text=f"✅ I've updated your EOD report for today. "
                                f"Total estimated hours: {report.final_estimated_hours or 0:.1f}",
                            )
                    else:
                        await self._safe_send_message(
                            channel=channel_id,
                            text="❌ It's past midnight in your timezone. Please submit a new report for today.",
                        )
                else:
                    # Create new report
                    report_create = DailyReportCreate(user_id=user.id, raw_text_input=sanitized_text)

                    report = await self.daily_report_service.submit_daily_report(report_create, user.id)

                    # Trigger unified analysis for new report
                    try:
                        analysis_date = (
                            report.report_date.date()
                            if isinstance(report.report_date, datetime)
                            else report.report_date
                        )
                        unified_analysis = await self.unified_analysis_service.analyze_daily_work(
                            user_id=user.id, analysis_date=analysis_date, force_reanalysis=True
                        )
                        total_hours = float(unified_analysis.total_estimated_hours)
                        simple_sum = (report.commit_hours or 0) + (report.additional_hours or 0)
                        deduplication_savings = max(0, simple_sum - total_hours)

                        if deduplication_savings > 0:
                            await self._safe_send_message(
                                channel=channel_id,
                                text=f"✅ I've recorded your EOD report for today.\n"
                                f"📊 Unified Analysis: {total_hours:.1f} total hours "
                                f"({deduplication_savings:.1f} hours deduplicated)",
                            )
                        else:
                            await self._safe_send_message(
                                channel=channel_id,
                                text=f"✅ I've recorded your EOD report for today. "
                                f"Estimated hours: {total_hours:.1f}",
                            )
                    except Exception as e:
                        logger.error(f"Failed to run unified analysis after DM submission: {e}")
                        await self._safe_send_message(
                            channel=channel_id,
                            text=f"✅ I've recorded your EOD report for today. "
                            f"Estimated hours: {report.final_estimated_hours or 0:.1f}",
                        )
            else:
                # Send validation errors or help message
                if len(message_text) < 20:
                    # Too short, show help
                    await self._safe_send_message(
                        channel=channel_id,
                        text="Hi! You can submit your EOD report by:\n"
                        "• Using the `/eod` command\n"
                        "• Sending me a detailed message about what you worked on today\n"
                        "• Replying to my daily reminder\n\n"
                        "Your report should describe the work you completed today.",
                    )
                else:
                    # Show specific validation errors
                    error_text = "❌ I couldn't process your report:\n\n"
                    for error in validation_errors:
                        error_text += f"• {error}\n"
                    error_text += "\nPlease provide more details about your work activities today."

                    await self._safe_send_message(channel=channel_id, text=error_text)

        except Exception as e:
            logger.error(f"Error handling DM message: {e}", exc_info=True)
            # Try to send error message, but don't fail if it doesn't work
            await self._safe_send_message(
                channel=channel_id,
                text="I encountered an error processing your message. Please try again.",
                thread_ts=thread_ts,
            )

    async def handle_button_interaction(
        self, slack_user_id: str, action: Dict[str, Any], response_url: str
    ) -> Dict[str, Any]:
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

            try:
                # Get user
                user = await self.user_service.get_user_by_slack_id(slack_user_id)
                if not user:
                    return {"text": "❌ User not found"}

                # Open modal for report update
                trigger_id = action.get("trigger_id")
                if trigger_id:
                    # Get existing report to pre-fill the modal
                    report = await self.daily_report_service.get_report_by_id(UUID(report_id))

                    if report:
                        modal_view = self._build_update_report_modal(user, report)
                        await self.slack_service.open_modal(trigger_id, modal_view)
                        return {"text": "Opening report update form..."}
                    else:
                        return {"text": "❌ Report not found"}
                else:
                    return {"text": "❌ Unable to open update form"}

            except Exception as e:
                logger.error(f"Error handling report update: {e}")
                return {"text": "❌ An error occurred"}

        return {"text": "Action received"}

    def _build_eod_modal(self, user: User) -> Dict[str, Any]:
        """Build the EOD report submission modal."""
        return {
            "type": "modal",
            "callback_id": "eod_report_submission",
            "title": {"type": "plain_text", "text": "End of Day Report"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"Hi {user.name}! Please share what you worked on today."},
                },
                {
                    "type": "input",
                    "block_id": "report_block",
                    "label": {"type": "plain_text", "text": "What did you accomplish today?"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "report_input",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "E.g., Completed user authentication feature, fixed bug in payment processing, attended team meeting...",
                        },
                    },
                },
            ],
            "submit": {"type": "plain_text", "text": "Submit Report"},
        }

    def _build_existing_report_blocks(
        self, report: DailyReport, user: User, can_update: bool = True
    ) -> List[Dict[str, Any]]:
        """Build blocks showing existing report with update option."""
        summary = report.clarified_tasks_summary or report.raw_text_input[:200] + "..."
        hours = report.final_estimated_hours or 0

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*You've already submitted a report for today:*\n\n{summary}\n\n"
                    f"*Estimated hours:* {hours:.1f}",
                },
            }
        ]

        if can_update:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Add More Details"},
                            "action_id": "update_report",
                            "value": str(report.id),
                            "style": "primary",
                        }
                    ],
                }
            )
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "_You can update your report until midnight in your timezone_"}
                    ],
                }
            )
        else:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": "_Report updates are closed after midnight_"}],
                }
            )

        return blocks

    async def _send_final_summary(self, user: User, report: DailyReport, channel_id: str, thread_ts: str) -> None:
        """Send final summary after clarification conversation."""
        # Try to get unified analysis for this report
        unified_analysis = None
        try:
            analysis_date = (
                report.report_date.date() if isinstance(report.report_date, datetime) else report.report_date
            )
            unified_analysis = await self.unified_analysis_service.analyze_daily_work(
                user_id=user.id, analysis_date=analysis_date, force_reanalysis=True
            )
        except Exception as e:
            logger.error(f"Failed to get unified analysis for final summary: {e}")

        if unified_analysis:
            total_hours = float(unified_analysis.total_estimated_hours)
            simple_sum = (report.commit_hours or 0) + (report.additional_hours or 0)
            deduplication_savings = max(0, simple_sum - total_hours)

            summary_message = self.templates.eod_summary(
                user_name=user.name,
                report_id=str(report.id),
                summary=report.clarified_tasks_summary or report.raw_text_input[:200] + "...",
                estimated_hours=total_hours,
                commit_hours=report.commit_hours or 0,
                additional_hours=report.additional_hours or 0,
                linked_commits=len(report.linked_commit_ids) if report.linked_commit_ids else 0,
            )

            if deduplication_savings > 0:
                summary_message["blocks"].append({"type": "divider"})
                summary_message["blocks"].append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"📊 *Unified Analysis:*\n• Total deduplicated hours: {total_hours:.1f}\n• Hours saved from deduplication: {deduplication_savings:.1f}\n• Work appears in both commits and report",
                        },
                    }
                )
        else:
            summary_message = self.templates.eod_summary(
                user_name=user.name,
                report_id=str(report.id),
                summary=report.clarified_tasks_summary or report.raw_text_input[:200] + "...",
                estimated_hours=report.final_estimated_hours or 0,
                commit_hours=report.commit_hours or 0,
                additional_hours=report.additional_hours or 0,
                linked_commits=len(report.linked_commit_ids) if report.linked_commit_ids else 0,
            )

        # Add thread timestamp to keep in conversation
        summary_message["thread_ts"] = thread_ts

        await self.slack_service.post_message(channel=channel_id, **summary_message)

    def _build_update_report_modal(self, user: User, report: DailyReport) -> Dict[str, Any]:
        """Build the modal for updating an existing EOD report."""
        return {
            "type": "modal",
            "callback_id": "eod_report_update",
            "private_metadata": str(report.id),  # Store report ID for update
            "title": {"type": "plain_text", "text": "Update EOD Report"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"Hi {user.name}! Update your report for today."},
                },
                {
                    "type": "input",
                    "block_id": "report_block",
                    "label": {"type": "plain_text", "text": "What did you accomplish today?"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "report_input",
                        "multiline": True,
                        "initial_value": report.raw_text_input,
                        "placeholder": {"type": "plain_text", "text": "Update your daily report..."},
                    },
                },
            ],
            "submit": {"type": "plain_text", "text": "Update Report"},
        }

    def _get_user_timezone(self, user: User) -> str:
        """Get user's timezone from preferences or use default."""
        if user.preferences:
            notification_prefs = user.preferences.get("notification", {})
            if "timezone" in notification_prefs:
                return notification_prefs["timezone"]
        return settings.EOD_REMINDER_TIMEZONE

    async def handle_preferences_command(self, slack_user_id: str, trigger_id: str) -> Dict[str, Any]:
        """Handle the /preferences slash command."""
        try:
            # Get user from Slack ID
            user = await self.user_service.get_user_by_slack_id(slack_user_id)
            if not user:
                return {"text": "❌ User not found. Please ensure your account is properly set up."}

            # Get current preferences
            preferences = user.preferences or {}
            notification_prefs = preferences.get("notification", {})

            # Build preferences modal
            modal = self._build_preferences_modal(user, notification_prefs)

            # Open the modal
            await self.slack_service.open_modal(trigger_id, modal)

            return {"response_type": "ephemeral"}

        except Exception as e:
            logger.exception(f"Error handling preferences command: {e}")
            return {"text": "❌ An error occurred. Please try again later."}

    def _build_preferences_modal(self, user: User, notification_prefs: Dict[str, Any]) -> Dict[str, Any]:
        """Build the preferences configuration modal."""
        # Get current values or defaults
        eod_enabled = notification_prefs.get("eod_reminder_enabled", True)
        eod_time = notification_prefs.get("eod_reminder_time", "16:30")
        timezone = notification_prefs.get("timezone", "America/Los_Angeles")

        return {
            "type": "modal",
            "callback_id": "preferences_update",
            "title": {"type": "plain_text", "text": "Notification Preferences"},
            "submit": {"type": "plain_text", "text": "Save Preferences"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Configure your notification preferences for GolfDaddy Brain."},
                },
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": "eod_enabled",
                    "element": {
                        "type": "checkboxes",
                        "action_id": "eod_enabled_checkbox",
                        "options": [
                            {"text": {"type": "plain_text", "text": "Enable EOD reminders"}, "value": "enabled"}
                        ],
                        "initial_options": (
                            [{"text": {"type": "plain_text", "text": "Enable EOD reminders"}, "value": "enabled"}]
                            if eod_enabled
                            else []
                        ),
                    },
                    "label": {"type": "plain_text", "text": "EOD Reminders"},
                },
                {
                    "type": "input",
                    "block_id": "eod_time",
                    "element": {
                        "type": "timepicker",
                        "action_id": "eod_time_picker",
                        "initial_time": eod_time,
                        "placeholder": {"type": "plain_text", "text": "Select time"},
                    },
                    "label": {"type": "plain_text", "text": "EOD Reminder Time"},
                },
                {
                    "type": "input",
                    "block_id": "timezone",
                    "element": {
                        "type": "static_select",
                        "action_id": "timezone_select",
                        "placeholder": {"type": "plain_text", "text": "Select timezone"},
                        "initial_option": {"text": {"type": "plain_text", "text": timezone}, "value": timezone},
                        "options": self._get_common_timezone_options(),
                    },
                    "label": {"type": "plain_text", "text": "Timezone"},
                },
            ],
        }

    def _get_common_timezone_options(self) -> List[Dict[str, Any]]:
        """Get common timezone options for the dropdown."""
        common_timezones = [
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
            "America/Phoenix",
            "America/Anchorage",
            "Pacific/Honolulu",
            "Europe/London",
            "Europe/Paris",
            "Europe/Berlin",
            "Asia/Tokyo",
            "Asia/Shanghai",
            "Asia/Kolkata",
            "Australia/Sydney",
        ]

        return [{"text": {"type": "plain_text", "text": tz}, "value": tz} for tz in common_timezones]

    def get_help_message(self) -> str:
        """Get the help message for available slash commands."""
        return """*Available Commands:*

• `/eod` - Submit or update your daily end-of-day report
• `/preferences` - Configure your notification preferences (reminder time, timezone)
• `/help` - Show this help message

*Tips:*
• You can update your EOD report multiple times before midnight
• EOD reminders are sent at your configured time (default: 4:30 PM)
• Reports include both your commit activity and manually reported work
• Use the preferences command to customize your reminder time and timezone"""

    async def handle_preferences_submission(self, slack_user_id: str, view_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle preferences modal submission."""
        try:
            # Get user
            user = await self.user_service.get_user_by_slack_id(slack_user_id)
            if not user:
                return {"response_action": "errors", "errors": {"general": "User not found"}}

            # Extract form values
            values = view_data.get("state", {}).get("values", {})

            # Get EOD enabled checkbox
            eod_enabled_values = (
                values.get("eod_enabled", {}).get("eod_enabled_checkbox", {}).get("selected_options", [])
            )
            eod_enabled = len(eod_enabled_values) > 0

            # Get EOD time
            eod_time = values.get("eod_time", {}).get("eod_time_picker", {}).get("selected_time", "16:30")

            # Get timezone
            timezone = (
                values.get("timezone", {})
                .get("timezone_select", {})
                .get("selected_option", {})
                .get("value", "America/Los_Angeles")
            )

            # Update user preferences
            preferences = user.preferences or {}
            preferences["notification"] = {
                "eod_reminder_enabled": eod_enabled,
                "eod_reminder_time": eod_time,
                "timezone": timezone,
            }

            # Save preferences
            from app.repositories.user_repository import UserRepository

            user_repo = UserRepository()
            await user_repo.update_user(user.id, {"preferences": preferences})

            # Send confirmation message
            await self.slack_service.send_direct_message(
                user_id=slack_user_id,
                text=f"✅ Your preferences have been updated!\n\n"
                + f"*EOD Reminders:* {'Enabled' if eod_enabled else 'Disabled'}\n"
                + f"*Reminder Time:* {eod_time}\n"
                + f"*Timezone:* {timezone}",
            )

            return {"response_action": "clear"}

        except Exception as e:
            logger.exception(f"Error handling preferences submission: {e}")
            return {
                "response_action": "errors",
                "errors": {"general": "Failed to update preferences. Please try again."},
            }
