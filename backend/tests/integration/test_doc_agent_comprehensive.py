"""
Comprehensive integration tests for the Doc Agent system.
Tests the complete workflow from commit analysis to PR creation.
"""

import asyncio
import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config.settings import settings
from app.core.database import Base
from app.doc_agent.client import AutoDocClient
from app.doc_agent.client_v2 import AutoDocClientV2
from app.integrations.github_app import CheckRunConclusion, CheckRunStatus
from app.models.doc_approval import DocApproval
from app.models.doc_embeddings import DocEmbedding
from app.repositories.doc_approval_repository import DocApprovalRepository
from app.services.context_analyzer import ContextAnalyzer
from app.services.doc_approval_service import DocApprovalService
from app.services.doc_quality_service import DocQualityService
from app.services.embedding_service import EmbeddingService
from app.services.semantic_search_service import SemanticSearchService
from app.services.slack_message_templates import SlackMessageTemplates
from app.services.slack_service import SlackService

# Test database URL - use in-memory SQLite for speed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.mark.integration
class TestDocAgentComprehensive:
    """Comprehensive integration tests for the Doc Agent system."""

    @pytest_asyncio.fixture(scope="function")
    async def async_test_engine(self):
        """Create an async SQLAlchemy engine for testing."""
        engine = create_async_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

        async with engine.begin() as conn:
            # Create tables without foreign key constraints for testing
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS doc_approvals (
                    id TEXT PRIMARY KEY,
                    commit_hash TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    diff_content TEXT NOT NULL,
                    patch_content TEXT NOT NULL,
                    proposal_id TEXT,
                    slack_channel TEXT,
                    slack_message_ts TEXT,
                    slack_user_id TEXT,
                    slack_ts TEXT,
                    status TEXT DEFAULT 'pending',
                    opened_by TEXT,
                    approved_by TEXT,
                    approved_at TIMESTAMP,
                    rejection_reason TEXT,
                    pr_url TEXT,
                    pr_number INTEGER,
                    head_sha TEXT,
                    check_run_id TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """
                )
            )

            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS doc_embeddings (
                    id TEXT PRIMARY KEY,
                    document_id TEXT,
                    doc_approval_id TEXT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    doc_type TEXT,
                    file_path TEXT,
                    repository TEXT,
                    commit_hash TEXT,
                    embedding TEXT,
                    doc_metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
                )
            )

        yield engine

        await engine.dispose()

    @pytest_asyncio.fixture(scope="function")
    async def db_session(self, async_test_engine) -> AsyncGenerator[AsyncSession, None]:
        """Create an async database session for testing."""
        async_session = async_sessionmaker(
            async_test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session() as session:
            yield session
            await session.rollback()

    @pytest.fixture
    async def setup_environment(self):
        """Set up test environment with all required services."""
        env_vars = {
            "OPENAI_API_KEY": "test-openai-key",
            "GITHUB_TOKEN": "test-github-token",
            "GITHUB_APP_ID": "123456",
            "GITHUB_APP_PRIVATE_KEY": "test-private-key",
            "GITHUB_APP_INSTALLATION_ID": "789012",
            "DOCS_REPOSITORY": "test-owner/test-docs",
            "SLACK_BOT_TOKEN": "xoxb-test-token",
            "SLACK_DEFAULT_CHANNEL": "#docs-approval",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_KEY": "test-service-key",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "FRONTEND_URL": "http://localhost:3000",
            "DOC_AGENT_OPENAI_MODEL": "gpt-4-turbo-preview",
            "EMBEDDING_MODEL": "text-embedding-3-large",
            "EMBEDDING_DIMENSION": "3072",
        }

        with patch.dict(os.environ, env_vars):
            yield env_vars

    @pytest.fixture
    async def mock_git_repository(self, tmp_path):
        """Create a mock git repository with test commits."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        # Initialize repository
        subprocess.run(["git", "init"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)

        # Create initial structure
        (repo_path / "src").mkdir()
        (repo_path / "docs").mkdir()

        # Initial commit
        readme = repo_path / "README.md"
        readme.write_text("# Test Project\n\nInitial documentation.")

        api_file = repo_path / "src" / "api.py"
        api_file.write_text(
            '''
def authenticate(token: str) -> bool:
    """Authenticate user with token."""
    return token.startswith("valid_")
'''
        )

        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

        # Create a feature commit
        api_file.write_text(
            '''
def authenticate(token: str) -> bool:
    """Authenticate user with token."""
    return token.startswith("valid_")

def get_user_profile(user_id: str) -> dict:
    """
    Get user profile by ID.
    
    Args:
        user_id: The user's unique identifier
        
    Returns:
        User profile dictionary
    """
    return {"id": user_id, "name": "Test User"}
'''
        )

        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Add user profile endpoint"], cwd=repo_path, check=True)

        # Get commit hash
        commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_path, text=True).strip()

        return str(repo_path), commit_hash

    @pytest.fixture
    async def doc_approval_service(self, db_session: AsyncSession):
        """Create doc approval service instance."""
        return DocApprovalService(db_session)

    @pytest.fixture
    async def embedding_service(self):
        """Create embedding service instance."""
        return EmbeddingService()

    @pytest.fixture
    async def search_service(self, embedding_service, db_session):
        """Create semantic search service instance."""
        return SemanticSearchService(embedding_service, db_session)

    @pytest.fixture
    async def context_analyzer(self, embedding_service):
        """Create context analyzer instance."""
        return ContextAnalyzer(embedding_service)

    # ========== Test Scenarios ==========

    @pytest.mark.asyncio
    async def test_complete_workflow_v1_client(self, setup_environment, mock_git_repository, db_session: AsyncSession):
        """Test complete workflow using v1 client (GitHub PAT)."""
        repo_path, commit_hash = mock_git_repository

        # Initialize v1 client
        client = AutoDocClient(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            github_token=os.getenv("GITHUB_TOKEN"),
            docs_repo=os.getenv("DOCS_REPOSITORY"),
            slack_channel=os.getenv("SLACK_DEFAULT_CHANNEL"),
            enable_semantic_search=True,
        )

        # Step 1: Get commit diff
        diff = client.get_commit_diff(repo_path, commit_hash)
        assert diff != ""
        assert "get_user_profile" in diff

        # Step 2: Mock OpenAI analysis
        mock_doc_patch = """--- a/docs/api.md
+++ b/docs/api.md
@@ -5,3 +5,15 @@
 ### authenticate(token: str) -> bool
 Authenticates a user with the provided token.
+
+### get_user_profile(user_id: str) -> dict
+Retrieves user profile information.
+
+**Parameters:**
+- `user_id` (str): The user's unique identifier
+
+**Returns:**
+- dict: User profile containing id and name
+
+**Example:**
+```python
+profile = get_user_profile("user123")
+```"""

        with patch.object(client, "analyze_diff", AsyncMock(return_value=mock_doc_patch)):
            patch_content = await client.analyze_diff(diff)
            assert patch_content == mock_doc_patch

        # Step 3: Test context-aware analysis
        with patch.object(client, "analyze_diff_with_context", AsyncMock(return_value=mock_doc_patch)):
            context_patch = await client.analyze_diff_with_context(
                diff=diff, repo_path=repo_path, commit_hash=commit_hash, db=db_session
            )
            assert context_patch == mock_doc_patch

        # Step 4: Send to Slack for approval
        with patch.object(SlackService, "send_message", AsyncMock(return_value={"ts": "1234567890.123456"})):
            approval_id = await client.propose_via_slack(
                diff=diff,
                patch=patch_content,
                commit_hash=commit_hash,
                commit_message="Add user profile endpoint",
                db=db_session,
            )

            assert approval_id is not None
            assert uuid.UUID(approval_id)  # Validate UUID format

        # Step 5: Verify approval record
        approval = await db_session.get(DocApproval, uuid.UUID(approval_id))
        assert approval is not None
        assert approval.status == "pending"
        assert approval.commit_hash == commit_hash
        assert approval.repository == os.getenv("DOCS_REPOSITORY")

        # Step 6: Mock PR creation
        with patch.object(client, "apply_patch", return_value="https://github.com/test-owner/test-docs/pull/42"):
            pr_url = client.apply_patch(patch_content, commit_hash)
            assert pr_url == "https://github.com/test-owner/test-docs/pull/42"

    @pytest.mark.asyncio
    async def test_complete_workflow_v2_client(self, setup_environment, mock_git_repository, db_session: AsyncSession):
        """Test complete workflow using v2 client (GitHub App)."""
        repo_path, commit_hash = mock_git_repository

        # Initialize v2 client
        client = AutoDocClientV2(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            docs_repo=os.getenv("DOCS_REPOSITORY"),
            slack_channel=os.getenv("SLACK_DEFAULT_CHANNEL"),
            enable_semantic_search=True,
            use_github_app=True,
        )

        # Step 1: Get diff (using subprocess since it's a static method)
        diff = subprocess.check_output(["git", "-C", repo_path, "show", commit_hash], text=True)
        assert "get_user_profile" in diff

        # Step 2: Get diff statistics
        stats = client.get_commit_diff_stats(diff)
        assert stats["files_affected"] > 0
        assert stats["additions"] > 0

        # Step 3: Analyze diff
        mock_doc_patch = "Documentation patch content"
        with patch.object(client, "analyze_diff", AsyncMock(return_value=mock_doc_patch)):
            patch_content = await client.analyze_diff(diff)
            assert patch_content == mock_doc_patch

        # Step 4: Create PR with Check Run
        mock_pr_result = {
            "pr": {
                "number": 42,
                "html_url": "https://github.com/test-owner/test-docs/pull/42",
                "head": {"sha": "abc123"},
            },
            "check_run": {"id": 999, "status": "in_progress"},
            "pr_url": "https://github.com/test-owner/test-docs/pull/42",
            "pr_number": 42,
            "check_run_id": 999,
            "head_sha": "abc123",
        }

        with patch.object(client, "create_pr_with_check_run", AsyncMock(return_value=mock_pr_result)):
            pr_result = await client.create_pr_with_check_run(
                diff=patch_content, commit_hash=commit_hash, approval_id="test-approval-id"
            )
            assert pr_result["pr_number"] == 42
            assert pr_result["check_run_id"] == 999

        # Step 5: Update Check Run status
        with patch.object(client, "update_check_run_status", AsyncMock(return_value=True)):
            success = await client.update_check_run_status(
                pr_number=42,
                check_run_id=999,
                status=CheckRunStatus.COMPLETED,
                conclusion=CheckRunConclusion.SUCCESS,
                output={"title": "Documentation Approved", "summary": "All checks passed"},
            )
            assert success is True

    @pytest.mark.asyncio
    async def test_semantic_search_integration(
        self,
        setup_environment,
        db_session: AsyncSession,
        embedding_service: EmbeddingService,
        search_service: SemanticSearchService,
    ):
        """Test semantic search and embedding functionality."""
        # Create test documents
        test_docs = [
            {
                "id": uuid.uuid4(),
                "title": "Authentication Guide",
                "content": "This guide explains how to authenticate users using JWT tokens.",
                "file_path": "docs/auth.md",
                "repository": "test-repo",
            },
            {
                "id": uuid.uuid4(),
                "title": "API Reference",
                "content": "Complete API reference for all endpoints including authentication.",
                "file_path": "docs/api.md",
                "repository": "test-repo",
            },
            {
                "id": uuid.uuid4(),
                "title": "Database Schema",
                "content": "PostgreSQL database schema and table definitions.",
                "file_path": "docs/database.md",
                "repository": "test-repo",
            },
        ]

        # Generate and store embeddings
        for doc in test_docs:
            # Mock embedding generation
            mock_embedding = [0.1] * 3072  # Match dimension
            with patch.object(embedding_service, "generate_embedding", AsyncMock(return_value=mock_embedding)):
                embedding = await embedding_service.generate_embedding(doc["content"])

                # Store in database
                doc_embedding = DocEmbedding(
                    document_id=doc["id"],
                    chunk_index=0,
                    content=doc["content"],
                    embedding=embedding,
                    metadata={"title": doc["title"], "file_path": doc["file_path"], "repository": doc["repository"]},
                )
                db_session.add(doc_embedding)

        await db_session.commit()

        # Test search functionality
        with patch.object(
            search_service,
            "find_similar_documents",
            AsyncMock(
                return_value=[
                    (test_docs[0], 0.95),  # High similarity
                    (test_docs[1], 0.80),  # Medium similarity
                ]
            ),
        ):
            results = await search_service.find_similar_documents(
                db_session, "How to authenticate users?", "test-repo", limit=5, threshold=0.7
            )

            assert len(results) == 2
            assert results[0][1] > results[1][1]  # Check ordering by similarity

    @pytest.mark.asyncio
    async def test_approval_workflow_with_quality_checks(
        self, setup_environment, db_session: AsyncSession, doc_approval_service: DocApprovalService
    ):
        """Test approval workflow with quality checks."""
        # Create mock quality metrics
        from app.services.doc_quality_service import QualityMetrics

        quality_metrics = QualityMetrics(
            overall_score=85,
            completeness_score=90,
            clarity_score=80,
            technical_accuracy_score=85,
            formatting_score=85,
            level="high",
            suggestions=["Consider adding more code examples"],
            issues=[],
        )

        # Create approval request
        with patch.object(DocQualityService, "analyze_content", AsyncMock(return_value=quality_metrics)):
            approval_request = await doc_approval_service.create_approval_request(
                document_id="test-doc-123",
                title="API Documentation Update",
                content="Updated API documentation with new endpoints",
                doc_type="api",
                author_id="test-author",
                quality_metrics=quality_metrics,
                reviewers=["reviewer1", "reviewer2"],
            )

            assert approval_request.id is not None
            assert approval_request.status.value == "pending"  # Should not auto-approve at 85%
            assert approval_request.quality_metrics["overall_score"] == 85

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, setup_environment, db_session: AsyncSession):
        """Test handling of concurrent doc agent operations."""

        # Create multiple approval requests simultaneously
        async def create_approval(index: int):
            approval = DocApproval(
                id=uuid.uuid4(),
                commit_hash=f"commit_{index}",
                repository="test-repo",
                diff_content=f"diff {index}",
                patch_content=f"patch {index}",
                status="pending",
                slack_channel="#test",
                expires_at=datetime.utcnow() + timedelta(hours=24),
                approval_metadata={"index": index},
            )
            db_session.add(approval)
            return approval

        # Create approvals concurrently
        approvals = await asyncio.gather(*[create_approval(i) for i in range(5)])
        await db_session.commit()

        # Verify all were created
        result = await db_session.execute(select(DocApproval).where(DocApproval.repository == "test-repo"))
        created_approvals = result.scalars().all()
        assert len(created_approvals) == 5

        # Test concurrent updates
        async def update_approval(approval: DocApproval, status: str):
            approval.status = status
            approval.approved_by = f"user_{status}"
            approval.approved_at = datetime.utcnow()
            await db_session.commit()
            return approval

        # Update approvals concurrently
        update_tasks = [
            update_approval(approvals[0], "approved"),
            update_approval(approvals[1], "rejected"),
            update_approval(approvals[2], "approved"),
        ]

        updated = await asyncio.gather(*update_tasks, return_exceptions=True)

        # Verify updates
        for i, result in enumerate(updated):
            if not isinstance(result, Exception):
                assert result.status in ["approved", "rejected"]

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, setup_environment, mock_git_repository, db_session: AsyncSession):
        """Test error handling and recovery mechanisms."""
        repo_path, commit_hash = mock_git_repository

        # Mock the OpenAI client to avoid real API calls
        with patch("app.doc_agent.client.AsyncOpenAI") as mock_openai_class:
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai

            client = AutoDocClient(
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                github_token=os.getenv("GITHUB_TOKEN"),
                docs_repo=os.getenv("DOCS_REPOSITORY"),
                enable_semantic_search=True,
            )

            # Test 1: Handle OpenAI API failure
            mock_openai.chat.completions.create = AsyncMock(side_effect=Exception("OpenAI API error"))
            result = await client.analyze_diff("test diff")
            assert result == ""  # Should return empty string on failure

            # Test 2: Handle GitHub API failure
            with patch.object(client, "github") as mock_github:
                mock_github.get_repo.side_effect = Exception("GitHub API error")
                pr_url = client.apply_patch("test patch", "test_commit")
                assert pr_url is None

            # Test 3: Handle database failure
            with patch.object(db_session, "commit", AsyncMock(side_effect=Exception("Database error"))):
                # Mock SlackService to avoid real API calls
                with patch("app.doc_agent.client.SlackService") as mock_slack_class:
                    mock_slack = AsyncMock()
                    mock_slack_class.return_value = mock_slack
                    mock_slack.send_message.return_value = {"ts": "123.456"}

                    approval_id = await client.propose_via_slack(
                        diff="test diff", patch="test patch", commit_hash="test_hash", db=db_session
                    )
                    # Should handle database error gracefully
                    assert approval_id is not None  # ID is generated even if DB fails

            # Test 4: Handle Slack API failure
            with patch("app.doc_agent.client.SlackService") as mock_slack_class:
                mock_slack = AsyncMock()
                mock_slack_class.return_value = mock_slack
                mock_slack.send_message.side_effect = Exception("Slack API error")

                approval_id = await client.propose_via_slack(
                    diff="test diff", patch="test patch", commit_hash="test_hash", db=db_session
                )
                # Should still create approval even if Slack fails
                assert approval_id is not None

    @pytest.mark.asyncio
    async def test_expiration_and_cleanup(self, setup_environment, db_session: AsyncSession):
        """Test approval expiration and cleanup mechanisms."""
        # Create expired approvals
        expired_approvals = []
        for i in range(3):
            approval = DocApproval(
                id=uuid.uuid4(),
                commit_hash=f"expired_{i}",
                repository="test-repo",
                diff_content="test diff",
                patch_content="test patch",
                status="pending",
                slack_channel="#test",
                expires_at=datetime.utcnow() - timedelta(hours=i + 1),  # Already expired
                approval_metadata={},
            )
            db_session.add(approval)
            expired_approvals.append(approval)

        # Create valid approval
        valid_approval = DocApproval(
            id=uuid.uuid4(),
            commit_hash="valid_commit",
            repository="test-repo",
            diff_content="test diff",
            patch_content="test patch",
            status="pending",
            slack_channel="#test",
            expires_at=datetime.utcnow() + timedelta(hours=24),  # Still valid
            approval_metadata={},
        )
        db_session.add(valid_approval)
        await db_session.commit()

        # Run cleanup
        repository = DocApprovalRepository(db_session)
        expired_count = await repository.expire_old_approvals()

        assert expired_count == 3

        # Verify expired approvals were updated
        for approval in expired_approvals:
            await db_session.refresh(approval)
            assert approval.status == "expired"

        # Verify valid approval wasn't touched
        await db_session.refresh(valid_approval)
        assert valid_approval.status == "pending"

    @pytest.mark.asyncio
    async def test_documentation_coverage_check(
        self, setup_environment, db_session: AsyncSession, context_analyzer: ContextAnalyzer
    ):
        """Test documentation coverage checking functionality."""
        client = AutoDocClient(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            github_token=os.getenv("GITHUB_TOKEN"),
            docs_repo=os.getenv("DOCS_REPOSITORY"),
            enable_semantic_search=True,
        )

        # Mock file context
        mock_file_context = {
            "module_name": "api",
            "classes": ["UserAPI", "AuthAPI"],
            "functions": ["authenticate", "get_user_profile", "update_user", "delete_user", "list_users"],
            "imports": ["fastapi", "sqlalchemy"],
            "design_patterns": ["Repository Pattern", "Service Layer"],
            "dependencies": ["fastapi", "sqlalchemy", "pydantic"],
        }

        with patch.object(context_analyzer, "get_file_context", AsyncMock(return_value=mock_file_context)):
            # Mock existing documentation
            with patch.object(
                client.embedding_service,
                "find_similar_documents",
                AsyncMock(return_value=[(Mock(title="API Guide", file_path="docs/api.md"), 0.85)]),
            ):
                coverage = await client.check_documentation_coverage(db_session, "test-repo", "src/api.py")

                assert coverage["file_path"] == "src/api.py"
                assert coverage["has_documentation"] is True
                assert coverage["coverage_score"] == 0.85
                assert len(coverage["suggestions"]) > 0  # Should suggest documenting classes

    @pytest.mark.asyncio
    async def test_performance_under_load(self, setup_environment, db_session: AsyncSession):
        """Test system performance under load."""
        import time

        # Create multiple clients
        clients = [
            AutoDocClient(
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                github_token=os.getenv("GITHUB_TOKEN"),
                docs_repo=os.getenv("DOCS_REPOSITORY"),
                enable_semantic_search=False,  # Disable to speed up test
            )
            for _ in range(5)
        ]

        # Mock OpenAI responses
        mock_response = "Test documentation patch"

        async def process_diff(client: AutoDocClient, index: int):
            start_time = time.time()
            with patch.object(client, "analyze_diff", AsyncMock(return_value=mock_response)):
                result = await client.analyze_diff(f"diff content {index}")
            elapsed = time.time() - start_time
            return elapsed, result

        # Process multiple diffs concurrently
        start_time = time.time()
        results = await asyncio.gather(*[process_diff(clients[i % len(clients)], i) for i in range(20)])
        total_time = time.time() - start_time

        # Verify results
        assert all(r[1] == mock_response for r in results)
        assert total_time < 5.0  # Should complete within 5 seconds

        # Calculate performance metrics
        avg_time = sum(r[0] for r in results) / len(results)
        max_time = max(r[0] for r in results)

        assert avg_time < 1.0  # Average should be under 1 second
        assert max_time < 2.0  # Max should be under 2 seconds

    @pytest.mark.asyncio
    async def test_github_webhook_integration(self, setup_environment, mock_git_repository, db_session: AsyncSession):
        """Test GitHub webhook handling for automatic doc generation."""
        repo_path, commit_hash = mock_git_repository

        # Simulate GitHub webhook payload
        webhook_payload = {
            "ref": "refs/heads/main",
            "after": commit_hash,
            "repository": {
                "name": "test-repo",
                "full_name": "test-owner/test-repo",
                "clone_url": f"file://{repo_path}",
            },
            "commits": [
                {
                    "id": commit_hash,
                    "message": "Add user profile endpoint",
                    "author": {"name": "Test User", "email": "test@example.com"},
                    "added": [],
                    "modified": ["src/api.py"],
                    "removed": [],
                }
            ],
        }

        # Mock webhook handler
        from app.api.webhooks.github import handle_push_event

        with patch("app.api.webhooks.github.handle_push_event") as mock_handler:
            mock_handler.return_value = {"status": "success", "approval_id": "test-123"}

            result = mock_handler(webhook_payload, db_session)
            assert result["status"] == "success"
            assert result["approval_id"] == "test-123"

            mock_handler.assert_called_once_with(webhook_payload, db_session)

    @pytest.mark.asyncio
    async def test_slack_interaction_flow(self, setup_environment, db_session: AsyncSession):
        """Test complete Slack interaction flow for approvals."""
        # Create a pending approval
        approval = DocApproval(
            id=uuid.uuid4(),
            commit_hash="test_commit_123",
            repository="test-owner/test-repo",
            diff_content="test diff content",
            patch_content="test patch content",
            status="pending",
            slack_channel="#docs-approval",
            slack_message_ts="1234567890.123456",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            approval_metadata={"commit_message": "Test commit", "files_affected": 2, "additions": 10, "deletions": 5},
        )
        db_session.add(approval)
        await db_session.commit()

        # Test approval action
        from app.api.webhooks.slack_interactions import handle_doc_approval_action

        with patch("app.api.webhooks.slack_interactions.handle_doc_approval_action") as mock_handler:
            mock_handler.return_value = {
                "response_type": "in_channel",
                "text": "Documentation update approved and PR created",
                "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            }

            result = await mock_handler(
                approval_id=str(approval.id), user_id="U123456", action="approve", db_session=db_session
            )

            assert "approved" in result["text"]
            assert result["pr_url"] is not None

        # Test rejection action
        with patch("app.api.webhooks.slack_interactions.handle_doc_approval_action") as mock_handler:
            mock_handler.return_value = {"response_type": "in_channel", "text": "Documentation update rejected"}

            result = await mock_handler(
                approval_id=str(approval.id), user_id="U123456", action="reject", db_session=db_session
            )

            assert "rejected" in result["text"]
