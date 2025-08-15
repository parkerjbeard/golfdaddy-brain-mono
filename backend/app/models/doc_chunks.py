"""
Models for documentation chunks with pgvector embeddings.
"""

import uuid
from datetime import datetime
from typing import Any, Dict

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class DocChunk(Base):
    """Model for document chunks with vector embeddings."""

    __tablename__ = "doc_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Document identification
    repo = Column(String, nullable=False, index=True)
    path = Column(String, nullable=False, index=True)
    heading = Column(String)
    order_key = Column(Integer, nullable=False)  # For maintaining chunk order

    # Content
    content = Column(Text, nullable=False)

    # Vector embedding (3072 dimensions for text-embedding-3-large)
    embedding = Column(Vector(3072), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DocChunk {self.repo}:{self.path} - {self.heading or 'chunk'}#{self.order_key}>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "repo": self.repo,
            "path": self.path,
            "heading": self.heading,
            "order_key": self.order_key,
            "content": self.content[:500] if self.content else None,  # Truncate for response
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Create composite index for efficient querying
Index("idx_doc_chunks_repo_path", DocChunk.repo, DocChunk.path)
Index("idx_doc_chunks_repo_path_order", DocChunk.repo, DocChunk.path, DocChunk.order_key)
