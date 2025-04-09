from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from app.config.database import get_db
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.raci_service import RaciService
from app.services.notification_service import NotificationService
from app.models.task import TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Pydantic models for request/response validation
class TaskCreate(BaseModel):
    description: str = Field(..., description="Task description")
    assignee_id: str = Field(..., description="ID of the user assigned to the task")
    responsible_id: Optional[str] = Field(None, description="ID of the responsible user (defaults to assignee)")
    accountable_id: Optional[str] = Field(None, description="ID of the accountable user")
    consulted_ids: Optional[List[str]] = Field(None, description="IDs of consulted users")
    informed_ids: Optional[List[str]] = Field(None, description="IDs of informed users")
    due_date: Optional[datetime] = Field(None, description="Due date for the task")

class TaskUpdate(BaseModel):
    description: Optional[str] = Field(None, description="Updated task description")
    assignee_id: Optional[str] = Field(None, description="Updated assignee ID")
    responsible_id: Optional[str] = Field(None, description="Updated responsible ID")
    accountable_id: Optional[str] = Field(None, description="Updated accountable ID")
    consulted_ids: Optional[List[str]] = Field(None, description="Updated consulted IDs")
    informed_ids: Optional[List[str]] = Field(None, description="Updated informed IDs")
    status: Optional[str] = Field(None, description="Updated task status")
    due_date: Optional[datetime] = Field(None, description="Updated due date")

class TaskResponse(BaseModel):
    id: str
    description: str
    status: str
    assignee_id: str
    responsible_id: str
    accountable_id: str
    consulted_ids: Optional[List[str]] = None
    informed_ids: Optional[List[str]] = None
    created_at: str
    updated_at: Optional[str] = None
    due_date: Optional[str] = None

class TaskList(BaseModel):
    tasks: List[TaskResponse]
    total: int

@router.post("", response_model=TaskResponse)
def create_task(
    task: TaskCreate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Create a new task with RACI roles.
    """
    # Initialize services
    raci_service = RaciService(db)
    notification_service = NotificationService(db)
    
    # Create task with RACI validation
    created_task, warnings = raci_service.assign_raci(
        description=task.description,
        assignee_id=task.assignee_id,
        responsible_id=task.responsible_id,
        accountable_id=task.accountable_id,
        consulted_ids=task.consulted_ids,
        informed_ids=task.informed_ids,
        due_date=task.due_date
    )
    
    # Send notification to assignee
    notification_service.task_created_notification(created_task.id)
    
    # Return created task
    return created_task.to_dict()

@router.get("", response_model=TaskList)
def list_tasks(
    assignee_id: Optional[str] = Query(None, description="Filter by assignee ID"),
    status: Optional[str] = Query(None, description="Filter by task status"),
    skip: int = Query(0, description="Number of tasks to skip"),
    limit: int = Query(100, description="Max number of tasks to return"),
    db: Session = Depends(get_db)
):
    """
    List tasks with optional filtering.
    """
    task_repository = TaskRepository(db)
    
    # Apply filters based on query parameters
    if assignee_id and status:
        filtered_tasks = [t for t in task_repository.find_tasks_by_assignee(assignee_id) 
                         if t.status.value == status]
    elif assignee_id:
        filtered_tasks = task_repository.find_tasks_by_assignee(assignee_id)
    elif status:
        try:
            status_enum = TaskStatus(status)
            filtered_tasks = task_repository.find_tasks_by_status(status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    else:
        filtered_tasks = task_repository.list_tasks()
    
    # Apply pagination
    paginated_tasks = filtered_tasks[skip:skip+limit]
    
    # Convert to response format
    return {
        "tasks": [task.to_dict() for task in paginated_tasks],
        "total": len(filtered_tasks)
    }

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific task by ID.
    """
    task_repository = TaskRepository(db)
    task = task_repository.get_task_by_id(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task.to_dict()

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    task_update: TaskUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Update a task's details or status.
    """
    task_repository = TaskRepository(db)
    raci_service = RaciService(db)
    notification_service = NotificationService(db)
    
    # Get existing task
    task = task_repository.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update RACI roles if provided
    if any(field is not None for field in [
        task_update.responsible_id, task_update.accountable_id, 
        task_update.consulted_ids, task_update.informed_ids
    ]):
        task = task_repository.assign_raci_roles(
            task_id=task_id,
            responsible_id=task_update.responsible_id,
            accountable_id=task_update.accountable_id,
            consulted_ids=task_update.consulted_ids,
            informed_ids=task_update.informed_ids
        )
    
    # Update other fields
    update_data = task_update.dict(exclude_unset=True, exclude={'status'})
    if update_data:
        task = task_repository.update_task(task_id, **update_data)
    
    # Update status if provided
    if task_update.status:
        try:
            status_enum = TaskStatus(task_update.status)
            
            # Special handling for blocked status
            if status_enum == TaskStatus.BLOCKED:
                # Notify accountable person (in real app, would capture blocking reason)
                notification_service.blocked_task_alert(task_id, "Task blocked by manager")
            
            task = task_repository.update_task_status(task_id, status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {task_update.status}")
    
    # Validate RACI roles after update
    is_valid, errors = raci_service.raci_validation(task_id)
    if not is_valid:
        return {
            **task.to_dict(),
            "warnings": errors
        }
    
    return task.to_dict()

@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a task.
    """
    task_repository = TaskRepository(db)
    
    # Attempt to delete the task
    success = task_repository.delete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted successfully"}