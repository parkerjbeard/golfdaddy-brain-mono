from pydantic import BaseModel, Field, Json
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    DEVELOPER = "Developer"
    MANAGER = "Manager"
    ADMIN = "Admin"

class User(BaseModel):
    id: UUID = Field(..., description="Corresponds to the Supabase auth.users id")
    email: Optional[str] = None
    slack_id: Optional[str] = Field(None, unique=True)
    role: UserRole = UserRole.DEVELOPER
    team: Optional[str] = None
    personal_mastery: Optional[Json[Dict[str, Any]]] = Field(None, description="Manager-specific tasks/feedback")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True # Replaces orm_mode=True in Pydantic v1
        use_enum_values = True # Important for serialization/deserialization of enums

    def __repr__(self) -> str:
        return f"<User id={self.id}, slack_id={self.slack_id}, role={self.role}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert User model to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "slack_id": self.slack_id,
            "role": self.role.value if self.role else None,
            "team": self.team,
            "personal_mastery": self.personal_mastery,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }