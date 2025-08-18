"""
Unit tests for the AutoDocClient class.
"""

import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.doc_agent.client import AutoDocClient
from app.models.doc_approval import DocApproval


class TestAutoDocClient:
    """Test cases for AutoDocClient."""

    @pytest.fixture
    def client(self):
        """Create a test client instance."""
        return AutoDocClient(
            openai_api_key="test-key",
            github_token="test-github-token",
            docs_repo="test-owner/test-repo",
            slack_channel="#test-channel",
        )

    @pytest.fixture
    def mock_github(self):
        """Mock GitHub client."""
        with patch("app.doc_agent.client.Github") as mock:
            yield mock

    @pytest.fixture
    def mock_openai(self):
        """Mock OpenAI client."""
        with patch("app.doc_agent.client.AsyncOpenAI") as mock:
            yield mock

    @pytest.fixture
    def mock_slack_service(self):
        """Mock Slack service."""
        with patch("app.doc_agent.client.SlackService") as mock:
            yield mock

    def test_init_validates_required_params(self):
        """Test that initialization validates required parameters."""
        # Missing OpenAI key
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            AutoDocClient(openai_api_key="", github_token="token", docs_repo="repo")

        # Missing GitHub token
        with pytest.raises(ValueError, match="GitHub token is required"):
            AutoDocClient(openai_api_key="key", github_token="", docs_repo="repo")

    def test_get_commit_diff_success(self, client, tmp_path):
        """Test successful commit diff retrieval."""
        # Create a temporary git repo
        repo_path = str(tmp_path)

        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.return_value = "diff --git a/test.md b/test.md\n+Added line"

            diff = client.get_commit_diff(repo_path, "abc123")

            assert diff == "diff --git a/test.md b/test.md\n+Added line"
            mock_subprocess.assert_called_with(["git", "-C", repo_path, "diff", "abc123^", "abc123"], text=True)

    def test_get_commit_diff_handles_errors(self, client):
        """Test commit diff error handling."""
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.side_effect = Exception("Git error")

            diff = client.get_commit_diff("/invalid/path", "abc123")

            assert diff == ""

    @pytest.mark.asyncio
    async def test_analyze_diff_success(self, client):
        """Test successful diff analysis with OpenAI."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Documentation patch content"

        with patch.object(client, "openai") as mock_openai:
            mock_chat = AsyncMock()
            mock_openai.chat = mock_chat
            mock_chat.completions.create = AsyncMock(return_value=mock_response)

            diff = "diff --git a/test.md b/test.md\n+Added line"
            result = await client.analyze_diff(diff)

            assert result == "Documentation patch content"
            mock_chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_diff_handles_empty_diff(self, client):
        """Test analyze_diff with empty diff."""
        result = await client.analyze_diff("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_analyze_diff_handles_openai_error(self, client):
        """Test analyze_diff error handling."""
        with patch.object(client, "openai") as mock_openai:
            mock_chat = AsyncMock()
            mock_openai.chat = mock_chat
            mock_chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            result = await client.analyze_diff("some diff")
            assert result == ""

    @pytest.mark.asyncio
    async def test_propose_via_slack_success(self, client, mock_slack_service):
        """Test successful Slack proposal."""
        # Mock database session
        mock_db = AsyncMock()
        mock_approval = DocApproval(
            id=uuid.uuid4(),
            commit_hash="abc123",
            repository="test-owner/test-repo",
            diff_content="diff content",
            patch_content="patch content",
            slack_channel="#test-channel",
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )

        # Mock Slack service
        mock_slack_instance = Mock()
        mock_slack_instance.send_message = AsyncMock(return_value={"ts": "123.456"})
        client.slack_service = mock_slack_instance

        with patch("app.doc_agent.client.get_db") as mock_get_db:
            mock_get_db.return_value.__aenter__.return_value = mock_db
            mock_db.add = Mock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()

            # Mock UUID generation for predictable ID
            with patch("uuid.uuid4", return_value=mock_approval.id):
                result = await client.propose_via_slack(
                    diff="diff content", patch="patch content", commit_hash="abc123", commit_message="Test commit"
                )

            assert result == str(mock_approval.id)
            mock_slack_instance.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_propose_via_slack_no_slack_service(self, client):
        """Test propose_via_slack when Slack is not configured."""
        client.slack_service = None

        result = await client.propose_via_slack(diff="diff", patch="patch", commit_hash="abc123")

        assert result is None

    def test_apply_patch_success(self, client, mock_github):
        """Test successful patch application and PR creation."""
        # Mock GitHub repo
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_repo.create_pull = Mock(return_value=Mock(html_url="https://github.com/test/pr/1"))

        mock_github_instance = Mock()
        mock_github_instance.get_repo = Mock(return_value=mock_repo)
        client.github = mock_github_instance

        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"

            with patch("subprocess.check_call") as mock_subprocess:
                pr_url = client.apply_patch("patch content", "abc123")

                assert pr_url == "https://github.com/test/pr/1"
                assert mock_subprocess.call_count >= 4  # clone, checkout, apply, push
                mock_repo.create_pull.assert_called_once()

    def test_apply_patch_no_github_client(self, client):
        """Test apply_patch when GitHub client is not configured."""
        client.github = None

        result = client.apply_patch("patch", "abc123")
        assert result is None

    def test_apply_patch_handles_clone_error(self, client, mock_github):
        """Test apply_patch handles git clone errors."""
        mock_repo = Mock()
        mock_github_instance = Mock()
        mock_github_instance.get_repo = Mock(return_value=mock_repo)
        client.github = mock_github_instance

        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"

            with patch("subprocess.check_call") as mock_subprocess:
                mock_subprocess.side_effect = Exception("Clone failed")

                result = client.apply_patch("patch", "abc123")
                assert result is None

    def test_retry_decorator(self):
        """Test the retry mechanism."""
        from app.doc_agent.client import _retry

        call_count = 0

        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        # Should succeed on third attempt
        result = _retry(failing_func, retries=3, initial_delay=0.01)
        assert result == "success"
        assert call_count == 3

        # Should fail if max retries exceeded
        call_count = 0

        def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        with pytest.raises(Exception, match="Always fails"):
            _retry(always_failing_func, retries=2, initial_delay=0.01)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_retry_decorator(self):
        """Test the async retry mechanism."""
        from app.doc_agent.client import _async_retry

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        # Should succeed on third attempt
        result = await _async_retry(failing_func, retries=3, initial_delay=0.01)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_create_and_send_approval_db_error(self, client):
        """Test approval creation with database error."""
        mock_db = AsyncMock()
        mock_db.add = Mock(side_effect=Exception("DB Error"))
        mock_db.rollback = AsyncMock()

        client.slack_service = Mock()

        result = await client._create_and_send_approval(mock_db, "diff", "patch", "abc123", "message", 1, 10, 5)

        assert result is None
        mock_db.rollback.assert_called_once()

    def test_integration_with_real_github_api(self, client):
        """Test integration points with real GitHub API structure."""
        # This test verifies that our mocks match the real API
        from github import Github, GithubException

        # Verify the client creates Github instance correctly
        assert hasattr(client, "github")

        # Verify expected methods exist
        if client.github:
            # These would be the actual methods we use
            expected_methods = ["get_repo"]
            for method in expected_methods:
                assert hasattr(client.github, method) or client.github is None
