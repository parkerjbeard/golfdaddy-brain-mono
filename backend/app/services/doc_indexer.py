"""
Documentation indexing service for parsing and storing Markdown documentation.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.core.database import AsyncSession
from app.integrations.ai_integration_v2 import AIIntegrationV2
from app.models.doc_chunks import DocChunk
from app.repositories.doc_chunk_repository import DocChunkRepository
from app.services.doc_parser import DocChunk as ParsedChunk
from app.services.doc_parser import MarkdownParser

logger = logging.getLogger(__name__)


class DocIndexer:
    """Service for indexing documentation files into the database with embeddings."""

    def __init__(self, session: AsyncSession):
        """Initialize the documentation indexer.

        Args:
            session: Database session for persistence
        """
        self.session = session
        self.parser = MarkdownParser()
        self.repository = DocChunkRepository(session)
        self.ai_integration = AIIntegrationV2()

    async def index_file(
        self, repo: str, file_path: Path, incremental: bool = True
    ) -> Tuple[Dict[str, Any], List[DocChunk]]:
        """Index a single documentation file.

        Args:
            repo: Repository identifier
            file_path: Path to the Markdown file
            incremental: Whether to perform incremental updates

        Returns:
            Tuple of (front_matter, indexed_chunks)
        """
        try:
            # Parse the file
            front_matter, parsed_chunks = self.parser.parse_file(file_path)

            if not parsed_chunks:
                logger.info(f"No content found in {file_path}")
                return front_matter, []

            # Get relative path for storage
            rel_path = str(file_path)

            indexed_chunks = []

            # Process each chunk
            for parsed in parsed_chunks:
                # Check if chunk needs updating (incremental mode)
                if incremental:
                    # Get all chunks for this document
                    existing_chunks = await self.repository.get_chunks_by_document(repo, rel_path)

                    # Find the chunk with matching heading
                    existing = None
                    for chunk in existing_chunks:
                        if chunk.heading == parsed.heading:
                            existing = chunk
                            break

                    if existing and self._chunks_equal(existing, parsed):
                        logger.debug(f"Skipping unchanged chunk: {parsed.heading}")
                        indexed_chunks.append(existing)
                        continue

                # Generate embedding for chunk
                embedding_text = self._create_embedding_text(parsed)
                embedding = await self.ai_integration.generate_embeddings(embedding_text)

                # Create or update chunk in database
                chunk_data = {
                    "repo": repo,
                    "path": rel_path,
                    "heading": parsed.heading,
                    "content": parsed.content,
                    "order_key": parsed.order_key,
                    "level": parsed.level,
                    "metadata": parsed.metadata or {},
                    "embedding": embedding,
                }

                # Use upsert_chunks with a single chunk
                chunks = await self.repository.upsert_chunks([chunk_data])
                chunk = chunks[0] if chunks else None

                indexed_chunks.append(chunk)
                logger.info(f"Indexed chunk: {parsed.heading} (level {parsed.level})")

            # Store front matter as metadata for the file
            if front_matter:
                await self._store_file_metadata(repo, rel_path, front_matter)

            return front_matter, indexed_chunks

        except Exception as e:
            logger.error(f"Error indexing file {file_path}: {e}")
            raise

    async def index_directory(self, repo: str, directory: Path, incremental: bool = True) -> Dict[str, Any]:
        """Index all Markdown files in a directory.

        Args:
            repo: Repository identifier
            directory: Directory path to index
            incremental: Whether to perform incremental updates

        Returns:
            Statistics about the indexing operation
        """
        stats = {"files_processed": 0, "chunks_indexed": 0, "errors": 0}

        # Find all Markdown files
        for file_path in directory.rglob("*.md"):
            # Skip hidden directories
            if any(part.startswith(".") for part in file_path.parts):
                continue

            try:
                front_matter, chunks = await self.index_file(repo, file_path, incremental)
                stats["files_processed"] += 1
                stats["chunks_indexed"] += len(chunks)
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                stats["errors"] += 1

        return stats

    async def search_similar_sections(self, repo: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for similar documentation sections.

        Args:
            repo: Repository identifier
            query: Search query text
            limit: Maximum number of results

        Returns:
            List of matching chunks with similarity scores
        """
        # Generate embedding for query
        query_embedding = await self.ai_integration.generate_embeddings(query)

        # Search in repository
        results = await self.repository.search_similar_chunks(repo=repo, embedding=query_embedding, limit=limit)

        return results

    async def get_document_structure(self, repo: str, file_path: str) -> Dict[str, Any]:
        """Get the hierarchical structure of a document.

        Args:
            repo: Repository identifier
            file_path: Path to the document

        Returns:
            Document structure with headings and hierarchy
        """
        chunks = await self.repository.get_chunks_by_document(repo, file_path)

        # Build hierarchical structure
        structure = {"path": file_path, "sections": []}

        for chunk in sorted(chunks, key=lambda c: c.order_key):
            section = {
                "heading": chunk.heading,
                "level": chunk.level,
                "has_content": bool(chunk.content),
                "metadata": chunk.metadata,
            }
            structure["sections"].append(section)

        return structure

    async def update_code_references(self, repo: str, updates: Dict[str, str]) -> int:
        """Update code references in documentation.

        Args:
            repo: Repository identifier
            updates: Dictionary mapping old code to new code

        Returns:
            Number of chunks updated
        """
        updated_count = 0

        # Find chunks containing code blocks
        all_chunks = await self.repository.get_chunks_by_repo(repo, limit=1000)

        for chunk in all_chunks:
            if not chunk.content:
                continue

            # Check if chunk contains any of the old code
            original_content = chunk.content
            updated_content = self.parser.update_code_snippets(original_content, updates)

            if updated_content != original_content:
                # Update the chunk
                chunk.content = updated_content

                # Regenerate embedding
                embedding_text = self._create_embedding_text(chunk)
                chunk.embedding = await self.ai_integration.generate_embeddings(embedding_text)

                await self.repository.update_chunk(chunk.id, {"content": chunk.content, "embedding": chunk.embedding})
                updated_count += 1
                logger.info(f"Updated code references in: {chunk.heading}")

        return updated_count

    def _create_embedding_text(self, chunk: ParsedChunk) -> str:
        """Create text for embedding generation from a chunk."""
        parts = [f"# {chunk.heading}", chunk.content]

        # Add code blocks if present
        if chunk.code_blocks:
            for block in chunk.code_blocks:
                parts.append(f"Code ({block['language']}): {block['code'][:200]}")

        return "\n".join(parts)

    def _chunks_equal(self, existing: DocChunk, parsed: ParsedChunk) -> bool:
        """Check if two chunks are functionally equal."""
        # Compare content
        if existing.content != parsed.content:
            return False

        # Compare heading
        if existing.heading != parsed.heading:
            return False

        return True

    async def _store_file_metadata(self, repo: str, file_path: str, metadata: Dict[str, Any]) -> None:
        """Store file-level metadata."""
        # This could be stored in a separate table or as a special chunk
        # For now, we'll store it as a metadata-only chunk
        chunk_data = {
            "repo": repo,
            "path": file_path,
            "heading": "__metadata__",
            "content": "",
            "order_key": -1,  # Special order key for metadata
            "level": 0,
            "metadata": metadata,
            "embedding": None,
        }

        await self.repository.upsert_chunks([chunk_data])
