"""
Repository for managing document chunks with vector embeddings.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.doc_chunks import DocChunk

logger = logging.getLogger(__name__)


class DocChunkRepository:
    """Repository for document chunk operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_chunk(self, chunk_data: Dict[str, Any]) -> DocChunk:
        """Create a new document chunk."""
        try:
            chunk = DocChunk(**chunk_data)
            self.session.add(chunk)
            await self.session.commit()
            await self.session.refresh(chunk)

            logger.info(f"Created doc chunk: {chunk.repo}:{chunk.path} - order {chunk.order_key}")
            return chunk

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating doc chunk: {e}", exc_info=True)
            raise DatabaseError(f"Failed to create doc chunk: {str(e)}")

    async def bulk_create_chunks(self, chunks_data: List[Dict[str, Any]]) -> List[DocChunk]:
        """Create multiple document chunks efficiently."""
        if not chunks_data:
            return []

        try:
            chunks = [DocChunk(**data) for data in chunks_data]
            self.session.add_all(chunks)
            await self.session.commit()

            logger.info(f"Created {len(chunks)} doc chunks")
            return chunks

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error bulk creating doc chunks: {e}", exc_info=True)
            raise DatabaseError(f"Failed to bulk create doc chunks: {str(e)}")

    async def upsert_chunks(self, chunks_data: List[Dict[str, Any]]) -> List[DocChunk]:
        """Upsert document chunks (insert or update on conflict)."""
        if not chunks_data:
            return []

        try:
            # Prepare statement for upsert
            stmt = insert(DocChunk).values(chunks_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["repo", "path", "order_key"],
                set_={
                    "heading": stmt.excluded.heading,
                    "content": stmt.excluded.content,
                    "embedding": stmt.excluded.embedding,
                    "updated_at": datetime.utcnow(),
                },
            )

            await self.session.execute(stmt)
            await self.session.commit()

            # Fetch the upserted chunks
            conditions = []
            for chunk_data in chunks_data:
                condition = and_(
                    DocChunk.repo == chunk_data["repo"],
                    DocChunk.path == chunk_data["path"],
                    DocChunk.order_key == chunk_data["order_key"],
                )
                conditions.append(condition)

            query = select(DocChunk).where(or_(*conditions))
            result = await self.session.execute(query)
            chunks = result.scalars().all()

            logger.info(f"Upserted {len(chunks)} doc chunks")
            return list(chunks)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error upserting doc chunks: {e}", exc_info=True)
            raise DatabaseError(f"Failed to upsert doc chunks: {str(e)}")

    async def get_chunk_by_id(self, chunk_id: UUID) -> Optional[DocChunk]:
        """Get a document chunk by ID."""
        try:
            query = select(DocChunk).where(DocChunk.id == chunk_id)
            result = await self.session.execute(query)
            chunk = result.scalar_one_or_none()

            if chunk:
                logger.info(f"Found doc chunk: {chunk_id}")
            else:
                logger.info(f"Doc chunk not found: {chunk_id}")

            return chunk

        except Exception as e:
            logger.error(f"Error fetching doc chunk {chunk_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch doc chunk: {str(e)}")

    async def get_chunks_by_document(self, repo: str, path: str) -> List[DocChunk]:
        """Get all chunks for a specific document, ordered by order_key."""
        try:
            query = (
                select(DocChunk).where(and_(DocChunk.repo == repo, DocChunk.path == path)).order_by(DocChunk.order_key)
            )

            result = await self.session.execute(query)
            chunks = result.scalars().all()

            logger.info(f"Found {len(chunks)} chunks for {repo}:{path}")
            return list(chunks)

        except Exception as e:
            logger.error(f"Error fetching chunks for {repo}:{path}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch document chunks: {str(e)}")

    async def get_chunks_by_repo(self, repo: str, limit: int = 100) -> List[DocChunk]:
        """Get all chunks for a repository."""
        try:
            query = (
                select(DocChunk).where(DocChunk.repo == repo).order_by(DocChunk.path, DocChunk.order_key).limit(limit)
            )

            result = await self.session.execute(query)
            chunks = result.scalars().all()

            logger.info(f"Found {len(chunks)} chunks for repo {repo}")
            return list(chunks)

        except Exception as e:
            logger.error(f"Error fetching chunks for repo {repo}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch repository chunks: {str(e)}")

    async def search_similar_chunks(
        self, embedding: List[float], repo: str, limit: int = 10, threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar document chunks using vector similarity."""
        try:
            # Convert embedding to numpy array for pgvector
            query_embedding = np.array(embedding)

            # Use raw SQL for vector similarity search
            sql = """
                SELECT 
                    id,
                    repo,
                    path,
                    heading,
                    content,
                    1 - (embedding <=> :embedding) AS similarity
                FROM doc_chunks
                WHERE repo = :repo
                AND 1 - (embedding <=> :embedding) > :threshold
                ORDER BY embedding <=> :embedding
                LIMIT :limit
            """

            result = await self.session.execute(
                sql, {"embedding": query_embedding.tolist(), "repo": repo, "threshold": threshold, "limit": limit}
            )

            chunks = []
            for row in result:
                chunks.append(
                    {
                        "id": str(row.id),
                        "repo": row.repo,
                        "path": row.path,
                        "heading": row.heading,
                        "content": row.content,
                        "similarity": float(row.similarity),
                    }
                )

            logger.info(f"Found {len(chunks)} similar chunks in {repo}")
            return chunks

        except Exception as e:
            logger.error(f"Error searching similar chunks: {e}", exc_info=True)
            raise DatabaseError(f"Failed to search similar chunks: {str(e)}")

    async def update_chunk(self, chunk_id: UUID, update_data: Dict[str, Any]) -> Optional[DocChunk]:
        """Update a document chunk."""
        try:
            chunk = await self.get_chunk_by_id(chunk_id)
            if not chunk:
                raise ResourceNotFoundError("DocChunk", str(chunk_id))

            for key, value in update_data.items():
                if hasattr(chunk, key):
                    setattr(chunk, key, value)

            chunk.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(chunk)

            logger.info(f"Updated doc chunk: {chunk_id}")
            return chunk

        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating doc chunk {chunk_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update doc chunk: {str(e)}")

    async def delete_chunk(self, chunk_id: UUID) -> bool:
        """Delete a document chunk."""
        try:
            chunk = await self.get_chunk_by_id(chunk_id)
            if not chunk:
                raise ResourceNotFoundError("DocChunk", str(chunk_id))

            await self.session.delete(chunk)
            await self.session.commit()

            logger.info(f"Deleted doc chunk: {chunk_id}")
            return True

        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting doc chunk {chunk_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to delete doc chunk: {str(e)}")

    async def delete_document_chunks(self, repo: str, path: str) -> int:
        """Delete all chunks for a specific document."""
        try:
            query = delete(DocChunk).where(and_(DocChunk.repo == repo, DocChunk.path == path))

            result = await self.session.execute(query)
            await self.session.commit()

            deleted_count = result.rowcount
            logger.info(f"Deleted {deleted_count} chunks for {repo}:{path}")
            return deleted_count

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting chunks for {repo}:{path}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to delete document chunks: {str(e)}")
