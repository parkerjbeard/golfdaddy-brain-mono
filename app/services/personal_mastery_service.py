from app.repositories.user_repository import UserRepository
from app.models.user import User, UserRole
from app.services.notification_service import NotificationService # Assuming this exists and is updated
from uuid import UUID
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class PersonalMasteryService:
    def __init__(self):
        self.user_repo = UserRepository()
        # Avoid direct instantiation if it causes circular dependency issues
        # self.notification_service = NotificationService() \

    def _get_notification_service(self) -> NotificationService:
        """Helper to avoid circular import at module level."""
        from app.services.notification_service import NotificationService
        return NotificationService()

    def assign_mastery_task(self, manager_id: UUID, task_details: Dict[str, Any]) -> bool:
        """Assigns or updates personal mastery task/goal for a manager.
           Assumes task_details is a dict to be stored in the user's JSONB field.
        """
        manager = self.user_repo.get_user_by_id(manager_id)
        if not manager:
            logger.error(f"Manager with ID {manager_id} not found.")
            return False
        if manager.role != UserRole.MANAGER:
            logger.warning(f"Attempted to assign mastery task to non-manager user {manager_id}")
            # Decide if this should be an error or allowed
            # return False

        # Merge or overwrite the personal_mastery field
        # Example: Overwrite completely
        update_data = {"personal_mastery": task_details}
        updated_user = self.user_repo.update_user(manager_id, update_data)
        
        if updated_user:
            logger.info(f"Assigned/Updated personal mastery task for manager {manager_id}")
            # Optionally send a notification
            try:
                self._get_notification_service().notify_personal_mastery(updated_user, task_details)
            except Exception as e:
                logger.error(f"Failed to send mastery notification to {manager_id}: {e}", exc_info=True)
            return True
        else:
            logger.error(f"Failed to update personal mastery for manager {manager_id}")
            return False

    def get_mastery_tasks(self, manager_id: UUID) -> Optional[Dict[str, Any]]:
        """Retrieves the personal mastery tasks/goals for a manager."""
        manager = self.user_repo.get_user_by_id(manager_id)
        if manager and manager.role == UserRole.MANAGER:
            # Ensure personal_mastery is parsed correctly if needed (Pydantic might handle it)
            return manager.personal_mastery
        elif manager:
             logger.warning(f"User {manager_id} is not a manager, cannot retrieve mastery tasks.")
             return None
        else:
            logger.error(f"Manager with ID {manager_id} not found.")
            return None

    def send_mastery_reminder(self, manager_id: UUID):
        """Sends a reminder notification about personal mastery tasks."""
        manager = self.user_repo.get_user_by_id(manager_id)
        if not manager or manager.role != UserRole.MANAGER:
            logger.warning(f"Cannot send mastery reminder to non-manager or non-existent user {manager_id}")
            return
            
        mastery_tasks = manager.personal_mastery
        if not mastery_tasks:
            logger.info(f"No personal mastery tasks found for manager {manager_id}, skipping reminder.")
            return

        try:
            self._get_notification_service().notify_personal_mastery(manager, mastery_tasks)
        except Exception as e:
            logger.error(f"Failed to send mastery reminder notification to {manager_id}: {e}", exc_info=True)

    # Add methods for tracking progress if needed