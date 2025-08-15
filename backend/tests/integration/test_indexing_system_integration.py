"""
Integration tests for the code and documentation indexing system.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.code_symbols import CodeSymbol
from app.models.doc_chunks import DocChunk
from app.services.code_indexer import CodeIndexer
from app.services.context_builder import ContextBuilder
from app.services.doc_indexer import DocIndexer


@pytest.fixture
async def test_session():
    """Create a test database session."""
    # Use in-memory SQLite for testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


class TestCodeIndexerIntegration:
    """Integration tests for code indexing."""

    @pytest.mark.asyncio
    @patch("app.services.code_indexer.AIIntegrationV2")
    async def test_index_python_file(self, mock_ai, test_session):
        """Test indexing a Python file."""
        # Mock AI integration
        mock_ai_instance = AsyncMock()
        mock_ai_instance.generate_embeddings.return_value = [0.1] * 3072
        mock_ai.return_value = mock_ai_instance

        indexer = CodeIndexer(test_session)
        indexer.ai_integration = mock_ai_instance

        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                '''
def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two numbers."""
    return a + b

class Calculator:
    """A simple calculator class."""
    
    def multiply(self, x: float, y: float) -> float:
        """Multiply two numbers."""
        return x * y
'''
            )
            temp_path = Path(f.name)

        try:
            # Index the file
            symbols = await indexer.index_file("test-repo", temp_path, incremental=False)

            # Verify symbols were indexed
            assert len(symbols) >= 3  # function, class, method

            # Check function
            func_symbol = next((s for s in symbols if s.name == "calculate_sum"), None)
            assert func_symbol is not None
            assert func_symbol.kind == "function"

            # Check class
            class_symbol = next((s for s in symbols if s.name == "Calculator"), None)
            assert class_symbol is not None
            assert class_symbol.kind == "class"

            # Verify embeddings were generated
            assert mock_ai_instance.generate_embeddings.call_count >= 3

        finally:
            temp_path.unlink()

    @pytest.mark.asyncio
    @patch("app.services.code_indexer.AIIntegrationV2")
    async def test_index_directory(self, mock_ai, test_session):
        """Test indexing a directory of code files."""
        # Mock AI integration
        mock_ai_instance = AsyncMock()
        mock_ai_instance.generate_embeddings.return_value = [0.1] * 3072
        mock_ai.return_value = mock_ai_instance

        indexer = CodeIndexer(test_session)
        indexer.ai_integration = mock_ai_instance

        # Create a temporary directory with code files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create Python file
            (temp_path / "module1.py").write_text(
                '''
def function1():
    """First function."""
    pass
'''
            )

            # Create another Python file
            (temp_path / "module2.py").write_text(
                '''
class MyClass:
    """Test class."""
    pass
