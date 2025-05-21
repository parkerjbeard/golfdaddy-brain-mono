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
from app.services.notification_service import NotificationService # Uncommented and ensured import

logger = logging.getLogger(__name__)

class RaciService:
    """Service for enforcing RACI rules for tasks."""
    
    def __init__(self):
        # Instantiate repositories directly
        # In a larger app, consider dependency injection framework
        self.task_repo = TaskRepository()
        self.user_repo = UserRepository()
        self.notification_service = NotificationService() # Instantiated NotificationService
    
    async def register_raci_assignments(
        self,
        title: str,
        description: str,
        assignee_id: UUID,
        creator_id: UUID,
        responsible_id: Optional[UUID] = None,
        accountable_id: Optional[UUID] = None,
        consulted_ids: Optional[List[UUID]] = None,
        informed_ids: Optional[List[UUID]] = None,
        due_date: Optional[datetime] = None,
        task_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: Optional[str] = None
    ) -> Tuple[Optional[Task], List[str]]:
        """Validates RACI roles, creates a Task object with all details, persists it, and returns task with warnings."""
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
            title=title,
            description=description,
            assignee_id=assignee_id,
            responsible_id=responsible_id, # Already validated or defaulted from validated assignee
            accountable_id=accountable_id, # Already validated or defaulted from validated assignee
            consulted_ids=valid_consulted_ids, # Use validated list
            informed_ids=valid_informed_ids,   # Use validated list
            creator_id=creator_id, # Validated
            due_date=due_date,
            status=TaskStatus.ASSIGNED, # Default status
            task_type=task_type,
            metadata=metadata if metadata else {},
            priority=priority,
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
        """Handles escalation logic when a task is marked as blocked, including notifications."""
        task = await self.task_repo.get_task_by_id(task_id)
        
        if not task:
            logger.warning(f"Escalation requested for non-existent task {task_id}")
            return
        
        if task.status != TaskStatus.BLOCKED:
            logger.warning(f"Escalation requested for task {task_id} which is not blocked (status: {task.status})")
            return

        accountable_user_notified = False
        if task.accountable_id:
            accountable_user = await self.user_repo.get_user_by_id(task.accountable_id)
            if accountable_user:
                logger.info(f"Escalating blocked task {task.id} to Accountable user {accountable_user.id} (Slack: {getattr(accountable_user, 'slack_id', 'N/A')})")
                try:
                    await self.notification_service.blocked_task_alert(
                        task_id=task.id, 
                        reason=f"Task {task.id} ({task.title[:30]}...) is BLOCKED. Escalating to Accountable User."
                        # blocking_user can be added if known
                    )
                    accountable_user_notified = True
                    logger.info(f"Notification sent to accountable user {accountable_user.id} for task {task.id}.")
                except Exception as e:
                    logger.error(f"Failed to send blocked_task_alert to accountable user {accountable_user.id} for task {task.id}: {e}", exc_info=True)
            else:
                logger.error(f"Accountable user {task.accountable_id} not found for escalating task {task.id}. Proceeding to fallback escalation.")
        else:
            logger.warning(f"Task {task.id} has no accountable_id set. Proceeding to fallback escalation.")

        if accountable_user_notified:
            return # Primary escalation target handled

        # Fallback escalation logic
        logger.info(f"Initiating fallback escalation for blocked task {task.id}.")
        
        creator_notified_for_fallback = False
        escalation_target_description = "No specific user identified or notified for fallback."

        if task.creator_id:
            creator_user = await self.user_repo.get_user_by_id(task.creator_id)
            if creator_user:
                logger.info(f"Fallback escalation for task {task.id}: Attempting to notify creator {creator_user.id} (Slack: {getattr(creator_user, 'slack_id', 'N/A')}).")
                fallback_reason = (
                    f"Task {task.id} ({task.title[:30]}...) is BLOCKED. "
                    f"Fallback escalation to Creator as Accountable user (ID: {task.accountable_id if task.accountable_id else 'Not Set'}) "
                    f"was not found or not assigned."
                )
                try:
                    await self.notification_service.notify_task_escalation_fallback(
                        task=task,
                        escalated_to_user=creator_user,
                        reason_summary=fallback_reason
                    )
                    creator_notified_for_fallback = True
                    escalation_target_description = f"Task Creator ({creator_user.id}) notified."
                    logger.info(f"Fallback notification sent to creator {creator_user.id} for task {task.id}.")
                except Exception as e:
                    logger.error(f"Failed to send notify_task_escalation_fallback to creator {creator_user.id} for task {task.id}: {e}", exc_info=True)
                    escalation_target_description = f"Task Creator ({creator_user.id}) notification attempt failed."
            else:
                logger.error(f"Task creator {task.creator_id} not found for task {task.id} during fallback escalation.")
                escalation_target_description = "Task Creator user record not found."
        else:
            logger.warning(f"Task {task.id} has no creator_id for fallback escalation.")
            escalation_target_description = "Task Creator ID not set on task."

        if creator_notified_for_fallback:
            logger.info(f"Fallback escalation for task {task.id} successfully processed to creator.")
        else:
            logger.warning(f"Could not complete fallback escalation notification for task {task.id}. Status: {escalation_target_description}")

        # Further fallback steps (system alerts, admin notifications) are logged below but not implemented as direct notifications here.
        logger.info(
            f"Blocked task {task.id} requires further attention if not resolved by user notifications. "
            f"Final fallback notification status: {escalation_target_description}. Consider system-level alerting/flagging."
        )
        # Example for dashboard flagging (remains a comment):
        # await self.system_alert_service.flag_task_for_manual_review(
        #     task_id=task.id, 
        #     reason=f"Blocked - Accountable user/fallback to creator ({escalation_target_description}) failed or needs review"
        # )

    # Add other RACI related business logic methods here