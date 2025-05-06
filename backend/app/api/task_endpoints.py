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
from app.models.task import TaskStatus, Task
from app.auth.dependencies import get_current_user as get_current_user_profile
from app.models.user import User, UserRole
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
    blocked_reason: Optional[str] = Field(None, description="Reason for blocking the task")

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
    warnings: Optional[List[str]] = None

class TaskList(BaseModel):
    tasks: List[TaskResponse]
    total: int

# Helper to instantiate services (consider dependency injection later)
def get_task_repository():
    return TaskRepository()

def get_user_repository():
    return UserRepository()

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
    
    # Create task with RACI validation, now passing creator_id
    # Assumes raci_service.assign_raci is updated to handle creator_id
    # and that it ensures creator_id is part of the Task object sent to task_repo.create_task
    created_task, warnings = await raci_service.assign_raci( # Made await, assuming raci_service.assign_raci is async
        description=task.description,
        assignee_id=task.assignee_id,
        responsible_id=task.responsible_id,
        accountable_id=task.accountable_id,
        consulted_ids=task.consulted_ids,
        informed_ids=task.informed_ids,
        due_date=task.due_date,
        creator_id=current_user.id # Pass creator_id
    )
    
    if not created_task:
        # Handle case where assign_raci itself fails before creating a task object
        # This might be due to validation errors that prevent task creation.
        # The original code had a pass here if created_task was None, which might mean assign_raci 
        # could return (None, warnings) for pure validation failures not resulting in a created task.
        # Raising an HTTPException might be more appropriate if no task is created due to such validation.
        if warnings:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Task creation failed due to RACI validation: {warnings}")
        else:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Task creation failed and RACI assignment returned no task object.")

    logger.info(f"Task {created_task.id} created successfully by user {current_user.id}")
    
    # Send notification to assignee, passing creator_id for context in notification if needed
    await notification_service.task_created_notification(created_task.id, current_user.id) # Made await
    
    response_data = created_task.to_dict() # Assumes Task.to_dict() exists or model_dump() is used
    if warnings:
        response_data["warnings"] = warnings
        logger.warning(f"Task {created_task.id} created with warnings by user {current_user.id}: {warnings}")

    return response_data

