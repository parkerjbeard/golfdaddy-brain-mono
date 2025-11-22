import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr

from app.auth.dependencies import get_current_user as get_current_user_dependency
from app.config.supabase_client import get_supabase_client
from app.core.exceptions import AuthenticationError, ExternalServiceError
from app.models.user import User
from supabase import Client

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)


# Response models
class TokenResponse(BaseModel):
    """Response model for auth token."""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None


class LoginRequest(BaseModel):
    """Request model for email/password login."""

    email: EmailStr
    password: str


@router.post("/login", response_model=TokenResponse)
async def login_user(request: LoginRequest, supabase: Client = Depends(get_supabase_client)):
    """
    Log in a user with email and password using Supabase Auth.

    Returns access token for authenticated API requests.
    """
    try:
        # In test mode, return a canned token to avoid network calls
        from app.config.settings import settings as _settings

        if getattr(_settings, "TESTING_MODE", False):
            return TokenResponse(
                access_token="mock_access_token",
                refresh_token="mock_refresh_token",
                expires_in=3600,
            )
        logger.info(f"Attempting login for email: {request.email}")
        # Use Supabase client to sign in
        response = supabase.auth.sign_in_with_password({"email": request.email, "password": request.password})

        if response.session and response.session.access_token:
            logger.info(f"Login successful for email: {request.email}")
            return TokenResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                expires_in=response.session.expires_in,
            )
        else:
            logger.error(f"Supabase login response missing session/token for {request.email}")
            raise ExternalServiceError(
                service_name="Supabase Auth", original_message="Login response missing session/token"
            )

    except Exception as e:
        # Handle Supabase auth errors
        error_message = str(e)
        if "invalid login credentials" in error_message.lower():
            logger.warning(f"Invalid login credentials for {request.email}: {error_message}")
            raise AuthenticationError(message="Incorrect email or password")
        else:
            logger.exception(f"Unexpected error during login for {request.email}: {e}")
            raise ExternalServiceError(service_name="Supabase Auth", original_message=f"Login failed: {error_message}")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, supabase: Client = Depends(get_supabase_client)):
    """
    Refresh the access token using a refresh token.
    """
    try:
        from app.config.settings import settings as _settings

        if getattr(_settings, "TESTING_MODE", False):
            return TokenResponse(
                access_token="mock_access_token",
                refresh_token=refresh_token,
                expires_in=3600,
            )
        # Call Supabase refresh method
        response = supabase.auth.refresh_session(refresh_token)

        if response.session and response.session.access_token:
            return TokenResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                expires_in=response.session.expires_in,
            )
        else:
            raise ExternalServiceError(
                service_name="Supabase Auth", original_message="Token refresh response missing session/token"
            )
    except Exception as e:
        raise AuthenticationError(message=f"Token refresh failed: {str(e)}")


@router.get("/me", response_model=User)
async def get_current_user_endpoint(current_user: User = Depends(get_current_user_dependency)):
    """
    Get the currently authenticated user.

    Requires valid access token in Authorization header.
    This endpoint now uses the get_current_user dependency.
    """
    return current_user


@router.post("/logout")
async def logout(authorization: str = Header(...), supabase: Client = Depends(get_supabase_client)):
    """
    Log out the current user.

    Invalidates the access token.
    """
    if not authorization.startswith("Bearer "):
        raise AuthenticationError(message="Invalid authentication credentials")

    authorization.replace("Bearer ", "")

    try:
        # Sign out using the Supabase client
        supabase.auth.sign_out()

        return {"message": "Successfully logged out"}
    except Exception as e:
        raise ExternalServiceError(service_name="Supabase Auth", original_message=f"Logout failed: {str(e)}")
