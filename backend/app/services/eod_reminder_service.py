"""
EOD (End of Day) reminder service for scheduling daily report prompts via Slack.
"""

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from app.config.settings import settings
from app.models.user import User
from app.repositories.commit_repository import CommitRepository
from app.repositories.user_repository import UserRepository
from app.services.slack_message_templates import SlackMessageTemplates
from app.services.slack_service import SlackService

logger = logging.getLogger(__name__)


class EODReminderService:
    """Service for managing end-of-day report reminders."""

    def __init__(self):
        self.user_repo = UserRepository()
        self.commit_repo = CommitRepository()
        self.slack_service = SlackService()
        self.templates = SlackMessageTemplates()

        # Default reminder time (5 PM)
        self.default_reminder_time = time(17, 0)  # 5:00 PM
        self.default_timezone = ZoneInfo(settings.EOD_REMINDER_TIMEZONE or "America/Los_Angeles")

    async def send_eod_reminders(self, dry_run: bool = False, check_time_window: bool = True) -> Dict[str, Any]:
        """
        Send EOD reminders to all active users.

        Args:
            dry_run: If True, don't actually send messages, just return what would be sent
            check_time_window: If True, only send reminders to users whose configured time is within the current 30-minute window

        Returns:
            Dictionary with results of the reminder sending process
        """
        results = {"total_users": 0, "reminders_sent": 0, "errors": [], "skipped": []}

        try:
            # Get all active users with Slack IDs
            users = await self.user_repo.list_all_users(limit=1000)
            active_users = [u for u in users[0] if u.is_active and u.slack_id]
            results["total_users"] = len(active_users)

            for user in active_users:
                try:
                    # Check user preferences for EOD reminders
                    notification_prefs = user.preferences.get("notification", {}) if user.preferences else {}
                    eod_enabled = notification_prefs.get("eod_reminder_enabled", True)

                    if not eod_enabled:
                        results["skipped"].append({"user_id": str(user.id), "reason": "reminders_disabled"})
                        continue

                    # Check if it's the right time for this user's reminder
                    if check_time_window:
                        user_reminder_time = notification_prefs.get("eod_reminder_time", "16:30")
                        user_timezone = notification_prefs.get("timezone", settings.EOD_REMINDER_TIMEZONE)

                        if not self._is_within_reminder_window(user_reminder_time, user_timezone):
                            results["skipped"].append({"user_id": str(user.id), "reason": "outside_time_window"})
                            continue

                    # Check if user has already submitted today's report
                    from app.repositories.daily_report_repository import DailyReportRepository

                    report_repo = DailyReportRepository()
                    today = datetime.now(timezone.utc).date()
                    existing_report = await report_repo.get_by_user_and_date(user.id, today)

                    if existing_report:
                        results["skipped"].append({"user_id": str(user.id), "reason": "already_submitted"})
                        continue

                    # Get today's commits for context
                    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                    today_end = today_start + timedelta(days=1)

                    user_commits = await self.commit_repo.get_commits_by_user_date_range(
                        user_id=user.id, start_date=today_start, end_date=today_end
                    )

                    # Prepare reminder message
                    last_commit_time = None
                    if user_commits:
                        last_commit_time = max(c.commit_date for c in user_commits)

                    message = self.templates.eod_reminder(
                        user_id=user.slack_id,
                        user_name=user.name or user.email.split("@")[0] if user.email else "there",
                        today_commits_count=len(user_commits),
                        last_commit_time=last_commit_time,
                    )

                    if not dry_run:
                        # Open DM and send reminder
                        dm_channel = await self.slack_service.open_dm(user.slack_id)
                        if dm_channel:
                            await self.slack_service.send_message(
                                channel=dm_channel, text=message["text"], blocks=message["blocks"]
                            )
                            results["reminders_sent"] += 1
                        else:
                            results["errors"].append({"user_id": str(user.id), "error": "failed_to_open_dm"})
                    else:
                        results["reminders_sent"] += 1
                        logger.info(f"[DRY RUN] Would send reminder to {user.name} ({user.slack_id})")

                except Exception as e:
                    logger.error(f"Error sending reminder to user {user.id}: {e}")
                    results["errors"].append({"user_id": str(user.id), "error": str(e)})

            return results

        except Exception as e:
            logger.error(f"Error in send_eod_reminders: {e}")
            results["errors"].append({"general_error": str(e)})
            return results

    async def schedule_user_reminder(
        self, user: User, reminder_time: Optional[time] = None, timezone_str: Optional[str] = None
    ) -> Optional[str]:
        """
        Schedule a reminder for a specific user.

        Args:
            user: User to schedule reminder for
            reminder_time: Time to send reminder (defaults to 5 PM)
            timezone_str: Timezone string (defaults to America/Los_Angeles)

        Returns:
            Scheduled message ID if successful, None otherwise
        """
        if not user.slack_id:
            logger.warning(f"User {user.id} has no Slack ID, cannot schedule reminder")
            return None

        try:
            # Use provided time or default
            send_time = reminder_time or self.default_reminder_time
            tz = ZoneInfo(timezone_str) if timezone_str else self.default_timezone

            # Calculate next reminder time
            now = datetime.now(tz)
            reminder_datetime = now.replace(hour=send_time.hour, minute=send_time.minute, second=0, microsecond=0)

            # If time has passed today, schedule for tomorrow
            if reminder_datetime <= now:
                reminder_datetime += timedelta(days=1)

            # Convert to Unix timestamp
            post_at = int(reminder_datetime.timestamp())

            # Get user's commit context for personalization
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            user_commits = await self.commit_repo.get_commits_by_user_date_range(
                user_id=user.id, start_date=today_start, end_date=now
            )

            # Prepare message
            message = self.templates.eod_reminder(
                user_id=user.slack_id,
                user_name=user.name or user.email.split("@")[0] if user.email else "there",
                today_commits_count=len(user_commits),
                last_commit_time=max(c.commit_date for c in user_commits) if user_commits else None,
            )

            # Open DM channel
            dm_channel = await self.slack_service.open_dm(user.slack_id)
            if not dm_channel:
                logger.error(f"Failed to open DM with user {user.id}")
                return None

            # Schedule message
            scheduled_id = await self.slack_service.schedule_message(
                channel=dm_channel, post_at=post_at, text=message["text"], blocks=message["blocks"]
            )

            if scheduled_id:
                logger.info(f"Scheduled EOD reminder for user {user.id} at {reminder_datetime}")

            return scheduled_id

        except Exception as e:
            logger.error(f"Error scheduling reminder for user {user.id}: {e}")
            return None

    async def cancel_user_reminder(self, user: User, scheduled_message_id: str) -> bool:
        """
        Cancel a scheduled reminder for a user.

        Args:
            user: User whose reminder to cancel
            scheduled_message_id: ID of the scheduled message

        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            # Slack doesn't have a direct API to cancel scheduled messages
            # This would need to be implemented if Slack adds this feature
            # For now, we'll track this in our database
            logger.warning("Cancelling scheduled messages not yet implemented by Slack API")
            return False

        except Exception as e:
            logger.error(f"Error cancelling reminder: {e}")
            return False

    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's EOD reminder preferences.

        This would typically be stored in the user's preferences field.
        """
        user = await self.user_repo.get_user_by_id(user_id)
        if not user or not user.preferences:
            return {
                "reminder_enabled": True,
                "reminder_time": "17:00",
                "timezone": "America/Los_Angeles",
                "include_commit_summary": True,
            }

        return user.preferences.get(
            "eod_reminder",
            {
                "reminder_enabled": True,
                "reminder_time": "17:00",
                "timezone": "America/Los_Angeles",
                "include_commit_summary": True,
            },
        )

    def _is_within_reminder_window(self, reminder_time_str: str, timezone_str: str, window_minutes: int = 30) -> bool:
        """
        Check if the current time is within the reminder window for a given time and timezone.

        Args:
            reminder_time_str: Time string in HH:MM format
            timezone_str: Timezone string
            window_minutes: Window size in minutes (default: 30)

        Returns:
            True if current time is within the window, False otherwise
        """
        try:
            # Parse reminder time
            hour, minute = map(int, reminder_time_str.split(":"))
            reminder_time = time(hour, minute)

            # Get current time in user's timezone
            tz = ZoneInfo(timezone_str)
            now = datetime.now(tz)
            now.time()

            # Calculate window
            reminder_datetime = now.replace(
                hour=reminder_time.hour, minute=reminder_time.minute, second=0, microsecond=0
            )
            window_start = reminder_datetime
            window_end = reminder_datetime + timedelta(minutes=window_minutes)

            # Check if current time is within window
            return window_start <= now <= window_end

        except Exception as e:
            logger.error(f"Error checking reminder window: {e}")
            # Default to True to avoid missing reminders due to errors
            return True


# Scheduled task function to be called by the scheduler
async def send_daily_eod_reminders():
    """Task function to send all EOD reminders."""
    logger.info("Starting daily EOD reminder task")
    service = EODReminderService()
    results = await service.send_eod_reminders()
    logger.info(f"EOD reminder task completed: {results['reminders_sent']} sent, {len(results['errors'])} errors")
    return results
