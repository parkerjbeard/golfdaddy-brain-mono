from typing import Optional, Dict, Any
from fastapi import Depends, Request, HTTPException, status, Header
from supabase import Client
from uuid import UUID
import asyncio

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
        auth_response = await asyncio.to_thread(supabase.auth.get_user, token)
        
        if not auth_response or not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        auth_user = auth_response.user
        user_id = UUID(auth_user.id)
        
        user_repository = UserRepository(supabase)
        user_profile = await user_repository.get_user_by_id(user_id)
        
        if not user_profile:
            new_user_data = {
                "id": user_id,
                "email": auth_user.email,
                "role": UserRole.USER,
            }
            new_user = User(**new_user_data)
            user_profile = await user_repository.create_user(new_user)
            
            if not user_profile:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user profile after auth user validation"
                )
        
        if auth_user.email and user_profile.email != auth_user.email:
            print(f"Warning: Discrepancy or missing email in public.users for {user_id}. Using auth email.")
            user_profile.email = auth_user.email

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