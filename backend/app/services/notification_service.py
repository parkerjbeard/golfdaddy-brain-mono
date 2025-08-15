# File: app/services/notification_service.py
# Direct Slack integration replacing Make.com webhooks

import asyncio
import json
import logging
import time
from threading import Thread
from typing import Any, Dict, List, Optional
from uuid import UUID

import schedule
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.exceptions import AppExceptionBase, ConfigurationError, ExternalServiceError, ResourceNotFoundError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.slack_message_templates import SlackMessageTemplates
from app.services.slack_service import SlackService
from supabase import Client

# Configure logging
logging.basicConfig(level=logging.INFO)  # This might be already set by main.py
logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via direct Slack integration."""

    def __init__(self, supabase: Optional[Client] = None):
        """
        Initialize the NotificationService with direct Slack integration.
        """
        self.slack_service = SlackService()
        self.templates = SlackMessageTemplates()
        self.user_repo = UserRepository()
        self.default_channel = settings.SLACK_DEFAULT_CHANNEL

    async def _get_slack_user_id(self, user: User, db: AsyncSession) -> Optional[str]:
        """Get Slack user ID from User object, attempting GitHub username lookup if needed."""
        if user.slack_id:
            return user.slack_id

        # Try to find by GitHub username if available
        if hasattr(user, "github_username") and user.github_username:
            slack_user = await self.slack_service.find_user_by_github_username(user.github_username, db)
            if slack_user:
                return slack_user["id"]

        # Try to find by email
        if user.email:
            slack_user = await self.slack_service.find_user_by_email(user.email)
            if slack_user:
                return slack_user["id"]

        return None

    async def notify_task_created(self, task: Any, creator: Optional[User] = None, db: AsyncSession = None):
        """Task creation notification - removed as per requirements."""
        # Direct messages for task creation are no longer sent
        logger.debug(f"Task created notification skipped for task {task.id} - direct messages disabled")
        return

    async def notify_milestone_tracking(self, manager: User, milestone: Dict[str, Any]):
        """Milestone tracking notification - removed as per requirements."""
        logger.debug(
            f"Milestone tracking notification skipped for manager {manager.id if manager else 'unknown'} - notifications disabled"
        )
        return

    async def notify_task_achievement(self, manager: User, achievement: Dict[str, Any]):
        """Task achievement notification - removed as per requirements."""
        logger.debug(
            f"Task achievement notification skipped for manager {manager.id if manager else 'unknown'} - notifications disabled"
        )
        return

    async def notify_manager_mastery_feedback(self, manager: User, feedback: Dict[str, Any]):
        """Manager mastery feedback notification - removed as per requirements."""
        logger.debug(
            f"Manager mastery feedback notification skipped for manager {manager.id if manager else 'unknown'} - notifications disabled"
        )
        return

    async def notify_daily_task_followup(self, manager: User, task: Dict[str, Any]):
        """Daily task followup notification - removed as per requirements."""
        # Note: EOD reminders are handled by EODReminderService, not this method
        logger.debug(
            f"Daily task followup notification skipped for manager {manager.id if manager else 'unknown'} - notifications disabled"
        )
        return

    async def blocked_task_alert(
        self, task_id: UUID, reason: str, blocking_user: Optional[User] = None, db: AsyncSession = None
    ):
        """Task blocked notification - removed as per requirements."""
        # Direct messages for task blocked alerts are no longer sent
        logger.debug(f"Task blocked alert skipped for task {task_id} - direct messages disabled")
        return

    async def send_development_plan_notification(
        self,
        manager_user_id: UUID,
        development_areas: List[str],
        num_tasks_created: int,
        plan_link: Optional[str] = None,
        db: AsyncSession = None,
    ):
        """Development plan notification - removed as per requirements."""
        # Direct messages for development plans are no longer sent
        logger.debug(f"Development plan notification skipped for manager {manager_user_id} - direct messages disabled")
        return

    async def notify_task_escalation_fallback(self, task: Any, escalated_to_user: User, reason_summary: str):
        """Task escalation fallback notification - removed as per requirements."""
        logger.debug(
            f"Task escalation notification skipped for task {task.id if task else 'unknown'} - notifications disabled"
        )
        return

    # --- Shorthand methods call the above specific notification handlers ---
    async def task_created_notification(self, task: Any, creator_id: Optional[UUID] = None):
        try:
            # Task object is now passed directly, no need to fetch it again
            if task:
                creator = await self.user_repo.get_user_by_id(creator_id) if creator_id else None
                await self.notify_task_created(task, creator)  # Pass the full Task object
            else:
                logger.warning(f"Cannot send task created notification: Task object is None")
        except Exception as e:
            logger.error(
                f"Error sending task created notification for task {task.id if task else 'Unknown'}: {e}", exc_info=True
            )

    async def milestone_tracking_notification(self, manager_id: UUID, milestone_data: Dict[str, Any]):
        try:
            manager = await self.user_repo.get_user_by_id(manager_id)
            if manager:
                await self.notify_milestone_tracking(manager, milestone_data)
            else:
                logger.warning(f"Cannot send milestone tracking notification: Manager {manager_id} not found")
        except Exception as e:
            logger.error(f"Error sending milestone tracking notification for manager {manager_id}: {e}", exc_info=True)

    async def task_achievement_notification(self, manager_id: UUID, achievement_data: Dict[str, Any]):
        try:
            manager = await self.user_repo.get_user_by_id(manager_id)
            if manager:
                await self.notify_task_achievement(manager, achievement_data)
            else:
                logger.warning(f"Cannot send task achievement notification: Manager {manager_id} not found")
        except Exception as e:
            logger.error(f"Error sending task achievement notification for manager {manager_id}: {e}", exc_info=True)

    async def manager_mastery_feedback_notification(self, manager_id: UUID, feedback_data: Dict[str, Any]):
        try:
            manager = await self.user_repo.get_user_by_id(manager_id)
            if manager:
                await self.notify_manager_mastery_feedback(manager, feedback_data)
            else:
                logger.warning(f"Cannot send manager mastery feedback: Manager {manager_id} not found")
        except Exception as e:
            logger.error(f"Error sending manager mastery feedback for manager {manager_id}: {e}", exc_info=True)

    async def daily_task_followup_notification(self, manager_id: UUID, task_data: Dict[str, Any]):
        try:
            manager = await self.user_repo.get_user_by_id(manager_id)
            if manager:
                await self.notify_daily_task_followup(manager, task_data)
            else:
                logger.warning(f"Cannot send daily task follow-up: Manager {manager_id} not found")
        except Exception as e:
            logger.error(f"Error sending daily task follow-up for manager {manager_id}: {e}", exc_info=True)

    async def send_documentation_proposal(
        self,
        commit_sha: str,
        commit_message: str,
        github_username: str,
        proposed_updates: List[Dict[str, str]],
        pr_url: Optional[str] = None,
        db: AsyncSession = None,
    ):
        """Documentation proposal notification - removed as per requirements."""
        # Direct messages for documentation proposals are no longer sent
        logger.debug(f"Documentation proposal notification skipped for {github_username} - direct messages disabled")
        return

    async def send_commit_analysis_summary(
        self,
        commit_sha: str,
        github_username: str,
        estimated_points: int,
        estimated_hours: float,
        complexity: str,
        impact_areas: List[str],
        db: AsyncSession = None,
    ):
        """Commit analysis summary notification - removed as per requirements."""
        # Direct messages for commit analysis are no longer sent
        logger.debug(f"Commit analysis notification skipped for {github_username} - direct messages disabled")
        return
