"""
Integration tests for the documentation planning engine.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.services.change_analyzer import ChangeAnalyzer
from app.services.doc_task_planner import DocumentationTaskPlanner
from app.services.target_file_selector import TargetFileSelector


class TestDocPlanningIntegration:
    """Integration tests for the documentation planning pipeline."""

    @pytest.fixture
    async def test_session(self):
        """Create a test database session."""
        # Use in-memory SQLite for testing
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            yield session

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_full_planning_pipeline(self, test_session):
        """Test the full documentation planning pipeline."""
        # Sample git diff with various changes
        diff = """diff --git a/api/users.py b/api/users.py
index 1234567..abcdefg 100644
--- a/api/users.py
+++ b/api/users.py
@@ -1,10 +1,20 @@
 from fastapi import APIRouter, HTTPException
 from typing import List, Optional
 
 router = APIRouter()
 
+@router.get("/users")
+async def list_users(limit: int = 10, offset: int = 0) -> List[dict]:
+    \"\"\"List all users with pagination.\"\"\"
+    # Implementation here
+    return []
+
+@router.post("/users")
+async def create_user(user_data: dict) -> dict:
+    \"\"\"Create a new user.\"\"\"
+    # Implementation here
+    return user_data
+
 @router.get("/users/{user_id}")
-async def get_user(user_id: int):
-    # Old implementation
-    return {"id": user_id}
+async def get_user(user_id: int) -> dict:
+    \"\"\"Get a specific user by ID.\"\"\"
+    # New implementation with better error handling
+    if user_id < 0:
+        raise HTTPException(status_code=400, detail="Invalid user ID")
+    return {"id": user_id, "name": "User"}

diff --git a/config/settings.py b/config/settings.py
index 2345678..bcdefgh 100644
--- a/config/settings.py
+++ b/config/settings.py
@@ -1,5 +1,8 @@
 import os
 
-DEBUG = True
+DEBUG = False
 DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/db")
+
+# New configuration options
+MAX_CONNECTIONS = 100
+REQUEST_TIMEOUT = 30

diff --git a/migrations/001_add_user_roles.sql b/migrations/001_add_user_roles.sql
new file mode 100644
index 0000000..3456789
--- /dev/null
+++ b/migrations/001_add_user_roles.sql
@@ -0,0 +1,10 @@
+-- Add roles to users table
+ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'user';
+
+-- Create index for role queries
+CREATE INDEX idx_users_role ON users(role);
+
+-- Update existing users
+UPDATE users SET role = 'user' WHERE role IS NULL;
"""

        # Step 1: Analyze the diff
        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        assert len(changes) == 3  # Three files changed

        # Verify API changes detected
        api_change = next((c for c in changes if "users.py" in c.file_path), None)
        assert api_change is not None
        assert len(api_change.endpoints) >= 2  # At least 2 new endpoints
        assert api_change.category.value in ["api_change", "new_feature"]

        # Verify config changes detected
        config_change = next((c for c in changes if "settings.py" in c.file_path), None)
        assert config_change is not None
        assert len(config_change.configs) >= 2  # DEBUG and new configs

        # Verify migration detected
        migration_change = next((c for c in changes if "migrations" in c.file_path), None)
        assert migration_change is not None

        # Step 2: Plan documentation tasks
        planner = DocumentationTaskPlanner()
        tasks = planner.plan_tasks(changes)

        assert len(tasks) > 0  # Should generate tasks

        # Check for API documentation task
        api_task = next((t for t in tasks if t.task_type.value == "api_reference"), None)
        assert api_task is not None
        assert api_task.confidence > 0.5

        # Check for config documentation task
        config_task = next((t for t in tasks if t.task_type.value == "config_reference"), None)
        assert config_task is not None

        # Check for changelog entry
        changelog_task = next((t for t in tasks if t.task_type.value == "changelog_entry"), None)
        assert changelog_task is not None

        # Step 3: Select target files (with mocked AI)
        with patch("app.services.target_file_selector.AIIntegrationV2") as mock_ai:
            mock_ai_instance = AsyncMock()
            mock_ai_instance.generate_embeddings.return_value = [0.1] * 3072
            mock_ai.return_value = mock_ai_instance

            selector = TargetFileSelector(test_session)
            selector.ai_integration = mock_ai_instance

            # Mock repository search
            selector.doc_repository.search_similar_chunks = AsyncMock(
                return_value=[
                    {"path": "docs/api/reference.md", "heading": "API Reference", "similarity": 0.8},
                    {"path": "docs/configuration.md", "heading": "Configuration", "similarity": 0.7},
                ]
            )
            selector.doc_repository.get_chunks_by_document = AsyncMock(return_value=[])

            # Create temporary docs structure
            with tempfile.TemporaryDirectory() as temp_dir:
                docs_dir = Path(temp_dir) / "docs"
                docs_dir.mkdir()
                (docs_dir / "api").mkdir()
                (temp_dir / "mkdocs.yml").touch()

                # Select files for API task
                api_targets = await selector.select_target_files(api_task, temp_dir, max_files=3)

                assert len(api_targets) > 0
                # Should find or suggest API documentation file
                assert any("api" in t.path.lower() for t in api_targets)

    @pytest.mark.asyncio
    async def test_breaking_change_planning(self, test_session):
        """Test planning for breaking changes."""
        # Diff with breaking changes
        diff = """diff --git a/api/auth.py b/api/auth.py
