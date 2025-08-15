"""
Patch generation service for documentation updates.
"""

import difflib
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PatchAction(Enum):
    """Types of patch actions."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RENAME = "rename"


@dataclass
class PatchMetadata:
    """Metadata for a patch."""

    timestamp: str
    author: str = "AI Documentation Writer"
    version: str = "1.0.0"
    doc_type: str = ""
    task_type: str = ""
    confidence: float = 0.0
    checksum: str = ""  # For verification
    parent_patch_id: Optional[str] = None  # For incremental patches


@dataclass
class DocumentationPatch:
    """Represents a documentation patch."""

    patch_id: str
    action: PatchAction
    file_path: str
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    diff: Optional[str] = None
    metadata: PatchMetadata = field(default_factory=lambda: PatchMetadata(timestamp=datetime.utcnow().isoformat()))
    applied: bool = False
    rollback_data: Optional[Dict[str, Any]] = None


@dataclass
class PatchSet:
    """Collection of patches that should be applied atomically."""

    patch_set_id: str
    patches: List[DocumentationPatch]
    metadata: Dict[str, Any]
    atomic: bool = True  # If true, all patches must succeed or all are rolled back
    applied: bool = False
    rollback_order: List[str] = field(default_factory=list)  # Order for rollback


class PatchGenerator:
    """Service for generating and managing documentation patches."""

    def __init__(self, workspace_dir: Optional[Path] = None):
        """Initialize the patch generator.

        Args:
            workspace_dir: Directory for storing patch history and rollback data
        """
        self.workspace_dir = workspace_dir or Path.cwd() / ".doc_patches"
        self.workspace_dir.mkdir(exist_ok=True, parents=True)
        self.patch_history: List[DocumentationPatch] = []
        self.active_patches: Dict[str, DocumentationPatch] = {}  # patch_id -> patch

    def generate_patch(
        self,
        action: PatchAction,
        file_path: str,
        original_content: Optional[str] = None,
        new_content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DocumentationPatch:
        """Generate a single documentation patch.

        Args:
            action: Type of patch action
            file_path: Path to the file
            original_content: Original file content (for updates)
            new_content: New file content
            metadata: Additional metadata

        Returns:
            Generated documentation patch
        """
        # Generate patch ID
        patch_id = self._generate_patch_id(file_path, new_content)

        # Generate diff if updating
        diff = None
        if action == PatchAction.UPDATE and original_content and new_content:
            diff = self._generate_unified_diff(original_content, new_content, file_path)

        # Create metadata
        patch_metadata = PatchMetadata(
            timestamp=datetime.utcnow().isoformat(),
            checksum=self._calculate_checksum(new_content or ""),
            **(metadata or {}),
        )

        # Create rollback data
        rollback_data = self._create_rollback_data(action, file_path, original_content) or {}

        # Create patch
        patch = DocumentationPatch(
            patch_id=patch_id,
            action=action,
            file_path=file_path,
            original_content=original_content,
            new_content=new_content,
            diff=diff,
            metadata=patch_metadata,
            rollback_data=rollback_data,
        )

        # Store in active patches
        self.active_patches[patch_id] = patch

        return patch

    def generate_patch_set(self, patches_data: List[Dict[str, Any]], atomic: bool = True) -> PatchSet:
        """Generate a set of patches to be applied atomically.

        Args:
            patches_data: List of patch data dictionaries
            atomic: Whether patches should be applied atomically

        Returns:
            Generated patch set
        """
        patches = []

        for patch_data in patches_data:
            patch = self.generate_patch(
                action=PatchAction(patch_data.get("action", "update")),
                file_path=patch_data["file_path"],
                original_content=patch_data.get("original_content"),
                new_content=patch_data.get("new_content"),
                metadata=patch_data.get("metadata"),
            )
            patches.append(patch)

        # Create patch set
        patch_set = PatchSet(
            patch_set_id=self._generate_patch_set_id(patches),
            patches=patches,
            metadata={"created_at": datetime.utcnow().isoformat(), "patch_count": len(patches), "atomic": atomic},
            atomic=atomic,
            rollback_order=[p.patch_id for p in reversed(patches)],  # Reverse order for rollback
        )

        return patch_set

    def apply_patch(self, patch: DocumentationPatch, dry_run: bool = False) -> Tuple[bool, Optional[str]]:
        """Apply a single documentation patch.

        Args:
            patch: Patch to apply
            dry_run: If true, don't actually apply the patch

        Returns:
            Tuple of (success, error_message)
        """
        try:
            if patch.applied:
                return False, "Patch already applied"

            file_path = Path(patch.file_path)

            if dry_run:
                # Validate patch without applying
                return self._validate_patch(patch)

            if patch.action == PatchAction.CREATE:
                if file_path.exists():
                    return False, f"File already exists: {file_path}"

                # Create parent directories if needed
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write new content
                file_path.write_text(patch.new_content or "")

            elif patch.action == PatchAction.UPDATE:
                if not file_path.exists():
                    return False, f"File not found: {file_path}"

                # Verify original content matches (for safety)
                current_content = file_path.read_text()
                if patch.original_content and current_content != patch.original_content:
                    # Check if it's a minor difference (whitespace, etc.)
                    if not self._contents_similar(current_content, patch.original_content):
                        return False, "Original content doesn't match current file content"

                # Apply update
                file_path.write_text(patch.new_content or "")

            elif patch.action == PatchAction.DELETE:
                if not file_path.exists():
                    return False, f"File not found: {file_path}"

                # Store backup for rollback
                if patch.rollback_data is None:
                    patch.rollback_data = {}
                patch.rollback_data["content"] = file_path.read_text()

                # Delete file
                file_path.unlink()

            elif patch.action == PatchAction.RENAME:
                if not file_path.exists():
                    return False, f"File not found: {file_path}"

                new_path = Path(patch.new_content)  # New content contains new path
                if new_path.exists():
                    return False, f"Target file already exists: {new_path}"

                # Rename file
                file_path.rename(new_path)

            # Mark as applied
            patch.applied = True

            # Save to history
            self._save_patch_to_history(patch)

            logger.info(f"Applied patch {patch.patch_id} to {patch.file_path}")
            return True, None

        except Exception as e:
            logger.error(f"Error applying patch {patch.patch_id}: {e}")
            return False, str(e)

    def apply_patch_set(self, patch_set: PatchSet, dry_run: bool = False) -> Tuple[bool, List[str]]:
        """Apply a set of patches atomically.

        Args:
            patch_set: Patch set to apply
            dry_run: If true, don't actually apply patches

        Returns:
            Tuple of (success, list of error messages)
        """
        if patch_set.applied:
            return False, ["Patch set already applied"]

        errors = []
        applied_patches = []

        for patch in patch_set.patches:
            success, error = self.apply_patch(patch, dry_run)

            if not success:
                errors.append(f"{patch.file_path}: {error}")

                # If atomic and not dry run, rollback applied patches
                if patch_set.atomic and not dry_run:
                    logger.info(f"Rolling back {len(applied_patches)} patches due to failure")
                    for applied_patch in reversed(applied_patches):
                        rollback_success, rollback_error = self.rollback_patch(applied_patch)
                        if not rollback_success:
                            errors.append(f"Rollback failed for {applied_patch.file_path}: {rollback_error}")
                        else:
                            logger.info(f"Successfully rolled back patch for {applied_patch.file_path}")

                    return False, errors
            else:
                applied_patches.append(patch)

        if not errors:
            patch_set.applied = True
            logger.info(f"Successfully applied patch set {patch_set.patch_set_id}")

        return len(errors) == 0, errors

    def rollback_patch(self, patch: DocumentationPatch) -> Tuple[bool, Optional[str]]:
        """Rollback a previously applied patch.

        Args:
            patch: Patch to rollback

        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not patch.applied:
                logger.warning(f"Cannot rollback patch {patch.patch_id} - not marked as applied")
                return False, "Patch not applied"

            if not patch.rollback_data and patch.action != PatchAction.CREATE:
                logger.warning(f"Cannot rollback patch {patch.patch_id} - no rollback data")
                return False, "No rollback data available"

            file_path = Path(patch.file_path)

            if patch.action == PatchAction.CREATE:
                # Delete the created file
                if file_path.exists():
                    logger.info(f"Deleting created file: {file_path}")
                    file_path.unlink()
                else:
                    logger.warning(f"File does not exist for rollback: {file_path}")

            elif patch.action == PatchAction.UPDATE:
                # Restore original content
                if "original_content" in patch.rollback_data:
                    file_path.write_text(patch.rollback_data["original_content"])
                elif patch.original_content:
                    file_path.write_text(patch.original_content)
                else:
                    return False, "No original content for rollback"

            elif patch.action == PatchAction.DELETE:
                # Restore deleted file
                if "content" in patch.rollback_data:
                    file_path.write_text(patch.rollback_data["content"])
                else:
                    return False, "No content for restoration"

            elif patch.action == PatchAction.RENAME:
                # Rename back
                if "original_path" in patch.rollback_data:
                    new_path = Path(patch.new_content)
                    original_path = Path(patch.rollback_data["original_path"])
                    if new_path.exists():
                        new_path.rename(original_path)

            # Mark as not applied
            patch.applied = False

            logger.info(f"Rolled back patch {patch.patch_id}")
            return True, None

        except Exception as e:
            logger.error(f"Error rolling back patch {patch.patch_id}: {e}")
            return False, str(e)

    def rollback_patch_set(self, patch_set: PatchSet) -> Tuple[bool, List[str]]:
        """Rollback an entire patch set.

        Args:
            patch_set: Patch set to rollback

        Returns:
            Tuple of (success, list of error messages)
        """
        if not patch_set.applied:
            return False, ["Patch set not applied"]

        errors = []

        # Rollback in reverse order
        for patch_id in patch_set.rollback_order:
            patch = next((p for p in patch_set.patches if p.patch_id == patch_id), None)
            if patch:
                success, error = self.rollback_patch(patch)
                if not success:
                    errors.append(f"{patch.file_path}: {error}")

        if not errors:
            patch_set.applied = False
            logger.info(f"Successfully rolled back patch set {patch_set.patch_set_id}")

        return len(errors) == 0, errors

    def generate_incremental_patch(
        self, base_patch: DocumentationPatch, new_content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> DocumentationPatch:
        """Generate an incremental patch based on a previous patch.

        Args:
            base_patch: Base patch to build upon
            new_content: New content for incremental update
            metadata: Additional metadata

        Returns:
            Incremental documentation patch
        """
        # Get current content (either from base patch or file)
        if base_patch.applied:
            file_path = Path(base_patch.file_path)
            if file_path.exists():
                current_content = file_path.read_text()
            else:
                current_content = base_patch.new_content
        else:
            current_content = base_patch.new_content

        # Create incremental patch
        incremental_metadata = metadata or {}
        incremental_metadata["parent_patch_id"] = base_patch.patch_id

        return self.generate_patch(
            action=PatchAction.UPDATE,
            file_path=base_patch.file_path,
            original_content=current_content,
            new_content=new_content,
            metadata=incremental_metadata,
        )

    def export_patches(self, patch_ids: Optional[List[str]] = None) -> str:
        """Export patches as a unified diff.

        Args:
            patch_ids: Specific patch IDs to export (None for all)

        Returns:
            Unified diff string
        """
        patches_to_export = []

        if patch_ids:
            patches_to_export = [self.active_patches[pid] for pid in patch_ids if pid in self.active_patches]
        else:
            patches_to_export = list(self.active_patches.values())

        diff_parts = []

        for patch in patches_to_export:
            if patch.diff:
                diff_parts.append(patch.diff)
            elif patch.action == PatchAction.CREATE:
                diff_parts.append(self._format_creation_diff(patch))
            elif patch.action == PatchAction.DELETE:
                diff_parts.append(self._format_deletion_diff(patch))

        return "\n".join(diff_parts)

    def _generate_patch_id(self, file_path: str, content: Optional[str]) -> str:
        """Generate a unique patch ID."""
        data = f"{file_path}:{content or ''}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:12]

    def _generate_patch_set_id(self, patches: List[DocumentationPatch]) -> str:
        """Generate a unique patch set ID."""
        patch_ids = "-".join(p.patch_id for p in patches)
        return hashlib.sha256(patch_ids.encode()).hexdigest()[:12]

    def _calculate_checksum(self, content: str) -> str:
        """Calculate content checksum for verification."""
        return hashlib.md5(content.encode()).hexdigest()

    def _generate_unified_diff(self, original: str, new: str, file_path: str) -> str:
        """Generate a unified diff between original and new content."""
        original_lines = original.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines, new_lines, fromfile=f"a/{file_path}", tofile=f"b/{file_path}", lineterm=""
        )

        return "".join(diff)

    def _format_creation_diff(self, patch: DocumentationPatch) -> str:
        """Format a creation patch as diff."""
        lines = []
        lines.append(f"--- /dev/null")
        lines.append(f"+++ b/{patch.file_path}")
        if patch.new_content:
            lines.append(f"@@ -0,0 +1,{len(patch.new_content.splitlines())} @@")

            for line in patch.new_content.splitlines():
                lines.append(f"+{line}")
        else:
            lines.append(f"@@ -0,0 +1,0 @@")

        return "\n".join(lines)

    def _format_deletion_diff(self, patch: DocumentationPatch) -> str:
        """Format a deletion patch as diff."""
        lines = []
        lines.append(f"--- a/{patch.file_path}")
        lines.append(f"+++ /dev/null")

        if patch.original_content:
            content_lines = patch.original_content.splitlines()
            lines.append(f"@@ -1,{len(content_lines)} +0,0 @@")

            for line in content_lines:
                lines.append(f"-{line}")

        return "\n".join(lines)

    def _create_rollback_data(
        self, action: PatchAction, file_path: str, original_content: Optional[str]
    ) -> Dict[str, Any]:
        """Create rollback data for a patch."""
        rollback_data = {}

        if action == PatchAction.UPDATE:
            rollback_data["original_content"] = original_content
        elif action == PatchAction.RENAME:
            rollback_data["original_path"] = file_path

        return rollback_data

    def _validate_patch(self, patch: DocumentationPatch) -> Tuple[bool, Optional[str]]:
        """Validate a patch without applying it."""
        file_path = Path(patch.file_path)

        if patch.action == PatchAction.CREATE:
            if file_path.exists():
                return False, f"File already exists: {file_path}"

        elif patch.action in [PatchAction.UPDATE, PatchAction.DELETE]:
            if not file_path.exists():
                return False, f"File not found: {file_path}"

        # Validate content
        if patch.new_content:
            # Check for basic validity (not empty for non-delete operations)
            if patch.action != PatchAction.DELETE and not patch.new_content.strip():
                return False, "New content is empty"

        return True, None

    def _contents_similar(self, content1: str, content2: str) -> bool:
        """Check if two contents are similar (ignoring minor differences)."""
        # Normalize whitespace
        norm1 = " ".join(content1.split())
        norm2 = " ".join(content2.split())

        # Use sequence matcher
        matcher = difflib.SequenceMatcher(None, norm1, norm2)
        similarity = matcher.ratio()

        # Consider similar if > 95% match
        return similarity > 0.95

    def _save_patch_to_history(self, patch: DocumentationPatch):
        """Save patch to history for audit trail."""
        self.patch_history.append(patch)

        # Also save to disk for persistence
        history_file = self.workspace_dir / f"patch_{patch.patch_id}.json"
        with open(history_file, "w") as f:
            json.dump(
                {
                    "patch_id": patch.patch_id,
                    "action": patch.action.value,
                    "file_path": patch.file_path,
                    "applied": patch.applied,
                    "metadata": {
                        "timestamp": patch.metadata.timestamp,
                        "author": patch.metadata.author,
                        "confidence": patch.metadata.confidence,
                    },
                },
                f,
                indent=2,
            )

    def load_patch_history(self) -> List[Dict[str, Any]]:
        """Load patch history from disk."""
        history = []

        for history_file in self.workspace_dir.glob("patch_*.json"):
            try:
                with open(history_file, "r") as f:
                    history.append(json.load(f))
            except Exception as e:
                logger.error(f"Error loading patch history from {history_file}: {e}")

        return history
