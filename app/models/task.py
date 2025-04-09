from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Enum, Text, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config.database import Base

class TaskStatus(str, enum.Enum):
    """Enum for task statuses."""
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"

class Task(Base):
    """Task model with RACI framework implementation."""
    
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    description = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.ASSIGNED)
    
    # RACI roles
    assignee_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    responsible_id = Column(String, ForeignKey("users.id"), nullable=False)
    accountable_id = Column(String, ForeignKey("users.id"), nullable=False)
    consulted_ids = Column(ARRAY(String), nullable=True)  # Store as array of user IDs
    informed_ids = Column(ARRAY(String), nullable=True)   # Store as array of user IDs
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    due_date = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    assignee = relationship("User", foreign_keys=[assignee_id], backref="assigned_tasks")
    responsible = relationship("User", foreign_keys=[responsible_id], backref="responsible_tasks")
    accountable = relationship("User", foreign_keys=[accountable_id], backref="accountable_tasks")
    
    def __repr__(self) -> str:
        return f"<Task id={self.id}, status={self.status}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Task model to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value if self.status else None,
            "assignee_id": self.assignee_id,
            "responsible_id": self.responsible_id,
            "accountable_id": self.accountable_id,
            "consulted_ids": self.consulted_ids,
            "informed_ids": self.informed_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None
        }