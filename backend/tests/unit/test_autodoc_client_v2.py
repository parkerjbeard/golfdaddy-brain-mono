"""Unit tests for improved AutoDocClient with GitHub App integration."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.doc_agent.client_v2 import AutoDocClientV2
from app.integrations.github_app import CheckRunConclusion, CheckRunStatus


class TestAutoDocClientV2:
    """Test cases for improved AutoDocClient."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch("app.doc_agent.client_v2.settings") as mock:
            mock.GITHUB_APP_ID = "app_123"
            mock.GITHUB_APP_PRIVATE_KEY = "private_key"
            mock.GITHUB_APP_INSTALLATION_ID = "install_456"
            mock.SLACK_BOT_TOKEN = "slack_token"
            mock.SLACK_DEFAULT_CHANNEL = "#docs"
            mock.DOC_AGENT_OPENAI_MODEL = "gpt-4-turbo"
            mock.FRONTEND_URL = "https://dashboard.example.com"
            yield mock

    @pytest.fixture
    def mock_github_app(self):
        """Mock GitHub App for testing."""
        with patch("app.doc_agent.client_v2.GitHubApp") as mock:
            instance = Mock()
            mock.return_value = instance
            yield instance

    @pytest.fixture
    def mock_openai(self):
        """Mock OpenAI client for testing."""
        with patch("app.doc_agent.client_v2.AsyncOpenAI") as mock:
            instance = AsyncMock()
            mock.return_value = instance
            yield instance

    @pytest.fixture
    async def client(self, mock_settings, mock_github_app, mock_openai):
        """Create AutoDocClientV2 instance for testing."""
        return AutoDocClientV2(openai_api_key="test_key", docs_repo="owner/repo", use_github_app=True)

    def test_init_with_github_app(self, mock_settings, mock_github_app):
        """Test initialization with GitHub App."""
        client = AutoDocClientV2(openai_api_key="test_key", docs_repo="owner/repo", use_github_app=True)

        assert client.use_github_app is True
        assert client.github_app is not None
        assert client.docs_repo == "owner/repo"
        mock_github_app.assert_called_once()

    def test_init_with_pat(self, mock_settings):
        """Test initialization with GitHub PAT."""
        with patch("app.doc_agent.client_v2.Github") as mock_github:
            client = AutoDocClientV2(
                openai_api_key="test_key", github_token="github_pat", docs_repo="owner/repo", use_github_app=False
            )

            assert client.use_github_app is False
            assert client.github_app is None
            mock_github.assert_called_once_with("github_pat")

    def test_init_missing_credentials(self, mock_settings):
        """Test initialization with missing credentials."""
        mock_settings.GITHUB_APP_ID = None

        with pytest.raises(ValueError, match="Either GitHub App credentials or GitHub token required"):
            AutoDocClientV2(openai_api_key="test_key", docs_repo="owner/repo", use_github_app=True)

    def test_get_commit_diff_stats_with_git(self):
        """Test getting commit diff statistics using git diff --numstat."""
        client = AutoDocClientV2(openai_api_key="test_key", github_token="token", use_github_app=False)

        diff = """diff --git a/file1.py b/file1.py
+++ b/file1.py
@@ -1,3 +1,4 @@
+added line
 existing line
-removed line
diff --git a/file2.py b/file2.py
+++ b/file2.py
@@ -1,2 +1,3 @@
+another added line"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "10\t5\tfile1.py\n3\t0\tfile2.py"

            stats = client.get_commit_diff_stats(diff)

            assert stats["files_affected"] == 2
            assert stats["additions"] == 13
            assert stats["deletions"] == 5

    def test_get_commit_diff_stats_fallback(self):
        """Test fallback to regex parsing when git diff fails."""
        client = AutoDocClientV2(openai_api_key="test_key", github_token="token", use_github_app=False)

        diff = """diff --git a/file1.py b/file1.py
