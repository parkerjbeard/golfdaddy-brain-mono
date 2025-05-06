from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, Optional
import logging
from uuid import UUID

from app.config.database import get_supabase_client
from supabase import Client, PostgrestAPIError
from gotrue.errors import AuthApiError
from app.models.user import User, UserRole # Import the Pydantic User model
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Scheme for extracting token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

@router.post("/login", response_model=TokenResponse)
async def login_for_access_token(
    form_data: LoginRequest = Body(...),
    supabase: Client = Depends(get_supabase_client)
):
    """Logs in a user using email/password via Supabase Auth.

    Assumes the user account (email/password) was created beforehand by an admin 
    in the Supabase dashboard.
    """
    try:
        logger.info(f"Attempting login for email: {form_data.email}")
        # Use Supabase client to sign in
        response = supabase.auth.sign_in_with_password({
            "email": form_data.email,
            "password": form_data.password
        })
        
        if response.session and response.session.access_token:
            logger.info(f"Login successful for email: {form_data.email}")
            return TokenResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
            )
        else:
            logger.error(f"Supabase login response missing session/token for {form_data.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed due to unexpected authentication server response.",
            )
            
    except AuthApiError as e:
        logger.warning(f"Supabase Auth API error during login for {form_data.email}: {e.message}")
        if "invalid login credentials" in str(e.message).lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Login failed: {e.message}",
            ) 
    except Exception as e:
        logger.exception(f"Unexpected error during login for {form_data.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login.",
        )

async def get_current_user_profile(
    token: str = Depends(oauth2_scheme),
    supabase: Client = Depends(get_supabase_client)
) -> User:
    """Dependency to get the current user's profile from Supabase JWT.
    
    Verifies JWT, fetches Supabase auth user, then retrieves or creates
    the corresponding profile in the public.users table.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 1. Verify JWT and get Supabase Auth User
        auth_response = supabase.auth.get_user(token)
        if not auth_response or not auth_response.user:
             logger.warning("Supabase auth.get_user did not return a user for the token.")
             raise credentials_exception
             
        supabase_auth_user = auth_response.user
        user_id_uuid = UUID(supabase_auth_user.id) # Convert string UUID to UUID object
        logger.info(f"JWT validated for user ID: {user_id_uuid}")

        # 2. Retrieve or Create User Profile in public.users
        user_repo = UserRepository(supabase) # Instantiate repo with the client
        user_profile = user_repo.get_user_by_id(user_id_uuid)
        
        if user_profile is None:
            logger.info(f"No profile found for user {user_id_uuid}. Creating one.")
            # Create profile if it doesn't exist
            new_profile_data = User(
                id=user_id_uuid,
                slack_id=None, # Slack ID is no longer primary identifier
                role=UserRole.DEVELOPER, # Default role, admin can change later
                team=None # Default team
                # Add email if you decide to store it in public.users table
                # email=supabase_auth_user.email 
            )
            user_profile = user_repo.create_user(new_profile_data)
            if user_profile is None:
                 logger.error(f"Failed to create user profile in public.users for {user_id_uuid}")
                 # Decide how to handle this - raise exception or allow limited access?
                 raise HTTPException(
                     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                     detail="Could not create user profile after successful authentication."
                 )
            logger.info(f"Successfully created profile for user {user_id_uuid}")
            
        logger.debug(f"Returning user profile for {user_id_uuid}: {user_profile}")
        return user_profile # Return the Pydantic User model (from public.users)

    except AuthApiError as e:
        logger.warning(f"Supabase Auth API error during token validation: {e.message}")
        raise credentials_exception
    except Exception as e:
        # Catch potential UUID conversion errors or other issues
        logger.exception(f"Unexpected error during token validation or profile retrieval: {e}")
        raise credentials_exception

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user_profile)):
    """Returns the profile of the currently authenticated user."""
    # The dependency already fetches and returns the user profile
    return current_user

# Add other auth endpoints here later if needed (e.g., refresh token, logout)