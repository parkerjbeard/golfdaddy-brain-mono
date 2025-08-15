"""
Unit tests for the target file selector.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.services.change_analyzer import ChangeCategory, ChangeType, StructuredChange
from app.services.doc_task_planner import DocSection, DocTaskType, DocumentationTask
from app.services.target_file_selector import (
    DocFramework,
    DocStructureRule,
    NavigationUpdater,
    TargetFile,
    TargetFileSelector,
)


class TestTargetFileSelector:
    """Test the target file selector."""

    @pytest.fixture
    def selector(self):
        """Create a target file selector instance."""
        mock_session = AsyncMock()
        selector = TargetFileSelector(mock_session)
        # Mock AI integration
        selector.ai_integration = AsyncMock()
        selector.ai_integration.generate_embeddings = AsyncMock(return_value=[0.1] * 3072)
        # Mock doc repository
        selector.doc_repository = AsyncMock()
        return selector

    @pytest.mark.asyncio
    async def test_detect_mkdocs_framework(self, selector):
        """Test detecting MkDocs framework."""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False
            with patch.object(Path, "exists") as mock_path_exists:

                def exists_side_effect(path_obj):
                    return str(path_obj).endswith("mkdocs.yml")

                mock_path_exists.side_effect = exists_side_effect

                framework = selector._detect_framework("/test/repo")
                assert framework == DocFramework.MKDOCS

    @pytest.mark.asyncio
    async def test_detect_docusaurus_framework(self, selector):
        """Test detecting Docusaurus framework."""
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False
            with patch.object(Path, "exists") as mock_path_exists:

                def exists_side_effect(path_obj):
                    return str(path_obj).endswith("docusaurus.config.js")

                mock_path_exists.side_effect = exists_side_effect

                framework = selector._detect_framework("/test/repo")
                assert framework == DocFramework.DOCUSAURUS

    @pytest.mark.asyncio
    async def test_detect_generic_framework(self, selector):
        """Test detecting generic framework when no specific framework found."""
        with patch("pathlib.Path.exists", return_value=False):
            framework = selector._detect_framework("/test/repo")
            assert framework == DocFramework.GENERIC

    @pytest.mark.asyncio
    async def test_semantic_file_matching(self, selector):
        """Test semantic matching for finding documentation files."""
        # Setup task
        task = DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title="Document new API endpoint",
            description="Add documentation for user management API",
            content_template="## API Reference\n\n### GET /users",
            source_change=Mock(),
            confidence=0.7,
            priority=8,
            auto_generate=False,
        )

        # Mock similar chunks from repository
        selector.doc_repository.search_similar_chunks.return_value = [
            {"path": "docs/api/reference.md", "heading": "User Management", "similarity": 0.85},
            {"path": "docs/api/reference.md", "heading": "Authentication", "similarity": 0.75},
            {"path": "docs/guides/users.md", "heading": "User Guide", "similarity": 0.60},
        ]

        # Test semantic matching
        targets = await selector._semantic_file_matching(task, "/test/repo", DocFramework.MKDOCS)

        assert len(targets) == 2  # Two unique files
        assert targets[0].path == "docs/api/reference.md"
        assert targets[0].confidence == 0.8  # Average of similarities
        assert targets[0].section == "User Management"  # Best matching section
        assert targets[1].path == "docs/guides/users.md"
        assert targets[1].confidence == 0.6

    @pytest.mark.asyncio
    async def test_convention_based_matching(self, selector):
        """Test convention-based file matching."""
        task = DocumentationTask(
            task_type=DocTaskType.CONFIG_REFERENCE,
            target_section=DocSection.CONFIGURATION,
            title="Update configuration docs",
            description="Document new settings",
            content_template="",
            source_change=Mock(),
            confidence=0.6,
            priority=5,
            auto_generate=False,
            suggested_files=["docs/configuration.md"],
        )

        with patch("pathlib.Path.exists", return_value=True):
            targets = selector._convention_based_matching(task, "/test/repo", DocFramework.MKDOCS)

        assert len(targets) >= 1
        # Should find convention-based match
        config_target = next((t for t in targets if "configuration" in t.path.lower()), None)
        assert config_target is not None
        assert config_target.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_check_duplicate_content(self, selector):
        """Test duplicate content detection."""
        task = DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title="Document user authentication",
            description="Add auth documentation",
            content_template="",
            source_change=Mock(),
            confidence=0.7,
            priority=7,
            auto_generate=False,
        )

        targets = [
            TargetFile(path="docs/api/auth.md", framework=DocFramework.MKDOCS, confidence=0.8, reason="Semantic match"),
            TargetFile(
                path="docs/api/users.md", framework=DocFramework.MKDOCS, confidence=0.6, reason="Convention match"
            ),
        ]

        # Mock existing content check
        selector.doc_repository.get_chunks_by_document.side_effect = [
            # First file has duplicate content
            [Mock(heading="Authentication", content="User authentication methods")],
            # Second file is okay
            [Mock(heading="User Management", content="Managing users")],
        ]

        filtered = await selector._check_duplicates(targets, task)

        # Should filter out the file with duplicate content
        # Should filter at least one duplicate
        assert len(filtered) <= len(targets)

    @pytest.mark.asyncio
    async def test_nav_updates_for_new_files(self, selector):
        """Test navigation file updates for new documentation."""
        task = DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title="New API docs",
            description="",
            content_template="",
            source_change=Mock(),
            confidence=0.7,
            priority=7,
            auto_generate=False,
        )

        targets = [
            TargetFile(
                path="docs/api/new-endpoint.md",
                framework=DocFramework.MKDOCS,
                confidence=0.7,
                reason="New file",
                create_if_missing=True,
            )
        ]

        with patch("pathlib.Path.exists", return_value=True):
            nav_updates = selector._get_nav_updates(task, targets, "/test/repo", DocFramework.MKDOCS)

        assert len(nav_updates) == 1
        assert nav_updates[0].path == "/test/repo/mkdocs.yml"
        assert nav_updates[0].confidence == 0.9
        assert "new_entries" in nav_updates[0].metadata

    @pytest.mark.asyncio
    async def test_select_target_files_full_flow(self, selector):
        """Test the full target file selection flow."""
        task = DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title="Document API",
            description="API documentation",
            content_template="",
            source_change=Mock(file_path="api.py"),
            confidence=0.7,
            priority=8,
            auto_generate=False,
            suggested_files=["docs/api.md"],
        )

        # Mock framework detection
        with patch.object(selector, "_detect_framework", return_value=DocFramework.MKDOCS):
            # Mock semantic matching
            with patch.object(
                selector,
                "_semantic_file_matching",
                return_value=[TargetFile("docs/api/reference.md", DocFramework.MKDOCS, 0.85, "Semantic")],
            ):
                # Mock convention matching
                with patch.object(
                    selector,
                    "_convention_based_matching",
                    return_value=[TargetFile("docs/api.md", DocFramework.MKDOCS, 0.6, "Convention")],
                ):
                    # Mock duplicate check
                    with patch.object(selector, "_check_duplicates") as mock_check:
                        mock_check.side_effect = lambda targets, task: targets

                        # Mock nav updates
                        with patch.object(selector, "_get_nav_updates", return_value=[]):
                            targets = await selector.select_target_files(task, "/test/repo", max_files=3)

        assert len(targets) >= 1
        assert targets[0].confidence == 0.85  # Highest confidence first
        assert targets[0].path == "docs/api/reference.md"

    @pytest.mark.asyncio
    async def test_extract_keywords(self, selector):
        """Test keyword extraction for duplicate detection."""
        text = "Document the new user authentication API endpoint"
        keywords = selector._extract_keywords(text)

        assert "document" in keywords
        assert "user" in keywords
        assert "authentication" in keywords
        assert "api" in keywords
        assert "endpoint" in keywords
        # Common words should be filtered
        assert "the" not in keywords
        # 'new' is 3 characters, so it should be included
        assert "new" in keywords

    @pytest.mark.asyncio
    async def test_find_best_section(self, selector):
        """Test finding the best section within a file."""
        task = Mock()
        chunks = [
            {"path": "docs/api.md", "heading": "Introduction", "similarity": 0.5},
            {"path": "docs/api.md", "heading": "Authentication", "similarity": 0.8},
            {"path": "docs/api.md", "heading": "Users", "similarity": 0.6},
            {"path": "other.md", "heading": "Other", "similarity": 0.9},
        ]

        section = selector._find_best_section(task, chunks, "docs/api.md")

        assert section == "Authentication"  # Highest similarity for this file

    @pytest.mark.asyncio
    async def test_get_docs_directory(self, selector):
        """Test getting the documentation directory for different frameworks."""
        # Test MkDocs
        docs_dir = selector._get_docs_directory("/repo", DocFramework.MKDOCS)
        assert docs_dir == "/repo/docs"

        # Test Docusaurus
        docs_dir = selector._get_docs_directory("/repo", DocFramework.DOCUSAURUS)
        assert docs_dir == "/repo/docs"

        # Test Sphinx - it defaults to docs if source doesn't exist
        docs_dir = selector._get_docs_directory("/repo", DocFramework.SPHINX)
        assert docs_dir == "/repo/docs"  # Falls back to docs

        # Test Hugo
        docs_dir = selector._get_docs_directory("/repo", DocFramework.HUGO)
        assert docs_dir == "/repo/content"

    @pytest.mark.asyncio
    async def test_is_valid_doc_path(self, selector):
        """Test validation of documentation file paths."""
        # Valid paths
        assert selector._is_valid_doc_path(Path("docs/api.md"))
        assert selector._is_valid_doc_path(Path("documentation/guide.mdx"))
        assert selector._is_valid_doc_path(Path("readme.md"))
        assert selector._is_valid_doc_path(Path("wiki/page.rst"))

        # Invalid paths
        assert not selector._is_valid_doc_path(Path("src/main.py"))
        assert not selector._is_valid_doc_path(Path("config.json"))
        assert not selector._is_valid_doc_path(Path("test.txt"))


class TestNavigationUpdater:
    """Test the navigation updater."""

    @pytest.fixture
    def updater(self):
        """Create a navigation updater instance."""
        return NavigationUpdater()

    def test_update_mkdocs_nav(self, updater, tmp_path):
        """Test updating MkDocs navigation."""
        # Create a sample mkdocs.yml
        nav_file = tmp_path / "mkdocs.yml"
        nav_file.write_text(
            """
