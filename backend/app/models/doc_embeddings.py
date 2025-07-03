"""
Models for document embeddings and code context.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, DateTime, Text, Float, JSON, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid

from app.core.database import Base


class DocEmbedding(Base):
    """Model for document embeddings used in semantic search."""
    
    __tablename__ = "doc_embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("docs.id", ondelete="CASCADE"), nullable=True)
    doc_approval_id = Column(UUID(as_uuid=True), ForeignKey("doc_approvals.id", ondelete="CASCADE"), nullable=True)
    
    # Document metadata
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    doc_type = Column(String)
    file_path = Column(String)
    repository = Column(String)
    commit_hash = Column(String)
    
    # Vector embedding
    embedding = Column(Vector(1536), nullable=False)
    
    # Additional metadata
    doc_metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<DocEmbedding {self.id} - {self.title[:50]}>"


class CodeContext(Base):
    """Model for storing code context and structure analysis."""
    
    __tablename__ = "code_context"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    
    # Code structure
    module_name = Column(String)
    class_names = Column(ARRAY(Text), default=list)
    function_names = Column(ARRAY(Text), default=list)
    imports = Column(ARRAY(Text), default=list)
    exports = Column(ARRAY(Text), default=list)
    
    # Patterns and conventions
    design_patterns = Column(ARRAY(Text), default=list)
    coding_style = Column(JSON, default=dict)
    
    # Relationships
    dependencies = Column(ARRAY(Text), default=list)
    dependents = Column(ARRAY(Text), default=list)
    related_issues = Column(ARRAY(Text), default=list)
    related_prs = Column(ARRAY(Text), default=list)
    
    # Metrics
    complexity_score = Column(Float)
    test_coverage = Column(Float)
    last_modified = Column(DateTime)
    
    # Embedding
    context_embedding = Column(Vector(1536))
    
    # Metadata
    context_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<CodeContext {self.repository}:{self.file_path}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "repository": self.repository,
            "file_path": self.file_path,
            "module_name": self.module_name,
            "classes": self.class_names,
            "functions": self.function_names[:10],  # Limit for response
            "imports": self.imports[:10],
            "design_patterns": self.design_patterns,
            "complexity": self.complexity_score,
            "test_coverage": self.test_coverage,
            "dependencies": len(self.dependencies),
            "last_modified": self.last_modified.isoformat() if self.last_modified else None
        }


class DocRelationship(Base):
    """Model for relationships between documents."""
    
    __tablename__ = "doc_relationships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_doc_id = Column(UUID(as_uuid=True), nullable=False)
    target_doc_id = Column(UUID(as_uuid=True), nullable=False)
    relationship_type = Column(String, nullable=False)  # references, extends, implements, related, supersedes
    confidence = Column(Float, default=0.0)
    
    # Additional context
    context = Column(Text)
    auto_detected = Column(String, default="true")  # Boolean as string for compatibility
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<DocRelationship {self.source_doc_id} -{self.relationship_type}-> {self.target_doc_id}>"