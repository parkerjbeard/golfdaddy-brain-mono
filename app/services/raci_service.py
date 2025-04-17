from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import logging

from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
# from app.services.notification_service import NotificationService # Potential circular dependency, handle carefully

logger = logging.getLogger(__name__)

class RaciService:
    """Service for enforcing RACI rules for tasks."""
    
    def __init__(self):
        # Instantiate repositories directly
        # In a larger app, consider dependency injection framework
        self.task_repo = TaskRepository()
        self.user_repo = UserRepository()
        # self.notification_service = NotificationService() # Be careful with circular dependencies
    
    def assign_raci(self, task: Task) -> bool:
        """Validates and potentially assigns default RACI roles if needed.
           Returns True if valid, False otherwise.
        """
        # Example validation: Ensure at least Responsible and Accountable are set
        if not task.responsible_id or not task.accountable_id:
            logger.warning(f"Task {task.id} created without mandatory R/A roles.")
            # Potentially assign defaults or reject? Depends on business logic.
            # For now, just log.
            # return False 

        # Example: Validate user IDs exist (optional, adds overhead)
        # user_ids = {task.responsible_id, task.accountable_id, task.assignee_id}
        # user_ids.update(task.consulted_ids or [])
        # user_ids.update(task.informed_ids or [])
        # for user_id in filter(None, user_ids):
        #     if not self.user_repo.get_user_by_id(user_id):
        #         logger.error(f"Invalid user ID {user_id} found in RACI assignment for task {task.id}")
        #         return False
                
        logger.info(f"RACI roles validated for task {task.id}")
        return True
    
    def raci_validation(self, task_id: str) -> Tuple[bool, List[str]]:
        """
        Validate RACI roles for a task.
        
        Returns:
            Tuple of (is_valid, List[str]) where the list contains errors
        """
        errors = []
        task = self.task_repo.get_task_by_id(task_id)
        
        if not task:
            return False, ["Task not found"]
        
        # Validate Responsible
        if not task.responsible_id:
            errors.append("Missing Responsible role")
        
        # Validate Accountable
        if not task.accountable_id:
            errors.append("Missing Accountable role")
        
        # All users must exist
        all_user_ids = [
            task.responsible_id,
            task.accountable_id
        ]
        
        if task.consulted_ids:
            all_user_ids.extend(task.consulted_ids)
        
        if task.informed_ids:
            all_user_ids.extend(task.informed_ids)
        
        for user_id in all_user_ids:
            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                errors.append(f"User with ID {user_id} not found")
        
        return len(errors) == 0, errors
    
    def escalate_blocked_task(self, task_id: UUID):
        """Handles escalation logic when a task is marked as blocked."""
        task = self.task_repo.get_task_by_id(task_id)
        if not task or task.status != "blocked":
            logger.warning(f"Escalation requested for non-blocked or non-existent task {task_id}")
            return

        accountable_user: Optional[User] = None
        if task.accountable_id:
            accountable_user = self.user_repo.get_user_by_id(task.accountable_id)

        if accountable_user:
            logger.info(f"Escalating blocked task {task.id} to Accountable user {accountable_user.id} (Slack: {accountable_user.slack_id})")
            # TODO: Integrate with NotificationService to send alert
            # Example: self.notification_service.notify_blocked_task(task, accountable_user)
            pass 
        else:
            logger.error(f"Could not find Accountable user ({task.accountable_id}) for escalating blocked task {task.id}")
            # TODO: Add fallback escalation (e.g., notify a default admin/manager)

    # Add other RACI related business logic methods here