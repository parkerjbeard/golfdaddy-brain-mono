"""
Model for tracking documentation approval requests.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class DocApproval(Base):
    """Model for documentation approval tracking with enhanced dashboard integration."""

    __tablename__ = "doc_approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commit_hash = Column(String, nullable=False, index=True)
    repository = Column(String, nullable=False)
    diff_content = Column(Text, nullable=False)
    patch_content = Column(Text, nullable=False)

    # Link to proposal
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("proposals.id", ondelete="SET NULL"), nullable=True)

    # Slack interaction details
    slack_channel = Column(String)
    slack_message_ts = Column(String)  # Message timestamp for threading
    slack_user_id = Column(String)  # User who will approve/reject
    slack_ts = Column(String)  # Slack timestamp for reference

    # Approval status and workflow
    status = Column(String, default="pending")  # pending, approved, rejected, expired
    opened_by = Column(String)  # User who initiated the approval
    approved_by = Column(String)  # Renamed from approved_by for clarity
    approved_at = Column(DateTime)  # Renamed from approved_at for clarity
    rejection_reason = Column(Text)

    # GitHub integration (enhanced)
    pr_url = Column(String)
    # PR number (Integer per latest migrations)
    pr_number = Column(Integer)
    # Optional GitHub integration metadata (ensure columns exist via migrations)
    head_sha = Column(String)  # SHA of the PR head for Check Run integration
    check_run_id = Column(String)  # GitHub Check Run ID for status updates

    # Additional data
    # Align with DB column named 'metadata' while exposing Python attribute 'approval_metadata'
    approval_metadata = Column('metadata', JSON, default=dict)
    # Expiration handling (exists in initial migration)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)  # Auto-expire after certain time

    def __repr__(self):
        return f"<DocApproval {self.id} - {self.repository}@{self.commit_hash[:7]} - {self.status}>"
