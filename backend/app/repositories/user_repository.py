import asyncio
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from supabase import Client, PostgrestAPIResponse
from app.config.supabase_client import get_supabase_client_safe
from app.models.user import User, UserRole # Import Pydantic model
import logging
import json
from datetime import datetime # For potential datetime fields in User model
from app.core.exceptions import DatabaseError, ResourceNotFoundError

logger = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, client: Client = None):
        self._client = client if client is not None else get_supabase_client_safe()
        self._table = "users"

    def _handle_supabase_error(self, response: PostgrestAPIResponse, context_message: str):
        """Helper to log and raise DatabaseError from Supabase errors."""
        if response and hasattr(response, 'error') and response.error:
            logger.error(f"{context_message}: Supabase error code {response.error.code if hasattr(response.error, 'code') else 'N/A'} - {response.error.message}")
            raise DatabaseError(f"{context_message}: {response.error.message}")
        # Add more specific checks if needed, e.g., for constraint violations like P0001, P0002, etc.

    def _process_user_dict_for_supabase(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        processed_dict = {}
        for key, value in data_dict.items():
            if isinstance(value, UUID):
                processed_dict[key] = str(value)
            elif isinstance(value, UserRole): # Assuming UserRole is an Enum
                processed_dict[key] = value.value
            elif isinstance(value, datetime):
                processed_dict[key] = value.isoformat()
            # Add other type conversions if User model has more complex types
            else:
                processed_dict[key] = value
        return processed_dict

    async def create_user(self, user_data: User) -> Optional[User]:
        """Creates a new user profile record in the database.
           Assumes the corresponding auth.users entry already exists.
           The user_data.id MUST match the auth.users.id.
        """
        try:
            user_dict_initial = user_data.model_dump(exclude_unset=True, by_alias=False)
            user_dict = self._process_user_dict_for_supabase(user_dict_initial)
            
            if 'id' not in user_dict or not user_dict['id']:
                logger.error("Cannot create user profile without a valid ID linked to auth.users.")
                raise DatabaseError("User profile creation requires a valid ID.") # Or BadRequestError depending on context

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).insert(user_dict).execute
            )
            
            self._handle_supabase_error(response, "Failed to create user profile")
            if response.data:
                logger.info(f"Successfully created user profile for ID: {response.data[0]['id']}")
                return User(**response.data[0])
            else:
                # This path should ideally be caught by _handle_supabase_error if error exists
                logger.error(f"Failed to create user profile: No data returned and no Supabase error object.")
                raise DatabaseError("Failed to create user profile: No data returned.")
        except DatabaseError: # Re-raise if already our custom type
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating user profile: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error creating user profile: {str(e)}")

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Retrieves a user by their UUID."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("id", str(user_id)).maybe_single().execute
            )
            # For maybe_single(), if no data and no error, it means not found.
            # response.error might be None and response.data None/empty if not found.
            # Supabase client typically returns status 406 if maybe_single finds no data.
            if response.data:
                return User(**response.data)
            elif response.status_code == 406 or (not response.data and not response.error): # Explicit not found
                logger.info(f"User with ID {user_id} not found.")
                return None # Services expect None for not found, they will raise ResourceNotFoundError if needed
            else: # Other errors
                self._handle_supabase_error(response, f"Error fetching user by ID {user_id}")
                # If _handle_supabase_error didn't raise (e.g. response.error was None but still no data and not 406)
                raise DatabaseError(f"Failed to fetch user by ID {user_id} for unknown reason.")
        except DatabaseError:
            raise        
        except Exception as e:
            logger.error(f"Unexpected error getting user by ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error getting user by ID {user_id}: {str(e)}")

    async def get_user_by_slack_id(self, slack_id: str) -> Optional[User]:
        """Retrieves a user by their Slack ID."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("slack_id", slack_id).maybe_single().execute
            )
            if response.data:
                return User(**response.data)
            elif response.status_code == 406 or (not response.data and not response.error):
                logger.info(f"User with Slack ID {slack_id} not found.")
                return None
            else:
                self._handle_supabase_error(response, f"Error fetching user by Slack ID {slack_id}")
                raise DatabaseError(f"Failed to fetch user by Slack ID {slack_id} for unknown reason.")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting user by Slack ID {slack_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error getting user by Slack ID {slack_id}: {str(e)}")

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieves a user by their email address."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.from_(self._table).select("*").eq("email", email).maybe_single().execute
            )
            if response.data:
                return User(**response.data)
            elif response.status_code == 406 or (not response.data and not response.error):
                logger.info(f"User with email {email} not found.")
                return None
            else:
                self._handle_supabase_error(response, f"Error fetching user by email {email}")
                raise DatabaseError(f"Failed to fetch user by email {email} for unknown reason.")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting user by email {email}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error getting user by email {email}: {str(e)}")

    async def get_user_by_github_username(self, github_username: str) -> Optional[User]:
        """Retrieves a user by their GitHub username."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("github_username", github_username).maybe_single().execute
            )
            if response.data:
                return User(**response.data)
            elif response.status_code == 406 or (not response.data and not response.error):
                logger.info(f"User with GitHub username {github_username} not found.")
                return None
            else:
                self._handle_supabase_error(response, f"Error fetching user by GitHub username {github_username}")
                raise DatabaseError(f"Failed to fetch user by GitHub username {github_username} for unknown reason.")
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting user by GitHub username {github_username}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error getting user by GitHub username {github_username}: {str(e)}")

    async def list_users_by_role(self, role: UserRole) -> List[User]:
        """Lists all users with a specific role."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("role", role.value).execute
            )
            self._handle_supabase_error(response, f"Error listing users by role {role.value}")
            return [User(**item) for item in response.data] if response.data else []
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing users by role {role.value}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error listing users by role {role.value}: {str(e)}")

    async def list_all_users(self, skip: int = 0, limit: int = 100) -> Tuple[List[User], int]:
        """Lists all users in the profile table with pagination."""
        try:
            count_response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*", count='exact').limit(0).execute
            )
            self._handle_supabase_error(count_response, "Error fetching total user count")
            total_count = count_response.count if count_response.count is not None else 0

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").range(skip, skip + limit - 1).execute
            )
            self._handle_supabase_error(response, f"Error listing all users with skip={skip}, limit={limit}")
            users = [User(**item) for item in response.data] if response.data else []
            return users, total_count
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing all users: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error listing all users: {str(e)}")

    async def update_user(self, user_id: UUID, update_data: Dict[str, Any]) -> Optional[User]:
        """Updates a user's profile data."""
        try:
            if 'id' in update_data:
                del update_data['id']
            if not update_data: # Check if update_data is empty
                logger.warning(f"Update_user called with empty data for user_id {user_id}")
                # Optionally, fetch and return the user if no changes are to be made, or raise BadRequestError
                # For now, let it proceed, Supabase might handle empty update gracefully or error.
                # However, it is better to handle it here.
                # Let's assume an empty update should not proceed to DB and is not an error, but a no-op.
                # If it should be an error, raise BadRequestError("No update data provided.")
                # To maintain original behavior of potentially returning existing user, we'd fetch it.
                # For now, if we want to prevent empty updates, we'd raise or return None early.
                # Let's return the existing user if update_data is empty (treat as no-op).
                return await self.get_user_by_id(user_id)

            # If the email is being updated, reflect the change in auth.users
            if "email" in update_data:
                try:
                    await asyncio.to_thread(
                        self._client.auth.admin.update_user_by_id,
                        str(user_id),
                        {"email": update_data["email"]},
                    )
                except Exception as e:
                    logger.error(f"Failed to update auth.users email for {user_id}: {e}", exc_info=True)
                    raise DatabaseError("Error updating auth user email")

            processed_update_data = self._process_user_dict_for_supabase(update_data)
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).update(processed_update_data).eq("id", str(user_id)).execute
            )
            
            # Check if user was found and updated. Response.data will contain updated record(s).
            # If response.data is empty, it could mean user_id did not match or another issue.
            if response.data:
                logger.info(f"Successfully updated user profile for ID: {user_id}")
                return User(**response.data[0])
            else:
                # If no data, check if it was a "not found" scenario or other error
                # First, check if the user actually exists. If not, ResourceNotFoundError.
                existing_user = await self.get_user_by_id(user_id) # This returns None if not found
                if not existing_user:
                    logger.error(f"Failed to update user profile: User with ID {user_id} not found.")
                    raise ResourceNotFoundError(resource_name="User", resource_id=str(user_id))
                
                # If user exists but update failed for other reason (e.g. Supabase error not caught by `error` attribute)
                self._handle_supabase_error(response, f"Failed to update user profile {user_id}")
                logger.error(f"Failed to update user profile {user_id}: No data returned and no specific Supabase error attribute. User may exist but update failed.")
                raise DatabaseError(f"Failed to update user profile {user_id}: Update operation returned no data.")
        except (DatabaseError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating user profile {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error updating user profile {user_id}: {str(e)}")

    async def sync_profile_from_auth(self, user_id: UUID) -> Optional[User]:
        """Synchronize profile fields from auth.users into public.users."""
        try:
            auth_user = await asyncio.to_thread(
                self._client.auth.admin.get_user_by_id,
                str(user_id),
            )
            if not auth_user:
                logger.warning(f"Auth user {user_id} not found during sync")
                return None

            update_data: Dict[str, Any] = {}
            if getattr(auth_user, "email", None):
                update_data["email"] = auth_user.email
            metadata = getattr(auth_user, "user_metadata", {}) or {}
            if metadata.get("name"):
                update_data["name"] = metadata["name"]
            if metadata.get("avatar_url"):
                update_data["avatar_url"] = metadata["avatar_url"]

            if update_data:
                return await self.update_user(user_id, update_data)
            return await self.get_user_by_id(user_id)
        except Exception as e:
            logger.error(f"Failed to sync profile from auth for {user_id}: {e}", exc_info=True)
            raise DatabaseError("Error syncing profile from auth")

    async def delete_user(self, user_id: UUID) -> bool:
        """Deletes a user's profile record. Returns True if successful."""
        try:
            # Check if user exists before attempting delete to provide ResourceNotFoundError if applicable
            existing_user = await self.get_user_by_id(user_id) # Relies on get_user_by_id returning None if not found
            if not existing_user:
                logger.warning(f"Attempted to delete non-existent user profile with ID {user_id}")
                raise ResourceNotFoundError(resource_name="User", resource_id=str(user_id))

            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).delete().eq("id", str(user_id)).execute
            )
            self._handle_supabase_error(response, f"Failed to delete user profile {user_id}")
            # Successful Supabase delete often returns an empty data list but no error.
            # If response.data is not empty, it might contain the deleted record(s) depending on client/settings.
            # The primary check is for absence of error.
            logger.info(f"Successfully deleted user profile for ID: {user_id}.")
            return True
        except (DatabaseError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting user profile {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error deleting user profile {user_id}: {str(e)}")

    async def get_director_for_manager(self, manager_id: UUID) -> Optional[User]:
        """Retrieves the director of a given manager."""
        try:
            manager = await self.get_user_by_id(manager_id)
            if not manager or not manager.reports_to_id:
                logger.info(f"Manager with ID {manager_id} not found or does not report to anyone.")
                return None
            
            director = await self.get_user_by_id(manager.reports_to_id)
            if not director:
                logger.warning(f"Director with ID {manager.reports_to_id} (for manager {manager_id}) not found, though reports_to_id was set.")
            return director
        except DatabaseError: # Re-raise specific errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting director for manager {manager_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error getting director for manager {manager_id}: {str(e)}")

    async def get_direct_reports(self, manager_id: UUID) -> List[User]:
        """Retrieves all direct reports for a given manager."""
        try:
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table).select("*").eq("reports_to_id", str(manager_id)).execute
            )
            self._handle_supabase_error(response, f"Error finding direct reports for manager {manager_id}")
            return [User(**item) for item in response.data] if response.data else []
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error finding direct reports for manager {manager_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error finding direct reports for manager {manager_id}: {str(e)}")

    async def get_peers(self, user_id: UUID) -> List[User]:
        """Retrieves peers for a given user (users reporting to the same manager, excluding the user themselves)."""
        try:
            user = await self.get_user_by_id(user_id)
            if not user or not user.reports_to_id:
                logger.info(f"User {user_id} not found or does not report to anyone, so no peers can be determined.")
                return []

            manager_id = user.reports_to_id
            response: PostgrestAPIResponse = await asyncio.to_thread(
                self._client.table(self._table)
                .select("*")
                .eq("reports_to_id", str(manager_id))
                .neq("id", str(user_id)) # Exclude the user themselves
                .execute
            )
            self._handle_supabase_error(response, f"Error finding peers for user {user_id} (manager: {manager_id})")
            return [User(**item) for item in response.data] if response.data else []
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Error finding peers for user {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Error finding peers for user {user_id}: {str(e)}")
    
