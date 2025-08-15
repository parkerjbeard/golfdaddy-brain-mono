"""
Unit tests for the patch generator service.
"""

import tempfile
from pathlib import Path

import pytest

from app.services.patch_generator import DocumentationPatch, PatchAction, PatchGenerator, PatchMetadata, PatchSet


class TestPatchGenerator:
    """Test the patch generator."""

    @pytest.fixture
    def generator(self):
        """Create a patch generator instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PatchGenerator(workspace_dir=Path(tmpdir))
            yield generator

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
            f.write("# Original Content\n\nThis is the original content.")
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_generate_patch_create(self, generator):
        """Test generating a creation patch."""
        patch = generator.generate_patch(
            action=PatchAction.CREATE, file_path="docs/new.md", new_content="# New Document\n\nNew content here."
        )

        assert patch.action == PatchAction.CREATE
        assert patch.file_path == "docs/new.md"
        assert patch.new_content == "# New Document\n\nNew content here."
        assert patch.patch_id is not None
        assert not patch.applied

    def test_generate_patch_update(self, generator):
        """Test generating an update patch."""
        original = "# Original\n\nOriginal content."
        new = "# Updated\n\nUpdated content."

        patch = generator.generate_patch(
            action=PatchAction.UPDATE, file_path="docs/existing.md", original_content=original, new_content=new
        )

        assert patch.action == PatchAction.UPDATE
        assert patch.original_content == original
        assert patch.new_content == new
        assert patch.diff is not None
        assert "Original" in patch.diff
        assert "Updated" in patch.diff

    def test_generate_patch_delete(self, generator):
        """Test generating a deletion patch."""
        patch = generator.generate_patch(
            action=PatchAction.DELETE, file_path="docs/remove.md", original_content="Content to remove"
        )

        assert patch.action == PatchAction.DELETE
        assert patch.file_path == "docs/remove.md"
        assert patch.original_content == "Content to remove"

    def test_generate_patch_set(self, generator):
        """Test generating a patch set."""
        patches_data = [
            {"action": "create", "file_path": "docs/file1.md", "new_content": "Content 1"},
            {"action": "update", "file_path": "docs/file2.md", "original_content": "Old", "new_content": "New"},
        ]

        patch_set = generator.generate_patch_set(patches_data, atomic=True)

        assert len(patch_set.patches) == 2
        assert patch_set.atomic
        assert not patch_set.applied
        assert len(patch_set.rollback_order) == 2
        # Rollback order should be reversed
        assert patch_set.rollback_order[0] == patch_set.patches[1].patch_id
        assert patch_set.rollback_order[1] == patch_set.patches[0].patch_id

    def test_apply_patch_create(self, generator):
        """Test applying a creation patch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "new.md"

            patch = generator.generate_patch(
                action=PatchAction.CREATE, file_path=str(file_path), new_content="# New File\n\nContent"
            )

            success, error = generator.apply_patch(patch)

            assert success
            assert error is None
            assert file_path.exists()
            assert file_path.read_text() == "# New File\n\nContent"
            assert patch.applied

    def test_apply_patch_create_already_exists(self, generator, temp_file):
        """Test applying creation patch when file already exists."""
        patch = generator.generate_patch(action=PatchAction.CREATE, file_path=str(temp_file), new_content="New content")

        success, error = generator.apply_patch(patch)

        assert not success
        assert "already exists" in error
        assert not patch.applied

    def test_apply_patch_update(self, generator, temp_file):
        """Test applying an update patch."""
        original_content = temp_file.read_text()
        new_content = "# Updated Content\n\nThis is updated."

        patch = generator.generate_patch(
            action=PatchAction.UPDATE,
            file_path=str(temp_file),
            original_content=original_content,
            new_content=new_content,
        )

        success, error = generator.apply_patch(patch)

        assert success
        assert error is None
        assert temp_file.read_text() == new_content
        assert patch.applied

    def test_apply_patch_update_content_mismatch(self, generator, temp_file):
        """Test applying update patch with content mismatch."""
        patch = generator.generate_patch(
            action=PatchAction.UPDATE,
            file_path=str(temp_file),
            original_content="Wrong original content",
            new_content="New content",
        )

        success, error = generator.apply_patch(patch)

        assert not success
        assert "doesn't match" in error
        assert not patch.applied

    def test_apply_patch_delete(self, generator, temp_file):
        """Test applying a deletion patch."""
        patch = generator.generate_patch(action=PatchAction.DELETE, file_path=str(temp_file))

        success, error = generator.apply_patch(patch)

        assert success
        assert error is None
        assert not temp_file.exists()
        assert patch.applied
        # Rollback data should contain the deleted content
        assert "content" in patch.rollback_data

    def test_apply_patch_dry_run(self, generator):
        """Test dry run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"

            patch = generator.generate_patch(
                action=PatchAction.CREATE, file_path=str(file_path), new_content="Test content"
            )

            success, error = generator.apply_patch(patch, dry_run=True)

            assert success
            assert error is None
            assert not file_path.exists()  # File should not be created in dry run
            assert not patch.applied  # Patch should not be marked as applied

    def test_apply_patch_set_atomic(self, generator):
        """Test applying an atomic patch set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.md"
            file2 = Path(tmpdir) / "file2.md"

            patches_data = [
                {"action": "create", "file_path": str(file1), "new_content": "Content 1"},
                {"action": "create", "file_path": str(file2), "new_content": "Content 2"},
            ]

            patch_set = generator.generate_patch_set(patches_data, atomic=True)
            success, errors = generator.apply_patch_set(patch_set)

            assert success
            assert len(errors) == 0
            assert file1.exists()
            assert file2.exists()
            assert patch_set.applied

    def test_apply_patch_set_atomic_rollback(self, generator):
        """Test atomic rollback when one patch fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.md"
            existing_file = Path(tmpdir) / "existing.md"
            existing_file.write_text("Existing")

            patches_data = [
                {"action": "create", "file_path": str(file1), "new_content": "Content 1"},
                {"action": "create", "file_path": str(existing_file), "new_content": "Content 2"},  # This will fail
            ]

            patch_set = generator.generate_patch_set(patches_data, atomic=True)
            success, errors = generator.apply_patch_set(patch_set)

            assert not success
            assert len(errors) > 0
            assert not file1.exists()  # Should be rolled back
            assert existing_file.read_text() == "Existing"  # Should remain unchanged
            assert not patch_set.applied

    def test_rollback_patch_create(self, generator):
        """Test rolling back a creation patch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "created.md"

            patch = generator.generate_patch(
                action=PatchAction.CREATE, file_path=str(file_path), new_content="Created content"
            )

            # Apply the patch
            generator.apply_patch(patch)
            assert file_path.exists()

            # Rollback
            success, error = generator.rollback_patch(patch)

            assert success
            assert error is None
            assert not file_path.exists()
            assert not patch.applied

    def test_rollback_patch_update(self, generator, temp_file):
        """Test rolling back an update patch."""
        original_content = temp_file.read_text()

        patch = generator.generate_patch(
            action=PatchAction.UPDATE,
            file_path=str(temp_file),
            original_content=original_content,
            new_content="Updated content",
        )

        # Apply the patch
        generator.apply_patch(patch)
        assert temp_file.read_text() == "Updated content"

        # Rollback
        success, error = generator.rollback_patch(patch)

        assert success
        assert error is None
        assert temp_file.read_text() == original_content
        assert not patch.applied

    def test_rollback_patch_delete(self, generator, temp_file):
        """Test rolling back a deletion patch."""
        original_content = temp_file.read_text()

        patch = generator.generate_patch(action=PatchAction.DELETE, file_path=str(temp_file))

        # Apply the patch
        generator.apply_patch(patch)
        assert not temp_file.exists()

        # Rollback
        success, error = generator.rollback_patch(patch)

        assert success
        assert error is None
        assert temp_file.exists()
        assert temp_file.read_text() == original_content
        assert not patch.applied

    def test_rollback_patch_set(self, generator):
        """Test rolling back an entire patch set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.md"
            file2 = Path(tmpdir) / "file2.md"

            patches_data = [
                {"action": "create", "file_path": str(file1), "new_content": "Content 1"},
                {"action": "create", "file_path": str(file2), "new_content": "Content 2"},
            ]

            patch_set = generator.generate_patch_set(patches_data)

            # Apply
            generator.apply_patch_set(patch_set)
            assert file1.exists()
            assert file2.exists()

            # Rollback
            success, errors = generator.rollback_patch_set(patch_set)

            assert success
            assert len(errors) == 0
            assert not file1.exists()
            assert not file2.exists()
            assert not patch_set.applied

    def test_generate_incremental_patch(self, generator, temp_file):
        """Test generating an incremental patch."""
        # Create base patch
        original_content = temp_file.read_text()
        base_patch = generator.generate_patch(
            action=PatchAction.UPDATE,
            file_path=str(temp_file),
            original_content=original_content,
            new_content="# First Update\n\nFirst update content.",
        )

        # Apply base patch
        generator.apply_patch(base_patch)

        # Generate incremental patch
        incremental_patch = generator.generate_incremental_patch(
            base_patch=base_patch, new_content="# Second Update\n\nSecond update content."
        )

        assert incremental_patch.action == PatchAction.UPDATE
        assert incremental_patch.original_content == "# First Update\n\nFirst update content."
        assert incremental_patch.new_content == "# Second Update\n\nSecond update content."
        assert incremental_patch.metadata.parent_patch_id == base_patch.patch_id

    def test_export_patches(self, generator):
        """Test exporting patches as unified diff."""
        patches = []

        # Create some patches
        patch1 = generator.generate_patch(
            action=PatchAction.CREATE, file_path="docs/new.md", new_content="# New File\nContent"
        )
        patches.append(patch1)

        patch2 = generator.generate_patch(
            action=PatchAction.UPDATE,
            file_path="docs/existing.md",
            original_content="Old content",
            new_content="New content",
        )
        patches.append(patch2)

        # Export all patches
        diff = generator.export_patches()

        assert "docs/new.md" in diff
        assert "docs/existing.md" in diff
        assert "+# New File" in diff
        assert "-Old content" in diff
        assert "+New content" in diff

    def test_patch_history(self, generator):
        """Test patch history tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"

            patch = generator.generate_patch(
                action=PatchAction.CREATE, file_path=str(file_path), new_content="Test content"
            )

            # Apply patch (should save to history)
            generator.apply_patch(patch)

            # Check history
            assert len(generator.patch_history) == 1
            assert generator.patch_history[0].patch_id == patch.patch_id

            # Check saved to disk
            history_file = generator.workspace_dir / f"patch_{patch.patch_id}.json"
            assert history_file.exists()

    def test_load_patch_history(self, generator):
        """Test loading patch history from disk."""
        # Create and apply a patch to save it
        patch = generator.generate_patch(action=PatchAction.CREATE, file_path="test.md", new_content="Content")

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            patch.file_path = str(file_path)
            generator.apply_patch(patch)

        # Load history
        history = generator.load_patch_history()

        assert len(history) > 0
        assert any(h["patch_id"] == patch.patch_id for h in history)
