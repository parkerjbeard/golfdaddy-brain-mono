"""
Models for tracking embedding model metadata.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class EmbeddingsMeta(Base):
    """Model for tracking embedding model versions and metadata."""

    __tablename__ = "embeddings_meta"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Model information
    model = Column(String, nullable=False, unique=True)  # e.g., "text-embedding-3-large"
    dim = Column(Integer, nullable=False)  # Dimension size (e.g., 3072)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<EmbeddingsMeta {self.model} - {self.dim}D>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "model": self.model,
            "dim": self.dim,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
