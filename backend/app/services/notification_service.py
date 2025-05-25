# File: app/services/notification_service.py
# Direct Slack integration replacing Make.com webhooks

import json
import logging
from typing import Dict, Any, Optional, List
from supabase import Client
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.models.task import Task, TaskStatus
from app.models.user import User
from uuid import UUID
import schedule
import time
from threading import Thread
import asyncio

from app.config.settings import settings
from app.core.exceptions import (
    ConfigurationError,
    ExternalServiceError,
    ResourceNotFoundError,
    AppExceptionBase
)
from app.services.slack_service import SlackService
from app.services.slack_message_templates import SlackMessageTemplates

# Configure logging
logging.basicConfig(level=logging.INFO) # This might be already set by main.py
logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications via direct Slack integration."""

    def __init__(self, supabase: Optional[Client] = None):
        """
        Initialize the NotificationService with direct Slack integration.
        """
        self.slack_service = SlackService()
        self.templates = SlackMessageTemplates()
        self.task_repo = TaskRepository() 
        self.user_repo = UserRepository()
        self.default_channel = settings.SLACK_DEFAULT_CHANNEL

    async def _get_slack_user_id(self, user: User, db: AsyncSession) -> Optional[str]:
        """Get Slack user ID from User object, attempting GitHub username lookup if needed."""
        if user.slack_id:
            return user.slack_id
        
        # Try to find by GitHub username if available
        if hasattr(user, 'github_username') and user.github_username:
            slack_user = await self.slack_service.find_user_by_github_username(user.github_username, db)
            if slack_user:
                return slack_user['id']
        
        # Try to find by email
        if user.email:
            slack_user = await self.slack_service.find_user_by_email(user.email)
            if slack_user:
                return slack_user['id']
        
        return None

    async def notify_task_created(self, task: Task, creator: Optional[User] = None, db: AsyncSession = None):
        """Send task creation notification via direct Slack integration."""
        if not task or not task.assignee_id:
            logger.warning("Task creation notification skipped: Task or assignee ID missing.")
            return
        
        try:
            assignee = await self.user_repo.get_user_by_id(task.assignee_id)
            if not assignee:
                logger.warning(f"Cannot send task created notification: Assignee user with ID {task.assignee_id} not found for task {task.id}")
                return

            responsible = await self.user_repo.get_user_by_id(task.responsible_id) if task.responsible_id else None
            accountable = await self.user_repo.get_user_by_id(task.accountable_id) if task.accountable_id else None
            
            # Get Slack user IDs
            responsible_slack_id = await self._get_slack_user_id(responsible, db) if responsible else None
            accountable_slack_id = await self._get_slack_user_id(accountable, db) if accountable else None
            
            # Generate message using template
            message = self.templates.task_created(
                task_name=task.title,
                task_id=str(task.id),
                responsible_user_id=responsible_slack_id or "unknown",
                accountable_user_id=accountable_slack_id or "unknown",
                priority=task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
                due_date=task.due_date,
                description=task.description
            )
            
            # Send to assignee
            assignee_slack_id = await self._get_slack_user_id(assignee, db)
            if assignee_slack_id:
                await self.slack_service.send_direct_message(
                    user_id=assignee_slack_id,
                    text=message["text"],
                    blocks=message["blocks"]
                )
            
            # Also send to default channel if configured
            if self.default_channel:
                await self.slack_service.send_message(
                    channel=self.default_channel,
                    text=message["text"],
                    blocks=message["blocks"]
                )
            
            logger.info(f"Task created notification sent for task {task.id}")
            
        except Exception as e:
            logger.error(f"Error sending task created notification for task {task.id}: {e}", exc_info=True)

    async def notify_milestone_tracking(self, manager: User, milestone: Dict[str, Any]):
        if not manager or not manager.slack_id:
            logger.warning("Milestone tracking notification skipped: Manager or Slack ID missing.")
            return
        try:
            payload = { # Payload construction ... (as before) ...
                "manager_id": str(manager.id),
                "manager_slack_id": manager.slack_id,
                "manager_name": getattr(manager, 'name', None),
                "milestone_id": milestone.get('id'),
                "milestone_description": milestone.get('description'),
                "milestone_month": milestone.get('month'),
                "milestone_status": milestone.get('status', 'pending'),
                "milestone_notes": milestone.get('notes'),
                "last_checkin_date": milestone.get('last_checkin_date'),
                "timestamp": time.time()
            }
            logger.info(f"Sending milestone tracking for manager {manager.id} to Make.com...")
            await self._send_webhook(settings.MAKE_WEBHOOK_MASTERY_REMINDER, payload)
        except (ConfigurationError, ExternalServiceError, AppExceptionBase) as e_webhook:
            logger.error(f"Webhook error during milestone tracking for manager {manager.id}: {e_webhook}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in notify_milestone_tracking for manager {manager.id}: {e}", exc_info=True)

    async def notify_task_achievement(self, manager: User, achievement: Dict[str, Any]): 
        if not manager or not manager.slack_id:
            logger.warning("Task achievement notification skipped: Manager or Slack ID missing.")
            return
        try:
            payload = { # Payload construction ... (as before) ...
                "manager_id": str(manager.id),
                "manager_slack_id": manager.slack_id,
                "manager_name": getattr(manager, 'name', None),
                "achievement_id": achievement.get('id'),
                "achievement_title": achievement.get('title'),
                "customer_value": achievement.get('customer_value'),
                "achievement_type": achievement.get('type', 'feature'), 
                "completed_by": achievement.get('completed_by'),
                "completion_date": achievement.get('completion_date'),
                "timestamp": time.time()
            }
            logger.info(f"Sending task achievement notification for manager {manager.id} to Make.com...")
            await self._send_webhook(settings.MAKE_WEBHOOK_MASTERY_REMINDER, payload)
        except (ConfigurationError, ExternalServiceError, AppExceptionBase) as e_webhook:
            logger.error(f"Webhook error during task achievement for manager {manager.id}: {e_webhook}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in notify_task_achievement for manager {manager.id}: {e}", exc_info=True)

    async def notify_manager_mastery_feedback(self, manager: User, feedback: Dict[str, Any]):
        if not manager or not manager.slack_id:
            logger.warning("Manager mastery feedback notification skipped: Manager or Slack ID missing.")
            return
        try:
            payload = { # Payload construction ... (as before) ...
                "manager_id": str(manager.id),
                "manager_slack_id": manager.slack_id,
                "manager_name": getattr(manager, 'name', None),
                "feedback_id": feedback.get('id'),
                "improvement_area": feedback.get('area'),
                "feedback_details": feedback.get('details'),
                "provided_by": feedback.get('provided_by', 'Daniel'),
                "action_items": feedback.get('action_items', []),
                "send_reminder": feedback.get('send_reminder', True),
                "timestamp": time.time()
            }
            logger.info(f"Sending manager mastery feedback for manager {manager.id} to Make.com...")
            await self._send_webhook(settings.MAKE_WEBHOOK_MASTERY_REMINDER, payload)
        except (ConfigurationError, ExternalServiceError, AppExceptionBase) as e_webhook:
            logger.error(f"Webhook error during manager mastery feedback for manager {manager.id}: {e_webhook}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in notify_manager_mastery_feedback for manager {manager.id}: {e}", exc_info=True)

    async def notify_daily_task_followup(self, manager: User, task: Dict[str, Any]):
        if not manager or not manager.slack_id:
            logger.warning("Daily task follow-up notification skipped: Manager or Slack ID missing.")
            return
        try:
            payload = { # Payload construction ... (as before) ...
                "manager_id": str(manager.id),
                "manager_slack_id": manager.slack_id,
                "manager_name": getattr(manager, 'name', None),
                "task_id": task.get('id'),
                "task_description": task.get('description'),
                "is_completed": task.get('is_completed', False),
                "creation_date": task.get('creation_date'),
                "due_date": task.get('due_date'),
                "is_eod_reminder": True,
                "timestamp": time.time()
            }
            logger.info(f"Sending daily task follow-up for manager {manager.id} to Make.com...")
            await self._send_webhook(settings.MAKE_WEBHOOK_EOD_REMINDER, payload)
        except (ConfigurationError, ExternalServiceError, AppExceptionBase) as e_webhook:
            logger.error(f"Webhook error during daily task follow-up for manager {manager.id}: {e_webhook}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in notify_daily_task_followup for manager {manager.id}: {e}", exc_info=True)

    async def blocked_task_alert(self, task_id: UUID, reason: str, blocking_user: Optional[User] = None, db: AsyncSession = None):
        """Send task blocked notification via direct Slack integration."""
        logger.info(f"Preparing blocked task alert for task ID: {task_id}")
        try:
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                logger.warning(f"Blocked task alert skipped: Task {task_id} not found.")
                return

            responsible_user = await self.user_repo.get_user_by_id(task.responsible_id) if task.responsible_id else None
            accountable_user = await self.user_repo.get_user_by_id(task.accountable_id) if task.accountable_id else None
            
            # Get Slack user IDs
            blocked_by_slack_id = await self._get_slack_user_id(blocking_user, db) if blocking_user else "unknown"
            responsible_slack_id = await self._get_slack_user_id(responsible_user, db) if responsible_user else "unknown"
            accountable_slack_id = await self._get_slack_user_id(accountable_user, db) if accountable_user else "unknown"
            
            # Generate message using template
            message = self.templates.task_blocked(
                task_name=task.title,
                task_id=str(task.id),
                blocked_by_user_id=blocked_by_slack_id,
                responsible_user_id=responsible_slack_id,
                accountable_user_id=accountable_slack_id,
                reason=reason
            )
            
            # Send to accountable user
            if accountable_slack_id and accountable_slack_id != "unknown":
                await self.slack_service.send_direct_message(
                    user_id=accountable_slack_id,
                    text=message["text"],
                    blocks=message["blocks"]
                )
            
            # Also send to responsible user if different from accountable
            if responsible_slack_id and responsible_slack_id != "unknown" and responsible_slack_id != accountable_slack_id:
                await self.slack_service.send_direct_message(
                    user_id=responsible_slack_id,
                    text=message["text"],
                    blocks=message["blocks"]
                )
            
            # Send to default channel
            if self.default_channel:
                await self.slack_service.send_message(
                    channel=self.default_channel,
                    text=message["text"],
                    blocks=message["blocks"]
                )
            
            logger.info(f"Task blocked alert sent for task {task.id}")
            
        except Exception as e:
            logger.error(f"Unexpected error in blocked_task_alert for task {task_id}: {e}", exc_info=True)

    async def send_development_plan_notification(
        self, 
        manager_user_id: UUID,
        development_areas: List[str], 
        num_tasks_created: int,
        plan_link: Optional[str] = None,
        db: AsyncSession = None
    ):
        """Send development plan notification via direct Slack integration."""
        if not manager_user_id:
            logger.warning("Development plan notification skipped: Manager User ID missing.")
            return

        try:
            manager = await self.user_repo.get_user_by_id(manager_user_id)
            if not manager:
                logger.warning(f"Cannot send development plan notification: Manager {manager_user_id} not found.")
                return
            
            # Get manager's Slack ID
            manager_slack_id = await self._get_slack_user_id(manager, db)
            if not manager_slack_id:
                logger.warning(f"Cannot send development plan notification: No Slack ID found for manager {manager_user_id}")
                return
            
            # Generate message using template
            # Note: Using personal_mastery_reminder template as placeholder - you may want to create a specific template
            message = self.templates.development_plan_created(
                user_id=manager_slack_id,
                manager_user_id=manager_slack_id,  # Assuming manager creates their own plan
                plan_name=f"Development Plan - {', '.join(development_areas[:2])}",
                objectives=development_areas,
                timeline=f"{num_tasks_created} tasks created"
            )
            
            # Send to manager
            await self.slack_service.send_direct_message(
                user_id=manager_slack_id,
                text=message["text"],
                blocks=message["blocks"]
            )
            
            logger.info(f"Development plan notification sent to manager {manager.id}")
            
        except Exception as e:
            logger.error(f"Unexpected error in send_development_plan_notification for manager {manager_user_id}: {e}", exc_info=True)

    async def notify_task_escalation_fallback(
        self, 
        task: Task, 
        escalated_to_user: User, 
        reason_summary: str
    ):
        """Trigger Make.com scenario for a task escalation fallback notification."""
        if not task or not escalated_to_user or not escalated_to_user.slack_id:
            logger.warning(
                "Task escalation fallback notification skipped: "
                f"Task ({task.id if task else 'N/A'}), "
                f"escalated_to_user ({escalated_to_user.id if escalated_to_user else 'N/A'}), "
                f"or escalated_to_user.slack_id is missing."
            )
            return

        try:
            # Ensure assignee details are available if assignee_id is present
            assignee_details = {"id": None, "name": None, "slack_id": None}
            if task.assignee_id:
                assignee = await self.user_repo.get_user_by_id(task.assignee_id)
                if assignee:
                    assignee_details["id"] = str(assignee.id)
                    assignee_details["name"] = getattr(assignee, 'name', None)
                    assignee_details["slack_id"] = getattr(assignee, 'slack_id', None)
                else:
                    logger.warning(f"Assignee user {task.assignee_id} not found for task {task.id} in fallback notification.")
            
            # Ensure responsible user details are available if responsible_id is present
            responsible_details = {"id": None, "name": None, "slack_id": None}
            if task.responsible_id:
                responsible_user = await self.user_repo.get_user_by_id(task.responsible_id)
                if responsible_user:
                    responsible_details["id"] = str(responsible_user.id)
                    responsible_details["name"] = getattr(responsible_user, 'name', None)
                    responsible_details["slack_id"] = getattr(responsible_user, 'slack_id', None)
                else:
                    logger.warning(f"Responsible user {task.responsible_id} not found for task {task.id} in fallback notification.")


            payload = {
                "notification_type": "task_escalation_fallback",
                "task_id": str(task.id),
                "task_title": task.title,
                "task_description": task.description,
                "task_status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                "task_due_date": task.due_date.isoformat() if task.due_date else None,
                "task_type": task.task_type,
                "escalated_to_user_id": str(escalated_to_user.id),
                "escalated_to_user_name": getattr(escalated_to_user, 'name', None),
                "escalated_to_user_slack_id": escalated_to_user.slack_id,
                "escalation_reason_summary": reason_summary,
                "original_assignee_id": assignee_details["id"],
                "original_assignee_name": assignee_details["name"],
                "original_assignee_slack_id": assignee_details["slack_id"],
                "original_responsible_id": responsible_details["id"],
                "original_responsible_name": responsible_details["name"],
                "original_responsible_slack_id": responsible_details["slack_id"],
                "original_accountable_id": str(task.accountable_id) if task.accountable_id else None, # Accountable might not exist, so direct ID
                "timestamp": time.time()
            }
            
            # NOTE: This notification type requires a new webhook URL to be configured in settings.
            # Example: settings.MAKE_WEBHOOK_TASK_ESCALATION_FALLBACK
            webhook_url = settings.MAKE_WEBHOOK_TASK_ESCALATION_FALLBACK 
            
            logger.info(
                f"Sending task escalation fallback notification for task {task.id} "
                f"to user {escalated_to_user.id} (Slack: {escalated_to_user.slack_id}) via {webhook_url}..."
            )
            await self._send_webhook(webhook_url, payload)

        except (ConfigurationError, ExternalServiceError, AppExceptionBase) as e_webhook:
            logger.error(
                f"Webhook error during task escalation fallback for task {task.id} to user {escalated_to_user.id}: {e_webhook}", 
                exc_info=True
            )
        except ResourceNotFoundError as e_res: # Catch if user_repo.get_user_by_id fails for assignee/responsible
            logger.warning(
                f"Resource not found during task escalation fallback for task {task.id} to user {escalated_to_user.id}: {e_res}", 
                exc_info=True
            )
        except Exception as e:
            logger.error(
                f"Unexpected error in notify_task_escalation_fallback for task {task.id} to user {escalated_to_user.id}: {e}", 
                exc_info=True
            )

    # --- Shorthand methods call the above specific notification handlers ---
    async def task_created_notification(self, task: Task, creator_id: Optional[UUID] = None):
         try:
             # Task object is now passed directly, no need to fetch it again
             if task:
                 creator = await self.user_repo.get_user_by_id(creator_id) if creator_id else None
                 await self.notify_task_created(task, creator) # Pass the full Task object
             else:
                 logger.warning(f"Cannot send task created notification: Task object is None")
         except Exception as e:
             logger.error(f"Error sending task created notification for task {task.id if task else 'Unknown'}: {e}", exc_info=True)
    
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
        db: AsyncSession = None
    ):
        """Send documentation update proposal to commit author via Slack."""
        try:
            # Find Slack user by GitHub username
            slack_user = await self.slack_service.find_user_by_github_username(github_username, db)
            if not slack_user:
                logger.warning(f"Cannot send documentation proposal: No Slack user found for GitHub username {github_username}")
                # Send to default channel instead
                if self.default_channel:
                    message = self.templates.documentation_proposal(
                        author_user_id="team",
                        commit_sha=commit_sha,
                        commit_message=commit_message,
                        proposed_updates=proposed_updates,
                        pr_url=pr_url
                    )
                    await self.slack_service.send_message(
                        channel=self.default_channel,
                        text=message["text"],
                        blocks=message["blocks"]
                    )
                return
            
            # Generate message using template
            message = self.templates.documentation_proposal(
                author_user_id=slack_user['id'],
                commit_sha=commit_sha,
                commit_message=commit_message,
                proposed_updates=proposed_updates,
                pr_url=pr_url
            )
            
            # Send direct message to commit author
            await self.slack_service.send_direct_message(
                user_id=slack_user['id'],
                text=message["text"],
                blocks=message["blocks"]
            )
            
            logger.info(f"Documentation proposal sent to {github_username} for commit {commit_sha[:8]}")
            
        except Exception as e:
            logger.error(f"Error sending documentation proposal: {e}", exc_info=True)
    
    async def send_commit_analysis_summary(
        self,
        commit_sha: str,
        github_username: str,
        estimated_points: int,
        estimated_hours: float,
        complexity: str,
        impact_areas: List[str],
        db: AsyncSession = None
    ):
        """Send commit analysis summary to commit author via Slack."""
        try:
            # Find Slack user by GitHub username
            slack_user = await self.slack_service.find_user_by_github_username(github_username, db)
            if not slack_user:
                logger.warning(f"Cannot send commit analysis: No Slack user found for GitHub username {github_username}")
                return
            
            # Generate message using template
            message = self.templates.commit_analysis_summary(
                author_user_id=slack_user['id'],
                commit_sha=commit_sha,
                estimated_points=estimated_points,
                estimated_hours=estimated_hours,
                complexity=complexity,
                impact_areas=impact_areas
            )
            
            # Send direct message to commit author
            await self.slack_service.send_direct_message(
                user_id=slack_user['id'],
                text=message["text"],
                blocks=message["blocks"]
            )
            
            logger.info(f"Commit analysis sent to {github_username} for commit {commit_sha[:8]}")
            
        except Exception as e:
            logger.error(f"Error sending commit analysis summary: {e}", exc_info=True)