"""
Models for documentation change proposals.
"""

import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.core.database import Base


class Proposal(Base):
    """Model for documentation change proposals."""

    __tablename__ = "proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source information
    commit = Column(String, nullable=False, index=True)  # Commit hash that triggered this
    repo = Column(String, nullable=False, index=True)

    # Proposal content
    patch = Column(Text, nullable=False)  # The proposed documentation patch
    targets = Column(ARRAY(String), default=list)  # Target files to be modified

    # Status tracking
    status = Column(String, default="pending")  # pending, approved, rejected, expired, applied

    # Quality scores
    scores = Column(JSON, default=dict)  # {"relevance": 0.9, "accuracy": 0.85, "completeness": 0.8}

    # Cost tracking
    cost_cents = Column(Integer, default=0)  # Cost in cents for AI generation

    # Additional metadata
    proposal_metadata = Column(JSON, default=dict)  # Any additional context or data

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Proposal {self.id} - {self.repo}@{self.commit[:7]} - {self.status}>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "commit": self.commit,
            "repo": self.repo,
            "patch": self.patch[:500] if self.patch else None,  # Truncate for response
            "targets": self.targets,
            "status": self.status,
            "scores": self.scores,
            "cost_cents": self.cost_cents,
            "metadata": self.proposal_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_total_score(self) -> float:
        """Calculate average quality score."""
        if not self.scores:
            return 0.0
        score_values = [v for v in self.scores.values() if isinstance(v, (int, float))]
        return sum(score_values) / len(score_values) if score_values else 0.0
