from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from app.models.task import Task, TaskStatus

class TaskRepository:
    """Repository for Task model operations with RACI framework support."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_task(self, description: str, assignee_id: str, responsible_id: str, 
                    accountable_id: str, consulted_ids: Optional[List[str]] = None,
                    informed_ids: Optional[List[str]] = None, 
                    due_date: Optional[datetime] = None) -> Task:
        """Create a new task with RACI roles."""
        task = Task(
            description=description,
            assignee_id=assignee_id,
            responsible_id=responsible_id,
            accountable_id=accountable_id,
            consulted_ids=consulted_ids or [],
            informed_ids=informed_ids or [],
            status=TaskStatus.ASSIGNED,
            due_date=due_date
        )
        
        self.db.add(task)
        self.db.flush()  # Flush to get the ID
        return task
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.db.query(Task).filter(Task.id == task_id).first()
    
    def list_tasks(self) -> List[Task]:
        """List all tasks."""
        return self.db.query(Task).all()
    
    def find_tasks_by_assignee(self, assignee_id: str) -> List[Task]:
        """Find all tasks assigned to a specific user."""
        return self.db.query(Task).filter(Task.assignee_id == assignee_id).all()
    
    def find_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Find all tasks with a specific status."""
        return self.db.query(Task).filter(Task.status == status).all()
    
    def find_tasks_by_responsible(self, responsible_id: str) -> List[Task]:
        """Find all tasks where user is responsible."""
        return self.db.query(Task).filter(Task.responsible_id == responsible_id).all()
    
    def find_tasks_by_accountable(self, accountable_id: str) -> List[Task]:
        """Find all tasks where user is accountable."""
        return self.db.query(Task).filter(Task.accountable_id == accountable_id).all()
    
    def find_tasks_by_consulted(self, user_id: str) -> List[Task]:
        """Find all tasks where user is consulted."""
        return self.db.query(Task).filter(Task.consulted_ids.contains([user_id])).all()
    
    def find_tasks_by_informed(self, user_id: str) -> List[Task]:
        """Find all tasks where user is informed."""
        return self.db.query(Task).filter(Task.informed_ids.contains([user_id])).all()
    
    def update_task_status(self, task_id: str, status: TaskStatus) -> Optional[Task]:
        """Update a task's status."""
        task = self.get_task_by_id(task_id)
        if not task:
            return None
        
        task.status = status
        self.db.flush()
        return task
    
    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        """Update task attributes."""
        task = self.get_task_by_id(task_id)
        if not task:
            return None
        
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        self.db.flush()
        return task
    
    def assign_raci_roles(self, task_id: str, responsible_id: Optional[str] = None,
                        accountable_id: Optional[str] = None, 
                        consulted_ids: Optional[List[str]] = None,
                        informed_ids: Optional[List[str]] = None) -> Optional[Task]:
        """Update RACI roles for a task."""
        update_data = {}
        if responsible_id is not None:
            update_data["responsible_id"] = responsible_id
        if accountable_id is not None:
            update_data["accountable_id"] = accountable_id
        if consulted_ids is not None:
            update_data["consulted_ids"] = consulted_ids
        if informed_ids is not None:
            update_data["informed_ids"] = informed_ids
            
        return self.update_task(task_id, **update_data)
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task by ID."""
        task = self.get_task_by_id(task_id)
        if not task:
            return False
        
        self.db.delete(task)
        self.db.flush()
        return True