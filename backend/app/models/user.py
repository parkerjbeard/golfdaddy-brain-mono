from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRole(str, Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    ADMIN = "admin"


class User(BaseModel):
    id: UUID = Field(..., description="Corresponds to the Supabase auth.users id")
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[EmailStr] = None  # This should ideally be consistently sourced from auth or kept in sync
    slack_id: Optional[str] = Field(None, unique=True, description="User's Slack ID")
    github_username: Optional[str] = Field(None, description="User's GitHub username")
    role: UserRole = UserRole.EMPLOYEE
    team: Optional[str] = None
    team_id: Optional[UUID] = None  # Foreign key to Team model
    reports_to_id: Optional[UUID] = Field(None, description="ID of the user this user reports to")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Arbitrary user metadata from DB")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: Optional[datetime] = None
    is_active: bool = True
    preferences: Optional[dict] = None  # For storing user-specific settings

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v):
        if isinstance(v, str):
            # Convert to lowercase for comparison
            v_lower = v.lower()
            # Map legacy roles and uppercase roles to normalized roles
            role_mapping = {
                "user": "employee",
                "developer": "employee",
                "viewer": "employee",
                "lead": "manager",
                "service_account": "employee",
                "employee": "employee",
                "manager": "manager",
                "admin": "admin",
            }
            return role_mapping.get(v_lower, "employee")  # Default to employee if unknown
        return v

    class Config:
        from_attributes = True  # Replaces orm_mode=True in Pydantic v1
        use_enum_values = True  # Important for serialization/deserialization of enums

    def __repr__(self) -> str:
        return f"<User id={self.id}, email={self.email}, role={self.role}>"

    # Using model_dump() is generally preferred over custom to_dict() with Pydantic v2
    # If to_dict() is still needed for specific reasons, ensure it includes github_username
    # def to_dict(self) -> Dict[str, Any]:
    #     base = self.model_dump(exclude_unset=True) # Pydantic V2 way
    #     # Ensure enum values are strings if not handled by model_dump config
    #     if isinstance(base.get('role'), Enum):
    #          base['role'] = base['role'].value
    #     return base
