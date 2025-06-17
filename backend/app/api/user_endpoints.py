# backend/app/api/user_endpoints.py
from fastapi import APIRouter, Depends, Query, status
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from app.models.user import User, UserRole  # Main User model
from app.repositories.user_repository import UserRepository
from app.auth.dependencies import (
    get_admin_user,
    get_current_user,
)  # Assuming get_current_user might be needed for non-admin user info
from pydantic import BaseModel, EmailStr, HttpUrl
from app.core.exceptions import ResourceNotFoundError, BadRequestError, DatabaseError

router = APIRouter(
    prefix="/users",
    tags=["users"],
    # dependencies=[Depends(get_admin_user)] # Apply admin auth to all routes in this router if desired
)

# --- Pydantic Models for API Responses and Payloads ---


class UserResponse(BaseModel):  # What data to send back when a user is fetched/listed
    id: UUID
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    slack_id: Optional[str] = None
    github_username: Optional[str] = None
    role: UserRole
    team: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        use_enum_values = False  # Send enum member names (e.g., "DEVELOPER") not values ("Developer") in API response if preferred
        # Or True to send values. Default for Pydantic v2 is to send values.


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    size: int
    # pages: int # Optional: calculate if needed


class UserUpdateByAdminPayload(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = (
        None  # Admin updating email should be handled carefully due to auth implications
    )
    slack_id: Optional[str] = None
    github_username: Optional[str] = None
    role: Optional[UserRole] = None
    team: Optional[str] = None
    team_id: Optional[UUID] = None
    avatar_url: Optional[HttpUrl] = None
    reports_to_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None
    personal_mastery: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    preferences: Optional[Dict[str, Any]] = None

    class Config:
        # Pydantic v2: if you want to accept enum names like "DEVELOPER" in payload
        # Pydantic automatically tries to convert to enum members.
        # use_enum_values = False # For input, Pydantic handles conversion from value or name.
        pass


class UserCreatePayload(BaseModel):
    """Payload for creating a user profile record."""

    id: UUID
    email: EmailStr
    name: Optional[str] = None
    slack_id: Optional[str] = None
    github_username: Optional[str] = None
    role: UserRole = UserRole.USER
    team: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None


class UserSelfUpdatePayload(BaseModel):
    """Fields a regular user is allowed to update on their own profile."""

    name: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    team: Optional[str] = None
    github_username: Optional[str] = None
    slack_id: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


# --- Helper for repository dependency ---
# (Could be in a central deps file if used by many endpoint modules)
def get_user_repository():
    return UserRepository()


# --- API Endpoints ---


@router.get("", response_model=UserListResponse, dependencies=[Depends(get_admin_user)])
async def list_users_admin(
    page: int = Query(1, ge=1, description="Page number, 1-indexed"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    user_repo: UserRepository = Depends(get_user_repository),
    # current_admin: User = Depends(get_admin_user) # Already in dependencies for the router or route
):
    """List all users with pagination. Admin access required."""
    skip = (page - 1) * size
    users, total_count = await user_repo.list_all_users(skip=skip, limit=size)

    # Convert full User models to UserResponse models
    user_responses = [UserResponse.model_validate(user) for user in users]

    return UserListResponse(
        users=user_responses, total=total_count, page=page, size=size
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_admin_user)],
)
async def create_user_admin(
    payload: UserCreatePayload,
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Create a new user profile. Admin access required."""
    new_user = User(**payload.model_dump())
    created_user = await user_repo.create_user(new_user)
    if not created_user:
        raise DatabaseError(message="Failed to create user")
    return UserResponse.model_validate(created_user)


@router.get(
    "/{user_id}", response_model=UserResponse, dependencies=[Depends(get_admin_user)]
)
async def get_user_admin(
    user_id: UUID,
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Retrieve a user by ID. Admin access required."""
    user = await user_repo.get_user_by_id(user_id)
    if not user:
        raise ResourceNotFoundError(resource_name="User", resource_id=str(user_id))
    return UserResponse.model_validate(user)


@router.put(
    "/{user_id}", response_model=UserResponse, dependencies=[Depends(get_admin_user)]
)
async def update_user_admin(
    user_id: UUID,
    payload: UserUpdateByAdminPayload,
    user_repo: UserRepository = Depends(get_user_repository),
    # current_admin: User = Depends(get_admin_user)
):
    """Update a user's details. Admin access required."""
    existing_user = await user_repo.get_user_by_id(user_id)
    if not existing_user:
        raise ResourceNotFoundError(resource_name="User", resource_id=str(user_id))

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise BadRequestError(message="No update data provided")

    # Handle email update carefully: Supabase auth email is separate from public.users email.
    # Updating email here only updates public.users.email.
    # For auth email change, use Supabase auth admin functions.
    if "email" in update_data and update_data["email"] != existing_user.email:
        # Log or decide policy for admin changing display email vs auth email
        print(
            f"Admin updating display email for user {user_id}. Auth email is not changed by this endpoint."
        )

    updated_user = await user_repo.update_user(user_id, update_data)
    if not updated_user:
        # This might happen if the update fails in the DB or if no actual changes were made
        # and the repo returns None (depends on repo implementation)
        # Re-fetch to be sure or check repo logic for update_user return value
        updated_user = await user_repo.get_user_by_id(user_id)
        if not updated_user:
            raise DatabaseError(
                message="Failed to update user or re-fetch after update."
            )

    return UserResponse.model_validate(updated_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_admin_user)],
)
async def delete_user_admin(
    user_id: UUID,
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Delete a user profile. Admin access required."""
    deleted = await user_repo.delete_user(user_id)
    if not deleted:
        raise DatabaseError(message="Failed to delete user")
    return None


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UserSelfUpdatePayload,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Update the currently authenticated user's own profile."""
    update_data = payload.model_dump(exclude_unset=True)
    updated_user = await user_repo.update_user(current_user.id, update_data)
    if not updated_user:
        raise DatabaseError(message="Failed to update user")
    return UserResponse.model_validate(updated_user)


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# You would add this router to your main FastAPI app instance in main.py
# from app.api import user_endpoints
# app.include_router(user_endpoints.router)
