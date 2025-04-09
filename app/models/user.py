from sqlalchemy import Column, String, Integer, JSON, DateTime, Enum
from sqlalchemy.sql import func
import enum
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from app.config.database import Base

class UserRole(str, enum.Enum):
    """Enum for user roles in the system."""
    DEVELOPER = "developer"
    MANAGER = "manager"
    ADMIN = "admin"

class User(Base):
    """User model representing employees in the system."""
    
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slack_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.DEVELOPER)
    team = Column(String, nullable=True)
    personal_mastery = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self) -> str:
        return f"<User id={self.id}, slack_id={self.slack_id}, role={self.role}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert User model to dictionary."""
        return {
            "id": self.id,
            "slack_id": self.slack_id,
            "name": self.name,
            "role": self.role.value if self.role else None,
            "team": self.team,
            "personal_mastery": self.personal_mastery,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }