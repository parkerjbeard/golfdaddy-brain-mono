"""
Model for tracking documentation approval requests.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Text, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class DocApproval(Base):
    """Model for documentation approval tracking."""
    
    __tablename__ = "doc_approvals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commit_hash = Column(String, nullable=False, index=True)
    repository = Column(String, nullable=False)
    diff_content = Column(Text, nullable=False)
    patch_content = Column(Text, nullable=False)
    
    # Slack interaction details
    slack_channel = Column(String)
    slack_message_ts = Column(String)  # Message timestamp for threading
    slack_user_id = Column(String)  # User who will approve/reject
    
    # Approval status
    status = Column(String, default="pending")  # pending, approved, rejected, expired
    approved_by = Column(String)
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    
    # Additional data
    approval_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)  # Auto-expire after certain time
    
    # GitHub PR details (if approved)
    pr_url = Column(String)
    pr_number = Column(String)
    
    def __repr__(self):
        return f"<DocApproval {self.id} - {self.repository}@{self.commit_hash[:7]} - {self.status}>"