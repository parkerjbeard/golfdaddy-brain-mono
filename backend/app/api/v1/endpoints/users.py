from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, EmailStr

# Removing this non-existent import
# from app.services.auth_service import get_current_active_user
from app.auth.dependencies import get_admin_user, get_current_user
from app.core.exceptions import (
    DatabaseError,
    ResourceNotFoundError,
)
from app.models.user import User, UserRole  # Pydantic model for response
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

router = APIRouter()


class UserCreatePayload(BaseModel):
    id: UUID
    email: EmailStr
    name: Optional[str] = None
    slack_id: Optional[str] = None
    github_username: Optional[str] = None
    role: UserRole = UserRole.EMPLOYEE
    team: Optional[str] = None
    avatar_url: Optional[str] = None


class UserUpdatePayload(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    team: Optional[str] = None
    github_username: Optional[str] = None
    slack_id: Optional[str] = None
    role: Optional[UserRole] = None
    team_id: Optional[UUID] = None
    reports_to_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None


# Create a function to get UserRepository instance
def get_user_repository():
    return UserRepository()


def get_user_service() -> UserService:
    return UserService()


@router.get("", response_model=List[User])
async def list_users(
    role: Optional[UserRole] = Query(None, description="Filter users by role (e.g., DEVELOPER, MANAGER)"),
    current_user: User = Depends(get_current_user),  # Require authentication
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Retrieve a list of users.
    Optionally filter by role.

    Note: Depending on security requirements, this endpoint might require ADMIN privileges
    or be restricted in other ways.
    """
    # if not current_user.role == UserRole.ADMIN and not current_user.role == UserRole.MANAGER:
    #     raise PermissionDeniedError(message="Not authorized to list users")

    if role:
        users = await user_repo.list_users_by_role(role)
    else:
        # Default to a reasonable limit if no role is specified, or adjust as needed.
        # list_all_users returns a tuple (users, total_count). We only need users here.
        result = await user_repo.list_all_users(limit=200)  # Adjust limit as needed
        users = result[0]

    if not users:
        return []  # Return empty list if no users found, rather than 404 for a list endpoint
    return users


@router.post(
    "",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_admin_user)],
)
async def create_user(
    payload: UserCreatePayload,
    user_service: UserService = Depends(get_user_service),
):
    new_user = User(**payload.model_dump())
    created_user = await user_service.create_user(new_user)
    if not created_user:
        raise DatabaseError(message="Failed to create user")
    return created_user


@router.get("/me", response_model=User)
async def read_current_user(current_user: User = Depends(get_current_user)):
    """
    Retrieve the currently authenticated user's information.
    Requires a valid JWT token in the Authorization header.
    """
    return current_user


# Example: Get a specific user (if needed by other parts of frontend, not strictly by ManagerDashboardPage)
@router.get("/{user_id}", response_model=User, dependencies=[Depends(get_admin_user)])
async def read_user(
    user_id: UUID,
    # current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
):
    """
    Retrieve a specific user by their ID.
    """
    # Add authorization checks if necessary, e.g., only admin or the user themselves can fetch
    db_user = await user_service.get_user(user_id)
    if db_user is None:
        raise ResourceNotFoundError(resource_name="User", resource_id=str(user_id))
    return db_user


@router.put("/{user_id}", response_model=User, dependencies=[Depends(get_admin_user)])
async def update_user(
    user_id: UUID,
    payload: UserUpdatePayload,
    user_service: UserService = Depends(get_user_service),
):
    update_data = payload.model_dump(exclude_unset=True)
    updated_user = await user_service.update_user(user_id, update_data)
    if not updated_user:
        raise DatabaseError(message="Failed to update user")
    return updated_user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_admin_user)],
)
async def delete_user(
    user_id: UUID,
    user_service: UserService = Depends(get_user_service),
):
    deleted = await user_service.delete_user(user_id)
    if not deleted:
        raise DatabaseError(message="Failed to delete user")
    return None


@router.put("/me", response_model=User)
async def update_current_user(
    payload: UserUpdatePayload,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    update_data = payload.model_dump(exclude_unset=True)
    updated = await user_service.update_user(current_user.id, update_data)
    if not updated:
        raise DatabaseError(message="Failed to update user")
    return updated
