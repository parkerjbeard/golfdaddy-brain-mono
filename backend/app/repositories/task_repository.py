from typing import List, Optional, Dict, Any
from uuid import UUID
from supabase import Client
from app.config.supabase_client import get_supabase_client_safe
from app.models.task import Task, TaskStatus # Pydantic model
from app.models.user import User # Assuming this is needed for creator/user context eventually
import logging
import asyncio
from datetime import datetime # Added for type checking
from decimal import Decimal # Ensure Decimal is imported

logger = logging.getLogger(__name__)

class TaskRepository:
    def __init__(self, client: Client = None):
        self._client = client if client is not None else get_supabase_client_safe()
        self._table = "tasks"

    def _process_dict_for_supabase(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        processed_dict = {}
        for key, value in data_dict.items():
            if isinstance(value, UUID):
                processed_dict[key] = str(value)
            elif isinstance(value, list) and value and isinstance(value[0], UUID):
                processed_dict[key] = [str(v) for v in value]
            elif isinstance(value, TaskStatus):
                processed_dict[key] = value.value
            elif isinstance(value, datetime):
                processed_dict[key] = value.isoformat()
            elif isinstance(value, Decimal): # Added Decimal to float conversion
                processed_dict[key] = float(value)
            else:
                processed_dict[key] = value
        return processed_dict

    async def create_task(self, task_data: Task) -> Optional[Task]:
        """Creates a new task in the database."""
        try:
            task_dict_initial = task_data.model_dump(exclude_unset=True, exclude_none=True, by_alias=False)
            task_dict = self._process_dict_for_supabase(task_dict_initial)

            if 'id' in task_dict and task_dict['id'] is None:
                del task_dict['id'] 
                
            response = await asyncio.to_thread(
                self._client.table(self._table).insert(task_dict).execute
            )
            
            if response.data:
                logger.info(f"Successfully created task: {response.data[0]['id']}")
                return Task(**response.data[0])
            else:
                error_message = response.error.message if response.error else "Unknown error"
                logger.error(f"Failed to create task: {error_message} {getattr(response, 'details', '')}")
                return None
        except Exception as e:
            logger.exception(f"Error creating task: {e}")
            return None

    async def get_task_by_id(self, task_id: UUID) -> Optional[Task]:
        """Retrieves a task by its ID."""
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("id", str(task_id)).maybe_single().execute
            )
            if response.data:
                return Task(**response.data)
            else:
                if response.error and response.status_code != 406: 
                     logger.error(f"Error fetching task by ID {task_id}: {response.error.message}")
                return None
        except Exception as e:
            logger.exception(f"Error getting task by ID {task_id}: {e}")
            return None

    async def find_tasks_by_assignee(self, assignee_id: UUID) -> List[Task]:
        """Finds all tasks assigned to a specific user."""
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("assignee_id", str(assignee_id)).execute
            )
            if response.data:
                return [Task(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error finding tasks for assignee {assignee_id}: {response.error.message}")
                return []
        except Exception as e:
            logger.exception(f"Error finding tasks for assignee {assignee_id}: {e}")
            return []

    async def find_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Finds all tasks with a specific status."""
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("status", status.value).execute
            )
            if response.data:
                return [Task(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error finding tasks by status {status.value}: {response.error.message}")
                return []
        except Exception as e:
            logger.exception(f"Error finding tasks by status {status.value}: {e}")
            return []
            
    async def find_tasks_by_raci_role(self, user_id: UUID, role_field: str) -> List[Task]:
        """Finds tasks where the user has a specific RACI role.
           role_field should be one of: 'responsible_id', 'accountable_id', 'consulted_ids', 'informed_ids'
        """
        if role_field not in ["responsible_id", "accountable_id", "consulted_ids", "informed_ids"]:
            raise ValueError("Invalid RACI role field specified")
        
        try:
            query = self._client.table(self._table).select("*") # Changed back to query for clarity
            user_id_str = str(user_id)

            if role_field in ["responsible_id", "accountable_id"]:
                query = query.eq(role_field, user_id_str)
            elif role_field in ["consulted_ids", "informed_ids"]:
                query = query.contains(role_field, [user_id_str])
                
            response = await asyncio.to_thread(query.execute) # Use the final query object
            
            if response.data:
                return [Task(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error finding tasks for user {user_id} in role {role_field}: {response.error.message}")
                return []
        except Exception as e:
            logger.exception(f"Error finding tasks by RACI role for user {user_id}, role {role_field}: {e}")
            return []

    async def find_tasks_for_user(self, user_id: UUID) -> List[Task]:
        """Finds all tasks where the user is an assignee or involved in any RACI role."""
        try:
            user_id_str = str(user_id)
            # For .or_ clauses with array columns (like consulted_ids, informed_ids) using contains (cs):
            # The value should be formatted as a string representing a PostgreSQL array literal, e.g., '{"uuid-value"}'
            # if you are matching a single element within the array.
            or_filter_parts = [
                f"assignee_id.eq.{user_id_str}",
                f"responsible_id.eq.{user_id_str}",
                f"accountable_id.eq.{user_id_str}",
                f"consulted_ids.cs.{{\"{user_id_str}\"}}", 
                f"informed_ids.cs.{{\"{user_id_str}\"}}",
                f"creator_id.eq.{user_id_str}"  # Added creator_id to this general user query
            ]
            or_filter = ",".join(or_filter_parts)
            
            logger.debug(f"Executing find_tasks_for_user with or_filter: {or_filter}")

            response = await asyncio.to_thread(
                self._client.table(self._table)
                .select("*")
                .or_(or_filter)
                .execute
            )

            if response.data:
                return [Task(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error finding tasks for user {user_id_str} (OR filter): {response.error.message} {getattr(response, 'details', '')}")
                return []
        except Exception as e:
            logger.exception(f"Error finding tasks for user {user_id} (OR filter): {e}")
            return []

    async def find_all_tasks(self, limit: int = 100, offset: int = 0) -> List[Task]: # Added pagination params
        """Retrieves all tasks, with optional pagination."""
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table).select("*").range(offset, offset + limit - 1).execute
            )
            if response.data:
                return [Task(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error fetching all tasks: {response.error.message}")
                return []
        except Exception as e:
            logger.exception(f"Error fetching all tasks: {e}")
            return []

    async def update_task(self, task_id: UUID, update_data: Dict[str, Any]) -> Optional[Task]:
        """Updates a task's data."""
        try:
            if 'id' in update_data:
                del update_data['id']
                
            processed_update_data = self._process_dict_for_supabase(update_data)

            response = await asyncio.to_thread(
                self._client.table(self._table).update(processed_update_data).eq("id", str(task_id)).execute
            )
            if response.data:
                logger.info(f"Successfully updated task: {task_id}")
                return Task(**response.data[0])
            else:
                error_message = response.error.message if response.error else "Unknown error or task not found"
                logger.error(f"Failed to update task {task_id}: {error_message} {getattr(response, 'details', '')}")
                return None
        except Exception as e:
            logger.exception(f"Error updating task {task_id}: {e}")
            return None

    async def delete_task(self, task_id: UUID) -> bool:
        """Deletes a task by its ID."""
        try:
            response = await asyncio.to_thread(
                self._client.table(self._table).delete().eq("id", str(task_id)).execute
            )
            # For delete, PostgREST returns 204 No Content on success, and data is often empty or just count.
            # Check for error first.
            if response.error:
                 logger.error(f"Failed to delete task {task_id}: {response.error.message} {getattr(response, 'details', '')}")
                 return False
            
            # Successfully initiated delete if no error, log status for confirmation
            logger.info(f"Delete operation for task {task_id} resulted in status: {response.status_code}")
            # Typically, a successful delete might return a count of deleted rows or be reflected in status_code.
            # If response.count is available and reliable from Supabase client for delete, it could be checked.
            # For now, lack of error implies success.
            return True
        except Exception as e:
            logger.exception(f"Error deleting task {task_id}: {e}")
            return False