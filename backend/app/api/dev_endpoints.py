"""
Development endpoints for testing and debugging.
These should be disabled in production.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dev", tags=["development"])


@router.post("/sync-current-user/{role}")
async def sync_current_user_with_role(role: str, current_user: User = Depends(get_current_user)):
    """
    Development endpoint to sync current user with a specific role.
    This helps with testing different role permissions.
    """
    try:
        # Validate role
        try:
            user_role = UserRole(role)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid role: {role}. Valid roles are: employee, manager, admin"
            )

        # Update user role
        user_repo = UserRepository()
        updated_user = await user_repo.update_user(current_user.id, {"role": user_role.value})

        if updated_user:
            logger.info(f"Updated user {current_user.id} role to {role}")
            return {"message": f"User role updated to {role}", "user": updated_user}
        else:
            raise HTTPException(status_code=500, detail="Failed to update user role")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing user role: {e}")
        raise HTTPException(status_code=500, detail=str(e))
