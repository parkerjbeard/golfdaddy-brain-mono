from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.database import Base


class CommitAnalysis(Base):
    """Model for storing individual commit analysis results"""
    __tablename__ = "commit_analyses"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    
    # Commit information
    commit_hash = Column(String(40), nullable=False, index=True)
    repository = Column(String(255), nullable=False)
    author_email = Column(String(255), nullable=False, index=True)
    author_name = Column(String(255))
    commit_date = Column(DateTime(timezone=True))
    
    # Analysis results
    complexity_score = Column(Integer, nullable=False)  # 1-10
    estimated_hours = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)  # low/medium/high
    seniority_score = Column(Integer, nullable=False)  # 1-10
    seniority_rationale = Column(Text)
    key_changes = Column(JSON, default=list)
    
    # Files and changes
    files_changed = Column(JSON, default=list)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    
    # Metadata
    analyzed_at = Column(DateTime(timezone=True), nullable=False)
    model_used = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), server_default="now()", onupdate=datetime.utcnow)