@router.get("", response_model=TaskList)
async def list_tasks(
    assignee_id: Optional[UUID] = None,
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    task_repo: TaskRepository = Depends(get_task_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    current_user: User = Depends(get_current_user_profile)
):
    """
    List tasks with optional filtering, respecting user permissions.
    """
    logger.info(f"User {current_user.id} (Role: {current_user.role}) listing tasks. Filters: assignee={assignee_id}, status={status_filter}")
    
    current_user_id_str = str(current_user.id)
    final_tasks: List[Task] = []
    seen_task_ids = set()

    def add_task_if_not_seen(task: Task):
        if task.id not in seen_task_ids:
            final_tasks.append(task)
            seen_task_ids.add(task.id)

    def user_has_access_to_task(task: Task, user_id: str) -> bool:
        if task.assignee_id and str(task.assignee_id) == user_id:
            return True
        if task.responsible_id and str(task.responsible_id) == user_id:
            return True
        if task.accountable_id and str(task.accountable_id) == user_id:
            return True
        if task.consulted_ids and user_id in [str(uid) for uid in task.consulted_ids if uid is not None]:
            return True
        if task.informed_ids and user_id in [str(uid) for uid in task.informed_ids if uid is not None]:
            return True
        if task.creator_id and str(task.creator_id) == user_id:
            return True
        return False

    if current_user.role == UserRole.ADMIN:
        logger.info(f"Admin user {current_user.id} fetching tasks.")
        if assignee_id:
            tasks_for_assignee = await task_repo.find_tasks_by_assignee(assignee_id)
            for task in tasks_for_assignee:
                add_task_if_not_seen(task)
            logger.info(f"Admin found {len(final_tasks)} tasks for assignee {assignee_id}")
        elif status_filter:
            tasks_with_status = await task_repo.find_tasks_by_status(status_filter)
            for task in tasks_with_status:
                add_task_if_not_seen(task)
            logger.info(f"Admin found {len(final_tasks)} tasks with status {status_filter}")
        else:
            all_tasks = await task_repo.find_all_tasks()
            for task in all_tasks:
                add_task_if_not_seen(task)
            logger.info(f"Admin fetched all {len(final_tasks)} tasks.")

    else:
        logger.info(f"Non-admin user {current_user.id} (Role: {current_user.role}) fetching tasks.")
        if assignee_id:
            tasks_for_assignee = await task_repo.find_tasks_by_assignee(assignee_id)
            for task in tasks_for_assignee:
                if user_has_access_to_task(task, current_user_id_str):
                    add_task_if_not_seen(task)
            logger.info(f"User {current_user.id} found {len(final_tasks)} tasks for assignee {assignee_id} they have access to.")
        
        elif status_filter:
            tasks_with_status = await task_repo.find_tasks_by_status(status_filter)
            for task in tasks_with_status:
                if user_has_access_to_task(task, current_user_id_str):
                    add_task_if_not_seen(task)
            logger.info(f"User {current_user.id} found {len(final_tasks)} tasks with status {status_filter} they have access to.")
        
        else:
            logger.info(f"User {current_user.id} fetching all tasks they are involved in.")
            involved_tasks = await task_repo.find_tasks_for_user(current_user.id)
            for task in involved_tasks:
                add_task_if_not_seen(task)

    response_tasks = []
    for task_obj in final_tasks:
        if hasattr(task_obj, 'to_dict') and callable(task_obj.to_dict):
            response_tasks.append(task_obj.to_dict())
        elif hasattr(task_obj, 'model_dump') and callable(task_obj.model_dump):
            response_tasks.append(task_obj.model_dump(by_alias=True))
        else:
            logger.warning(f"Task object {task_obj.id} could not be serialized to dict.")
            try:
                response_tasks.append(dict(task_obj))
            except TypeError:
                 logger.error(f"Could not convert task {task_obj.id} to dict for response.")

    return {
        "tasks": response_tasks,
        "total": len(response_tasks)
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
    task = await task_repo.get_task_by_id(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    current_user_id_str = str(current_user.id)
    if not (
        (task.assignee_id and str(task.assignee_id) == current_user_id_str) or
        (task.responsible_id and str(task.responsible_id) == current_user_id_str) or
        (task.accountable_id and str(task.accountable_id) == current_user_id_str) or
        (task.consulted_ids and current_user_id_str in [str(uid) for uid in task.consulted_ids]) or
        (task.informed_ids and current_user_id_str in [str(uid) for uid in task.informed_ids]) or
        (task.creator_id and str(task.creator_id) == current_user_id_str)
    ):
        logger.warning(f"User {current_user.id} does not have permission to view task {task_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized to view this task")

    return task.to_dict()

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate = Body(...),
    task_repo: TaskRepository = Depends(get_task_repository),
    raci_service: RaciService = Depends(get_raci_service),
    notification_service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user_profile)
):
    """
    Update a task's details or status.
    """
    logger.info(f"User {current_user.id} attempting to update task {task_id}")
    existing_task = await task_repo.get_task_by_id(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")

    current_user_id_str = str(current_user.id)
    can_update = False
    if existing_task.assignee_id and str(existing_task.assignee_id) == current_user_id_str:
        can_update = True
    elif existing_task.responsible_id and str(existing_task.responsible_id) == current_user_id_str:
        can_update = True
    elif existing_task.accountable_id and str(existing_task.accountable_id) == current_user_id_str:
        can_update = True

    if not can_update:
        logger.warning(f"User {current_user.id} does not have permission to update task {task_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized to update this task")

    update_data = task_update.dict(exclude_unset=True)
    final_update_payload = {}

    raci_fields_to_update = {}
    if task_update.responsible_id is not None: raci_fields_to_update['responsible_id'] = task_update.responsible_id
    if task_update.accountable_id is not None: raci_fields_to_update['accountable_id'] = task_update.accountable_id
    if task_update.consulted_ids is not None: raci_fields_to_update['consulted_ids'] = task_update.consulted_ids
    if task_update.informed_ids is not None: raci_fields_to_update['informed_ids'] = task_update.informed_ids
    
    if raci_fields_to_update:
        final_update_payload.update(raci_fields_to_update)

    simple_update_fields = task_update.dict(exclude_unset=True, exclude={'status', 'responsible_id', 'accountable_id', 'consulted_ids', 'informed_ids', 'blocked_reason'})
    if simple_update_fields:
        final_update_payload.update(simple_update_fields)
    
    if task_update.status:
        try:
            status_enum = TaskStatus(task_update.status)
            final_update_payload['status'] = status_enum
            
            if status_enum == TaskStatus.BLOCKED:
                block_reason = task_update.blocked_reason or "Task blocked without a specific reason."
                final_update_payload['blocked_reason'] = block_reason
                logger.info(f"Task {task_id} is being blocked. Reason: {block_reason}")
                await notification_service.blocked_task_alert(existing_task.id, block_reason, blocking_user=current_user)
            elif existing_task.status == TaskStatus.BLOCKED and status_enum != TaskStatus.BLOCKED:
                final_update_payload['blocked_reason'] = None

        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {task_update.status}")
    
    if not final_update_payload:
        logger.info(f"No update data provided for task {task_id}")
        return existing_task.to_dict()

    updated_task = await task_repo.update_task(task_id, final_update_payload)
    if not updated_task:
        raise HTTPException(status_code=500, detail="Failed to update task")
    
    return updated_task.to_dict()

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    task_repo: TaskRepository = Depends(get_task_repository),
    current_user: User = Depends(get_current_user_profile)
):
    """
    Delete a task.
    """
    logger.info(f"User {current_user.id} (Role: {current_user.role}) attempting to delete task {task_id}")
    existing_task = await task_repo.get_task_by_id(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    can_delete = False
    # ADMINs can delete any task
    if current_user.role == UserRole.ADMIN:
        can_delete = True
        logger.info(f"Admin user {current_user.id} authorized to delete task {task_id}.")
    # Users can delete if they are accountable for the task
    elif existing_task.accountable_id and str(current_user.id) == str(existing_task.accountable_id):
        can_delete = True
    # Users can delete if they are the creator of the task
    elif existing_task.creator_id and str(current_user.id) == str(existing_task.creator_id):
        can_delete = True
    
    if not can_delete:
        logger.warning(f"User {current_user.id} does not have permission to delete task {task_id}. Accountable: {existing_task.accountable_id}, Creator: {existing_task.creator_id}, User Role: {current_user.role}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized to delete this task")
    
    deleted = await task_repo.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete task")
    
    logger.info(f"Task {task_id} deleted successfully by user {current_user.id}")
    return