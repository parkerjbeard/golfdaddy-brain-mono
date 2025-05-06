from typing import List, Optional, Dict, Any
from uuid import UUID
from supabase import Client
from app.config.supabase_client import get_supabase_client
from app.models.user import User, UserRole # Import Pydantic model
import logging
import json

logger = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, client: Client = get_supabase_client()):
        self._client = client
        self._table = "users"

    def create_user(self, user_data: User) -> Optional[User]:
        """Creates a new user profile record in the database.
           Assumes the corresponding auth.users entry already exists.
           The user_data.id MUST match the auth.users.id.
        """
        try:
            user_dict = user_data.model_dump(exclude_unset=True) # Use model_dump for Pydantic v2
            # Ensure id is present as it links to auth.users
            if 'id' not in user_dict or not user_dict['id']:
                logger.error("Cannot create user profile without a valid ID linked to auth.users.")
                return None

            response = self._client.table(self._table).insert(user_dict).execute()
            
            if response.data:
                logger.info(f"Successfully created user profile for ID: {response.data[0]['id']}")
                return User(**response.data[0])
            else:
                 # Log Supabase errors if available
                error_message = response.error.message if response.error else "Unknown error"
                logger.error(f"Failed to create user profile: {error_message}")
                return None
        except Exception as e:
            logger.exception(f"Error creating user profile: {e}")
            return None

    def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Retrieves a user by their UUID (which matches auth.users.id)."""
        try:
            response = self._client.table(self._table).select("*").eq("id", str(user_id)).maybe_single().execute()
            if response.data:
                return User(**response.data)
            else:
                # Log Supabase errors if available and not just 'Not Found'
                if response.error and response.status_code != 406: # 406 means no rows found for maybe_single()
                     logger.error(f"Error fetching user by ID {user_id}: {response.error.message}")
                return None
        except Exception as e:
            logger.exception(f"Error getting user by ID {user_id}: {e}")
            return None

    def get_user_by_slack_id(self, slack_id: str) -> Optional[User]:
        """Retrieves a user by their Slack ID."""
        try:
            response = self._client.table(self._table).select("*").eq("slack_id", slack_id).maybe_single().execute()
            if response.data:
                return User(**response.data)
            else:
                if response.error and response.status_code != 406:
                    logger.error(f"Error fetching user by Slack ID {slack_id}: {response.error.message}")
                return None
        except Exception as e:
            logger.exception(f"Error getting user by Slack ID {slack_id}: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieves a user by their email address."""
        try:
            logger.info(f"Looking up user by email: {email}")
            
            # Use from_ instead of table() to help bypass RLS
            logger.info(f"Sending request to Supabase users table using from_ method")
            response = self._client.from_(self._table).select("*").eq("email", email).maybe_single().execute()
            
            # Log the response status
            logger.info(f"Supabase response status for email lookup: {getattr(response, 'status_code', 'unknown')}")
            
            # Check if response itself is None before trying to access response.data
            if response is None:
                logger.error(f"Received None response when fetching user by email {email}")
                return None
                
            if hasattr(response, 'error') and response.error:
                logger.error(f"Supabase error in email lookup: {response.error.message if hasattr(response.error, 'message') else response.error}")
                
            if response.data:
                logger.info(f"Found user with email {email}: {response.data.get('id')}")
                # Log user fields but redact sensitive information
                user_fields = {k: v for k, v in response.data.items() if k not in ['password', 'token']}
                logger.info(f"User data retrieved: {json.dumps(user_fields, default=str)}")
                return User(**response.data)
            else:
                if response.error and response.status_code != 406:  # 406 means no rows found
                    logger.error(f"Error fetching user by email {email}: {response.error.message}")
                logger.warning(f"No user found with email {email}")
                return None
        except Exception as e:
            logger.exception(f"Error getting user by email {email}: {e}")
            return None

    def list_users_by_role(self, role: UserRole) -> List[User]:
        """Lists all users with a specific role."""
        try:
            response = self._client.table(self._table).select("*").eq("role", role.value).execute()
            if response.data:
                return [User(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error listing users by role {role.value}: {response.error.message}")
                return []
        except Exception as e:
            logger.exception(f"Error listing users by role {role.value}: {e}")
            return []

    def list_all_users(self) -> List[User]:
        """Lists all users in the profile table."""
        try:
            response = self._client.table(self._table).select("*").execute()
            if response.data:
                return [User(**item) for item in response.data]
            else:
                if response.error:
                    logger.error(f"Error listing all users: {response.error.message}")
                return []
        except Exception as e:
            logger.exception(f"Error listing all users: {e}")
            return []

    def update_user(self, user_id: UUID, update_data: Dict[str, Any]) -> Optional[User]:
        """Updates a user's profile data.
           `update_data` should be a dictionary of fields to update.
        """
        try:
            # Optional: Validate update_data against User model fields if needed
            # We don't allow changing the primary key (id)
            if 'id' in update_data:
                del update_data['id']
            
            response = self._client.table(self._table).update(update_data).eq("id", str(user_id)).execute()
            if response.data:
                logger.info(f"Successfully updated user profile for ID: {user_id}")
                return User(**response.data[0])
            else:
                # Log Supabase errors if available
                error_message = response.error.message if response.error else "Unknown error or user not found"
                logger.error(f"Failed to update user profile {user_id}: {error_message}")
                return None
        except Exception as e:
            logger.exception(f"Error updating user profile {user_id}: {e}")
            return None

    def delete_user(self, user_id: UUID) -> bool:
        """Deletes a user's profile record. Does not delete the auth.users entry."""
        try:
            response = self._client.table(self._table).delete().eq("id", str(user_id)).execute()
            # Check if deletion was successful (response.data might be empty on success)
            if response.error:
                 logger.error(f"Failed to delete user profile {user_id}: {response.error.message}")
                 return False
            logger.info(f"Successfully deleted user profile for ID: {user_id}")
            return True
        except Exception as e:
            logger.exception(f"Error deleting user profile {user_id}: {e}")
            return False