index 1234567..abcdefg 100644
--- a/api/auth.py
+++ b/api/auth.py
@@ -1,10 +1,8 @@
 from fastapi import APIRouter
 
 router = APIRouter()
 
-@router.post("/login")
-async def login(username: str, password: str):
-    # BREAKING CHANGE: Removed old login endpoint
-    pass
+# Login endpoint removed - use /auth/token instead
+
+@router.post("/auth/token")
+async def get_token(credentials: dict):
+    \"\"\"New authentication endpoint.\"\"\"
+    return {"access_token": "..."}
"""

        # Analyze and plan
        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        planner = DocumentationTaskPlanner()
        tasks = planner.plan_tasks(changes)

        # Should identify breaking change
        breaking_change = changes[0]
        assert len(breaking_change.breaking_changes) > 0
        assert breaking_change.category.value == "breaking_change"

        # Should create high-priority upgrade guide
        upgrade_task = next((t for t in tasks if t.task_type.value == "upgrade_guide"), None)
        assert upgrade_task is not None
        assert upgrade_task.priority == 10  # Highest priority
        assert upgrade_task.confidence >= 0.9  # High confidence
        assert not upgrade_task.auto_generate  # Requires manual review

    @pytest.mark.asyncio
    async def test_framework_specific_targeting(self, test_session):
        """Test framework-specific file targeting."""
        # Mock AI
        with patch("app.services.target_file_selector.AIIntegrationV2") as mock_ai:
            mock_ai_instance = AsyncMock()
            mock_ai_instance.generate_embeddings.return_value = [0.1] * 3072
            mock_ai.return_value = mock_ai_instance

            selector = TargetFileSelector(test_session)
            selector.ai_integration = mock_ai_instance
            selector.doc_repository.search_similar_chunks = AsyncMock(return_value=[])
            selector.doc_repository.get_chunks_by_document = AsyncMock(return_value=[])

            # Test with MkDocs structure
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create MkDocs structure
                Path(temp_dir, "mkdocs.yml").write_text(
                    """
site_name: Test Docs
nav:
  - Home: index.md
  - API: api/reference.md
"""
                )
                docs_dir = Path(temp_dir) / "docs"
                docs_dir.mkdir()
                (docs_dir / "api").mkdir()
                (docs_dir / "api" / "reference.md").touch()

                # Create a task
                task = Mock(
                    task_type=Mock(value="api_reference"),
                    target_section=Mock(value="api_documentation"),
                    title="Test API",
                    description="Test",
                    content_template="",
                    suggested_files=[],
                )

                targets = await selector.select_target_files(task, temp_dir)

                # Should detect MkDocs and suggest appropriate structure
                assert any("docs/api" in str(t.path) for t in targets)

                # Check for nav file update if new files
                new_file_targets = [t for t in targets if t.create_if_missing]
                if new_file_targets:
                    nav_targets = [t for t in targets if "mkdocs.yml" in str(t.path)]
                    assert len(nav_targets) > 0

    @pytest.mark.asyncio
    async def test_confidence_based_automation(self, test_session):
        """Test that high-confidence tasks can be automated."""
        # Simple, clear change that should have high confidence
        diff = """diff --git a/CHANGELOG.md b/CHANGELOG.md
