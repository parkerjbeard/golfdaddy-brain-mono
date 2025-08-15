"""
Daily Work Analysis Models

This module defines the database models for the unified daily analysis system
that processes and aggregates work data from multiple sources (GitHub, Jira, etc.)
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import JSON, TIMESTAMP, Boolean, Column, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class DailyWorkAnalysis(Base):
    """
    Main model for storing daily aggregated work analysis results.
    This represents a single day's worth of analyzed work data for a user.
    """

    __tablename__ = "daily_work_analyses"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # User and date identification
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    analysis_date = Column(Date, nullable=False, index=True)

    # Analysis metadata
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Analysis results
    total_work_items = Column(Integer, default=0)
    total_commits = Column(Integer, default=0)
    total_tickets = Column(Integer, default=0)
    total_prs = Column(Integer, default=0)

    # Aggregated metrics
    total_loc_added = Column(Integer, default=0)
    total_loc_removed = Column(Integer, default=0)
    total_files_changed = Column(Integer, default=0)

    # Time tracking
    total_estimated_hours = Column(Float, default=0.0)

    # AI-generated summaries
    daily_summary = Column(Text)
    key_achievements = Column(JSON)  # List of key achievements
    technical_highlights = Column(JSON)  # List of technical highlights

    # Work item details (stored as JSON for flexibility)
    work_items = Column(JSON)  # List of WorkItem dictionaries

    # Deduplication tracking
    deduplication_results = Column(JSON)  # List of deduplication results

    # Processing status
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    processing_error = Column(Text)
    last_processed_at = Column(TIMESTAMP(timezone=True))

    # Source tracking
    data_sources = Column(JSON)  # List of data sources processed (e.g., ["github", "jira"])


class WorkItem(Base):
    """
    Individual work item model for detailed tracking.
    This can represent a commit, ticket, PR, or any other work unit.
    """

    __tablename__ = "work_items"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign key to daily analysis
    daily_analysis_id = Column(UUID(as_uuid=True), ForeignKey("daily_work_analyses.id"), nullable=False, index=True)

    # Work item identification
    item_type = Column(String(50), nullable=False)  # commit, ticket, pr, etc.
    source = Column(String(50), nullable=False)  # github, jira, etc.
    source_id = Column(String(255), nullable=False)  # Original ID from source system

    # Work item metadata
    title = Column(Text)
    description = Column(Text)
    url = Column(Text)

    # Timing
    created_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))

    # Metrics
    loc_added = Column(Integer, default=0)
    loc_removed = Column(Integer, default=0)
    files_changed = Column(Integer, default=0)
    estimated_hours = Column(Float, default=0.0)

    # Additional data (flexible storage)
    item_metadata = Column("metadata", JSON)

    # Deduplication
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_id = Column(UUID(as_uuid=True), ForeignKey("work_items.id"))

    # AI analysis
    ai_summary = Column(Text)
    ai_tags = Column(JSON)  # List of AI-generated tags

    # Relationships
    daily_analysis = relationship("DailyWorkAnalysis", back_populates="work_items_relation")
    duplicate_of = relationship("WorkItem", remote_side=[id])


class DeduplicationResult(Base):
    """
    Model for tracking deduplication results and decisions.
    """

    __tablename__ = "deduplication_results"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign key to daily analysis
    daily_analysis_id = Column(UUID(as_uuid=True), ForeignKey("daily_work_analyses.id"), nullable=False, index=True)

    # Items being compared
    item1_id = Column(String(255), nullable=False)
    item1_type = Column(String(50), nullable=False)
    item1_source = Column(String(50), nullable=False)

    item2_id = Column(String(255), nullable=False)
    item2_type = Column(String(50), nullable=False)
    item2_source = Column(String(50), nullable=False)

    # Deduplication result
    is_duplicate = Column(Boolean, nullable=False)
    confidence_score = Column(Float)  # 0.0 to 1.0
    reason = Column(Text)

    # Metadata
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    daily_analysis = relationship("DailyWorkAnalysis", back_populates="deduplication_results_relation")


# Update relationships in the Base models if needed
DailyWorkAnalysis.work_items_relation = relationship(
    "WorkItem", back_populates="daily_analysis", cascade="all, delete-orphan"
)
DailyWorkAnalysis.deduplication_results_relation = relationship(
    "DeduplicationResult", back_populates="daily_analysis", cascade="all, delete-orphan"
)
