from typing import List, Optional, Dict, Any
from uuid import UUID
from supabase import Client
from app.config.supabase_client import get_supabase_client
from app.models.task import Task, TaskStatus # Pydantic model
import logging

logger = logging.getLogger(__name__)

class TaskRepository:
    def __init__(self, client: Client = get_supabase_client()):
        self._client = client
        self._table = "tasks"

    def create_task(self, task_data: Task) -> Optional[Task]:
        """Creates a new task in the database."""
        try:
            # Exclude fields that the DB generates (id, created_at, updated_at) if they are None
            task_dict = task_data.model_dump(exclude_unset=True, exclude_none=True)
            if 'id' in task_dict and task_dict['id'] is None:
                del task_dict['id'] # Let DB generate UUID
                
            response = self._client.table(self._table).insert(task_dict).execute()
            
            if response.data:
                logger.info(f"Successfully created task: {response.data[0]['id']}")
                return Task(**response.data[0])
            else:
                error_message = response.error.message if response.error else "Unknown error"
                logger.error(f"Failed to create task: {error_message}")
                return None
        except Exception as e:
            logger.exception(f"Error creating task: {e}")
            return None

    def get_task_by_id(self, task_id: UUID) -> Optional[Task]:
        """Retrieves a task by its ID."""
        try:
            response = self._client.table(self._table).select("*").eq("id", str(task_id)).maybe_single().execute()
            if response.data:
                return Task(**response.data)
            else:
                if response.error and response.status_code != 406: 
                     logger.error(f"Error fetching task by ID {task_id}: {response.error.message}")
                return None
        except Exception as e:
            logger.exception(f"Error getting task by ID {task_id}: {e}")
            return None

    def find_tasks_by_assignee(self, assignee_id: UUID) -> List[Task]:
        """Finds all tasks assigned to a specific user."""
        try:
            response = self._client.table(self._table).select("*").eq("assignee_id", str(assignee_id)).execute()
            if response.data:
                return [Task(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error finding tasks for assignee {assignee_id}: {response.error.message}")
                return []
        except Exception as e:
            logger.exception(f"Error finding tasks for assignee {assignee_id}: {e}")
            return []

    def find_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Finds all tasks with a specific status."""
        try:
            response = self._client.table(self._table).select("*").eq("status", status.value).execute()
            if response.data:
                return [Task(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error finding tasks by status {status.value}: {response.error.message}")
                return []
        except Exception as e:
            logger.exception(f"Error finding tasks by status {status.value}: {e}")
            return []
            
    def find_tasks_by_raci_role(self, user_id: UUID, role_field: str) -> List[Task]:
        """Finds tasks where the user has a specific RACI role.
           role_field should be one of: 'responsible_id', 'accountable_id', 'consulted_ids', 'informed_ids'
        """
        if role_field not in ["responsible_id", "accountable_id", "consulted_ids", "informed_ids"]:
            raise ValueError("Invalid RACI role field specified")
        
        try:
            query = self._client.table(self._table).select("*")
            user_id_str = str(user_id)

            if role_field in ["responsible_id", "accountable_id"]:
                query = query.eq(role_field, user_id_str)
            elif role_field in ["consulted_ids", "informed_ids"]:
                # Use contains operator for array fields
                query = query.contains(role_field, [user_id_str])
                
            response = query.execute()
            
            if response.data:
                return [Task(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error finding tasks for user {user_id} in role {role_field}: {response.error.message}")
                return []
        except Exception as e:
            logger.exception(f"Error finding tasks by RACI role for user {user_id}, role {role_field}: {e}")
            return []

    def update_task(self, task_id: UUID, update_data: Dict[str, Any]) -> Optional[Task]:
        """Updates a task's data.
           `update_data` should be a dictionary of fields to update.
           Handles enum serialization automatically if Pydantic model is passed.
        """
        try:
            # Don't allow changing the primary key
            if 'id' in update_data:
                del update_data['id']
                
            # Convert enum values if present
            if 'status' in update_data and isinstance(update_data['status'], TaskStatus):
                update_data['status'] = update_data['status'].value

            response = self._client.table(self._table).update(update_data).eq("id", str(task_id)).execute()
            if response.data:
                logger.info(f"Successfully updated task: {task_id}")
                return Task(**response.data[0])
            else:
                error_message = response.error.message if response.error else "Unknown error or task not found"
                logger.error(f"Failed to update task {task_id}: {error_message}")
                return None
        except Exception as e:
            logger.exception(f"Error updating task {task_id}: {e}")
            return None

    def delete_task(self, task_id: UUID) -> bool:
        """Deletes a task by its ID."""
        try:
            response = self._client.table(self._table).delete().eq("id", str(task_id)).execute()
            if response.error:
                 logger.error(f"Failed to delete task {task_id}: {response.error.message}")
                 return False
            logger.info(f"Successfully deleted task: {task_id}")
            return True
        except Exception as e:
            logger.exception(f"Error deleting task {task_id}: {e}")
            return False