'''
            )

            # Index the directory
            stats = await indexer.index_directory("test-repo", temp_path, extensions=[".py"], incremental=False)

            # Verify statistics
            assert stats["files_processed"] == 2
            assert stats["symbols_indexed"] >= 2
            assert stats["errors"] == 0

    @pytest.mark.asyncio
    @patch("app.services.code_indexer.AIIntegrationV2")
    async def test_incremental_indexing(self, mock_ai, test_session):
        """Test incremental indexing of changed files."""
        # Mock AI integration
        mock_ai_instance = AsyncMock()
        mock_ai_instance.generate_embeddings.return_value = [0.1] * 3072
        mock_ai.return_value = mock_ai_instance

        indexer = CodeIndexer(test_session)
        indexer.ai_integration = mock_ai_instance

        # Simulate commit changes
        changed_files = [
            {"path": "new_file.py", "change_type": "added"},
            {"path": "modified_file.py", "change_type": "modified"},
            {"path": "deleted_file.py", "change_type": "deleted"},
        ]

        # Mock file reading for added/modified files
        with patch.object(indexer, "index_file") as mock_index_file:
            mock_index_file.return_value = [Mock(spec=CodeSymbol)]

            with patch.object(indexer.repository, "delete_file_symbols") as mock_delete:
                mock_delete.return_value = 2

                stats = await indexer.index_commit_changes("test-repo", changed_files)

                # Verify statistics
                assert stats["files_processed"] == 2  # added + modified
                assert stats["files_deleted"] == 1
                assert mock_index_file.call_count == 2
                assert mock_delete.call_count == 1


class TestDocIndexerIntegration:
    """Integration tests for documentation indexing."""

    @pytest.mark.asyncio
    @patch("app.services.doc_indexer.AIIntegrationV2")
    async def test_index_markdown_file(self, mock_ai, test_session):
        """Test indexing a Markdown file."""
        # Mock AI integration
        mock_ai_instance = AsyncMock()
        mock_ai_instance.generate_embeddings.return_value = [0.1] * 3072
        mock_ai.return_value = mock_ai_instance

        indexer = DocIndexer(test_session)
        indexer.ai_integration = mock_ai_instance

        # Create a temporary Markdown file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """---
title: API Documentation
version: 1.0
---

# Introduction

This is the API documentation.

## Authentication

Use API keys for authentication.

### Getting Started

Follow these steps to get started.
"""
            )
            temp_path = Path(f.name)

        try:
            # Index the file
            front_matter, chunks = await indexer.index_file("test-repo", temp_path, incremental=False)

            # Verify front matter
            assert front_matter["title"] == "API Documentation"
            assert front_matter["version"] == 1.0

            # Verify chunks were indexed
            assert len(chunks) >= 3

            # Check headings
            intro_chunk = next((c for c in chunks if c.heading == "Introduction"), None)
            assert intro_chunk is not None

            auth_chunk = next((c for c in chunks if c.heading == "Authentication"), None)
            assert auth_chunk is not None

            # Verify embeddings were generated
            assert mock_ai_instance.generate_embeddings.call_count >= 3

        finally:
            temp_path.unlink()

    @pytest.mark.asyncio
    @patch("app.services.doc_indexer.AIIntegrationV2")
    async def test_search_similar_sections(self, mock_ai, test_session):
        """Test searching for similar documentation sections."""
        # Mock AI integration
        mock_ai_instance = AsyncMock()
        mock_ai_instance.generate_embeddings.return_value = [0.2] * 3072
        mock_ai.return_value = mock_ai_instance

        indexer = DocIndexer(test_session)
        indexer.ai_integration = mock_ai_instance

        # Mock repository search
        with patch.object(indexer.repository, "search_similar_chunks") as mock_search:
            mock_search.return_value = [
                {"id": "chunk1", "heading": "Authentication", "content": "Authentication docs", "similarity": 0.85},
                {"id": "chunk2", "heading": "Authorization", "content": "Authorization docs", "similarity": 0.75},
            ]

            # Search for similar sections
            results = await indexer.search_similar_sections("test-repo", "How to authenticate?", limit=5)

            # Verify results
            assert len(results) == 2
            assert results[0]["similarity"] == 0.85
            assert results[0]["heading"] == "Authentication"


class TestContextBuilderIntegration:
    """Integration tests for context building."""

    @pytest.mark.asyncio
    @patch("app.services.context_builder.AIIntegrationV2")
    async def test_build_change_context(self, mock_ai, test_session):
        """Test building context for a code change."""
        # Mock AI integration
        mock_ai_instance = AsyncMock()
        mock_ai_instance.generate_embeddings.return_value = [0.1] * 3072
        mock_ai.return_value = mock_ai_instance

        builder = ContextBuilder(test_session)
        builder.ai_integration = mock_ai_instance

        # Sample diff
        diff = '''diff --git a/api.py b/api.py
index 1234567..abcdefg 100644
--- a/api.py
+++ b/api.py
@@ -10,6 +10,10 @@ class API:
     def get_users(self):
         return self.users
     
+    def add_user(self, user):
+        """Add a new user."""
+        self.users.append(user)
+        return user
'''

        # Mock repository methods
        with patch.object(builder.code_repository, "get_symbols_by_file") as mock_get_symbols:
            mock_get_symbols.return_value = [
                Mock(
                    name="API",
                    kind="class",
                    path="api.py",
                    sig="class API",
                    docstring="API class",
                    lang="python",
                    span={"start": {"line": 5}, "end": {"line": 20}},
                )
            ]

            with patch.object(builder.code_repository, "search_similar_symbols") as mock_search_code:
                mock_search_code.return_value = []

                with patch.object(builder.doc_repository, "search_similar_chunks") as mock_search_docs:
                    mock_search_docs.return_value = []

                    # Build context
                    context = await builder.build_change_context("test-repo", diff, context_lines=3)

                    # Verify context
                    assert context.changed_symbols is not None
                    assert len(context.changed_symbols) >= 1
                    assert context.diff_context["stats"]["additions"] > 0
                    assert "add_user" in diff

    @pytest.mark.asyncio
    @patch("app.services.context_builder.AIIntegrationV2")
    async def test_context_caching(self, mock_ai, test_session):
        """Test that context is cached properly."""
        # Mock AI integration
        mock_ai_instance = AsyncMock()
        mock_ai_instance.generate_embeddings.return_value = [0.1] * 3072
        mock_ai.return_value = mock_ai_instance

        builder = ContextBuilder(test_session, cache_size=10)
        builder.ai_integration = mock_ai_instance

        diff = "diff --git a/test.py b/test.py\n+new line"

        # Mock repository methods
        with patch.object(builder.code_repository, "get_symbols_by_file") as mock_get:
            mock_get.return_value = []

            with patch.object(builder.code_repository, "search_similar_symbols") as mock_search:
                mock_search.return_value = []

                with patch.object(builder.doc_repository, "search_similar_chunks") as mock_docs:
                    mock_docs.return_value = []

                    # First call - should query repositories
                    context1 = await builder.build_change_context("test-repo", diff)
                    assert mock_get.call_count == 1

                    # Second call - should use cache
                    context2 = await builder.build_change_context("test-repo", diff)
                    assert mock_get.call_count == 1  # Not called again

                    # Contexts should be the same object (cached)
                    assert context1 is context2
