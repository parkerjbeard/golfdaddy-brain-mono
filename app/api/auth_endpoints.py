from fastapi import APIRouter, Depends, HTTPException, Request, status, Response, Header
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Dict, Optional, Any, List
from pydantic import BaseModel, EmailStr
from supabase import Client

from app.config.supabase_client import get_supabase_client
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from uuid import UUID

router = APIRouter(prefix="/auth", tags=["authentication"])

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

class UserResponse(BaseModel):
    """Response model for user information."""
    id: UUID
    email: Optional[str] = None
    role: Optional[str] = None
    slack_id: Optional[str] = None
    team: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@router.post("/login", response_model=TokenResponse)
async def login_user(
    request: LoginRequest,
    supabase: Client = Depends(get_supabase_client)
):
    """
    Log in a user with email and password using Supabase Auth.
    
    Returns access token for authenticated API requests.
    """
    try:
        # Use Supabase client to sign in
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if response.session and response.session.access_token:
            return TokenResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                expires_in=response.session.expires_in
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed due to unexpected authentication server response."
            )
            
    except Exception as e:
        # Handle Supabase auth errors
        error_message = str(e)
        if "invalid login credentials" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Login failed: {error_message}",
            )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    supabase: Client = Depends(get_supabase_client)
):
    """
    Refresh the access token using a refresh token.
    """
    try:
        # Call Supabase refresh method
        response = supabase.auth.refresh_session(refresh_token)
        
        if response.session and response.session.access_token:
            return TokenResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                expires_in=response.session.expires_in
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh failed."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    authorization: str = Header(...),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Get the currently authenticated user.
    
    Requires valid access token in Authorization header.
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
        
        # Get additional user profile info from the public.users table
        user_repo = UserRepository(supabase)
        user_profile = user_repo.get_user_by_id(UUID(auth_user.id))
        
        # If profile doesn't exist yet, create a default one
        if not user_profile:
            new_user = User(
                id=UUID(auth_user.id),
                email=auth_user.email,
                role=UserRole.USER,
                slack_id=None,
                team=None
            )
            user_profile = user_repo.create_user(new_user)
        
        if not user_profile:
            return UserResponse(
                id=UUID(auth_user.id),
                email=auth_user.email
            )
        
        # Return combined user data
        return UserResponse(
            id=user_profile.id,
            email=auth_user.email,
            role=user_profile.role.value if user_profile.role else None,
            slack_id=user_profile.slack_id,
            team=user_profile.team,
            metadata=auth_user.app_metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/logout")
async def logout(
    authorization: str = Header(...),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Log out the current user.
    
    Invalidates the access token.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # Sign out using the Supabase client
        supabase.auth.sign_out()
        
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        ) 