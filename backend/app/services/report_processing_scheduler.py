"""
Report Processing Scheduler Service.

Handles scheduled tasks for daily report processing including:
- Midnight processing of finalized reports
- Clarification timeout checks
- Report aggregation for analytics
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config.settings import settings
from app.models.daily_report import DailyReport
from app.models.user import User
from app.services.daily_report_service import DailyReportService
from app.services.slack_message_templates import SlackMessageTemplates
from app.services.slack_service import SlackService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


class ReportProcessingScheduler:
    """Handles scheduled processing of daily reports."""

    def __init__(self):
        self.daily_report_service = DailyReportService()
        self.user_service = UserService()
        self.slack_service = SlackService()
        self.templates = SlackMessageTemplates()
        self._running = False

    async def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("Report scheduler already running")
            return

        self._running = True
        logger.info("Starting report processing scheduler")

        # Start background tasks
        asyncio.create_task(self._midnight_processing_loop())
        asyncio.create_task(self._clarification_timeout_checker())

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        logger.info("Stopping report processing scheduler")

    async def _midnight_processing_loop(self):
        """
        Process reports at midnight in each user's timezone.
        Runs every hour to catch different timezones.
        """
        while self._running:
            try:
                await self._process_midnight_reports()
                # Run every hour
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in midnight processing loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def _clarification_timeout_checker(self):
        """
        Check for expired clarification requests every hour.
        """
        while self._running:
            try:
                await self._check_clarification_timeouts()
                # Run every hour
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in clarification timeout checker: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _process_midnight_reports(self):
        """
        Process all reports that have reached midnight in users' timezones.
        """
        logger.info("Starting midnight report processing")

        # Get all active users
        users = await self.user_service.get_all_active_users()

        for user in users:
            try:
                # Get user's timezone
                user_tz = self._get_user_timezone(user)

                # Check if it's just past midnight in user's timezone
                user_time = datetime.now(ZoneInfo(user_tz))

                # Process if it's between midnight and 1am in user's timezone
                if 0 <= user_time.hour < 1:
                    await self._process_user_daily_report(user, user_tz)

            except Exception as e:
                logger.error(f"Error processing midnight report for user {user.id}: {e}", exc_info=True)

    async def _process_user_daily_report(self, user: User, user_tz: str):
        """
        Process a single user's daily report at midnight.
        """
        # Get yesterday's date in user's timezone
        user_time = datetime.now(ZoneInfo(user_tz))
        yesterday = user_time - timedelta(days=1)

        # Get report for yesterday
        report = await self.daily_report_service.get_user_report_for_date(user.id, yesterday, user_tz)

        if not report:
            logger.info(f"No report found for user {user.id} on {yesterday.date()}")
            return

        # Check if report is already finalized
        if report.conversation_state and report.conversation_state.get("finalized"):
            logger.info(f"Report {report.id} already finalized")
            return

        # Mark report as finalized
        await self.daily_report_service.update_daily_report(
            report.id,
            {
                "conversation_state": {
                    **report.conversation_state,
                    "finalized": True,
                    "finalized_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            user.id,
        )

        # Send final summary to Slack if needed
        if user.slack_id and report.slack_thread_ts:
            await self._send_final_report_summary(user, report)

        logger.info(f"Finalized report {report.id} for user {user.id}")

    async def _send_final_report_summary(self, user: User, report: DailyReport):
        """
        Send final report summary to Slack after midnight processing.
        """
        try:
            dm_channel = await self.slack_service.open_dm(user.slack_id)
            if not dm_channel:
                logger.error(f"Failed to open DM for user {user.slack_id}")
                return

            # Create finalization message
            final_message = (
                f"📊 *Daily Report Finalized*\n\n"
                f"Your report for yesterday has been finalized:\n"
                f"• Total hours: {report.final_estimated_hours or 0:.1f}\n"
                f"• Commit hours: {report.commit_hours or 0:.1f}\n"
                f"• Additional hours: {report.additional_hours or 0:.1f}\n\n"
                f"_This report is now locked and included in your weekly analytics._"
            )

            await self.slack_service.post_message(
                channel=dm_channel, text=final_message, thread_ts=report.slack_thread_ts  # Post in original thread
            )

        except Exception as e:
            logger.error(f"Error sending final report summary: {e}", exc_info=True)

    async def _check_clarification_timeouts(self):
        """
        Check for expired clarification requests and finalize those reports.
        """
        logger.info("Checking for clarification timeouts")

        # Page through all reports with pending clarifications to avoid missing items beyond first batch
        limit = 200
        offset = 0

        while True:
            reports = await self.daily_report_service.get_reports_with_pending_clarifications(
                limit=limit, offset=offset
            )
            if not reports:
                break

            for report in reports:
                try:
                    conv_state = report.conversation_state or {}
                    expires_at_str = conv_state.get("expires_at")

                    if not expires_at_str:
                        continue

                    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))

                    if datetime.now(timezone.utc) > expires_at:
                        # Clarification expired - finalize report
                        await self._finalize_expired_clarification(report)

                except Exception as e:
                    logger.error(f"Error checking clarification timeout for report {report.id}: {e}", exc_info=True)

            if len(reports) < limit:
                break
            offset += limit

    async def _finalize_expired_clarification(self, report: DailyReport):
        """
        Finalize a report with expired clarification.
        """
        # Update conversation state
        await self.daily_report_service.update_daily_report(
            report.id,
            {
                "conversation_state": {
                    **report.conversation_state,
                    "status": "expired",
                    "expired_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            report.user_id,
        )

        # Send notification if possible
        user = await self.user_service.get_user_by_id(report.user_id)
        if user and user.slack_id and report.slack_thread_ts:
            try:
                dm_channel = await self.slack_service.open_dm(user.slack_id)
                if dm_channel:
                    await self.slack_service.post_message(
                        channel=dm_channel,
                        text="⏰ Clarification request expired. Your report has been finalized with the original information.",
                        thread_ts=report.slack_thread_ts,
                    )
            except Exception as e:
                logger.error(f"Error sending expiration notification: {e}", exc_info=True)

        logger.info(f"Finalized expired clarification for report {report.id}")

    def _get_user_timezone(self, user: User) -> str:
        """Get user's timezone from preferences or use default."""
        if user.preferences and "timezone" in user.preferences:
            return user.preferences["timezone"]
        return settings.EOD_REMINDER_TIMEZONE

    async def process_all_pending_reports(self):
        """
        Manually process all pending reports regardless of timezone.
        Useful for testing or manual triggers.
        """
        logger.info("Processing all pending reports")

        users = await self.user_service.get_all_active_users()
        processed = 0

        for user in users:
            user_tz = self._get_user_timezone(user)
            report = await self.daily_report_service.get_user_report_for_date(
                user.id, datetime.now(timezone.utc), user_tz
            )

            if report and not (report.conversation_state or {}).get("finalized"):
                await self._process_user_daily_report(user, user_tz)
                processed += 1

        logger.info(f"Processed {processed} pending reports")
        return processed