index 1234567..abcdefg 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -1,3 +1,8 @@
 # Changelog
 
+## [1.2.0] - 2024-01-15
+
+### Added
+- New user management API endpoints
+
 ## [1.1.0] - 2024-01-01"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        planner = DocumentationTaskPlanner()
        tasks = planner.plan_tasks(changes)

        # Changelog updates should have high confidence
        changelog_tasks = [t for t in tasks if t.task_type.value == "changelog_entry"]
        if changelog_tasks:
            task = changelog_tasks[0]
            assert task.confidence >= 0.8
            assert task.auto_generate is True  # Can be automated

    @pytest.mark.asyncio
    async def test_duplicate_prevention(self, test_session):
        """Test that duplicate documentation is prevented."""
        with patch("app.services.target_file_selector.AIIntegrationV2") as mock_ai:
            mock_ai_instance = AsyncMock()
            mock_ai_instance.generate_embeddings.return_value = [0.1] * 3072
            mock_ai.return_value = mock_ai_instance

            selector = TargetFileSelector(test_session)
            selector.ai_integration = mock_ai_instance

            # Mock finding similar content
            selector.doc_repository.search_similar_chunks = AsyncMock(
                return_value=[{"path": "docs/api.md", "heading": "User API", "similarity": 0.9}]
            )

            # Mock existing chunks with duplicate content
            selector.doc_repository.get_chunks_by_document = AsyncMock(
                return_value=[Mock(heading="User Management API", content="API for managing users")]
            )

            # Create task for user API (should be detected as duplicate)
            task = Mock(
                task_type=Mock(value="api_reference"),
                target_section=Mock(value="api_documentation"),
                title="Document user management API",
                description="Add user API documentation",
                content_template="",
                suggested_files=["docs/api.md"],
            )

            targets = await selector.select_target_files(task, "/test/repo")

            # Should filter out files with duplicate content
            # or return empty if all are duplicates
            for target in targets:
                if target.path == "docs/api.md":
                    # If this file is returned, it should be for updating, not creating duplicate
                    assert target.reason != "Semantic match"

    @pytest.mark.asyncio
    async def test_multi_file_change_coordination(self, test_session):
        """Test coordinating documentation across multiple file changes."""
        # Complex diff with related changes across multiple files
        diff = """diff --git a/api/v2/users.py b/api/v2/users.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/api/v2/users.py
@@ -0,0 +1,15 @@
+from fastapi import APIRouter
+
+router = APIRouter(prefix="/v2")
+
+@router.get("/users")
+async def list_users_v2():
+    return []

diff --git a/api/v1/users.py b/api/v1/users.py
index 1234567..abcdefg 100644
--- a/api/v1/users.py
+++ b/api/v1/users.py
@@ -1,5 +1,7 @@
+# DEPRECATED: Use v2 API instead
+import warnings
+
 @router.get("/users")
 async def list_users():
-    return []
+    warnings.warn("This endpoint is deprecated, use v2", DeprecationWarning)
+    return []

diff --git a/docs/api/migration.md b/docs/api/migration.md
new file mode 100644
index 0000000..2345678
--- /dev/null
+++ b/docs/api/migration.md
@@ -0,0 +1,5 @@
+# API Migration Guide
+
+## V1 to V2 Migration
+
+The v1 API is now deprecated. Please migrate to v2.
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        planner = DocumentationTaskPlanner()
        tasks = planner.plan_tasks(changes)

        # Should coordinate documentation across v1 deprecation and v2 addition
        assert len(changes) >= 2  # Multiple files changed

        # Should create tasks for:
        # 1. New v2 API documentation
        # 2. Deprecation notice for v1
        # 3. Migration guide updates

        task_types = [t.task_type.value for t in tasks]

        # Should have API documentation tasks
        assert "api_reference" in task_types

        # Should recognize the migration documentation is already being added
        # and possibly skip or merge related tasks
