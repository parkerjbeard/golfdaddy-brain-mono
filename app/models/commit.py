from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from app.config.database import Base

class Commit(Base):
    """Commit model for storing GitHub commit data with AI analysis."""
    
    __tablename__ = "commits"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    commit_hash = Column(String, unique=True, nullable=False, index=True)
    
    # User who authored the commit
    author_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    author = relationship("User", backref="commits")
    
    # Repository information
    repository = Column(String, nullable=False)
    branch = Column(String, nullable=False)
    
    # Commit metadata
    commit_message = Column(Text, nullable=False)
    commit_timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # Code change metrics
    lines_added = Column(Integer, nullable=True)
    lines_deleted = Column(Integer, nullable=True)
    changed_files = Column(JSON, nullable=True)  # List of file paths changed
    
    # AI analysis results
    ai_points = Column(Integer, nullable=True)
    ai_estimated_hours = Column(Float, nullable=True)
    ai_analysis_notes = Column(Text, nullable=True)
    
    # Detailed point calculation data
    complexity_score = Column(Integer, nullable=True)  # 1-10 rating
    risk_level = Column(String, nullable=True)  # low/medium/high
    risk_factor = Column(Float, nullable=True)  # 1.0/1.5/2.0
    point_calculation = Column(JSON, nullable=True)  # Store the full calculation details
    
    # Record creation timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self) -> str:
        return f"<Commit hash={self.commit_hash}, author_id={self.author_id}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Commit model to dictionary."""
        return {
            "id": self.id,
            "commit_hash": self.commit_hash,
            "author_id": self.author_id,
            "repository": self.repository,
            "branch": self.branch,
            "commit_message": self.commit_message,
            "commit_timestamp": self.commit_timestamp.isoformat() if self.commit_timestamp else None,
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
            "changed_files": self.changed_files,
            "ai_points": self.ai_points,
            "ai_estimated_hours": self.ai_estimated_hours,
            "ai_analysis_notes": self.ai_analysis_notes,
            "complexity_score": self.complexity_score,
            "risk_level": self.risk_level,
            "risk_factor": self.risk_factor,
            "point_calculation": self.point_calculation,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }