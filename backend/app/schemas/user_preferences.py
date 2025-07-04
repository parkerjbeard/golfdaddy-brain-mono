from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import time
from zoneinfo import available_timezones


class NotificationPreferences(BaseModel):
    eod_reminder_enabled: bool = Field(default=True, description="Whether to receive EOD reminders")
    eod_reminder_time: str = Field(default="16:30", description="Time to receive EOD reminder (HH:MM format)")
    timezone: str = Field(default="America/Los_Angeles", description="User's timezone")

    @field_validator("eod_reminder_time")
    @classmethod
    def validate_time_format(cls, v):
        try:
            time.fromisoformat(v)
        except ValueError:
            raise ValueError('Time must be in HH:MM format (e.g., "16:30")')
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v):
        if v not in available_timezones():
            raise ValueError("Invalid timezone. Must be a valid timezone identifier.")
        return v


class UserPreferencesUpdate(BaseModel):
    notification_preferences: Optional[NotificationPreferences] = None


class UserPreferencesResponse(BaseModel):
    notification_preferences: NotificationPreferences

    class Config:
        from_attributes = True
