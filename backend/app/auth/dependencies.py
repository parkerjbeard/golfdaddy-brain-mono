import asyncio
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status

from app.config.supabase_client import get_supabase_client_safe
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from supabase import Client

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None), supabase: Client = Depends(get_supabase_client_safe)
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
    if not authorization or not authorization.startswith("Bearer "):
        # When API key auth is enabled, surface API key message to align with API middleware behavior
        api_auth_enabled = False
        try:
            import os
            val = os.environ.get("ENABLE_API_AUTH")
            if val is not None:
                api_auth_enabled = str(val).lower() in ("1", "true", "yes")
            else:
                # Default to settings if env not present
                from app.config.settings import settings as _settings
                api_auth_enabled = bool(getattr(_settings, "ENABLE_API_AUTH", False))
        except Exception:
            api_auth_enabled = False
        if api_auth_enabled:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
        logger.warning("Invalid authorization header format - does not start with 'Bearer '")
        # Mimic FastAPI validation error semantics for missing header when API key auth is disabled
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Field required")

    token = authorization.replace("Bearer ", "")

    try:
        logger.info("Validating JWT token with Supabase auth")
        auth_response = await asyncio.to_thread(supabase.auth.get_user, token)

        if not auth_response or not auth_response.user:
            logger.warning("Invalid or expired JWT token - no user found in auth response")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        auth_user = auth_response.user
        user_id = UUID(auth_user.id)
        logger.info(f"JWT token validated for user ID: {user_id}")

        # Create a UserRepository using the injected Supabase client
        user_repository = UserRepository(client=supabase)
        user_profile = await user_repository.get_user_by_id(user_id)

        if not user_profile:
            logger.info(f"User profile not found for authenticated ID: {user_id}. Creating new profile.")

            # Use EMPLOYEE as default role, which is the lowest permission role
            # This can be changed later by an admin if needed
            new_user_data = {
                "id": user_id,
                "email": auth_user.email,
                "name": auth_user.email.split("@")[0] if auth_user.email else None,
                "role": UserRole.EMPLOYEE,
            }

            try:
                new_user = User(**new_user_data)
                user_profile = await user_repository.create_user(new_user)

                if not user_profile:
                    logger.error(f"Failed to create user profile for authenticated user: {user_id}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create user profile after auth user validation",
                    )

                logger.info(f"Successfully created new user profile for ID: {user_id}")
            except Exception as e:
                logger.exception(f"Error creating user profile: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create user profile: {str(e)}"
                )

        if auth_user.email and user_profile.email != auth_user.email:
            logger.warning(
                f"Discrepancy in email for user {user_id}. Auth email: {auth_user.email}, Profile email: {user_profile.email}"
            )
            user_profile.email = auth_user.email

        return user_profile

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
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
        logger.warning(f"User {current_user.id} with role {current_user.role} attempted to access admin-only endpoint")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")

    logger.info(f"Admin access granted to user {current_user.id}")
    return current_user


async def get_manager_or_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Verify that the current user is a manager or admin.

    Args:
        current_user: Current user data from token

    Returns:
        User information if manager or admin

    Raises:
        HTTPException: If user is not a manager or admin
    """
    allowed_roles = [UserRole.MANAGER, UserRole.ADMIN]
    if not current_user.role or current_user.role not in allowed_roles:
        logger.warning(
            f"User {current_user.id} with role {current_user.role} attempted to access manager-only endpoint"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager or admin privileges required")

    logger.info(f"Manager/admin access granted to user {current_user.id}")
    return current_user
