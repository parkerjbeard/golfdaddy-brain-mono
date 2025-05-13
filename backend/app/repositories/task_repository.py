from typing import List, Optional, Dict, Any
from uuid import UUID
from supabase import Client, PostgrestAPIResponse # Import for type hint
from app.config.supabase_client import get_supabase_client_safe
from app.models.task import Task, TaskStatus # Pydantic model
from app.models.user import User # Assuming this is needed for creator/user context eventually
import logging
import asyncio
from datetime import datetime # Added for type checking
from decimal import Decimal # Ensure Decimal is imported
from app.core.exceptions import DatabaseError, ResourceNotFoundError, BadRequestError

logger = logging.getLogger(__name__)

class TaskRepository:
    def __init__(self, client: Client = None):
        self._client = client if client is not None else get_supabase_client_safe()
        self._table = "tasks"

    def _handle_supabase_error(self, response: PostgrestAPIResponse, context_message: str):
        """Helper to log and raise DatabaseError from Supabase errors."""
        if response and hasattr(response, 'error') and response.error:
            logger.error(f"{context_message}: Supabase error code {response.error.code if hasattr(response.error, 'code') else 'N/A'} - {response.error.message}")
            raise DatabaseError(f"{context_message}: {response.error.message}")

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
                
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).insert(task_dict).execute
            )
            
            self._handle_supabase_error(response, "Failed to create task")
            if response.data:
                logger.info(f"Successfully created task: {response.data[0]['id']}")
                return Task(**response.data[0])
            else:
                # This path should ideally be caught by _handle_supabase_error if error exists
                logger.error(f"Failed to create task: No data returned and no Supabase error object.")
                raise DatabaseError("Failed to create task: No data returned.")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating task: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error creating task: {str(e)}")

    async def get_task_by_id(self, task_id: UUID) -> Optional[Task]:
        """Retrieves a task by its ID."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("id", str(task_id)).maybe_single().execute
            )
            if response.data:
                return Task(**response.data)
            elif response.status_code == 406 or (not response.data and not response.error):
                logger.info(f"Task with ID {task_id} not found.")
                return None
            else:
                self._handle_supabase_error(response, f"Error fetching task by ID {task_id}")
                raise DatabaseError(f"Failed to fetch task by ID {task_id} for unknown reason.")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting task by ID {task_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error getting task by ID {task_id}: {str(e)}")

    async def find_tasks_by_assignee(self, assignee_id: UUID) -> List[Task]:
        """Finds all tasks assigned to a specific user."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("assignee_id", str(assignee_id)).execute
            )
            self._handle_supabase_error(response, f"Error finding tasks for assignee {assignee_id}")
            return [Task(**item) for item in response.data] if response.data else []
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error finding tasks for assignee {assignee_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error finding tasks for assignee {assignee_id}: {str(e)}")

    async def find_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Finds all tasks with a specific status."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("status", status.value).execute
            )
            self._handle_supabase_error(response, f"Error finding tasks by status {status.value}")
            return [Task(**item) for item in response.data] if response.data else []
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error finding tasks by status {status.value}: {e}", exc_info=True)
            raise DatabaseError(f"Error finding tasks by status {status.value}: {str(e)}")
            
    async def find_tasks_by_raci_role(self, user_id: UUID, role_field: str) -> List[Task]:
        """Finds tasks where the user has a specific RACI role.
           role_field should be one of: 'responsible_id', 'accountable_id', 'consulted_ids', 'informed_ids'
        """
        if role_field not in ["responsible_id", "accountable_id", "consulted_ids", "informed_ids"]:
            # This is a programming error or invalid input, not a DB error.
            logger.error(f"Invalid RACI role field specified: {role_field}")
            raise BadRequestError(f"Invalid RACI role field specified: {role_field}")
        
        try:
            query = self._client.table(self._table).select("*") 
            user_id_str = str(user_id)

            if role_field in ["responsible_id", "accountable_id"]:
                query = query.eq(role_field, user_id_str)
            elif role_field in ["consulted_ids", "informed_ids"]:
                query = query.contains(role_field, [user_id_str])
                
            response: PostgrestAPIResponse = await asyncio.to_thread(query.execute)
            
            self._handle_supabase_error(response, f"Error finding tasks for user {user_id} in role {role_field}")
            return [Task(**item) for item in response.data] if response.data else []
        except (DatabaseError, BadRequestError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error finding tasks by RACI role for user {user_id}, role {role_field}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error finding tasks by RACI role for user {user_id}, role {role_field}: {str(e)}")

    async def find_tasks_for_user(self, user_id: UUID) -> List[Task]:
        """Finds all tasks where the user is an assignee or involved in any RACI role."""
        try:
            user_id_str = str(user_id)
            or_filter_parts = [
                f"assignee_id.eq.{user_id_str}",
                f"responsible_id.eq.{user_id_str}",
                f"accountable_id.eq.{user_id_str}",
                f"consulted_ids.cs.{{\"{user_id_str}\"}}", 
                f"informed_ids.cs.{{\"{user_id_str}\"}}",
                f"creator_id.eq.{user_id_str}"
            ]
            or_filter = ",".join(or_filter_parts)
            
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table)
                .select("*")
                .or_(or_filter)
                .execute
            )

            self._handle_supabase_error(response, f"Error finding tasks for user {user_id_str} (OR filter)")
            return [Task(**item) for item in response.data] if response.data else []
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error finding tasks for user {user_id} (OR filter): {e}", exc_info=True)
            raise DatabaseError(f"Error finding tasks for user {user_id} (OR filter): {str(e)}")

    async def find_all_tasks(self, limit: int = 100, offset: int = 0) -> List[Task]:
        """Retrieves all tasks, with optional pagination."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").range(offset, offset + limit - 1).execute
            )
            self._handle_supabase_error(response, "Error fetching all tasks")
            return [Task(**item) for item in response.data] if response.data else []
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error fetching all tasks: {e}", exc_info=True)
            raise DatabaseError(f"Error fetching all tasks: {str(e)}")

    async def update_task(self, task_id: UUID, update_data: Dict[str, Any]) -> Optional[Task]:
        """Updates a task's data."""
        try:
            if 'id' in update_data:
                del update_data['id']
            
            if not update_data:
                logger.warning(f"Update_task called with empty data for task_id {task_id}")
                return await self.get_task_by_id(task_id) # Return existing task if no update data
                
            processed_update_data = self._process_dict_for_supabase(update_data)

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).update(processed_update_data).eq("id", str(task_id)).execute
            )

            if response.data:
                logger.info(f"Successfully updated task: {task_id}")
                return Task(**response.data[0])
            else:
                # Check if task exists before claiming update failed due to other DB error
                existing_task = await self.get_task_by_id(task_id)
                if not existing_task:
                    logger.error(f"Failed to update task: Task with ID {task_id} not found.")
                    raise ResourceNotFoundError(resource_name="Task", resource_id=str(task_id))
                
                self._handle_supabase_error(response, f"Failed to update task {task_id}")
                # If _handle_supabase_error didn't raise, it means no specific error, but no data was returned.
                logger.error(f"Failed to update task {task_id}: No data returned and no specific Supabase error. Task might exist but update failed.")
                raise DatabaseError(f"Failed to update task {task_id}: Update operation returned no data.")
        except (DatabaseError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating task {task_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error updating task {task_id}: {str(e)}")

    async def delete_task(self, task_id: UUID) -> bool:
        """Deletes a task by its ID."""
        try:
            existing_task = await self.get_task_by_id(task_id)
            if not existing_task:
                logger.warning(f"Attempted to delete non-existent task with ID {task_id}")
                raise ResourceNotFoundError(resource_name="Task", resource_id=str(task_id))

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).delete().eq("id", str(task_id)).execute
            )
            self._handle_supabase_error(response, f"Failed to delete task {task_id}")
            logger.info(f"Delete operation for task {task_id} successful.")
            return True
        except (DatabaseError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting task {task_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error deleting task {task_id}: {str(e)}")