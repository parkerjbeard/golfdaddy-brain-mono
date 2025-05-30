# File: app/services/notification_service.py
# (Showing relevant parts demonstrating Make.com webhook usage)

import requests
import json
from typing import Dict, Any, Optional, List
from supabase import Client
import logging
# Slack integration removed - will be replaced with Make integration
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.models.task import Task, TaskStatus
from app.models.user import User
from uuid import UUID
import schedule
import time
from threading import Thread
import asyncio # Added import

from app.config.settings import settings # Import settings to get webhook URLs
from app.core.exceptions import (
    ConfigurationError,
    ExternalServiceError,
    ResourceNotFoundError, # For context if repo calls raise it
    AppExceptionBase
)

# Configure logging
logging.basicConfig(level=logging.INFO) # This might be already set by main.py
logger = logging.getLogger(__name__)

class NotificationService:
    """Service for triggering Make.com notifications via webhooks."""

    def __init__(self, supabase: Optional[Client] = None):
        """
        Initialize the NotificationService.
        """
        self.session = requests.Session()
        self.task_repo = TaskRepository() 
        self.user_repo = UserRepository()

    async def _send_webhook(self, webhook_url: str, payload: Dict[str, Any]) -> bool: # Made async
        """Helper method to send data to a Make.com webhook."""
        if not webhook_url or "YOUR_MAKE_" in webhook_url or "https://hook.make.com/your-" in webhook_url:
            logger.error(f"Make.com webhook URL is not configured or is a placeholder: {webhook_url}")
            raise ConfigurationError(f"Make.com webhook URL is not configured or is a placeholder: {webhook_url}")
        try:
            headers = {'Content-Type': 'application/json'}
            response = await asyncio.to_thread(
                self.session.post,
                webhook_url, 
                headers=headers, 
                data=json.dumps(payload, default=str), 
                timeout=10
            )
            response.raise_for_status() 
            logger.info(f"Successfully triggered Make.com webhook: {webhook_url}")
            return True
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout triggering Make.com webhook {webhook_url}: {e}", exc_info=True)
            raise ExternalServiceError(service_name="Make.com Webhook", original_message=f"Timeout connecting to {webhook_url}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error triggering Make.com webhook {webhook_url}: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise ExternalServiceError(service_name="Make.com Webhook", original_message=f"HTTP {e.response.status_code} from {webhook_url}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to trigger Make.com webhook {webhook_url}: {e}", exc_info=True)
            raise ExternalServiceError(service_name="Make.com Webhook", original_message=f"Request failed for {webhook_url}: {str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while sending webhook to {webhook_url}: {e}", exc_info=True)
            raise AppExceptionBase(f"Unexpected error sending webhook to {webhook_url}: {str(e)}")

    async def notify_task_created(self, task: Task, creator: Optional[User] = None): # Made async
        """Trigger Make.com scenario for a new task notification."""
        if not task or not task.assignee_id: # Ensure task and assignee exist
            logger.warning("Task creation notification skipped: Task or assignee ID missing.")
            return
        try:
            assignee = await self.user_repo.get_user_by_id(task.assignee_id)
            if not assignee:
                logger.warning(f"Cannot send task created notification: Assignee user with ID {task.assignee_id} not found for task {task.id}")
                return # Fail gracefully for this notification if assignee not found

            responsible = await self.user_repo.get_user_by_id(task.responsible_id) if task.responsible_id else None
            accountable = await self.user_repo.get_user_by_id(task.accountable_id) if task.accountable_id else None

            payload = {
                "task_id": str(task.id),
                "task_title": task.title, # Added title
                "task_description": task.description,
                "task_type": task.task_type, # Added task_type
                "assignee_slack_id": assignee.slack_id,
                "assignee_name": getattr(assignee, 'name', None),
                "responsible_slack_id": responsible.slack_id if responsible else None,
                "accountable_slack_id": accountable.slack_id if accountable else None,
                "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "creator_slack_id": creator.slack_id if creator else None,
                "creator_name": getattr(creator, 'name', None) if creator else None,
                "notification_type": "task_created" # Added notification type for Make.com routing
            }
            
            # Add development-specific fields if it's a manager development task
            if task.task_type == "manager_development" and task.metadata:
                payload["development_area"] = task.metadata.get("development_area")
                payload["learning_objectives"] = task.metadata.get("learning_objectives")
                # Potentially add other metadata fields relevant to the notification

            logger.info(f"Sending task created payload for task {task.id} (type: {task.task_type}) to Make.com...")
            await self._send_webhook(settings.MAKE_WEBHOOK_TASK_CREATED, payload)
        except (ConfigurationError, ExternalServiceError, AppExceptionBase) as e_webhook:
            logger.error(f"Webhook error during task created notification for task {task.id}: {e_webhook}", exc_info=True)
            # Optionally re-raise or handle (e.g., queue for retry)
        except ResourceNotFoundError as e_res:
             logger.warning(f"Resource not found during task created notification for task {task.id}: {e_res}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in notify_task_created for task {task.id}: {e}", exc_info=True)

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

    async def blocked_task_alert(self, task_id: UUID, reason: str, blocking_user: Optional[User] = None):
        logger.info(f"Preparing blocked task alert for task ID: {task_id}")
        try:
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                logger.warning(f"Blocked task alert skipped: Task {task_id} not found.")
                return

            accountable_user = await self.user_repo.get_user_by_id(task.accountable_id) if task.accountable_id else None
            if task.accountable_id and not accountable_user:
                logger.warning(f"Accountable user {task.accountable_id} not found for blocked task alert {task_id}")
            
            assignee_user = await self.user_repo.get_user_by_id(task.assignee_id) if task.assignee_id else None
            if task.assignee_id and not assignee_user:
                 logger.warning(f"Assignee user {task.assignee_id} not found for blocked task alert {task_id}")

            payload = { # Payload construction ... (as before) ...
                "task_id": str(task.id),
                "task_description": task.description,
                "blocked_reason": reason,
                "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                "assignee_id": str(task.assignee_id) if task.assignee_id else None,
                "assignee_name": getattr(assignee_user, 'name', None) if assignee_user else None,
                "assignee_slack_id": getattr(assignee_user, 'slack_id', None) if assignee_user else None,
                "accountable_id": str(task.accountable_id) if task.accountable_id else None,
                "accountable_name": getattr(accountable_user, 'name', None) if accountable_user else None,
                "accountable_slack_id": getattr(accountable_user, 'slack_id', None) if accountable_user else None,
                "blocked_by_user_id": str(blocking_user.id) if blocking_user else None,
                "blocked_by_user_name": getattr(blocking_user, 'name', None) if blocking_user else None,
                "blocked_by_user_slack_id": getattr(blocking_user, 'slack_id', None) if blocking_user else None,
                "timestamp": time.time()
            }
            webhook_url = settings.MAKE_WEBHOOK_TASK_BLOCKED
            logger.info(f"Sending task blocked alert payload for task {task.id} to Make.com webhook: {webhook_url}")
            await self._send_webhook(webhook_url, payload)
        except (ConfigurationError, ExternalServiceError, AppExceptionBase) as e_webhook:
            logger.error(f"Webhook error during blocked task alert for task {task_id}: {e_webhook}", exc_info=True)
        except ResourceNotFoundError as e_res:
             logger.warning(f"Resource not found during blocked task alert for task {task_id}: {e_res}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in blocked_task_alert for task {task_id}: {e}", exc_info=True)

    async def send_development_plan_notification(
        self, 
        manager_user_id: UUID, # Changed from manager_slack_id to user_id for consistency
        development_areas: List[str], 
        num_tasks_created: int,
        plan_link: Optional[str] = None # Optional link to view the plan
    ):
        """Trigger Make.com scenario for a new development plan notification."""
        if not manager_user_id:
            logger.warning("Development plan notification skipped: Manager User ID missing.")
            return

        try:
            manager = await self.user_repo.get_user_by_id(manager_user_id)
            if not manager or not manager.slack_id:
                logger.warning(f"Cannot send development plan notification: Manager {manager_user_id} not found or Slack ID missing.")
                return

            payload = {
                "manager_user_id": str(manager.id),
                "manager_slack_id": manager.slack_id,
                "manager_name": getattr(manager, 'name', 'Manager'),
                "development_areas": development_areas,
                "num_tasks_created": num_tasks_created,
                "plan_link": plan_link,
                "notification_type": "development_plan_created"
            }
            webhook_url = settings.MAKE_WEBHOOK_DEV_PLAN_CREATED
            if not webhook_url or "YOUR_MAKE_" in webhook_url:
                logger.error(f"Make.com webhook URL for development plan creation is not configured: {webhook_url}")
                # Depending on policy, either raise ConfigurationError or log and skip
                # For now, logging and skipping to avoid breaking flow if webhook is optional/not yet set up
                return 

            logger.info(f"Sending development plan created payload for manager {manager.id} to {webhook_url}...")
            await self._send_webhook(webhook_url, payload)

        except (ConfigurationError, ExternalServiceError, AppExceptionBase) as e_webhook:
            logger.error(f"Webhook error during development plan notification for manager {manager_user_id}: {e_webhook}", exc_info=True)
        except ResourceNotFoundError as e_res:
            logger.warning(f"Resource not found (manager) during development plan notification for manager {manager_user_id}: {e_res}", exc_info=True)
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

    # Method send_task_reminders would also need to be async and its internal calls to _send_webhook handled.
    # Example for one part of send_task_reminders:
    # async def send_task_reminders(self):
    #     logger.info("Checking for overdue tasks to send reminders...")
    #     overdue_tasks = await self.task_repo.get_overdue_tasks() # Made await
    #     for task in overdue_tasks:
    #         try:
    #             assignee = await self.user_repo.get_user_by_id(task.assignee_id) # Made await
    #             if assignee and assignee.slack_id:
    #                 payload = { ... }
    #                 await self._send_webhook(settings.MAKE_WEBHOOK_TASK_REMINDER, payload) # Made await
    #         except (ConfigurationError, ExternalServiceError, AppExceptionBase) as e_webhook:
    #             logger.error(f"Webhook error sending task reminder for task {task.id}: {e_webhook}", exc_info=True)
    #         except ResourceNotFoundError as e_res:
    #             logger.warning(f"Resource not found for task reminder {task.id} (assignee: {task.assignee_id}): {e_res}")
    #         except Exception as e:
    #             logger.error(f"Error processing reminder for task {task.id}: {e}", exc_info=True)