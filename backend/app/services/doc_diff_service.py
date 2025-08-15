"""
Documentation Diff and Rollback Service

Provides diff generation, preview capabilities, and rollback mechanisms
for documentation changes with version control.
"""

import difflib
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import ResourceNotFoundError, ValidationError
from supabase import Client

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of documentation changes."""

    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"
    MOVE = "move"
    RENAME = "rename"


class DiffFormat(Enum):
    """Diff output formats."""

    UNIFIED = "unified"
    SIDE_BY_SIDE = "side_by_side"
    HTML = "html"
    JSON = "json"


@dataclass
class DocumentVersion:
    """Document version information."""

    id: str
    document_id: str
    version_number: int
    content: str
    content_hash: str
    title: str
    author_id: str
    created_at: datetime
    commit_message: Optional[str] = None
    parent_version_id: Optional[str] = None
    tags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class DiffChunk:
    """A chunk of differences between two documents."""

    change_type: ChangeType
    line_start: int
    line_end: int
    old_content: str
    new_content: str
    context_before: str
    context_after: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "change_type": self.change_type.value,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "context_before": self.context_before,
            "context_after": self.context_after,
        }


@dataclass
class DocumentDiff:
    """Complete diff between two document versions."""

    from_version_id: str
    to_version_id: str
    from_version_number: int
    to_version_number: int
    chunks: List[DiffChunk]
    summary: Dict[str, int]  # lines_added, lines_removed, lines_modified
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "from_version_id": self.from_version_id,
            "to_version_id": self.to_version_id,
            "from_version_number": self.from_version_number,
            "to_version_number": self.to_version_number,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "summary": self.summary,
            "created_at": self.created_at.isoformat(),
        }


class DocDiffService:
    """Service for managing document diffs, versions, and rollbacks."""

    def __init__(self, supabase: Client):
        """Initialize the diff service."""
        self.supabase = supabase

        # Configuration
        self.max_versions_per_doc = 50  # Keep last 50 versions
        self.auto_cleanup_days = 90  # Clean up versions older than 90 days

        logger.info("DocDiffService initialized")

    async def create_version(
        self,
        document_id: str,
        content: str,
        title: str,
        author_id: str,
        commit_message: Optional[str] = None,
        parent_version_id: Optional[str] = None,
    ) -> DocumentVersion:
        """
        Create a new version of a document.

        Args:
            document_id: ID of the document
            content: Document content
            title: Document title
            author_id: ID of the author
            commit_message: Optional commit message
            parent_version_id: Optional parent version ID

        Returns:
            DocumentVersion instance
        """
        try:
            # Calculate content hash
            content_hash = self._calculate_content_hash(content)

            # Get current version number
            version_number = await self._get_next_version_number(document_id)

            # Create version
            version = DocumentVersion(
                id=self._generate_version_id(),
                document_id=document_id,
                version_number=version_number,
                content=content,
                content_hash=content_hash,
                title=title,
                author_id=author_id,
                created_at=datetime.now(),
                commit_message=commit_message,
                parent_version_id=parent_version_id,
            )

            # Save to database
            await self._save_version(version)

            # Clean up old versions if needed
            await self._cleanup_old_versions(document_id)

            logger.info(f"Created version {version_number} for document {document_id}")
            return version

        except Exception as e:
            logger.error(f"Error creating version for document {document_id}: {e}")
            raise

    async def get_version(self, version_id: str) -> DocumentVersion:
        """Get a specific document version."""
        try:
            response = self.supabase.table("document_versions").select("*").eq("id", version_id).single().execute()

            if not response.data:
                raise ResourceNotFoundError(resource_name="DocumentVersion", resource_id=version_id)

            return self._version_from_db(response.data)

        except Exception as e:
            logger.error(f"Error fetching version {version_id}: {e}")
            raise

    async def list_versions(self, document_id: str, limit: int = 20) -> List[DocumentVersion]:
        """List versions for a document."""
        try:
            response = (
                self.supabase.table("document_versions")
                .select("*")
                .eq("document_id", document_id)
                .order("version_number", desc=True)
                .limit(limit)
                .execute()
            )

            return [self._version_from_db(row) for row in response.data]

        except Exception as e:
            logger.error(f"Error listing versions for document {document_id}: {e}")
            raise

    async def generate_diff(
        self, from_version_id: str, to_version_id: str, diff_format: DiffFormat = DiffFormat.UNIFIED
    ) -> DocumentDiff:
        """
        Generate diff between two document versions.

        Args:
            from_version_id: Source version ID
            to_version_id: Target version ID
            diff_format: Format for diff output

        Returns:
            DocumentDiff instance
        """
        try:
            # Get versions
            from_version = await self.get_version(from_version_id)
            to_version = await self.get_version(to_version_id)

            # Validate same document
            if from_version.document_id != to_version.document_id:
                raise ValidationError("Cannot diff versions from different documents")

            # Generate diff chunks
            chunks = self._generate_diff_chunks(from_version.content, to_version.content)

            # Calculate summary
            summary = self._calculate_diff_summary(chunks)

            diff = DocumentDiff(
                from_version_id=from_version_id,
                to_version_id=to_version_id,
                from_version_number=from_version.version_number,
                to_version_number=to_version.version_number,
                chunks=chunks,
                summary=summary,
                created_at=datetime.now(),
            )

            logger.info(
                f"Generated diff between versions {from_version.version_number} and {to_version.version_number}"
            )
            return diff

        except Exception as e:
            logger.error(f"Error generating diff between {from_version_id} and {to_version_id}: {e}")
            raise

    async def preview_changes(
        self, current_content: str, proposed_content: str, format_type: DiffFormat = DiffFormat.SIDE_BY_SIDE
    ) -> Dict[str, Any]:
        """
        Preview changes between current and proposed content.

        Args:
            current_content: Current document content
            proposed_content: Proposed new content
            format_type: Format for preview

        Returns:
            Dictionary with formatted diff preview
        """
        try:
            # Generate diff chunks
            chunks = self._generate_diff_chunks(current_content, proposed_content)

            # Calculate summary
            summary = self._calculate_diff_summary(chunks)

            # Format based on requested type
            if format_type == DiffFormat.HTML:
                formatted_diff = self._format_diff_html(chunks, current_content, proposed_content)
            elif format_type == DiffFormat.SIDE_BY_SIDE:
                formatted_diff = self._format_diff_side_by_side(chunks, current_content, proposed_content)
            elif format_type == DiffFormat.JSON:
                formatted_diff = [chunk.to_dict() for chunk in chunks]
            else:  # UNIFIED
                formatted_diff = self._format_diff_unified(chunks, current_content, proposed_content)

            return {
                "summary": summary,
                "format": format_type.value,
                "diff": formatted_diff,
                "created_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating diff preview: {e}")
            raise

    async def rollback_to_version(
        self, document_id: str, target_version_id: str, author_id: str, rollback_reason: str = ""
    ) -> DocumentVersion:
        """
        Rollback document to a specific version.

        Args:
            document_id: ID of the document
            target_version_id: Version to rollback to
            author_id: ID of the user performing rollback
            rollback_reason: Reason for rollback

        Returns:
            New DocumentVersion with rolled back content
        """
        try:
            # Get target version
            target_version = await self.get_version(target_version_id)

            # Validate document ID matches
            if target_version.document_id != document_id:
                raise ValidationError("Target version does not belong to specified document")

            # Get current version for commit message
            current_versions = await self.list_versions(document_id, limit=1)
            current_version_num = current_versions[0].version_number if current_versions else 0

            # Create rollback commit message
            commit_message = f"Rollback to version {target_version.version_number}"
            if rollback_reason:
                commit_message += f": {rollback_reason}"

            # Create new version with rolled back content
            rollback_version = await self.create_version(
                document_id=document_id,
                content=target_version.content,
                title=target_version.title,
                author_id=author_id,
                commit_message=commit_message,
                parent_version_id=current_versions[0].id if current_versions else None,
            )

            # Log rollback
            await self._log_rollback(document_id, target_version_id, rollback_version.id, author_id, rollback_reason)

            logger.info(f"Rolled back document {document_id} to version {target_version.version_number}")
            return rollback_version

        except Exception as e:
            logger.error(f"Error rolling back document {document_id} to version {target_version_id}: {e}")
            raise

    async def get_rollback_history(self, document_id: str) -> List[Dict[str, Any]]:
        """Get rollback history for a document."""
        try:
            response = (
                self.supabase.table("document_rollbacks")
                .select("*")
                .eq("document_id", document_id)
                .order("created_at", desc=True)
                .execute()
            )

            return response.data

        except Exception as e:
            logger.error(f"Error fetching rollback history for document {document_id}: {e}")
            raise

    def _calculate_content_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _generate_version_id(self) -> str:
        """Generate unique version ID."""
        import uuid

        return str(uuid.uuid4())

    async def _get_next_version_number(self, document_id: str) -> int:
        """Get next version number for a document."""
        try:
            response = (
                self.supabase.table("document_versions")
                .select("version_number")
                .eq("document_id", document_id)
                .order("version_number", desc=True)
                .limit(1)
                .execute()
            )

            if response.data:
                return response.data[0]["version_number"] + 1
            else:
                return 1

        except Exception as e:
            logger.warning(f"Error getting next version number for {document_id}: {e}")
            return 1

    async def _save_version(self, version: DocumentVersion) -> None:
        """Save version to database."""
        try:
            data = {
                "id": version.id,
                "document_id": version.document_id,
                "version_number": version.version_number,
                "content": version.content,
                "content_hash": version.content_hash,
                "title": version.title,
                "author_id": version.author_id,
                "created_at": version.created_at.isoformat(),
                "commit_message": version.commit_message,
                "parent_version_id": version.parent_version_id,
                "tags": version.tags or [],
            }

            self.supabase.table("document_versions").insert(data).execute()

        except Exception as e:
            logger.error(f"Error saving version {version.id}: {e}")
            raise

    def _version_from_db(self, data: Dict[str, Any]) -> DocumentVersion:
        """Convert database row to DocumentVersion object."""
        return DocumentVersion(
            id=data["id"],
            document_id=data["document_id"],
            version_number=data["version_number"],
            content=data["content"],
            content_hash=data["content_hash"],
            title=data["title"],
            author_id=data["author_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            commit_message=data.get("commit_message"),
            parent_version_id=data.get("parent_version_id"),
            tags=data.get("tags", []),
        )

    def _generate_diff_chunks(self, old_content: str, new_content: str) -> List[DiffChunk]:
        """Generate diff chunks between two content strings."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        chunks = []
        differ = difflib.SequenceMatcher(None, old_lines, new_lines)

        for tag, i1, i2, j1, j2 in differ.get_opcodes():
            if tag == "equal":
                continue

            # Determine change type
            if tag == "delete":
                change_type = ChangeType.DELETION
                old_content_chunk = "".join(old_lines[i1:i2])
                new_content_chunk = ""
            elif tag == "insert":
                change_type = ChangeType.ADDITION
                old_content_chunk = ""
                new_content_chunk = "".join(new_lines[j1:j2])
            else:  # replace
                change_type = ChangeType.MODIFICATION
                old_content_chunk = "".join(old_lines[i1:i2])
                new_content_chunk = "".join(new_lines[j1:j2])

            # Get context
            context_before = "".join(old_lines[max(0, i1 - 3) : i1]) if i1 > 0 else ""
            context_after = "".join(old_lines[i2 : min(len(old_lines), i2 + 3)]) if i2 < len(old_lines) else ""

            chunk = DiffChunk(
                change_type=change_type,
                line_start=i1 + 1,  # 1-based line numbers
                line_end=i2 + 1,
                old_content=old_content_chunk.rstrip("\n"),
                new_content=new_content_chunk.rstrip("\n"),
                context_before=context_before.rstrip("\n"),
                context_after=context_after.rstrip("\n"),
            )

            chunks.append(chunk)

        return chunks

    def _calculate_diff_summary(self, chunks: List[DiffChunk]) -> Dict[str, int]:
        """Calculate summary statistics for diff chunks."""
        lines_added = 0
        lines_removed = 0
        lines_modified = 0

        for chunk in chunks:
            if chunk.change_type == ChangeType.ADDITION:
                lines_added += len(chunk.new_content.splitlines())
            elif chunk.change_type == ChangeType.DELETION:
                lines_removed += len(chunk.old_content.splitlines())
            elif chunk.change_type == ChangeType.MODIFICATION:
                old_lines = len(chunk.old_content.splitlines())
                new_lines = len(chunk.new_content.splitlines())
                lines_modified += max(old_lines, new_lines)

        return {
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "lines_modified": lines_modified,
            "total_changes": len(chunks),
        }

    def _format_diff_unified(self, chunks: List[DiffChunk], old_content: str, new_content: str) -> str:
        """Format diff as unified diff."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after", lineterm="")

        return "".join(diff)

    def _format_diff_side_by_side(
        self, chunks: List[DiffChunk], old_content: str, new_content: str
    ) -> List[Dict[str, Any]]:
        """Format diff as side-by-side comparison."""
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        result = []
        old_idx = 0
        new_idx = 0

        for chunk in chunks:
            # Add unchanged lines before this chunk
            while old_idx < chunk.line_start - 1:
                result.append(
                    {
                        "old_line_num": old_idx + 1,
                        "new_line_num": new_idx + 1,
                        "old_content": old_lines[old_idx] if old_idx < len(old_lines) else "",
                        "new_content": new_lines[new_idx] if new_idx < len(new_lines) else "",
                        "type": "unchanged",
                    }
                )
                old_idx += 1
                new_idx += 1

            # Add the changed chunk
            if chunk.change_type == ChangeType.ADDITION:
                for line in chunk.new_content.splitlines():
                    result.append(
                        {
                            "old_line_num": None,
                            "new_line_num": new_idx + 1,
                            "old_content": "",
                            "new_content": line,
                            "type": "addition",
                        }
                    )
                    new_idx += 1
            elif chunk.change_type == ChangeType.DELETION:
                for line in chunk.old_content.splitlines():
                    result.append(
                        {
                            "old_line_num": old_idx + 1,
                            "new_line_num": None,
                            "old_content": line,
                            "new_content": "",
                            "type": "deletion",
                        }
                    )
                    old_idx += 1
            else:  # MODIFICATION
                old_chunk_lines = chunk.old_content.splitlines()
                new_chunk_lines = chunk.new_content.splitlines()
                max_lines = max(len(old_chunk_lines), len(new_chunk_lines))

                for i in range(max_lines):
                    old_line = old_chunk_lines[i] if i < len(old_chunk_lines) else ""
                    new_line = new_chunk_lines[i] if i < len(new_chunk_lines) else ""

                    result.append(
                        {
                            "old_line_num": old_idx + 1 if old_line else None,
                            "new_line_num": new_idx + 1 if new_line else None,
                            "old_content": old_line,
                            "new_content": new_line,
                            "type": "modification",
                        }
                    )

                    if old_line:
                        old_idx += 1
                    if new_line:
                        new_idx += 1

        return result

    def _format_diff_html(self, chunks: List[DiffChunk], old_content: str, new_content: str) -> str:
        """Format diff as HTML."""
        html_diff = difflib.HtmlDiff()
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        return html_diff.make_file(old_lines, new_lines, context=True, numlines=3)

    async def _cleanup_old_versions(self, document_id: str) -> None:
        """Clean up old versions if limit exceeded."""
        try:
            # Get version count
            response = (
                self.supabase.table("document_versions")
                .select("id")
                .eq("document_id", document_id)
                .order("version_number", desc=True)
                .execute()
            )

            if len(response.data) > self.max_versions_per_doc:
                # Keep most recent versions, delete oldest
                versions_to_keep = response.data[: self.max_versions_per_doc]
                keep_ids = [v["id"] for v in versions_to_keep]

                # Delete older versions
                self.supabase.table("document_versions").delete().eq("document_id", document_id).not_.in_(
                    "id", keep_ids
                ).execute()

                logger.info(f"Cleaned up old versions for document {document_id}")

        except Exception as e:
            logger.warning(f"Error cleaning up old versions for {document_id}: {e}")

    async def _log_rollback(
        self, document_id: str, target_version_id: str, new_version_id: str, author_id: str, reason: str
    ) -> None:
        """Log rollback operation."""
        try:
            data = {
                "id": self._generate_version_id(),
                "document_id": document_id,
                "target_version_id": target_version_id,
                "new_version_id": new_version_id,
                "author_id": author_id,
                "reason": reason,
                "created_at": datetime.now().isoformat(),
            }

            self.supabase.table("document_rollbacks").insert(data).execute()

        except Exception as e:
            logger.warning(f"Error logging rollback: {e}")


# Database schemas
DOCUMENT_VERSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    version_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    author_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    commit_message TEXT,
    parent_version_id UUID,
    tags JSONB DEFAULT '[]',
    
    FOREIGN KEY (author_id) REFERENCES users(id),
    UNIQUE(document_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_document_versions_document ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_version ON document_versions(document_id, version_number);
CREATE INDEX IF NOT EXISTS idx_document_versions_hash ON document_versions(content_hash);
"""

DOCUMENT_ROLLBACKS_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_rollbacks (
    id UUID PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    target_version_id UUID NOT NULL,
    new_version_id UUID NOT NULL,
    author_id UUID NOT NULL,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    FOREIGN KEY (author_id) REFERENCES users(id),
    FOREIGN KEY (target_version_id) REFERENCES document_versions(id),
    FOREIGN KEY (new_version_id) REFERENCES document_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_document_rollbacks_document ON document_rollbacks(document_id);
"""
