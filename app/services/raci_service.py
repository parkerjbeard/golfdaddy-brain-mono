from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository

class RaciService:
    """Service for enforcing RACI rules for tasks."""
    
    def __init__(self, db: Session):
        self.db = db
        self.task_repository = TaskRepository(db)
        self.user_repository = UserRepository(db)
    
    def assign_raci(self, description: str, assignee_id: str, 
                   responsible_id: Optional[str] = None,
                   accountable_id: Optional[str] = None,
                   consulted_ids: Optional[List[str]] = None,
                   informed_ids: Optional[List[str]] = None,
                   **task_kwargs) -> Tuple[Task, List[str]]:
        """
        Assign RACI roles to a task, ensuring valid role assignment.
        
        Returns:
            Tuple of (Task, List[str]) where the list contains any warnings
        """
        warnings = []
        
        # Default responsible to assignee if not provided
        if responsible_id is None:
            responsible_id = assignee_id
            warnings.append("Responsible role defaulted to assignee")
        
        # Default accountable to assignee if not provided
        if accountable_id is None:
            # Try to find a manager
            assignee = self.user_repository.get_user_by_id(assignee_id)
            if assignee and assignee.team:
                managers = self.user_repository.list_users_by_role(UserRole.MANAGER)
                team_managers = [m for m in managers if m.team == assignee.team]
                
                if team_managers:
                    accountable_id = team_managers[0].id
                    warnings.append(f"Accountable role defaulted to team manager {team_managers[0].name}")
                else:
                    accountable_id = assignee_id
                    warnings.append("Accountable role defaulted to assignee (no team manager found)")
            else:
                accountable_id = assignee_id
                warnings.append("Accountable role defaulted to assignee")
        
        # Create the task with validated RACI roles
        task = self.task_repository.create_task(
            description=description,
            assignee_id=assignee_id,
            responsible_id=responsible_id,
            accountable_id=accountable_id,
            consulted_ids=consulted_ids,
            informed_ids=informed_ids,
            **task_kwargs
        )
        
        return task, warnings
    
    def raci_validation(self, task_id: str) -> Tuple[bool, List[str]]:
        """
        Validate RACI roles for a task.
        
        Returns:
            Tuple of (is_valid, List[str]) where the list contains errors
        """
        errors = []
        task = self.task_repository.get_task_by_id(task_id)
        
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
            user = self.user_repository.get_user_by_id(user_id)
            if not user:
                errors.append(f"User with ID {user_id} not found")
        
        return len(errors) == 0, errors
    
    def escalate_blocked_task(self, task_id: str, blocking_reason: str) -> Tuple[bool, str]:
        """
        Escalate a blocked task to the accountable person.
        
        Returns:
            Tuple of (success, message)
        """
        task = self.task_repository.get_task_by_id(task_id)
        
        if not task:
            return False, "Task not found"
        
        # Update task status to blocked
        self.task_repository.update_task_status(task_id, TaskStatus.BLOCKED)
        
        # Add blocking reason to task
        self.task_repository.update_task(task_id, blocking_reason=blocking_reason)
        
        # Get the accountable user for notification purposes
        accountable_user = self.user_repository.get_user_by_id(task.accountable_id)
        
        # Note: Actual notification will be handled by notification_service
        # We just return the info needed for the notification
        
        if accountable_user:
            return True, f"Task escalated to {accountable_user.name}"
        else:
            return True, "Task marked as blocked but accountable user not found"