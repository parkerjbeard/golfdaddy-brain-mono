import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.config.supabase_client import get_supabase_client_safe as get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user_preferences import NotificationPreferences, UserPreferencesResponse, UserPreferencesUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/preferences", response_model=UserPreferencesResponse)
def get_user_preferences(current_user: User = Depends(get_current_user), db=Depends(get_db)) -> UserPreferencesResponse:
    """Get the current user's notification preferences."""
    user_repo = UserRepository(db)
    user = asyncio.run(user_repo.get_user_by_id(current_user.id))

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get preferences or use defaults
    preferences = user.preferences or {}
    notification_prefs = preferences.get("notification", {})

    # Create notification preferences with defaults
    notification_preferences = NotificationPreferences(
        eod_reminder_enabled=notification_prefs.get("eod_reminder_enabled", True),
        eod_reminder_time=notification_prefs.get("eod_reminder_time", "16:30"),
        timezone=notification_prefs.get("timezone", "America/Los_Angeles"),
    )

    return UserPreferencesResponse(notification_preferences=notification_preferences)


@router.put("/preferences", response_model=UserPreferencesResponse)
def update_user_preferences(
    preferences_update: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> UserPreferencesResponse:
    """Update the current user's notification preferences."""
    user_repo = UserRepository(db)
    user = asyncio.run(user_repo.get_user_by_id(current_user.id))

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get existing preferences or initialize
    preferences = user.preferences or {}

    # Update notification preferences if provided
    if preferences_update.notification_preferences:
        preferences["notification"] = preferences_update.notification_preferences.model_dump()

    # Update user preferences
    updated_user = asyncio.run(user_repo.update_user(user_id=user.id, update_data={"preferences": preferences}))

    if not updated_user:
        raise HTTPException(status_code=500, detail="Failed to update preferences")

    # Return updated preferences
    notification_prefs = preferences.get("notification", {})
    notification_preferences = NotificationPreferences(
        eod_reminder_enabled=notification_prefs.get("eod_reminder_enabled", True),
        eod_reminder_time=notification_prefs.get("eod_reminder_time", "16:30"),
        timezone=notification_prefs.get("timezone", "America/Los_Angeles"),
    )

    logger.info(f"Updated preferences for user {user.id}")

    return UserPreferencesResponse(notification_preferences=notification_preferences)
