from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.db.database import Base


class ObjectiveStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class SocialMediaMetric(Base):
    __tablename__ = "social_media_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    platform = Column(String(50), nullable=False, index=True)
    views = Column(Integer, default=0)
    engagement = Column(Float, default=0.0)
    reach = Column(Integer)
    impressions = Column(Integer)
    clicks = Column(Integer)
    shares = Column(Integer)
    comments = Column(Integer)
    likes = Column(Integer)
    zap_run_id = Column(String(255))
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    csat_score = Column(Integer, nullable=False)  # 1-5 scale
    feedback_text = Column(Text)
    user_id = Column(String(255), index=True)
    user_email = Column(String(255))
    feedback_category = Column(String(100))
    sentiment = Column(String(50))  # positive, negative, neutral
    product_area = Column(String(100))
    resolution_status = Column(String(50), default="pending")
    resolution_notes = Column(Text)
    zap_run_id = Column(String(255))
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Objective(Base):
    __tablename__ = "objectives"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum(ObjectiveStatus), default=ObjectiveStatus.ACTIVE, nullable=False, index=True)
    priority = Column(Enum(Priority), default=Priority.MEDIUM)
    owner = Column(String(255))
    team = Column(String(100))
    due_date = Column(DateTime)
    progress = Column(Integer, default=0)  # 0-100 percentage
    key_results = Column(JSON)  # Array of key results
    milestones = Column(JSON)  # Array of milestones
    zap_run_id = Column(String(255))
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Win(Base):
    __tablename__ = "wins"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100), default="general")
    impact = Column(String(50), default="medium")  # low, medium, high
    ai_generated = Column(Boolean, default=True)
    ai_prompt = Column(Text)  # The prompt used to generate the win if AI-generated
    team_members = Column(JSON)  # Array of team members involved
    metrics = Column(JSON)  # Associated metrics/KPIs
    related_objective_id = Column(UUID(as_uuid=True), ForeignKey('objectives.id'))
    visibility = Column(String(50), default="public")  # public, team, private
    tags = Column(JSON)  # Array of tags
    zap_run_id = Column(String(255))
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    related_objective = relationship("Objective", backref="wins")


class Analytics(Base):
    __tablename__ = "analytics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    metric_name = Column(String(255), nullable=False, index=True)
    metric_value = Column(JSON, nullable=False)  # Flexible JSON for different metric types
    category = Column(String(100), default="general", index=True)
    source = Column(String(100), default="zapier")
    dimension = Column(String(100))  # e.g., "department", "product", "region"
    dimension_value = Column(String(255))  # e.g., "sales", "product-a", "north-america"
    comparison_period = Column(String(50))  # e.g., "month-over-month", "year-over-year"
    comparison_value = Column(JSON)  # Previous period's value for comparison
    target_value = Column(JSON)  # Target/goal value
    tags = Column(JSON)  # Array of tags
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    zap_run_id = Column(String(255))
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FormSubmission(Base):
    __tablename__ = "form_submissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    form_id = Column(String(255), nullable=False, index=True)
    form_name = Column(String(255), nullable=False)
    form_type = Column(String(100), default="general")  # feedback, survey, application, etc.
    respondent_email = Column(String(255))
    respondent_name = Column(String(255))
    responses = Column(JSON, nullable=False)  # All form responses as JSON
    score = Column(Float)  # If the form has a calculated score
    status = Column(String(50), default="new")  # new, reviewed, processed, archived
    assigned_to = Column(String(255))  # Who should review this submission
    notes = Column(Text)  # Internal notes about the submission
    tags = Column(JSON)  # Array of tags
    form_metadata = Column(JSON)  # Additional metadata
    submission_timestamp = Column(DateTime)  # When the form was actually submitted
    zap_run_id = Column(String(255))
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True)
    department = Column(String(100), index=True)
    title = Column(String(255))
    phone = Column(String(50))
    location = Column(String(255))
    manager = Column(String(255))
    manager_id = Column(String(100))
    status = Column(Enum(EmployeeStatus), default=EmployeeStatus.ACTIVE, nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    skills = Column(JSON)  # Array of skills
    certifications = Column(JSON)  # Array of certifications
    emergency_contact = Column(JSON)  # Emergency contact info
    custom_fields = Column(JSON)  # Any additional custom fields
    profile_image_url = Column(String(500))
    slack_user_id = Column(String(100))
    github_username = Column(String(100))
    zap_run_id = Column(String(255))
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Create indexes for common queries
from sqlalchemy import Index

# Composite indexes for common query patterns
Index('idx_social_media_platform_timestamp', SocialMediaMetric.platform, SocialMediaMetric.timestamp)
Index('idx_feedback_score_timestamp', UserFeedback.csat_score, UserFeedback.timestamp)
Index('idx_analytics_category_metric', Analytics.category, Analytics.metric_name)
Index('idx_form_type_status', FormSubmission.form_type, FormSubmission.status)
Index('idx_employee_dept_status', Employee.department, Employee.status)