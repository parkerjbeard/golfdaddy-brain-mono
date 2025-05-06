from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    USER = "USER"
    DEVELOPER = "Developer"
    MANAGER = "Manager"
    ADMIN = "Admin"

class User(BaseModel):
    id: UUID = Field(..., description="Corresponds to the Supabase auth.users id")
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None # This should ideally be consistently sourced from auth or kept in sync
    slack_id: Optional[str] = Field(None, unique=True, description="User's Slack ID")
    github_username: Optional[str] = Field(None, description="User's GitHub username")
    role: UserRole = UserRole.USER
    team: Optional[str] = None
    # personal_mastery field seems specific, maps to metadata or a separate feature.
    # For generic metadata from DB:
    metadata: Optional[Dict[str, Any]] = Field(None, description="Arbitrary user metadata from DB")
    personal_mastery: Optional[Dict[str, Any]] = Field(None, description="Manager-specific tasks/feedback, potentially part of metadata or separate structure")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True # Replaces orm_mode=True in Pydantic v1
        use_enum_values = True # Important for serialization/deserialization of enums

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