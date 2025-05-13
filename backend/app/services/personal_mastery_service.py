from app.repositories.user_repository import UserRepository
from app.models.user import User, UserRole
# from app.services.notification_service import NotificationService # Avoid direct import for circ dep
from uuid import UUID
from typing import List, Dict, Any, Optional
import logging
from app.core.exceptions import (
    ResourceNotFoundError,
    DatabaseError,
    PermissionDeniedError,
    BadRequestError # For role/validation type issues
)

logger = logging.getLogger(__name__)

class PersonalMasteryService:
    def __init__(self):
        self.user_repo = UserRepository()

    def _get_notification_service(self):
        """Helper to avoid circular import at module level."""
        from app.services.notification_service import NotificationService
        return NotificationService()

    async def assign_mastery_task(self, manager_id: UUID, task_details: Dict[str, Any]) -> bool:
        """Assigns or updates personal mastery task/goal for a manager.
           Assumes task_details is a dict to be stored in the user's JSONB field.
        """
        manager = await self.user_repo.get_user_by_id(manager_id) # Made async
        if not manager:
            logger.error(f"Manager with ID {manager_id} not found for assigning mastery task.")
            raise ResourceNotFoundError(resource_name="Manager", resource_id=str(manager_id))
        
        if manager.role != UserRole.MANAGER:
            logger.warning(f"Attempted to assign mastery task to non-manager user {manager_id} (Role: {manager.role})")
            raise BadRequestError(f"User {manager_id} is not a manager. Mastery tasks are for managers only.")

        update_data = {"personal_mastery": task_details}
        updated_user = await self.user_repo.update_user(manager_id, update_data) # Made async
        
        if updated_user:
            logger.info(f"Assigned/Updated personal mastery task for manager {manager_id}")
            try:
                # Assuming notify_personal_mastery is async in NotificationService
                await self._get_notification_service().notify_personal_mastery(updated_user, task_details)
            except Exception as e_notify:
                logger.error(f"Failed to send mastery notification to manager {manager_id}: {e_notify}", exc_info=True)
            return True # Success in assigning task, notification is best-effort
        else:
            logger.error(f"Failed to update personal mastery for manager {manager_id} in repository.")
            raise DatabaseError(f"Failed to update personal mastery for manager {manager_id}")

    async def get_mastery_tasks(self, manager_id: UUID) -> Optional[Dict[str, Any]]:
        """Retrieves the personal mastery tasks/goals for a manager."""
        manager = await self.user_repo.get_user_by_id(manager_id) # Made async
        if not manager:
            logger.info(f"Manager with ID {manager_id} not found when retrieving mastery tasks.")
            # Depending on API design, could raise ResourceNotFoundError or return None.
            # For a GET, if the primary resource (manager) isn't found, 404 is appropriate.
            raise ResourceNotFoundError(resource_name="Manager", resource_id=str(manager_id))
        
        if manager.role != UserRole.MANAGER:
             logger.warning(f"User {manager_id} is not a manager. Cannot retrieve mastery tasks specifically for managers.")
             # This could be a PermissionDeniedError or just return None if the tasks are strictly for managers.
             # Let's assume for now it means no applicable tasks rather than forbidden.
             return None 
        
        return manager.personal_mastery

    async def send_mastery_reminder(self, manager_id: UUID):
        """Sends a reminder notification about personal mastery tasks."""
        manager = await self.user_repo.get_user_by_id(manager_id) # Made async
        if not manager:
            logger.warning(f"Cannot send mastery reminder: Manager {manager_id} not found.")
            # Optionally raise ResourceNotFoundError if strict, or just return if reminder is best-effort.
            return
            
        if manager.role != UserRole.MANAGER:
            logger.warning(f"Cannot send mastery reminder to non-manager user {manager_id} (Role: {manager.role})")
            return
            
        mastery_tasks = manager.personal_mastery
        if not mastery_tasks:
            logger.info(f"No personal mastery tasks found for manager {manager_id}, skipping reminder.")
            return

        try:
            # Assuming notify_personal_mastery is async
            await self._get_notification_service().notify_personal_mastery(manager, mastery_tasks)
            logger.info(f"Successfully sent mastery reminder to manager {manager_id}.")
        except Exception as e_notify:
            logger.error(f"Failed to send mastery reminder notification to manager {manager_id}: {e_notify}", exc_info=True)

    # Add methods for tracking progress if needed