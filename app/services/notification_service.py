import requests
import json
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import logging

from app.config.settings import settings
from app.models.task import Task
from app.models.user import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationService:
    """Service for triggering Make.com notifications via webhooks."""

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the NotificationService.
        A database session might be needed if fetching additional context is required,
        but often the calling service will provide all necessary data.
        """
        self.db = db
        self.session = requests.Session() # Use a session for potential performance benefits

    def _send_webhook(self, webhook_url: str, payload: Dict[str, Any]) -> bool:
        """Helper method to send data to a Make.com webhook."""
        if not webhook_url or "YOUR_MAKE_" in webhook_url:
            logger.warning(f"Make.com webhook URL is not configured or is a placeholder: {webhook_url}")
            return False
        try:
            headers = {'Content-Type': 'application/json'}
            response = self.session.post(webhook_url, headers=headers, data=json.dumps(payload), timeout=10)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            logger.info(f"Successfully triggered Make.com webhook: {webhook_url}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to trigger Make.com webhook {webhook_url}: {e}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred while sending webhook to {webhook_url}: {e}")
            return False

    def notify_task_created(self, task: Task, creator: Optional[User] = None):
        """Trigger Make.com scenario for a new task notification."""
        if not task or not task.assignee: # Ensure task and assignee exist
             logger.warning("Task creation notification skipped: Task or assignee missing.")
             return

        payload = {
            "task_id": task.id,
            "task_description": task.description,
            "assignee_slack_id": task.assignee.slack_id, # Assuming User model has slack_id
            "assignee_name": task.assignee.name, # Assuming User model has name
            "responsible_slack_id": task.responsible.slack_id if task.responsible else None,
            "accountable_slack_id": task.accountable.slack_id if task.accountable else None,
            "status": task.status.value, # Send the string value of the enum
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "creator_slack_id": creator.slack_id if creator else None,
            "creator_name": creator.name if creator else None,
            # Add any other relevant task details Make.com might need
        }
        self._send_webhook(settings.make_webhook_task_created, payload)

    def notify_task_blocked(self, task: Task, blocker_user: Optional[User] = None):
        """Trigger Make.com scenario when a task is blocked."""
        if not task or not task.accountable: # Ensure task and accountable person exist
             logger.warning("Task blocked notification skipped: Task or accountable user missing.")
             return

        payload = {
            "task_id": task.id,
            "task_description": task.description,
            "assignee_slack_id": task.assignee.slack_id if task.assignee else None,
            "assignee_name": task.assignee.name if task.assignee else None,
            "accountable_slack_id": task.accountable.slack_id, # Accountable should exist
            "accountable_name": task.accountable.name, # Assuming User model has name
            "blocker_slack_id": blocker_user.slack_id if blocker_user else None, # User who marked as blocked
            "blocker_name": blocker_user.name if blocker_user else None,
             # Add reason for blocking if available in the task model or passed in
            # "block_reason": task.block_reason or "No reason provided",
        }
        # Typically notify the Accountable person and maybe the Assignee
        self._send_webhook(settings.make_webhook_task_blocked, payload)

    def trigger_eod_reminder(self, user: User, tasks_today: List[Task]):
        """Trigger Make.com scenario for End-of-Day reminders."""
        if not user or not user.slack_id:
            logger.warning("EOD reminder skipped: User or user Slack ID missing.")
            return

        tasks_summary = [
            {
                "id": t.id,
                "description": t.description,
                "status": t.status.value,
                "due_date": t.due_date.isoformat() if t.due_date else None,
            } for t in tasks_today
        ]

        payload = {
            "user_slack_id": user.slack_id,
            "user_name": user.name,
            "tasks_summary": tasks_summary,
            # Add any other context needed for the EOD message
        }
        self._send_webhook(settings.make_webhook_eod_reminder, payload)

    def trigger_personal_mastery_reminder(self, manager: User, mastery_tasks: List[Dict[str, Any]]):
        """Trigger Make.com scenario for Personal Mastery task reminders."""
        if not manager or not manager.slack_id:
            logger.warning("Personal Mastery reminder skipped: Manager or manager Slack ID missing.")
            return

        # Assuming mastery_tasks is a list of dicts stored perhaps in User.personal_mastery JSON
        # Adjust structure based on your actual implementation in user.py/personal_mastery_service.py
        payload = {
            "manager_slack_id": manager.slack_id,
            "manager_name": manager.name,
            "mastery_tasks": mastery_tasks, # Send the list of tasks/goals
        }
        self._send_webhook(settings.make_webhook_mastery_reminder, payload)

# Example usage (conceptual - would be called from other services)
# if __name__ == '__main__':
#     # This part is just for illustration and won't run in production
#     # Assumes you have dummy Task and User objects created somewhere
#     # and settings are loaded correctly with placeholder URLs.
#
#     # Example: Task Created
#     # dummy_task = Task(...)
#     # dummy_creator = User(...)
#     # notification_service = NotificationService()
#     # notification_service.notify_task_created(dummy_task, dummy_creator)
#
#     # Example: Task Blocked
#     # dummy_blocked_task = Task(...)
#     # dummy_blocker = User(...)
#     # notification_service.notify_task_blocked(dummy_blocked_task, dummy_blocker)
#
#     # Example: EOD Reminder (needs a list of tasks)
#     # dummy_user = User(...)
#     # dummy_tasks = [Task(...), Task(...)]
#     # notification_service.trigger_eod_reminder(dummy_user, dummy_tasks)
#
#     # Example: Personal Mastery Reminder (needs list of mastery goals)
#     # dummy_manager = User(...)
#     # dummy_mastery = [{"goal": "Improve feedback", "status": "pending"}]
#     # notification_service.trigger_personal_mastery_reminder(dummy_manager, dummy_mastery)
#     pass