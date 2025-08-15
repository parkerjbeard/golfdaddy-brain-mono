"""
Models for code symbols with AST-parsed data and embeddings.
"""

import uuid
from datetime import datetime
from typing import Any, Dict

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class CodeSymbol(Base):
    """Model for AST-parsed code symbols with embeddings."""

    __tablename__ = "code_symbols"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Symbol location
    repo = Column(String, nullable=False, index=True)
    path = Column(String, nullable=False, index=True)
    lang = Column(String, nullable=False)  # Language: python, typescript, etc.

    # Symbol details
    kind = Column(String, nullable=False)  # class, function, method, interface, etc.
    name = Column(String, nullable=False, index=True)
    sig = Column(Text)  # Signature (function params, class inheritance, etc.)
    span = Column(JSON)  # Line/column span: {"start": {"line": 10, "col": 0}, "end": {"line": 20, "col": 0}}
    docstring = Column(Text)  # Extracted documentation

    # Vector embedding (3072 dimensions for text-embedding-3-large)
    embedding = Column(Vector(3072))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CodeSymbol {self.kind}:{self.name} in {self.repo}:{self.path}>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "repo": self.repo,
            "path": self.path,
            "lang": self.lang,
            "kind": self.kind,
            "name": self.name,
            "sig": self.sig,
            "span": self.span,
            "docstring": self.docstring[:200] if self.docstring else None,  # Truncate for response
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Create composite indexes for efficient querying
Index("idx_code_symbols_repo_path", CodeSymbol.repo, CodeSymbol.path)
Index("idx_code_symbols_repo_kind", CodeSymbol.repo, CodeSymbol.kind)
Index("idx_code_symbols_repo_name", CodeSymbol.repo, CodeSymbol.name)
