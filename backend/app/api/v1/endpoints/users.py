from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID

from app.models.user import User, UserRole # Pydantic model for response
from app.repositories.user_repository import UserRepository
# Removing this non-existent import
# from app.services.auth_service import get_current_active_user
from app.auth.dependencies import get_current_user

router = APIRouter()

# Create a function to get UserRepository instance
def get_user_repository():
    return UserRepository()

@router.get("", response_model=List[User])
async def list_users(
    role: Optional[UserRole] = Query(None, description="Filter users by role (e.g., DEVELOPER, MANAGER)"),
    # current_user: User = Depends(get_current_active_user), # Optional: Add auth if needed
    user_repo: UserRepository = Depends(get_user_repository)
):
    """
    Retrieve a list of users.
    Optionally filter by role.
    
    Note: Depending on security requirements, this endpoint might require ADMIN privileges
    or be restricted in other ways.
    """
    # if not current_user.role == UserRole.ADMIN and not current_user.role == UserRole.MANAGER:
    #     raise HTTPException(status_code=403, detail="Not authorized to list users")

    if role:
        users = await user_repo.list_users_by_role(role)
    else:
        # Default to a reasonable limit if no role is specified, or adjust as needed.
        # list_all_users returns a tuple (users, total_count). We only need users here.
        result = await user_repo.list_all_users(limit=200) # Adjust limit as needed
        users = result[0]
        
    if not users:
        return [] # Return empty list if no users found, rather than 404 for a list endpoint
    return users

@router.get("/me", response_model=User)
async def read_current_user(
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve the currently authenticated user's information.
    Requires a valid JWT token in the Authorization header.
    """
    return current_user

# Example: Get a specific user (if needed by other parts of frontend, not strictly by ManagerDashboardPage)
@router.get("/{user_id}", response_model=User)
async def read_user(
    user_id: UUID,
    # current_user: User = Depends(get_current_active_user),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """
    Retrieve a specific user by their ID.
    """
    # Add authorization checks if necessary, e.g., only admin or the user themselves can fetch
    db_user = await user_repo.get_user_by_id(user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user 