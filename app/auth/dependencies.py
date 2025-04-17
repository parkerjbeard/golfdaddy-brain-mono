from typing import Optional, Dict, Any
from fastapi import Depends, Request, HTTPException, status, Header
from supabase import Client
from uuid import UUID

from app.config.supabase_client import get_supabase_client
from app.repositories.user_repository import UserRepository
from app.models.user import User, UserRole

async def get_current_user(
    authorization: str = Header(...),
    supabase: Client = Depends(get_supabase_client)
) -> User:
    """
    Get the current authenticated user from Supabase JWT token.
    
    Args:
        authorization: Authorization header with Bearer token
        supabase: Supabase client
        
    Returns:
        User model with combined auth and profile data
        
    Raises:
        HTTPException: If token is invalid or user doesn't exist
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # Verify the token and get user
        auth_response = supabase.auth.get_user(token)
        
        if not auth_response or not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        auth_user = auth_response.user
        user_id = UUID(auth_user.id)
        
        # Get additional user profile info from the public.users table
        user_repository = UserRepository(supabase)
        user_profile = user_repository.get_user_by_id(user_id)
        
        # If profile doesn't exist yet, create a default one
        if not user_profile:
            new_user = User(
                id=user_id,
                email=auth_user.email,
                role=UserRole.USER,
                slack_id=None,
                team=None
            )
            user_profile = user_repository.create_user(new_user)
            
            if not user_profile:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user profile"
                )
        
        # Add auth metadata to the user model
        # This would be handled better with a proper combined model
        user_profile_dict = user_profile.model_dump()
        user_profile_dict["auth_metadata"] = auth_user.app_metadata
        user_profile_dict["email"] = auth_user.email  # Ensure email is available
        
        return user_profile
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify that the current user is an admin.
    
    Args:
        current_user: Current user data from token
        
    Returns:
        User information if admin
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.role or current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
        
    return current_user 