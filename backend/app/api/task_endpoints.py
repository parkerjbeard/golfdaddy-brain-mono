from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Body, Query, status
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

from app.config.database import get_db
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.raci_service import RaciService
from app.services.notification_service import NotificationService
from app.models.task import TaskStatus
from app.api.auth import get_current_user_profile
from app.models.user import User
import logging

logger = logging.getLogger(__name__)

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

# Helper to instantiate services (consider dependency injection later)
def get_task_repository():
    return TaskRepository()

def get_raci_service():
    return RaciService()

def get_notification_service():
    return NotificationService()

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate = Body(...),
    task_repo: TaskRepository = Depends(get_task_repository),
    raci_service: RaciService = Depends(get_raci_service),
    notification_service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user_profile)
):
    """
    Create a new task with RACI roles.
    """
    logger.info(f"User {current_user.id} attempting to create task: {task.description[:50]}...")
    
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
    
    if not created_task:
        logger.warning(f"RACI validation failed during task creation by user {current_user.id}")
        # Depending on assign_raci implementation, decide how to respond
        # For now, we proceed but log the warning.
        pass
    
    logger.info(f"Task {created_task.id} created successfully by user {current_user.id}")
    
    # Send notification to assignee
    notification_service.task_created_notification(created_task.id)
    
    return created_task.to_dict()

@router.get("", response_model=TaskList)
async def list_tasks(
    assignee_id: Optional[UUID] = None,
    status: Optional[TaskStatus] = None,
    task_repo: TaskRepository = Depends(get_task_repository),
    current_user: User = Depends(get_current_user_profile)
):
    """
    List tasks with optional filtering.
    """
    logger.info(f"User {current_user.id} listing tasks. Filters: assignee={assignee_id}, status={status}")
    
    if assignee_id:
        filtered_tasks = task_repo.find_tasks_by_assignee(assignee_id)
    elif status:
        try:
            status_enum = TaskStatus(status)
            filtered_tasks = task_repo.find_tasks_by_status(status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    else:
        # TODO: Implement filtering based on current_user's role/permissions
        # For now, fetching all tasks - potentially insecure / inefficient
        # Example: Fetch tasks where user is involved in RACI
        user_tasks = []
        user_tasks.extend(task_repo.find_tasks_by_assignee(current_user.id))
        user_tasks.extend(task_repo.find_tasks_by_raci_role(current_user.id, 'responsible_id'))
        user_tasks.extend(task_repo.find_tasks_by_raci_role(current_user.id, 'accountable_id'))
        user_tasks.extend(task_repo.find_tasks_by_raci_role(current_user.id, 'consulted_ids'))
        user_tasks.extend(task_repo.find_tasks_by_raci_role(current_user.id, 'informed_ids'))
        # Deduplicate tasks
        tasks_dict = {task.id: task for task in user_tasks}
        filtered_tasks = list(tasks_dict.values())
    
    # Apply pagination
    paginated_tasks = filtered_tasks
    
    # Convert to response format
    return {
        "tasks": [task.to_dict() for task in paginated_tasks],
        "total": len(filtered_tasks)
    }

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    task_repo: TaskRepository = Depends(get_task_repository),
    current_user: User = Depends(get_current_user_profile)
):
    """
    Get a specific task by ID.
    """
    logger.info(f"User {current_user.id} attempting to get task {task_id}")
    task = task_repo.get_task_by_id(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task.to_dict()

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate = Body(...),
    task_repo: TaskRepository = Depends(get_task_repository),
    raci_service: RaciService = Depends(get_raci_service),
    current_user: User = Depends(get_current_user_profile)
):
    """
    Update a task's details or status.
    """
    logger.info(f"User {current_user.id} attempting to update task {task_id}")
    existing_task = task_repo.get_task_by_id(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update RACI roles if provided
    if any(field is not None for field in [
        task_update.responsible_id, task_update.accountable_id, 
        task_update.consulted_ids, task_update.informed_ids
    ]):
        existing_task = task_repo.assign_raci_roles(
            task_id=task_id,
            responsible_id=task_update.responsible_id,
            accountable_id=task_update.accountable_id,
            consulted_ids=task_update.consulted_ids,
            informed_ids=task_update.informed_ids
        )
    
    # Update other fields
    update_data = task_update.dict(exclude_unset=True, exclude={'status'})
    if update_data:
        existing_task = task_repo.update_task(task_id, **update_data)
    
    # Update status if provided
    if task_update.status:
        try:
            status_enum = TaskStatus(task_update.status)
            
            # Special handling for blocked status
            if status_enum == TaskStatus.BLOCKED:
                # Notify accountable person (in real app, would capture blocking reason)
                notification_service.blocked_task_alert(task_id, "Task blocked by manager")
            
            existing_task = task_repo.update_task_status(task_id, status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {task_update.status}")
    
    # Validate RACI roles after update
    is_valid, errors = raci_service.raci_validation(task_id)
    if not is_valid:
        return {
            **existing_task.to_dict(),
            "warnings": errors
        }
    
    return existing_task.to_dict()

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    task_repo: TaskRepository = Depends(get_task_repository),
    current_user: User = Depends(get_current_user_profile)
):
    """
    Delete a task.
    """
    logger.info(f"User {current_user.id} attempting to delete task {task_id}")
    existing_task = task_repo.get_task_by_id(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # TODO: Add permission check - can current_user delete this task?
    
    deleted = task_repo.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete task")
    
    logger.info(f"Task {task_id} deleted successfully by user {current_user.id}")
    return