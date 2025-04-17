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

from app.config.settings import settings

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
        self._scheduler_thread = None
        self._stop_scheduler = False

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
        if not task or not task.assignee_id: # Ensure task and assignee exist
             logger.warning("Task creation notification skipped: Task or assignee missing.")
             return
             
        # Get the assignee user if we only have an ID
        assignee = None
        if not hasattr(task, 'assignee') or task.assignee is None:
            assignee = self.user_repo.get_user_by_id(task.assignee_id)
        else:
            assignee = task.assignee
            
        if not assignee:
            logger.warning(f"Cannot find assignee user with ID {task.assignee_id}")
            return

        # Get responsible and accountable users if needed
        responsible = None
        if hasattr(task, 'responsible_id') and task.responsible_id:
            responsible = self.user_repo.get_user_by_id(task.responsible_id)
            
        accountable = None
        if hasattr(task, 'accountable_id') and task.accountable_id:
            accountable = self.user_repo.get_user_by_id(task.accountable_id)

        payload = {
            "task_id": str(task.id),
            "task_description": task.description,
            "assignee_slack_id": assignee.slack_id if assignee else None,
            "assignee_name": assignee.name if assignee and hasattr(assignee, 'name') else None,
            "responsible_slack_id": responsible.slack_id if responsible else None,
            "accountable_slack_id": accountable.slack_id if accountable else None,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "creator_slack_id": creator.slack_id if creator else None,
            "creator_name": creator.name if creator and hasattr(creator, 'name') else None,
        }
        self._send_webhook(settings.MAKE_WEBHOOK_TASK_CREATED, payload)

    def notify_task_blocked(self, task: Task, blocker_user: Optional[User] = None):
        """Trigger Make.com scenario when a task is blocked."""
        if not task or not task.accountable_id: # Ensure task and accountable person exist
             logger.warning("Task blocked notification skipped: Task or accountable user missing.")
             return
             
        # Get the accountable user if we only have an ID
        accountable = None
        if not hasattr(task, 'accountable') or task.accountable is None:
            accountable = self.user_repo.get_user_by_id(task.accountable_id)
        else:
            accountable = task.accountable
            
        if not accountable:
            logger.warning(f"Cannot find accountable user with ID {task.accountable_id}")
            return
            
        # Get assignee if needed
        assignee = None
        if hasattr(task, 'assignee_id') and task.assignee_id:
            assignee = self.user_repo.get_user_by_id(task.assignee_id)

        payload = {
            "task_id": str(task.id),
            "task_description": task.description,
            "assignee_slack_id": assignee.slack_id if assignee else None,
            "assignee_name": assignee.name if assignee and hasattr(assignee, 'name') else None,
            "accountable_slack_id": accountable.slack_id if accountable else None,
            "accountable_name": accountable.name if accountable and hasattr(accountable, 'name') else None,
            "blocker_slack_id": blocker_user.slack_id if blocker_user else None,
            "blocker_name": blocker_user.name if blocker_user and hasattr(blocker_user, 'name') else None,
        }
        self._send_webhook(settings.MAKE_WEBHOOK_TASK_BLOCKED, payload)

    def send_task_reminders(self):
        """Send reminders for all open tasks."""
        logger.info("Sending task reminders...")
        
        # Check that we have a Supabase client
        if not self.supabase:
            logger.error("Cannot send task reminders: Supabase client not available")
            return
            
        try:
            # Get all open tasks
            all_tasks = self.task_repo.find_tasks_by_status(TaskStatus.ASSIGNED)
            all_tasks.extend(self.task_repo.find_tasks_by_status(TaskStatus.IN_PROGRESS))
            
            logger.info(f"Found {len(all_tasks)} open tasks")
            
            # Group tasks by assignee
            tasks_by_assignee = {}
            for task in all_tasks:
                if task.assignee_id:
                    assignee_id = str(task.assignee_id)
                    if assignee_id not in tasks_by_assignee:
                        tasks_by_assignee[assignee_id] = []
                    tasks_by_assignee[assignee_id].append(task)
            
            # Send reminders to each assignee
            for assignee_id, tasks in tasks_by_assignee.items():
                try:
                    self.send_tasks_reminder_to_user(UUID(assignee_id), tasks)
                    time.sleep(1)  # Avoid hitting rate limits
                except Exception as e:
                    logger.error(f"Error sending reminder to user {assignee_id}: {str(e)}")
            
            logger.info("Task reminders sent successfully")
        except Exception as e:
            logger.error(f"Error sending task reminders: {str(e)}")

    def send_tasks_reminder_to_user(self, user_id: UUID, tasks: List[Task]):
        """Send a reminder about open tasks to a specific user."""
        user = self.user_repo.get_user_by_id(user_id)
        if not user or not user.slack_id:
            logger.warning(f"Cannot send task reminder to user {user_id}: User or Slack ID not found")
            return
            
        if not tasks:
            return  # No tasks to remind about
            
        # Format task info for Make.com webhook
        tasks_data = []
        for task in tasks:
            tasks_data.append({
                "id": str(task.id),
                "description": task.description,
                "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                "due_date": task.due_date.isoformat() if task.due_date else None
            })
            
        payload = {
            "user_id": str(user_id),
            "user_slack_id": user.slack_id,
            "user_name": user.name if hasattr(user, 'name') else None,
            "tasks": tasks_data,
            "task_count": len(tasks)
        }
        
        # Send the reminder via Make.com webhook
        self._send_webhook(settings.MAKE_WEBHOOK_TASK_REMINDER, payload)
        logger.info(f"Sent task reminder to user {user_id} for {len(tasks)} tasks")

    def trigger_eod_reminder(self, user: User, tasks_today: List[Task]):
        """Trigger Make.com scenario for End-of-Day reminders."""
        if not user or not user.slack_id:
            logger.warning("EOD reminder skipped: User or user Slack ID missing.")
            return

        tasks_summary = [
            {
                "id": str(t.id),
                "description": t.description,
                "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
                "due_date": t.due_date.isoformat() if t.due_date else None,
            } for t in tasks_today
        ]

        payload = {
            "user_slack_id": user.slack_id,
            "user_name": user.name if hasattr(user, 'name') else None,
            "tasks_summary": tasks_summary,
        }
        self._send_webhook(settings.MAKE_WEBHOOK_EOD_REMINDER, payload)

    # Slack-specific methods removed - will be replaced with Make integration
    
    def task_created_notification(self, task_id: UUID):
        """Shorthand method to notify about a new task."""
        try:
            task = self.task_repo.get_task_by_id(task_id)
            if task:
                self.notify_task_created(task)
            else:
                logger.warning(f"Cannot send task created notification: Task {task_id} not found")
        except Exception as e:
            logger.error(f"Error sending task created notification: {e}")
    
    def send_eod_reminder(self, user_id: UUID):
        """Send an end-of-day reminder to a user with their tasks."""
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            logger.warning(f"Cannot send EOD reminder to user {user_id}: User not found")
            return
            
        # Get today's tasks for the user
        today_tasks = self.task_repo.find_active_tasks_by_user(user_id)
        
        # Trigger the EOD reminder via Make.com
        self.trigger_eod_reminder(user, today_tasks)
        logger.info(f"Sent EOD reminder to user {user_id} with {len(today_tasks)} tasks")

    def _run_eod_job(self):
        """Run the EOD job for all users."""
        try:
            logger.info("Running End-of-Day reminders...")
            
            # Get all active users
            users = self.user_repo.get_all_active_users()
            
            for user in users:
                try:
                    self.send_eod_reminder(user.id)
                    time.sleep(1)  # Avoid hitting rate limits
                except Exception as e:
                    logger.error(f"Error sending EOD reminder to user {user.id}: {str(e)}")
            
            logger.info("EOD reminders sent successfully")
        except Exception as e:
            logger.error(f"Error running EOD job: {str(e)}")

    def start_eod_scheduler(self):
        """Start the EOD reminder scheduler in a background thread."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("EOD scheduler is already running")
            return
            
        self._stop_scheduler = False
        self._scheduler_thread = Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info("EOD scheduler started")

    def stop_eod_scheduler(self):
        """Stop the EOD reminder scheduler."""
        if not self._scheduler_thread or not self._scheduler_thread.is_alive():
            logger.warning("EOD scheduler is not running")
            return
            
        self._stop_scheduler = True
        self._scheduler_thread.join(timeout=5)
        if self._scheduler_thread.is_alive():
            logger.warning("EOD scheduler did not stop gracefully")
        else:
            logger.info("EOD scheduler stopped")

    def _scheduler_loop(self):
        """Background thread loop for scheduling EOD reminders."""
        # Schedule the EOD job for 5 PM every weekday
        schedule.every().monday.at("17:00").do(self._run_eod_job)
        schedule.every().tuesday.at("17:00").do(self._run_eod_job)
        schedule.every().wednesday.at("17:00").do(self._run_eod_job)
        schedule.every().thursday.at("17:00").do(self._run_eod_job)
        schedule.every().friday.at("17:00").do(self._run_eod_job)
        
        while not self._stop_scheduler:
            schedule.run_pending()
            time.sleep(60)

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