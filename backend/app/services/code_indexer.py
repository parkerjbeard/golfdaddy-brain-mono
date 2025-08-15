"""
Unified code indexing service for parsing, embedding generation, and storage.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.database import AsyncSession
from app.integrations.ai_integration_v2 import AIIntegrationV2
from app.models.code_symbols import CodeSymbol
from app.repositories.code_symbol_repository import CodeSymbolRepository
from app.services.code_parser import CodeParser
from app.services.code_parser import CodeSymbol as ParsedSymbol

logger = logging.getLogger(__name__)


class CodeIndexer:
    """Service for indexing code files into the database with embeddings."""

    def __init__(self, session: AsyncSession):
        """Initialize the code indexer.

        Args:
            session: Database session for persistence
        """
        self.session = session
        self.parser = CodeParser()
        self.repository = CodeSymbolRepository(session)
        self.ai_integration = AIIntegrationV2()

    async def index_file(self, repo: str, file_path: Path, incremental: bool = True) -> List[CodeSymbol]:
        """Index a single code file.

        Args:
            repo: Repository identifier
            file_path: Path to the code file
            incremental: Whether to perform incremental updates

        Returns:
            List of indexed code symbols
        """
        try:
            # Parse the file
            parsed_symbols = self.parser.parse_file(file_path)

            if not parsed_symbols:
                logger.info(f"No symbols found in {file_path}")
                return []

            # Get relative path for storage
            rel_path = str(file_path)

            indexed_symbols = []

            # Process each symbol
            for parsed in parsed_symbols:
                # Check if symbol needs updating (incremental mode)
                if incremental:
                    # Search for existing symbol by name in this file
                    existing_symbols = await self.repository.search_symbols_by_name(repo, parsed.name)

                    # Filter to find the one in this file
                    existing = None
                    for sym in existing_symbols:
                        if sym.path == rel_path:
                            existing = sym
                            break

                    if existing and self._symbols_equal(existing, parsed):
                        logger.debug(f"Skipping unchanged symbol: {parsed.name}")
                        indexed_symbols.append(existing)
                        continue

                # Generate embedding for symbol
                embedding_text = self._create_embedding_text(parsed)
                embedding = await self.ai_integration.generate_embeddings(embedding_text)

                # Create or update symbol in database
                symbol_data = {
                    "repo": repo,
                    "path": rel_path,
                    "name": parsed.name,
                    "kind": parsed.kind,
                    "sig": parsed.signature,  # Model uses 'sig' not 'signature'
                    "docstring": parsed.docstring,
                    "lang": parsed.language or self._detect_language(file_path),  # Model uses 'lang' not 'language'
                    "embedding": embedding,
                    "span": {
                        "start": {"line": parsed.start_line, "col": parsed.start_col},
                        "end": {"line": parsed.end_line, "col": parsed.end_col},
                    },
                }

                # Use upsert_symbols with a single symbol
                symbols = await self.repository.upsert_symbols([symbol_data])
                symbol = symbols[0] if symbols else None

                indexed_symbols.append(symbol)
                logger.info(f"Indexed symbol: {parsed.name} ({parsed.kind})")

            return indexed_symbols

        except Exception as e:
            logger.error(f"Error indexing file {file_path}: {e}")
            raise

    async def index_directory(
        self, repo: str, directory: Path, extensions: List[str] = None, incremental: bool = True
    ) -> Dict[str, Any]:
        """Index all code files in a directory.

        Args:
            repo: Repository identifier
            directory: Directory path to index
            extensions: File extensions to include (e.g., ['.py', '.js'])
            incremental: Whether to perform incremental updates

        Returns:
            Statistics about the indexing operation
        """
        if extensions is None:
            extensions = list(self.parser.LANGUAGE_EXTENSIONS.keys())

        stats = {"files_processed": 0, "symbols_indexed": 0, "errors": 0}

        # Find all matching files
        for ext in extensions:
            for file_path in directory.rglob(f"*{ext}"):
                # Skip hidden directories and common ignore patterns
                if any(part.startswith(".") for part in file_path.parts):
                    continue
                if any(part in ["node_modules", "__pycache__", "venv"] for part in file_path.parts):
                    continue

                try:
                    symbols = await self.index_file(repo, file_path, incremental)
                    stats["files_processed"] += 1
                    stats["symbols_indexed"] += len(symbols)
                except Exception as e:
                    logger.error(f"Error indexing {file_path}: {e}")
                    stats["errors"] += 1

        return stats

    async def index_commit_changes(self, repo: str, changed_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Index changes from a commit.

        Args:
            repo: Repository identifier
            changed_files: List of changed files with change types

        Returns:
            Statistics about the indexing operation
        """
        stats = {"files_processed": 0, "files_deleted": 0, "symbols_indexed": 0, "errors": 0}

        for file_info in changed_files:
            file_path = Path(file_info["path"])
            change_type = file_info.get("change_type", "modified")

            try:
                if change_type == "deleted":
                    # Remove symbols for deleted file
                    deleted_count = await self.repository.delete_file_symbols(repo, str(file_path))
                    stats["files_deleted"] += 1
                    logger.info(f"Deleted {deleted_count} symbols from {file_path}")

                elif change_type in ["added", "modified"]:
                    # Index the file
                    symbols = await self.index_file(repo, file_path, incremental=True)
                    stats["files_processed"] += 1
                    stats["symbols_indexed"] += len(symbols)

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                stats["errors"] += 1

        return stats

    async def search_symbols(
        self, repo: str, query: str, kind: Optional[str] = None, language: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for similar code symbols.

        Args:
            repo: Repository identifier
            query: Search query text
            kind: Filter by symbol kind (function, class, etc.)
            language: Filter by programming language
            limit: Maximum number of results

        Returns:
            List of matching symbols with similarity scores
        """
        # Generate embedding for query
        query_embedding = await self.ai_integration.generate_embeddings(query)

        # Search in repository
        results = await self.repository.search_similar_symbols(
            repo=repo, embedding=query_embedding, kind=kind, language=language, limit=limit
        )

        return results

    def _create_embedding_text(self, symbol: ParsedSymbol) -> str:
        """Create text for embedding generation from a symbol."""
        parts = [
            f"{symbol.kind}: {symbol.name}",
        ]

        if symbol.signature:
            parts.append(f"Signature: {symbol.signature}")

        if symbol.docstring:
            parts.append(f"Documentation: {symbol.docstring}")

        if symbol.language:
            parts.append(f"Language: {symbol.language}")

        return "\n".join(parts)

    def _symbols_equal(self, existing: CodeSymbol, parsed: ParsedSymbol) -> bool:
        """Check if two symbols are functionally equal."""
        # Compare essential attributes
        if existing.name != parsed.name:
            return False

        if existing.kind != parsed.kind:
            return False

        if existing.sig != parsed.signature:  # Model uses 'sig'
            return False

        if existing.docstring != parsed.docstring:
            return False

        # Compare span
        existing_span = existing.span or {}
        if (
            existing_span.get("start", {}).get("line") != parsed.start_line
            or existing_span.get("end", {}).get("line") != parsed.end_line
        ):
            return False

        return True

    def _detect_language(self, file_path: Path) -> str:
        """Detect language from file extension."""
        return self.parser.LANGUAGE_EXTENSIONS.get(file_path.suffix.lower(), "unknown")