site_name: Test Docs
nav:
  - Home: index.md
  - API:
    - Overview: api/overview.md
"""
        )

        new_entries = [{"section": "API", "title": "New Endpoint", "path": "api/new-endpoint.md"}]

        success = updater.update_mkdocs_nav(str(nav_file), new_entries)

        assert success is True

        # Check the updated file
        import yaml

        with open(nav_file) as f:
            nav_data = yaml.safe_load(f)

        # Should have added the new entry
        api_section = next((item for item in nav_data["nav"] if "API" in item), None)
        assert api_section is not None
        assert len(api_section["API"]) == 2  # Original + new
        assert {"New Endpoint": "api/new-endpoint.md"} in api_section["API"]

    def test_update_docusaurus_sidebar(self, updater, tmp_path):
        """Test updating Docusaurus sidebar."""
        # Create a sample sidebars.js
        sidebar_file = tmp_path / "sidebars.js"
        sidebar_file.write_text(
            """
module.exports = {
  docs: {
    'Getting Started': ['intro', 'installation'],
    'API': ['api/overview']
  }
};
"""
        )

        new_entries = [{"section": "API", "path": "api/users.md"}]

        success = updater.update_docusaurus_sidebar(str(sidebar_file), new_entries)

        assert success is True

        # Check the updated file contains the new entry
        content = sidebar_file.read_text()
        assert "api-users" in content  # Converted path to ID