+++ b/file1.py
+++ b/file2.py
+added line 1
+added line 2
-removed line"""

        with patch("subprocess.run", side_effect=Exception("git error")):
            stats = client.get_commit_diff_stats(diff)

            assert stats["files_affected"] == 2  # Two +++ lines
            assert stats["additions"] == 2  # Two + lines
            assert stats["deletions"] == 1  # One - line

    @pytest.mark.asyncio
    async def test_analyze_diff(self, client, mock_openai):
        """Test analyzing diff with OpenAI."""
        diff = "diff --git a/test.py b/test.py\n+new code"

        # Mock OpenAI response
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content="Generated documentation patch"))]
        mock_openai.chat.completions.create.return_value = mock_response

        result = await client.analyze_diff(diff)

        assert result == "Generated documentation patch"
        mock_openai.chat.completions.create.assert_called_once()

        # Verify API call parameters
        call_args = mock_openai.chat.completions.create.call_args
        assert call_args[1]["model"] == "gpt-4-turbo"
        assert len(call_args[1]["messages"]) == 2
        assert "technical writer" in call_args[1]["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_analyze_diff_no_client(self, mock_settings):
        """Test analyzing diff without OpenAI client."""
        client = AutoDocClientV2(openai_api_key="test_key", github_token="token", use_github_app=False)
        client.openai_client = None

        result = await client.analyze_diff("diff")

        assert result == ""

    @pytest.mark.asyncio
    async def test_create_pr_with_check_run(self, client, mock_github_app):
        """Test creating PR with check run."""
        diff = "diff --git a/docs/api.md b/docs/api.md\n+new content"
        commit_hash = "abc123def456"

        # Mock GitHub App methods
        mock_github_app.get_file_contents.return_value = {"sha": "base_sha"}
        mock_github_app.create_or_update_file.return_value = {"commit": {"sha": "new_sha"}}
        mock_github_app.create_pull_request.return_value = {
            "number": 42,
            "html_url": "https://github.com/owner/repo/pull/42",
            "head": {"sha": "head_sha"},
        }
        mock_github_app.create_check_run.return_value = {"id": 12345, "name": "Docs Approval"}

        result = await client.create_pr_with_check_run(diff, commit_hash, approval_id="approval_123")

        assert result is not None
        assert result["pr_number"] == 42
        assert result["check_run_id"] == 12345
        assert result["pr_url"] == "https://github.com/owner/repo/pull/42"

        # Verify GitHub App calls
        mock_github_app.create_pull_request.assert_called_once()
        mock_github_app.create_check_run.assert_called_once()

        # Verify check run parameters
        check_call = mock_github_app.create_check_run.call_args
        assert check_call[1]["name"] == "Docs Approval"
        assert check_call[1]["status"] == CheckRunStatus.IN_PROGRESS
        assert "approval_123" in check_call[1]["external_id"]

    @pytest.mark.asyncio
    async def test_update_check_run_status(self, client, mock_github_app):
        """Test updating check run status."""
        result = await client.update_check_run_status(
            pr_number=42, check_run_id=12345, status=CheckRunStatus.COMPLETED, conclusion=CheckRunConclusion.SUCCESS
        )

        assert result is True

        mock_github_app.update_check_run.assert_called_once_with(
            "owner", "repo", 12345, status=CheckRunStatus.COMPLETED, conclusion=CheckRunConclusion.SUCCESS, output=None
        )

    def test_parse_diff_files(self, client):
        """Test parsing diff files."""
        diff = """diff --git a/file1.md b/file1.md
+++ b/file1.md
+Line 1
+Line 2
diff --git a/file2.md b/file2.md
+++ b/file2.md
+Another line
-Removed line"""

        files = client._parse_diff_files(diff)

        assert "file1.md" in files
        assert files["file1.md"] == "Line 1\nLine 2"
        assert "file2.md" in files
        assert files["file2.md"] == "Another line"

    @pytest.mark.asyncio
    async def test_propose_via_slack(self, client, mock_github_app):
        """Test proposing changes via Slack."""
        with patch("app.doc_agent.client_v2.SlackService") as mock_slack_class:
            mock_slack = AsyncMock()
            mock_slack_class.return_value = mock_slack
            mock_slack.send_message.return_value = {"ts": "1234567890.123456"}

            with patch("app.doc_agent.client_v2.get_db") as mock_get_db:
                mock_db = AsyncMock()
                mock_get_db.return_value.__aenter__.return_value = mock_db

                # Mock PR creation
                mock_github_app.create_pull_request.return_value = {
                    "number": 42,
                    "html_url": "https://github.com/owner/repo/pull/42",
                    "head": {"sha": "head_sha"},
                }
                mock_github_app.create_check_run.return_value = {"id": 12345}

                client.slack_service = mock_slack

                approval_id = await client.propose_via_slack(
                    diff="diff content", patch="patch content", commit_hash="abc123", commit_message="Test commit"
                )

                assert approval_id is not None
                mock_slack.send_message.assert_called_once()

                # Verify Slack message contains dashboard URL
                slack_call = mock_slack.send_message.call_args
                assert "dashboard.example.com/approvals/" in str(slack_call)

    @pytest.mark.asyncio
    async def test_propose_via_slack_no_service(self, client):
        """Test proposing via Slack when service not configured."""
        client.slack_service = None

        result = await client.propose_via_slack(diff="diff", patch="patch", commit_hash="abc123")

        assert result is None
