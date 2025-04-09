import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import logging

from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService # Assuming notification_service is in the same directory or PYTHONPATH is set

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PersonalMasteryService:
    """
    Service for managing personal mastery tasks assigned to managers.
    Tasks are stored in the User.personal_mastery JSON field.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repository = UserRepository(db)
        # Instantiate NotificationService - consider dependency injection in a real app
        self.notification_service = NotificationService(db)

    def _get_mastery_tasks_list(self, manager: User) -> List[Dict[str, Any]]:
        """Safely retrieves the list of mastery tasks, returning empty list if none."""
        tasks = manager.personal_mastery
        if isinstance(tasks, list):
            return tasks
        return []

    def assign_mastery_task(self, manager_id: str, description: str) -> Optional[Dict[str, Any]]:
        """
        Assigns a new personal mastery task to a manager.

        Args:
            manager_id: The ID of the manager user.
            description: The description of the mastery task.

        Returns:
            The newly created task dictionary or None if manager not found/not a manager.
        """
        manager = self.user_repository.get_user_by_id(manager_id)
        if not manager or manager.role != UserRole.MANAGER:
            logger.warning(f"Cannot assign mastery task: User {manager_id} not found or is not a manager.")
            return None

        tasks = self._get_mastery_tasks_list(manager)

        new_task = {
            "id": str(uuid.uuid4()),
            "description": description,
            "status": "pending", # Default status
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None
        }
        tasks.append(new_task)

        # Update the user's personal_mastery field
        updated = self.user_repository.update_user(manager_id, personal_mastery=tasks)
        if updated:
            logger.info(f"Assigned mastery task '{new_task['id']}' to manager {manager_id}")
            return new_task
        else:
            logger.error(f"Failed to update manager {manager_id} with new mastery task.")
            # Attempt to rollback the change in memory (though DB update failed)
            tasks.pop()
            return None

    def update_mastery_task_status(self, manager_id: str, task_id: str, status: str) -> Optional[Dict[str, Any]]:
        """
        Updates the status of a specific mastery task for a manager.

        Args:
            manager_id: The ID of the manager user.
            task_id: The ID of the mastery task to update.
            status: The new status (e.g., "completed", "pending").

        Returns:
            The updated task dictionary or None if not found or update fails.
        """
        manager = self.user_repository.get_user_by_id(manager_id)
        if not manager or manager.role != UserRole.MANAGER:
            logger.warning(f"Cannot update mastery task: User {manager_id} not found or is not a manager.")
            return None

        tasks = self._get_mastery_tasks_list(manager)
        task_found = None
        task_index = -1

        for i, task in enumerate(tasks):
            if task.get("id") == task_id:
                task_found = task
                task_index = i
                break

        if not task_found:
            logger.warning(f"Mastery task {task_id} not found for manager {manager_id}.")
            return None

        # Update status and completed_at timestamp if status changes to completed
        original_status = task_found.get("status")
        task_found["status"] = status
        if status == "completed" and original_status != "completed":
            task_found["completed_at"] = datetime.now(timezone.utc).isoformat()
        elif status != "completed":
             task_found["completed_at"] = None # Clear completion date if moved away from completed

        # Replace the task in the list
        tasks[task_index] = task_found

        # Update the user's personal_mastery field
        updated = self.user_repository.update_user(manager_id, personal_mastery=tasks)
        if updated:
            logger.info(f"Updated mastery task '{task_id}' for manager {manager_id} to status '{status}'")
            return task_found
        else:
            # Revert in-memory change if DB update failed
            task_found["status"] = original_status # Revert status
            # Revert completed_at logic might be needed depending on original state
            logger.error(f"Failed to update manager {manager_id} with updated mastery task status.")
            return None


    def get_mastery_tasks(self, manager_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all personal mastery tasks for a specific manager.

        Args:
            manager_id: The ID of the manager user.

        Returns:
            A list of task dictionaries, or an empty list if manager not found or no tasks.
        """
        manager = self.user_repository.get_user_by_id(manager_id)
        if not manager or manager.role != UserRole.MANAGER:
            return []

        return self._get_mastery_tasks_list(manager)

    def send_mastery_reminders(self) -> Tuple[int, int]:
        """
        Sends reminders to all managers about their pending personal mastery tasks.
        This function is intended to be called by a scheduler.

        Returns:
            A tuple (managers_processed, reminders_sent)
        """
        managers = self.user_repository.list_users_by_role(UserRole.MANAGER)
        managers_processed = 0
        reminders_sent = 0

        for manager in managers:
            managers_processed += 1
            tasks = self._get_mastery_tasks_list(manager)
            pending_tasks = [task for task in tasks if task.get("status", "pending") == "pending"]

            if pending_tasks:
                logger.info(f"Sending mastery reminder to manager {manager.id} ({manager.name}) for {len(pending_tasks)} pending tasks.")
                # Call the notification service to trigger the Make.com webhook
                self.notification_service.trigger_personal_mastery_reminder(manager, pending_tasks)
                reminders_sent += 1
            else:
                 logger.info(f"No pending mastery tasks for manager {manager.id} ({manager.name}). Skipping reminder.")


        logger.info(f"Personal Mastery Reminder Job: Processed {managers_processed} managers, sent {reminders_sent} reminders.")
        return managers_processed, reminders_sent

# Example usage (conceptual - would be called from API endpoints or scheduler)
# if __name__ == '__main__':
#     # Requires a database session (db) to be set up
#     # from app.config.database import SessionLocal
#     # db = SessionLocal()
#     # pm_service = PersonalMasteryService(db)
#
#     # Example: Assign a task
#     # manager_user_id = "some-manager-uuid" # Replace with actual manager ID
#     # new_task_info = pm_service.assign_mastery_task(manager_user_id, "Conduct weekly 1:1s effectively")
#     # if new_task_info:
#     #     print(f"Assigned Task: {new_task_info}")
#
#     # Example: Get tasks
#     # tasks = pm_service.get_mastery_tasks(manager_user_id)
#     # print(f"Tasks for manager {manager_user_id}: {tasks}")
#
#     # Example: Update task status
#     # if tasks:
#     #    task_to_update_id = tasks[0]['id']
#     #    updated_task = pm_service.update_mastery_task_status(manager_user_id, task_to_update_id, "completed")
#     #    if updated_task:
#     #        print(f"Updated Task: {updated_task}")
#
#     # Example: Run the reminder job (simulate scheduler call)
#     # processed, sent = pm_service.send_mastery_reminders()
#     # print(f"Reminder job finished: Processed={processed}, Sent={sent}")
#
#     # db.close()
#     pass