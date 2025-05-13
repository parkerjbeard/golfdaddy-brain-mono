import asyncio
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import logging
from datetime import datetime

from app.models.task import Task, TaskStatus
from app.models.user import User
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.core.exceptions import ResourceNotFoundError, DatabaseError, BadRequestError
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

        # Validate critical user IDs first
        creator = await self.user_repo.get_user_by_id(creator_id)
        if not creator:
            raise ResourceNotFoundError(resource_name="Creator User", resource_id=str(creator_id))
        
        assignee = await self.user_repo.get_user_by_id(assignee_id)
        if not assignee:
            raise ResourceNotFoundError(resource_name="Assignee User", resource_id=str(assignee_id))

        # Defaulting logic for responsible and accountable
        if not responsible_id:
            responsible_id = assignee_id
            warnings.append(f"Responsible ID not provided, defaulted to assignee ID: {assignee_id}")
        else:
            responsible_user = await self.user_repo.get_user_by_id(responsible_id)
            if not responsible_user:
                raise ResourceNotFoundError(resource_name="Responsible User", resource_id=str(responsible_id))
        
        if not accountable_id:
            accountable_id = assignee_id # Example, might need better logic
            warnings.append(f"Accountable ID not provided, defaulted to assignee ID: {assignee_id}. Review required.")
        else:
            accountable_user = await self.user_repo.get_user_by_id(accountable_id)
            if not accountable_user:
                raise ResourceNotFoundError(resource_name="Accountable User", resource_id=str(accountable_id))

        # Validate non-critical user IDs (consulted, informed) and collect warnings
        valid_consulted_ids = []
        if consulted_ids:
            for user_id_to_check in consulted_ids:
                user = await self.user_repo.get_user_by_id(user_id_to_check)
                if not user:
                    warn_msg = f"Consulted user ID {user_id_to_check} not found and will be omitted."
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)
                else:
                    valid_consulted_ids.append(user_id_to_check)
        
        valid_informed_ids = []
        if informed_ids:
            for user_id_to_check in informed_ids:
                user = await self.user_repo.get_user_by_id(user_id_to_check)
                if not user:
                    warn_msg = f"Informed user ID {user_id_to_check} not found and will be omitted."
                    logger.warning(warn_msg)
                    warnings.append(warn_msg)
                else:
                    valid_informed_ids.append(user_id_to_check)

        # Construct the Task Pydantic model
        task_data = Task(
            description=description,
            assignee_id=assignee_id,
            responsible_id=responsible_id, # Already validated or defaulted from validated assignee
            accountable_id=accountable_id, # Already validated or defaulted from validated assignee
            consulted_ids=valid_consulted_ids, # Use validated list
            informed_ids=valid_informed_ids,   # Use validated list
            creator_id=creator_id, # Validated
            due_date=due_date,
            status=TaskStatus.ASSIGNED # Default status
            # id, created_at, updated_at will be set by DB or repo
        )
        
        # Persist the task
        created_task = await self.task_repo.create_task(task_data)
        
        if not created_task:
            logger.error(f"Task persistence failed after RACI assignment for description: {description[:50]}...")
            raise DatabaseError("Failed to save the task to the database after RACI assignment.")
                
        logger.info(f"RACI roles assigned and task {created_task.id} created successfully with {len(warnings)} warnings.")
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
            if not accountable_user:
                # If accountable user is critical for escalation, this could be an error
                logger.error(f"Accountable user {task.accountable_id} not found for escalating task {task.id}. Escalation cannot proceed.")
                # Consider raising ResourceNotFoundError or handling as a critical failure of escalation
                # For now, just logging and returning, as per original logic of not doing much more.
                return 

        if accountable_user: # This check is now more robust
            logger.info(f"Escalating blocked task {task.id} to Accountable user {accountable_user.id} (Slack: {getattr(accountable_user, 'slack_id', 'N/A')})")
            # TODO: Integrate with NotificationService.blocked_task_alert or a specific escalation notification
            # This would require NotificationService to be injectable or accessible here.
            # Example: await self.notification_service.notify_escalation(task, accountable_user, reason="Task Blocked")
            pass 

    # Add other RACI related business logic methods here