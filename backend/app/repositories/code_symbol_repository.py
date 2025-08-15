"""
Repository for managing code symbols with AST parsing and embeddings.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.code_symbols import CodeSymbol

logger = logging.getLogger(__name__)


class CodeSymbolRepository:
    """Repository for code symbol operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_symbol(self, symbol_data: Dict[str, Any]) -> CodeSymbol:
        """Create a new code symbol."""
        try:
            symbol = CodeSymbol(**symbol_data)
            self.session.add(symbol)
            await self.session.commit()
            await self.session.refresh(symbol)

            logger.info(f"Created code symbol: {symbol.kind}:{symbol.name} in {symbol.repo}:{symbol.path}")
            return symbol

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating code symbol: {e}", exc_info=True)
            raise DatabaseError(f"Failed to create code symbol: {str(e)}")

    async def bulk_create_symbols(self, symbols_data: List[Dict[str, Any]]) -> List[CodeSymbol]:
        """Create multiple code symbols efficiently."""
        if not symbols_data:
            return []

        try:
            symbols = [CodeSymbol(**data) for data in symbols_data]
            self.session.add_all(symbols)
            await self.session.commit()

            logger.info(f"Created {len(symbols)} code symbols")
            return symbols

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error bulk creating code symbols: {e}", exc_info=True)
            raise DatabaseError(f"Failed to bulk create code symbols: {str(e)}")

    async def upsert_symbols(self, symbols_data: List[Dict[str, Any]]) -> List[CodeSymbol]:
        """Upsert code symbols (insert or update on conflict)."""
        if not symbols_data:
            return []

        try:
            # Prepare statement for upsert
            stmt = insert(CodeSymbol).values(symbols_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["repo", "path", "kind", "name"],
                set_={
                    "sig": stmt.excluded.sig,
                    "span": stmt.excluded.span,
                    "docstring": stmt.excluded.docstring,
                    "embedding": stmt.excluded.embedding,
                    "updated_at": datetime.utcnow(),
                },
            )

            await self.session.execute(stmt)
            await self.session.commit()

            # Fetch the upserted symbols
            conditions = []
            for symbol_data in symbols_data:
                condition = and_(
                    CodeSymbol.repo == symbol_data["repo"],
                    CodeSymbol.path == symbol_data["path"],
                    CodeSymbol.kind == symbol_data["kind"],
                    CodeSymbol.name == symbol_data["name"],
                )
                conditions.append(condition)

            query = select(CodeSymbol).where(or_(*conditions))
            result = await self.session.execute(query)
            symbols = result.scalars().all()

            logger.info(f"Upserted {len(symbols)} code symbols")
            return list(symbols)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error upserting code symbols: {e}", exc_info=True)
            raise DatabaseError(f"Failed to upsert code symbols: {str(e)}")

    async def get_symbol_by_id(self, symbol_id: UUID) -> Optional[CodeSymbol]:
        """Get a code symbol by ID."""
        try:
            query = select(CodeSymbol).where(CodeSymbol.id == symbol_id)
            result = await self.session.execute(query)
            symbol = result.scalar_one_or_none()

            if symbol:
                logger.info(f"Found code symbol: {symbol_id}")
            else:
                logger.info(f"Code symbol not found: {symbol_id}")

            return symbol

        except Exception as e:
            logger.error(f"Error fetching code symbol {symbol_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch code symbol: {str(e)}")

    async def get_symbols_by_file(self, repo: str, path: str) -> List[CodeSymbol]:
        """Get all symbols in a specific file."""
        try:
            query = (
                select(CodeSymbol)
                .where(and_(CodeSymbol.repo == repo, CodeSymbol.path == path))
                .order_by(CodeSymbol.kind, CodeSymbol.name)
            )

            result = await self.session.execute(query)
            symbols = result.scalars().all()

            logger.info(f"Found {len(symbols)} symbols in {repo}:{path}")
            return list(symbols)

        except Exception as e:
            logger.error(f"Error fetching symbols for {repo}:{path}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch file symbols: {str(e)}")

    async def get_symbols_by_kind(self, repo: str, kind: str, limit: int = 100) -> List[CodeSymbol]:
        """Get all symbols of a specific kind in a repository."""
        try:
            query = (
                select(CodeSymbol)
                .where(and_(CodeSymbol.repo == repo, CodeSymbol.kind == kind))
                .order_by(CodeSymbol.name)
                .limit(limit)
            )

            result = await self.session.execute(query)
            symbols = result.scalars().all()

            logger.info(f"Found {len(symbols)} {kind} symbols in repo {repo}")
            return list(symbols)

        except Exception as e:
            logger.error(f"Error fetching {kind} symbols for repo {repo}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch symbols by kind: {str(e)}")

    async def search_symbols_by_name(self, repo: str, name_pattern: str, limit: int = 50) -> List[CodeSymbol]:
        """Search for symbols by name pattern."""
        try:
            query = (
                select(CodeSymbol)
                .where(and_(CodeSymbol.repo == repo, CodeSymbol.name.ilike(f"%{name_pattern}%")))
                .order_by(CodeSymbol.name)
                .limit(limit)
            )

            result = await self.session.execute(query)
            symbols = result.scalars().all()

            logger.info(f"Found {len(symbols)} symbols matching '{name_pattern}' in {repo}")
            return list(symbols)

        except Exception as e:
            logger.error(f"Error searching symbols by name: {e}", exc_info=True)
            raise DatabaseError(f"Failed to search symbols: {str(e)}")

    async def search_similar_symbols(
        self, embedding: List[float], repo: str, kind: Optional[str] = None, limit: int = 10, threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search for similar code symbols using vector similarity."""
        try:
            # Convert embedding to numpy array for pgvector
            query_embedding = np.array(embedding)

            # Build SQL query with optional kind filter
            kind_clause = "AND kind = :kind" if kind else ""

            sql = f"""
                SELECT 
                    id,
                    repo,
                    path,
                    kind,
                    name,
                    sig,
                    docstring,
                    1 - (embedding <=> :embedding) AS similarity
                FROM code_symbols
                WHERE repo = :repo
                AND embedding IS NOT NULL
                AND 1 - (embedding <=> :embedding) > :threshold
                {kind_clause}
                ORDER BY embedding <=> :embedding
                LIMIT :limit
            """

            params = {"embedding": query_embedding.tolist(), "repo": repo, "threshold": threshold, "limit": limit}

            if kind:
                params["kind"] = kind

            result = await self.session.execute(sql, params)

            symbols = []
            for row in result:
                symbols.append(
                    {
                        "id": str(row.id),
                        "repo": row.repo,
                        "path": row.path,
                        "kind": row.kind,
                        "name": row.name,
                        "sig": row.sig,
                        "docstring": row.docstring,
                        "similarity": float(row.similarity),
                    }
                )

            logger.info(f"Found {len(symbols)} similar symbols in {repo}")
            return symbols

        except Exception as e:
            logger.error(f"Error searching similar symbols: {e}", exc_info=True)
            raise DatabaseError(f"Failed to search similar symbols: {str(e)}")

    async def update_symbol(self, symbol_id: UUID, update_data: Dict[str, Any]) -> Optional[CodeSymbol]:
        """Update a code symbol."""
        try:
            symbol = await self.get_symbol_by_id(symbol_id)
            if not symbol:
                raise ResourceNotFoundError("CodeSymbol", str(symbol_id))

            for key, value in update_data.items():
                if hasattr(symbol, key):
                    setattr(symbol, key, value)

            symbol.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(symbol)

            logger.info(f"Updated code symbol: {symbol_id}")
            return symbol

        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating code symbol {symbol_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update code symbol: {str(e)}")

    async def delete_symbol(self, symbol_id: UUID) -> bool:
        """Delete a code symbol."""
        try:
            symbol = await self.get_symbol_by_id(symbol_id)
            if not symbol:
                raise ResourceNotFoundError("CodeSymbol", str(symbol_id))

            await self.session.delete(symbol)
            await self.session.commit()

            logger.info(f"Deleted code symbol: {symbol_id}")
            return True

        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting code symbol {symbol_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to delete code symbol: {str(e)}")

    async def delete_file_symbols(self, repo: str, path: str) -> int:
        """Delete all symbols for a specific file."""
        try:
            query = delete(CodeSymbol).where(and_(CodeSymbol.repo == repo, CodeSymbol.path == path))

            result = await self.session.execute(query)
            await self.session.commit()

            deleted_count = result.rowcount
            logger.info(f"Deleted {deleted_count} symbols for {repo}:{path}")
            return deleted_count

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting symbols for {repo}:{path}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to delete file symbols: {str(e)}")

    async def get_repo_statistics(self, repo: str) -> Dict[str, Any]:
        """Get statistics about symbols in a repository."""
        try:
            # Count symbols by kind
            sql = """
                SELECT 
                    kind,
                    COUNT(*) as count
                FROM code_symbols
                WHERE repo = :repo
                GROUP BY kind
                ORDER BY count DESC
            """

            result = await self.session.execute(sql, {"repo": repo})

            stats = {"total_symbols": 0, "by_kind": {}, "files_count": 0}

            for row in result:
                stats["by_kind"][row.kind] = row.count
                stats["total_symbols"] += row.count

            # Count unique files
            file_query = select(CodeSymbol.path).where(CodeSymbol.repo == repo).distinct()

            file_result = await self.session.execute(file_query)
            stats["files_count"] = len(file_result.all())

            logger.info(
                f"Generated statistics for repo {repo}: {stats['total_symbols']} symbols in {stats['files_count']} files"
            )
            return stats

        except Exception as e:
            logger.error(f"Error getting repo statistics: {e}", exc_info=True)
            raise DatabaseError(f"Failed to get repository statistics: {str(e)}")
