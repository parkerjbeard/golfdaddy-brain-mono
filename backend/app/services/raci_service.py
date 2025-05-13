import asyncio
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import logging
from datetime import datetime

from app.models.task import Task, TaskStatus
from app.models.user import User
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
    
    async def assign_raci(
        self,
        description: str,
        assignee_id: UUID,
        creator_id: UUID,
        responsible_id: Optional[UUID] = None,
        accountable_id: Optional[UUID] = None,
        consulted_ids: Optional[List[UUID]] = None,
        informed_ids: Optional[List[UUID]] = None,
        due_date: Optional[datetime] = None,
    ) -> Tuple[Optional[Task], List[str]]:
        """Validates RACI roles, creates a Task object, persists it, and returns task with warnings."""
        warnings = []

        # Defaulting logic (example)
        if not responsible_id:
            responsible_id = assignee_id
            warnings.append(f"Responsible ID not provided, defaulted to assignee ID: {assignee_id}")
        
        if not accountable_id:
            # Accountable might be more complex, e.g., assignee's manager or a project lead
            # For now, let's say it's required or also defaults to assignee for simplicity here, but flag it.
            accountable_id = assignee_id # Example, might need better logic
            warnings.append(f"Accountable ID not provided, defaulted to assignee ID: {assignee_id}. Review required.")

        # Basic validation: Ensure at least Responsible and Accountable are set after defaulting
        if not responsible_id or not accountable_id:
            logger.error("Critical RACI roles (Responsible, Accountable) are missing after defaulting.")
            return None, warnings + ["Responsible and Accountable roles are mandatory."]
        
        # Validate user IDs exist (optional, adds overhead but good for data integrity)
        user_ids_to_check = {assignee_id, responsible_id, accountable_id, creator_id}
        if consulted_ids: user_ids_to_check.update(consulted_ids)
        if informed_ids: user_ids_to_check.update(informed_ids)
        
        for user_id_to_check in filter(None, user_ids_to_check):
            user = await self.user_repo.get_user_by_id(user_id_to_check)
            if not user:
                error_msg = f"Invalid user ID {user_id_to_check} found in RACI assignment."
                logger.error(error_msg)
                warnings.append(error_msg)
                # Depending on strictness, might return None here
                # return None, warnings
        
        if any("Invalid user ID" in w for w in warnings):
             logger.warning(f"Task creation halted due to invalid user IDs in RACI: {warnings}")
             return None, warnings # Stop if critical user IDs are invalid

        # Construct the Task Pydantic model
        task_data = Task(
            description=description,
            assignee_id=assignee_id,
            responsible_id=responsible_id,
            accountable_id=accountable_id,
            consulted_ids=consulted_ids or [],
            informed_ids=informed_ids or [],
            creator_id=creator_id,
            due_date=due_date,
            status=TaskStatus.ASSIGNED # Default status
            # id, created_at, updated_at will be set by DB or repo
        )
        
        # Persist the task
        created_task = await self.task_repo.create_task(task_data)
        
        if not created_task:
            logger.error("Task persistence failed after RACI assignment.")
            warnings.append("Failed to save the task to the database.")
            return None, warnings
                
        logger.info(f"RACI roles assigned and task {created_task.id} created successfully.")
        return created_task, warnings
    
    async def raci_validation(self, task_id: UUID) -> Tuple[bool, List[str]]:
        """
        Validate RACI roles for an existing task.
        Returns: Tuple of (is_valid, List[str]) where the list contains errors
        """
        errors = []
        task = await self.task_repo.get_task_by_id(task_id)
        
        if not task:
            return False, ["Task not found"]
        
        if not task.responsible_id:
            errors.append("Missing Responsible role")
        if not task.accountable_id:
            errors.append("Missing Accountable role")
        
        all_user_ids_to_check = set()
        if task.assignee_id: all_user_ids_to_check.add(task.assignee_id)
        if task.responsible_id: all_user_ids_to_check.add(task.responsible_id)
        if task.accountable_id: all_user_ids_to_check.add(task.accountable_id)
        if task.creator_id: all_user_ids_to_check.add(task.creator_id)
        if task.consulted_ids: all_user_ids_to_check.update(task.consulted_ids)
        if task.informed_ids: all_user_ids_to_check.update(task.informed_ids)
        
        for user_id_val in filter(None, all_user_ids_to_check):
            user = await self.user_repo.get_user_by_id(user_id_val)
            if not user:
                errors.append(f"User with ID {user_id_val} in RACI/task roles not found")
        
        return len(errors) == 0, errors
    
    async def escalate_blocked_task(self, task_id: UUID):
        """Handles escalation logic when a task is marked as blocked."""
        task = await self.task_repo.get_task_by_id(task_id)
        if not task or task.status != TaskStatus.BLOCKED:
            logger.warning(f"Escalation requested for non-blocked or non-existent task {task_id}")
            return

        accountable_user: Optional[User] = None
        if task.accountable_id:
            accountable_user = await self.user_repo.get_user_by_id(task.accountable_id)

        if accountable_user:
            logger.info(f"Escalating blocked task {task.id} to Accountable user {accountable_user.id} (Slack: {getattr(accountable_user, 'slack_id', 'N/A')})")
            # TODO: Integrate with NotificationService.blocked_task_alert or a specific escalation notification
            # This would require NotificationService to be injectable or accessible here.
            # Example: await self.notification_service.notify_escalation(task, accountable_user, reason="Task Blocked")
            pass 
        else:
            logger.error(f"Could not find Accountable user ({task.accountable_id}) for escalating blocked task {task.id}")
            # TODO: Add fallback escalation (e.g., notify a default admin/manager)

    # Add other RACI related business logic methods here