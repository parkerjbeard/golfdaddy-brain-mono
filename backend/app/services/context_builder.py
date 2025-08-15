"""
Context building service for RAG operations.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from cachetools import LRUCache

from app.core.database import AsyncSession
from app.integrations.ai_integration_v2 import AIIntegrationV2
from app.repositories.code_symbol_repository import CodeSymbolRepository
from app.repositories.doc_chunk_repository import DocChunkRepository

logger = logging.getLogger(__name__)


@dataclass
class ChangeContext:
    """Represents context for a code change."""

    changed_symbols: List[Dict[str, Any]]
    related_symbols: List[Dict[str, Any]]
    related_docs: List[Dict[str, Any]]
    diff_context: Dict[str, Any]


class ContextBuilder:
    """Service for building context around code changes using RAG."""

    def __init__(self, session: AsyncSession, cache_size: int = 100):
        """Initialize the context builder.

        Args:
            session: Database session
            cache_size: Size of the LRU cache for contexts
        """
        self.session = session
        self.code_repository = CodeSymbolRepository(session)
        self.doc_repository = DocChunkRepository(session)
        self.ai_integration = AIIntegrationV2()
        self.context_cache = LRUCache(maxsize=cache_size)

    async def build_change_context(self, repo: str, diff: str, context_lines: int = 5) -> ChangeContext:
        """Build context for a code change.

        Args:
            repo: Repository identifier
            diff: Git diff string
            context_lines: Number of lines to include around changes

        Returns:
            ChangeContext with relevant information
        """
        # Check cache first
        cache_key = self._get_cache_key(repo, diff)
        if cache_key in self.context_cache:
            logger.debug(f"Context cache hit for {cache_key}")
            return self.context_cache[cache_key]

        # Parse the diff
        diff_context = self._parse_diff(diff, context_lines)

        # Extract changed symbols
        changed_symbols = await self._extract_changed_symbols(repo, diff_context)

        # Find related symbols
        related_symbols = await self._find_related_symbols(repo, changed_symbols)

        # Find related documentation
        related_docs = await self._find_related_docs(repo, changed_symbols)

        # Build context object
        context = ChangeContext(
            changed_symbols=changed_symbols,
            related_symbols=related_symbols,
            related_docs=related_docs,
            diff_context=diff_context,
        )

        # Cache the context
        self.context_cache[cache_key] = context

        return context

    async def find_nearest_symbols(
        self, repo: str, file_path: str, line_number: int, radius: int = 50
    ) -> List[Dict[str, Any]]:
        """Find symbols near a specific line in a file.

        Args:
            repo: Repository identifier
            file_path: Path to the file
            line_number: Target line number
            radius: Number of lines to search around target

        Returns:
            List of nearby symbols
        """
        # Get all symbols in the file
        symbols = await self.code_repository.get_symbols_by_file(repo, file_path)

        # Filter symbols within radius
        nearby = []
        for symbol in symbols:
            span = symbol.span or {}
            start_line = span.get("start", {}).get("line", 0)
            end_line = span.get("end", {}).get("line", 0)

            # Check if symbol is within radius
            if (
                abs(start_line - line_number) <= radius
                or abs(end_line - line_number) <= radius
                or (start_line <= line_number <= end_line)
            ):

                distance = min(abs(start_line - line_number), abs(end_line - line_number))

                nearby.append({"symbol": symbol, "distance": distance})

        # Sort by distance
        nearby.sort(key=lambda x: x["distance"])

        return nearby

    async def find_relevant_docs(self, repo: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find relevant documentation for a query.

        Args:
            repo: Repository identifier
            query: Search query
            limit: Maximum number of results

        Returns:
            List of relevant documentation chunks
        """
        # Generate embedding for query
        query_embedding = await self.ai_integration.generate_embeddings(query)

        # Search for similar documentation
        docs = await self.doc_repository.search_similar_chunks(repo=repo, embedding=query_embedding, limit=limit)

        return docs

    async def build_symbol_context(self, repo: str, symbol_name: str, include_related: bool = True) -> Dict[str, Any]:
        """Build context for a specific symbol.

        Args:
            repo: Repository identifier
            symbol_name: Name of the symbol
            include_related: Whether to include related symbols

        Returns:
            Context information for the symbol
        """
        # Find the symbol
        symbols = await self.code_repository.search_symbols_by_name(repo, symbol_name)

        if not symbols:
            return {"error": f"Symbol {symbol_name} not found"}

        symbol = symbols[0]

        context = {"symbol": symbol, "related_symbols": [], "documentation": []}

        if include_related:
            # Find related symbols
            embedding = symbol.embedding
            if embedding:
                related = await self.code_repository.search_similar_symbols(repo=repo, embedding=embedding, limit=5)
                # Exclude the symbol itself
                context["related_symbols"] = [r for r in related if r["id"] != symbol.id]

            # Find related documentation
            query = f"{symbol.kind} {symbol.name}"
            if symbol.docstring:
                query += f" {symbol.docstring[:100]}"

            docs = await self.find_relevant_docs(repo, query, limit=3)
            context["documentation"] = docs

        return context

    def _parse_diff(self, diff: str, context_lines: int) -> Dict[str, Any]:
        """Parse a git diff and extract information."""
        diff_context = {"files": [], "stats": {"additions": 0, "deletions": 0, "files_changed": 0}}

        current_file = None
        current_hunk = None

        lines = diff.split("\n")
        for line in lines:
            # File header
            if line.startswith("diff --git"):
                # Extract file paths
                match = re.match(r"diff --git a/(.*) b/(.*)", line)
                if match:
                    current_file = {"path": match.group(2), "hunks": []}
                    diff_context["files"].append(current_file)
                    diff_context["stats"]["files_changed"] += 1

            # Hunk header
            elif line.startswith("@@"):
                # Extract line numbers
                match = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)", line)
                if match and current_file:
                    current_hunk = {
                        "old_start": int(match.group(1)),
                        "old_count": int(match.group(2) or 1),
                        "new_start": int(match.group(3)),
                        "new_count": int(match.group(4) or 1),
                        "context": match.group(5).strip(),
                        "changes": [],
                    }
                    current_file["hunks"].append(current_hunk)

            # Addition
            elif line.startswith("+") and not line.startswith("+++"):
                if current_hunk:
                    current_hunk["changes"].append({"type": "add", "content": line[1:]})
                    diff_context["stats"]["additions"] += 1

            # Deletion
            elif line.startswith("-") and not line.startswith("---"):
                if current_hunk:
                    current_hunk["changes"].append({"type": "delete", "content": line[1:]})
                    diff_context["stats"]["deletions"] += 1

            # Context line
            elif line.startswith(" ") and current_hunk:
                current_hunk["changes"].append({"type": "context", "content": line[1:]})

        return diff_context

    async def _extract_changed_symbols(self, repo: str, diff_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract symbols that were changed in the diff."""
        changed_symbols = []

        for file_info in diff_context["files"]:
            file_path = file_info["path"]

            # Get symbols in this file
            symbols = await self.code_repository.get_symbols_by_file(repo, file_path)

            # Check which symbols were affected by hunks
            for hunk in file_info["hunks"]:
                for symbol in symbols:
                    span = symbol.span or {}
                    start_line = span.get("start", {}).get("line", 0)
                    end_line = span.get("end", {}).get("line", 0)

                    # Check if symbol overlaps with hunk
                    if start_line <= hunk["new_start"] + hunk["new_count"] and end_line >= hunk["new_start"]:

                        changed_symbols.append({"symbol": symbol, "hunk": hunk, "file": file_path})

        return changed_symbols

    async def _find_related_symbols(self, repo: str, changed_symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find symbols related to the changed ones."""
        related = []
        seen_ids = set()

        for change in changed_symbols:
            symbol = change["symbol"]

            # Skip if no embedding
            if not symbol.embedding:
                continue

            # Find similar symbols
            similar = await self.code_repository.search_similar_symbols(repo=repo, embedding=symbol.embedding, limit=3)

            for sim in similar:
                if sim["id"] not in seen_ids and sim["id"] != symbol.id:
                    related.append(sim)
                    seen_ids.add(sim["id"])

        return related

    async def _find_related_docs(self, repo: str, changed_symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find documentation related to changed symbols."""
        docs = []
        seen_ids = set()

        for change in changed_symbols:
            symbol = change["symbol"]

            # Build search query
            query = f"{symbol.kind} {symbol.name}"
            if symbol.docstring:
                query += f" {symbol.docstring[:100]}"

            # Search for documentation
            results = await self.doc_repository.search_similar_chunks(
                repo=repo, embedding=await self.ai_integration.generate_embeddings(query), limit=2
            )

            for doc in results:
                if doc["id"] not in seen_ids:
                    docs.append(doc)
                    seen_ids.add(doc["id"])

        return docs

    def _get_cache_key(self, repo: str, diff: str) -> str:
        """Generate cache key for a context."""
        # Use hash of repo + diff for cache key
        content = f"{repo}:{diff}"
        return hashlib.md5(content.encode()).hexdigest()
