"""
Simplified integration tests for Doc Agent with complete mocking.
This demonstrates that the doc agent integration works correctly.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.doc_agent.client import AutoDocClient
from app.models.doc_approval import DocApproval


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.mark.integration
class TestDocAgentSimple:
    """Simplified integration tests with complete mocking."""

    @pytest_asyncio.fixture
    async def db_engine(self):
        """Create test database engine."""
        engine = create_async_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        
        async with engine.begin() as conn:
            # Create simplified test tables
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS doc_approvals (
                    id TEXT PRIMARY KEY,
                    commit_hash TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    diff_content TEXT NOT NULL,
                    patch_content TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    pr_url TEXT,
                    metadata TEXT DEFAULT '{}',
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        
        yield engine
        await engine.dispose()

    @pytest_asyncio.fixture
    async def db_session(self, db_engine):
        """Create test database session."""
        SessionLocal = async_sessionmaker(
            db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        async with SessionLocal() as session:
            yield session

    @pytest.mark.asyncio
    async def test_complete_workflow_with_mocks(self, db_session):
        """Test complete workflow with all external services mocked."""
        
        # Mock all external dependencies
        with patch("app.doc_agent.client.AsyncOpenAI") as mock_openai_class, \
             patch("app.doc_agent.client.Github") as mock_github_class, \
             patch("app.doc_agent.client.SlackService") as mock_slack_class:
            
            # Setup OpenAI mock
            mock_openai = Mock()
            mock_openai_class.return_value = mock_openai
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Generated documentation patch"
            # Use AsyncMock for the async method
            mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # Setup GitHub mock
            mock_github = Mock()
            mock_github_class.return_value = mock_github
            mock_repo = Mock()
            mock_repo.default_branch = "main"
            mock_pr = Mock()
            mock_pr.html_url = "https://github.com/test/pr/123"
            mock_repo.create_pull.return_value = mock_pr
            mock_github.get_repo.return_value = mock_repo
            
            # Setup Slack mock
            mock_slack = Mock()
            mock_slack_class.return_value = mock_slack
            mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
            
            # Create client
            client = AutoDocClient(
                openai_api_key="test-key",
                github_token="test-token",
                docs_repo="test-owner/test-repo",
                slack_channel="#test",
                enable_semantic_search=False
            )
            
            # Test 1: Analyze diff
            diff = "diff --git a/test.py b/test.py\n+added line"
            result = await client.analyze_diff(diff)
            assert result == "Generated documentation patch"
            mock_openai.chat.completions.create.assert_called_once()
            
            # Test 2: Create PR
            pr_url = client.apply_patch("patch content", "commit123")
            assert pr_url == "https://github.com/test/pr/123"
            mock_github.get_repo.assert_called_with("test-owner/test-repo")
            
            # Test 3: Send to Slack
            approval_id = await client.propose_via_slack(
                diff=diff,
                patch="patch content",
                commit_hash="commit123",
                commit_message="Test commit",
                db=db_session
            )
            assert approval_id is not None
            assert uuid.UUID(approval_id)  # Validate UUID format
            mock_slack.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling(self, db_session):
        """Test error handling with mocked failures."""
        
        with patch("app.doc_agent.client.AsyncOpenAI") as mock_openai_class, \
             patch("app.doc_agent.client.Github") as mock_github_class, \
             patch("app.doc_agent.client.SlackService") as mock_slack_class:
            
            # Setup mocks to fail
            mock_openai = Mock()
            mock_openai_class.return_value = mock_openai
            mock_openai.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
            
            mock_github = Mock()
            mock_github_class.return_value = mock_github
            mock_github.get_repo.side_effect = Exception("GitHub Error")
            
            mock_slack = Mock()
            mock_slack_class.return_value = mock_slack
            mock_slack.send_message = AsyncMock(side_effect=Exception("Slack Error"))
            
            client = AutoDocClient(
                openai_api_key="test-key",
                github_token="test-token",
                docs_repo="test-owner/test-repo",
                enable_semantic_search=False
            )
            
            # Test OpenAI failure - should return empty string
            result = await client.analyze_diff("test diff")
            assert result == ""
            
            # Test GitHub failure - should return None
            pr_url = client.apply_patch("patch", "commit")
            assert pr_url is None
            
            # Test Slack failure - should still create approval ID
            approval_id = await client.propose_via_slack(
                diff="diff",
                patch="patch",
                commit_hash="hash",
                db=db_session
            )
            assert approval_id is not None  # Should still generate ID

    @pytest.mark.asyncio
    async def test_database_operations(self, db_session):
        """Test database operations work correctly."""
        
        # Create test approval
        approval = DocApproval(
            id=uuid.uuid4(),
            commit_hash="test123",
            repository="test-repo",
            diff_content="test diff",
            patch_content="test patch",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        # Add to database using raw SQL
        await db_session.execute(
            text("""
                INSERT INTO doc_approvals (id, commit_hash, repository, diff_content, 
                                         patch_content, status, expires_at)
                VALUES (:id, :commit_hash, :repository, :diff_content, 
                        :patch_content, :status, :expires_at)
            """),
            {
                "id": str(approval.id),
                "commit_hash": approval.commit_hash,
                "repository": approval.repository,
                "diff_content": approval.diff_content,
                "patch_content": approval.patch_content,
                "status": approval.status,
                "expires_at": approval.expires_at
            }
        )
        await db_session.commit()
        
        # Query back
        result = await db_session.execute(
            text("SELECT * FROM doc_approvals WHERE commit_hash = :hash"),
            {"hash": "test123"}
        )
        row = result.fetchone()
        
        assert row is not None
        assert row.commit_hash == "test123"
        assert row.status == "pending"

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, db_session):
        """Test handling concurrent operations."""
        import asyncio
        
        with patch("app.doc_agent.client.AsyncOpenAI") as mock_openai_class:
            mock_openai = Mock()
            mock_openai_class.return_value = mock_openai
            
            # Make it return quickly
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Quick response"
            mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
            
            client = AutoDocClient(
                openai_api_key="test-key",
                github_token="test-token",
                docs_repo="test-repo",
                enable_semantic_search=False
            )
            
            # Run multiple operations concurrently
            tasks = [
                client.analyze_diff(f"diff {i}")
                for i in range(5)
            ]
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            assert all(r == "Quick response" for r in results)
            assert mock_openai.chat.completions.create.call_count == 5