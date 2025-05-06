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

from app.config.settings import settings # Import settings to get webhook URLs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationService:
    """Service for triggering Make.com notifications via webhooks."""

    def __init__(self, supabase: Optional[Client] = None):
        """
        Initialize the NotificationService.
        A Supabase client is needed for working with repositories.
        """
        self.supabase = supabase
        self.session = requests.Session() # Use a session for potential performance benefits
        # Slack integration removed
        self.task_repo = TaskRepository(supabase) if supabase else TaskRepository()
        self.user_repo = UserRepository(supabase) if supabase else UserRepository()
        # ... (scheduler parts omitted for brevity) ...

    def _send_webhook(self, webhook_url: str, payload: Dict[str, Any]) -> bool:
        """Helper method to send data to a Make.com webhook."""
        if not webhook_url or "YOUR_MAKE_" in webhook_url or "https://hook.make.com/your-" in webhook_url: # Added check for placeholder
            logger.warning(f"Make.com webhook URL is not configured or is a placeholder: {webhook_url}")
            return False
        try:
            headers = {'Content-Type': 'application/json'}
            # Use json.dumps with default=str to handle potential non-serializable types like UUID/datetime
            response = self.session.post(webhook_url, headers=headers, data=json.dumps(payload, default=str), timeout=10)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            logger.info(f"Successfully triggered Make.com webhook: {webhook_url}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to trigger Make.com webhook {webhook_url}: {e}")
            if e.response is not None:
                logger.error(f"Response status: {e.response.status_code}, Body: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred while sending webhook to {webhook_url}: {e}")
            return False

    def notify_task_created(self, task: Task, creator: Optional[User] = None):
        """Trigger Make.com scenario for a new task notification."""
        if not task or not task.assignee_id: # Ensure task and assignee exist
            logger.warning("Task creation notification skipped: Task or assignee ID missing.")
            return

        # Fetch assignee details if needed
        assignee = self.user_repo.get_user_by_id(task.assignee_id)
        if not assignee:
            logger.warning(f"Cannot find assignee user with ID {task.assignee_id}")
            return

        # Fetch optional user details
        responsible = self.user_repo.get_user_by_id(task.responsible_id) if task.responsible_id else None
        accountable = self.user_repo.get_user_by_id(task.accountable_id) if task.accountable_id else None

        # Prepare payload with Slack IDs
        payload = {
            "task_id": str(task.id),
            "task_description": task.description,
            "assignee_slack_id": assignee.slack_id, # Key field for Make.com
            "assignee_name": getattr(assignee, 'name', None), # Add name if available
            "responsible_slack_id": responsible.slack_id if responsible else None,
            "accountable_slack_id": accountable.slack_id if accountable else None,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "creator_slack_id": creator.slack_id if creator else None,
            "creator_name": getattr(creator, 'name', None) if creator else None, # Add name if available
        }
        logger.info(f"Sending task created payload for task {task.id} to Make.com...")
        # Send to the specific Make.com webhook URL from settings
        self._send_webhook(settings.MAKE_WEBHOOK_TASK_CREATED, payload)

    def notify_milestone_tracking(self, manager: User, milestone: Dict[str, Any]):
        """
        Trigger Make.com scenario for milestone tracking with managers.
        Milestones are manually defined monthly goals that are tracked via check-ins.
        """
        if not manager or not manager.slack_id:
            logger.warning("Milestone tracking notification skipped: Manager or Slack ID missing.")
            return

        # Prepare payload with milestone data
        payload = {
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
        # Send to the milestone webhook URL from settings
        self._send_webhook(settings.MAKE_WEBHOOK_MASTERY_REMINDER, payload)

    def notify_task_achievement(self, manager: User, achievement: Dict[str, Any]):
        """
        Trigger Make.com scenario for task achievement notifications.
        Provides contextual information about completed tasks/features
        from a customer-centric perspective.
        """
        if not manager or not manager.slack_id:
            logger.warning("Task achievement notification skipped: Manager or Slack ID missing.")
            return

        # Prepare payload with achievement data
        payload = {
            "manager_id": str(manager.id),
            "manager_slack_id": manager.slack_id,
            "manager_name": getattr(manager, 'name', None),
            "achievement_id": achievement.get('id'),
            "achievement_title": achievement.get('title'),
            # Contextual description from customer perspective
            "customer_value": achievement.get('customer_value'),
            "achievement_type": achievement.get('type', 'feature'), # feature, bug, improvement
            "completed_by": achievement.get('completed_by'),
            "completion_date": achievement.get('completion_date'),
            "timestamp": time.time()
        }
        
        logger.info(f"Sending task achievement notification for manager {manager.id} to Make.com...")
        # Send to the mastery webhook URL from settings
        self._send_webhook(settings.MAKE_WEBHOOK_MASTERY_REMINDER, payload)

    def notify_manager_mastery_feedback(self, manager: User, feedback: Dict[str, Any]):
        """
        Trigger Make.com scenario for personal mastery feedback to managers.
        This is for improvement categories that Daniel inputs for managers.
        """
        if not manager or not manager.slack_id:
            logger.warning("Manager mastery feedback notification skipped: Manager or Slack ID missing.")
            return

        # Prepare payload with improvement feedback
        payload = {
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
        # Send to the mastery webhook URL from settings
        self._send_webhook(settings.MAKE_WEBHOOK_MASTERY_REMINDER, payload)

    def notify_daily_task_followup(self, manager: User, task: Dict[str, Any]):
        """
        Trigger Make.com scenario for EOD follow-up on manager's daily tasks.
        Checks if manually inputted "must-do" tasks got completed.
        """
        if not manager or not manager.slack_id:
            logger.warning("Daily task follow-up notification skipped: Manager or Slack ID missing.")
            return

        # Prepare payload with daily task data
        payload = {
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
        # Send to the EOD reminder webhook URL from settings
        self._send_webhook(settings.MAKE_WEBHOOK_EOD_REMINDER, payload)

    # --- Other notification methods (notify_task_blocked, etc.) would follow a similar pattern ---

    def task_created_notification(self, task_id: UUID):
         """Shorthand method called by other services to notify about a new task."""
         # This method now correctly fetches the full task needed by notify_task_created
         try:
             task = self.task_repo.get_task_by_id(task_id)
             if task:
                 # Potentially fetch creator info if needed/available
                 creator = None
                 # Pass the full Task object
                 self.notify_task_created(task, creator)
             else:
                 logger.warning(f"Cannot send task created notification: Task {task_id} not found")
         except Exception as e:
             logger.error(f"Error sending task created notification for task {task_id}: {e}", exc_info=True)
    
    def milestone_tracking_notification(self, manager_id: UUID, milestone_data: Dict[str, Any]):
        """Shorthand method called by other services to notify about milestone tracking."""
        try:
            manager = self.user_repo.get_user_by_id(manager_id)
            if manager:
                self.notify_milestone_tracking(manager, milestone_data)
            else:
                logger.warning(f"Cannot send milestone tracking notification: Manager {manager_id} not found")
        except Exception as e:
            logger.error(f"Error sending milestone tracking notification for manager {manager_id}: {e}", exc_info=True)
            
    def task_achievement_notification(self, manager_id: UUID, achievement_data: Dict[str, Any]):
        """Shorthand method called by other services to notify about task achievements."""
        try:
            manager = self.user_repo.get_user_by_id(manager_id)
            if manager:
                self.notify_task_achievement(manager, achievement_data)
            else:
                logger.warning(f"Cannot send task achievement notification: Manager {manager_id} not found")
        except Exception as e:
            logger.error(f"Error sending task achievement notification for manager {manager_id}: {e}", exc_info=True)
            
    def manager_mastery_feedback_notification(self, manager_id: UUID, feedback_data: Dict[str, Any]):
        """Shorthand method called by other services to send mastery feedback to managers."""
        try:
            manager = self.user_repo.get_user_by_id(manager_id)
            if manager:
                self.notify_manager_mastery_feedback(manager, feedback_data)
            else:
                logger.warning(f"Cannot send manager mastery feedback: Manager {manager_id} not found")
        except Exception as e:
            logger.error(f"Error sending manager mastery feedback for manager {manager_id}: {e}", exc_info=True)
            
    def daily_task_followup_notification(self, manager_id: UUID, task_data: Dict[str, Any]):
        """Shorthand method called by other services to send EOD follow-ups on daily tasks."""
        try:
            manager = self.user_repo.get_user_by_id(manager_id)
            if manager:
                self.notify_daily_task_followup(manager, task_data)
            else:
                logger.warning(f"Cannot send daily task follow-up: Manager {manager_id} not found")
        except Exception as e:
            logger.error(f"Error sending daily task follow-up for manager {manager_id}: {e}", exc_info=True)

    # --- (send_task_reminders, trigger_eod_reminder etc. also use _send_webhook) ---