"""
Service for semantic search and documentation discovery.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.docs import Doc  # TODO: Create this model if needed
from app.models.doc_approval import DocApproval
from app.models.doc_embeddings import CodeContext, DocEmbedding, DocRelationship
from app.services.context_analyzer import ContextAnalyzer
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class SemanticSearchService:
    """Service for semantic search across documentation and code."""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.context_analyzer = ContextAnalyzer(self.embedding_service)

    async def search_documentation(
        self,
        db: AsyncSession,
        query: str,
        repository: Optional[str] = None,
        doc_type: Optional[str] = None,
        limit: int = 10,
        include_context: bool = True,
    ) -> Dict[str, Any]:
        """Search documentation using semantic similarity."""
        # Find similar documents
        similar_docs = await self.embedding_service.find_similar_documents(db, query, repository, limit, threshold=0.5)

        results = []
        for doc_embedding, similarity in similar_docs:
            result = {
                "id": str(doc_embedding.id),
                "title": doc_embedding.title,
                "content": doc_embedding.content,
                "type": doc_embedding.doc_type,
                "repository": doc_embedding.repository,
                "file_path": doc_embedding.file_path,
                "similarity": similarity,
                "metadata": doc_embedding.doc_metadata,
            }

            # Include related code context if requested
            if include_context and repository:
                related_code = await self.embedding_service.find_related_code(
                    db, doc_embedding.title, repository, limit=3
                )

                result["related_code"] = [
                    {
                        "file_path": code.file_path,
                        "module": code.module_name,
                        "classes": code.class_names[:3],
                        "functions": code.function_names[:5],
                        "similarity": score,
                    }
                    for code, score in related_code
                ]

            results.append(result)

        # Get search metadata
        total_docs = await self._count_total_documents(db, repository)

        return {
            "query": query,
            "repository": repository,
            "results": results,
            "total_results": len(results),
            "total_documents": total_docs,
            "search_time": datetime.utcnow().isoformat(),
        }

    async def find_related_documentation(
        self, db: AsyncSession, document_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find documentation related to a specific document."""
        # Get the source document
        doc_embedding = await db.get(DocEmbedding, document_id)
        if not doc_embedding:
            return []

        # Search using the document's content
        query = f"{doc_embedding.title} {doc_embedding.content[:200]}"
        similar_docs = await self.embedding_service.find_similar_documents(
            db, query, doc_embedding.repository, limit + 1, threshold=0.6
        )

        # Filter out the source document
        results = []
        for doc, similarity in similar_docs:
            if str(doc.id) != document_id:
                results.append(
                    {
                        "id": str(doc.id),
                        "title": doc.title,
                        "type": doc.doc_type,
                        "file_path": doc.file_path,
                        "similarity": similarity,
                        "relationship": self._determine_relationship(doc_embedding, doc, similarity),
                    }
                )

        return results[:limit]

    async def analyze_documentation_gaps(
        self, db: AsyncSession, repository: str, threshold: float = 0.7
    ) -> Dict[str, Any]:
        """Analyze gaps in documentation coverage."""
        # Get all code contexts for the repository
        stmt = select(CodeContext).where(CodeContext.repository == repository)
        result = await db.execute(stmt)
        code_contexts = result.scalars().all()

        gaps = {
            "undocumented_files": [],
            "poorly_documented_files": [],
            "suggested_documentation": [],
            "coverage_summary": {"total_files": len(code_contexts), "documented_files": 0, "coverage_percentage": 0.0},
        }

        for context in code_contexts:
            # Search for documentation about this file
            search_query = f"{context.file_path} {context.module_name or ''}"
            docs = await self.embedding_service.find_similar_documents(
                db, search_query, repository, limit=1, threshold=threshold
            )

            if not docs:
                gaps["undocumented_files"].append(
                    {
                        "file_path": context.file_path,
                        "module": context.module_name,
                        "classes": len(context.class_names),
                        "functions": len(context.function_names),
                        "complexity": context.complexity_score,
                    }
                )
            elif docs[0][1] < 0.8:  # Low similarity score
                gaps["poorly_documented_files"].append(
                    {
                        "file_path": context.file_path,
                        "best_match": docs[0][0].title,
                        "match_score": docs[0][1],
                        "improvement_needed": True,
                    }
                )
            else:
                gaps["coverage_summary"]["documented_files"] += 1

        # Calculate coverage
        if code_contexts:
            gaps["coverage_summary"]["coverage_percentage"] = (
                gaps["coverage_summary"]["documented_files"] / gaps["coverage_summary"]["total_files"] * 100
            )

        # Generate suggestions for top undocumented files
        undocumented_sorted = sorted(gaps["undocumented_files"], key=lambda x: x.get("complexity", 0), reverse=True)

        for file_info in undocumented_sorted[:5]:
            gaps["suggested_documentation"].append(
                {
                    "file_path": file_info["file_path"],
                    "priority": "high" if file_info.get("complexity", 0) > 50 else "medium",
                    "suggested_sections": self._suggest_doc_sections(file_info),
                }
            )

        return gaps

    async def get_documentation_graph(self, db: AsyncSession, repository: str, max_nodes: int = 50) -> Dict[str, Any]:
        """Get a graph representation of documentation relationships."""
        # Get all document embeddings for the repository
        stmt = select(DocEmbedding).where(DocEmbedding.repository == repository).limit(max_nodes)
        result = await db.execute(stmt)
        docs = result.scalars().all()

        nodes = []
        edges = []

        # Create nodes
        for doc in docs:
            nodes.append(
                {"id": str(doc.id), "label": doc.title, "type": doc.doc_type or "document", "size": len(doc.content)}
            )

        # Find relationships between documents
        for i, doc1 in enumerate(docs):
            for j, doc2 in enumerate(docs[i + 1 :], i + 1):
                if doc1.embedding and doc2.embedding:
                    similarity = self.embedding_service.calculate_similarity(doc1.embedding, doc2.embedding)

                    if similarity > 0.7:  # Strong relationship
                        edges.append(
                            {"source": str(doc1.id), "target": str(doc2.id), "weight": similarity, "type": "related"}
                        )

        # Add explicit relationships from database
        stmt = select(DocRelationship).where(
            or_(
                DocRelationship.source_doc_id.in_([d.id for d in docs]),
                DocRelationship.target_doc_id.in_([d.id for d in docs]),
            )
        )
        result = await db.execute(stmt)
        relationships = result.scalars().all()

        for rel in relationships:
            edges.append(
                {
                    "source": str(rel.source_doc_id),
                    "target": str(rel.target_doc_id),
                    "weight": rel.confidence,
                    "type": rel.relationship_type,
                }
            )

        return {
            "nodes": nodes,
            "edges": edges,
            "statistics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "average_connections": len(edges) / len(nodes) if nodes else 0,
            },
        }

    async def suggest_documentation_improvements(self, db: AsyncSession, document_id: str) -> Dict[str, Any]:
        """Suggest improvements for a specific document."""
        doc_embedding = await db.get(DocEmbedding, document_id)
        if not doc_embedding:
            return {"error": "Document not found"}

        suggestions = {
            "document_id": document_id,
            "title": doc_embedding.title,
            "current_quality": {},
            "improvements": [],
            "related_updates": [],
        }

        # Analyze current content
        content_length = len(doc_embedding.content)
        has_examples = "example" in doc_embedding.content.lower() or "```" in doc_embedding.content
        has_links = "http" in doc_embedding.content or "[" in doc_embedding.content

        suggestions["current_quality"] = {
            "length": content_length,
            "has_examples": has_examples,
            "has_links": has_links,
            "last_updated": doc_embedding.updated_at.isoformat() if doc_embedding.updated_at else None,
        }

        # Generate improvement suggestions
        if content_length < 500:
            suggestions["improvements"].append(
                {
                    "type": "expand_content",
                    "priority": "high",
                    "description": "Document is quite short. Consider adding more details and explanations.",
                }
            )

        if not has_examples:
            suggestions["improvements"].append(
                {
                    "type": "add_examples",
                    "priority": "medium",
                    "description": "Add code examples to illustrate concepts.",
                }
            )

        if not has_links:
            suggestions["improvements"].append(
                {
                    "type": "add_references",
                    "priority": "low",
                    "description": "Consider adding links to related documentation or external resources.",
                }
            )

        # Check for recent code changes that might affect this doc
        if doc_embedding.file_path:
            # Find recent approvals for related files
            stmt = (
                select(DocApproval)
                .where(
                    and_(
                        DocApproval.repository == doc_embedding.repository,
                        DocApproval.status == "approved",
                        DocApproval.created_at > datetime.utcnow().replace(days=-30),
                    )
                )
                .limit(5)
            )

            result = await db.execute(stmt)
            recent_approvals = result.scalars().all()

            for approval in recent_approvals:
                # Check if approval affects related files
                if approval.approval_metadata.get("affected_files"):
                    for file in approval.approval_metadata["affected_files"]:
                        if file in doc_embedding.content:
                            suggestions["related_updates"].append(
                                {
                                    "commit": approval.commit_hash[:7],
                                    "date": approval.created_at.isoformat(),
                                    "file": file,
                                    "suggestion": f"Review if commit {approval.commit_hash[:7]} requires documentation updates",
                                }
                            )

        return suggestions

    def _determine_relationship(self, doc1: DocEmbedding, doc2: DocEmbedding, similarity: float) -> str:
        """Determine the type of relationship between two documents."""
        # Simple heuristic-based relationship detection
        if similarity > 0.9:
            return "duplicate"
        elif doc1.doc_type == doc2.doc_type and similarity > 0.8:
            return "closely_related"
        elif "api" in doc1.title.lower() and "api" in doc2.title.lower():
            return "same_category"
        elif doc1.file_path and doc2.file_path:
            # Check if they're in the same directory
            dir1 = "/".join(doc1.file_path.split("/")[:-1])
            dir2 = "/".join(doc2.file_path.split("/")[:-1])
            if dir1 == dir2:
                return "same_module"

        return "related"

    def _suggest_doc_sections(self, file_info: Dict[str, Any]) -> List[str]:
        """Suggest documentation sections based on file info."""
        sections = ["Overview", "Usage"]

        if file_info.get("classes", 0) > 0:
            sections.append("Classes")
            sections.append("API Reference")

        if file_info.get("functions", 0) > 5:
            sections.append("Functions")
            sections.append("Examples")

        if file_info.get("complexity", 0) > 30:
            sections.append("Architecture")
            sections.append("Design Decisions")

        return sections

    async def _count_total_documents(self, db: AsyncSession, repository: Optional[str] = None) -> int:
        """Count total documents in repository."""
        stmt = select(DocEmbedding)
        if repository:
            stmt = stmt.where(DocEmbedding.repository == repository)

        result = await db.execute(stmt.count())
        return result.scalar() or 0
