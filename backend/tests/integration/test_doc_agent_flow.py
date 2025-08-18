"""Integration tests for the complete documentation agent flow."""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.doc_agent.client_v2 import AutoDocClientV2
from app.integrations.ai_integration_v2 import AIIntegrationV2
from app.integrations.github_app import CheckRunConclusion, CheckRunStatus, GitHubApp
# Remove cross-module import - define test helper locally if needed


class TestDocAgentIntegration:
    """Integration tests for documentation agent workflow."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Set up environment variables for testing."""
        monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
        monkeypatch.setenv("GITHUB_APP_ID", "test_app_id")
        monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "test_private_key")
        monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "test_install_id")
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test_webhook_secret")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "test_slack_token")
        monkeypatch.setenv("DOCS_REPOSITORY", "owner/docs-repo")
        monkeypatch.setenv("DATABASE_URL", "postgresql://test")
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test_supabase_key")

    @pytest.fixture
    def mock_github_api_responses(self):
        """Mock GitHub API responses."""
        return {
            "installation_token": {
                "token": "ghs_test_token",
                "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
            },
            "create_pr": {
                "number": 42,
                "html_url": "https://github.com/owner/docs-repo/pull/42",
                "head": {"sha": "abc123def456"},
            },
            "create_check_run": {"id": 12345, "name": "Docs Approval", "status": "in_progress"},
            "update_check_run": {"id": 12345, "status": "completed", "conclusion": "success"},
        }

    @pytest.fixture
    def mock_openai_responses(self):
        """Mock OpenAI API responses."""
        return {
            "analyze_diff": "Generated documentation patch content",
            "embeddings": [0.1] * 3072,  # text-embedding-3-large dimension
            "commit_analysis": {
                "estimated_hours": 3.5,
                "complexity_score": 6,
                "key_changes": ["Added new API endpoint", "Fixed authentication bug"],
            },
        }

    @pytest.mark.asyncio
    async def test_full_doc_agent_flow(self, mock_env, mock_github_api_responses, mock_openai_responses):
        """Test the complete documentation agent flow from diff to PR creation."""

        # Sample git diff
        test_diff = """diff --git a/api/endpoints.py b/api/endpoints.py
index 1234567..abcdefg 100644
--- a/api/endpoints.py
+++ b/api/endpoints.py
@@ -10,6 +10,12 @@ class APIRouter:
     def get_users(self):
         return self.db.query(User).all()
     
+    def create_user(self, user_data):
+        \"\"\"Create a new user.\"\"\"
+        user = User(**user_data)
+        self.db.add(user)
+        self.db.commit()
+        return user
"""

        with (
            patch("requests.post") as mock_post,
            patch("requests.get") as mock_get,
            patch("requests.patch") as mock_patch,
            patch("jwt.encode") as mock_jwt,
            patch("doc_agent.client_v2.AsyncOpenAI") as mock_openai_class,
            patch("doc_agent.client_v2.SlackService") as mock_slack_class,
            patch("doc_agent.client_v2.get_db") as mock_get_db,
        ):

            # Set up JWT mock
            mock_jwt.return_value = "test_jwt_token"

            # Set up GitHub API mocks
            def github_api_side_effect(url, *args, **kwargs):
                response = Mock()
                if "installations" in url and "access_tokens" in url:
                    response.json.return_value = mock_github_api_responses["installation_token"]
                elif url.endswith("/pulls"):
                    response.json.return_value = mock_github_api_responses["create_pr"]
                elif url.endswith("/check-runs"):
                    response.json.return_value = mock_github_api_responses["create_check_run"]
                return response

            mock_post.side_effect = github_api_side_effect

            def github_patch_side_effect(url, *args, **kwargs):
                response = Mock()
                response.json.return_value = mock_github_api_responses["update_check_run"]
                return response

            mock_patch.side_effect = github_patch_side_effect

            # Set up OpenAI mocks
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai

            # Mock diff analysis
            mock_completion = AsyncMock()
            mock_completion.choices = [Mock(message=Mock(content=mock_openai_responses["analyze_diff"]))]
            mock_openai.chat.completions.create.return_value = mock_completion

            # Mock embeddings
            mock_embedding = AsyncMock()
            mock_embedding.data = [Mock(embedding=mock_openai_responses["embeddings"])]
            mock_openai.embeddings.create.return_value = mock_embedding

            # Set up Slack mock
            mock_slack = AsyncMock()
            mock_slack.send_message.return_value = {"ts": "1234567890.123456"}
            mock_slack_class.return_value = mock_slack

            # Set up database mock
            mock_db = AsyncMock()
            mock_get_db.return_value.__aenter__.return_value = mock_db

            # Create client and run flow
            client = AutoDocClientV2(openai_api_key="test_key", docs_repo="owner/docs-repo", use_github_app=True)

            # Analyze diff
            patch = await client.analyze_diff(test_diff)
            assert patch == mock_openai_responses["analyze_diff"]

            # Propose via Slack (which creates PR and check run)
            approval_id = await client.propose_via_slack(
                diff=test_diff, patch=patch, commit_hash="test_commit_123", commit_message="Add create_user endpoint"
            )

            # Verify the flow executed correctly
            assert approval_id is not None

            # Verify OpenAI was called for diff analysis
            mock_openai.chat.completions.create.assert_called()

            # Verify GitHub App created PR and check run
            assert mock_post.call_count >= 2  # At least token + PR creation

            # Verify Slack message was sent
            mock_slack.send_message.assert_called_once()
            slack_call = mock_slack.send_message.call_args
            assert "owner/docs-repo" in str(slack_call)
            assert "dashboard.example.com/approvals/" in str(slack_call)

    @pytest.mark.asyncio
    async def test_pre_commit_hook_integration(self, mock_env):
        """Test the pre-commit hook integration."""

        test_diff = """diff --git a/test.py b/test.py
+def new_function():
+    return "test"
"""

        with (
            patch("subprocess.check_output") as mock_subprocess,
            patch("doc_agent.client.AutoDocClient") as mock_client_class,
        ):

            # Mock git commands
            def subprocess_side_effect(cmd, *args, **kwargs):
                if cmd == ["git", "diff", "--cached"]:
                    return test_diff
                elif cmd == ["git", "rev-parse", "HEAD"]:
                    return "abc123def456"
                elif cmd == ["git", "log", "-1", "--pretty=%B"]:
                    return "Test commit message"
                return ""

            mock_subprocess.side_effect = subprocess_side_effect

            # Mock AutoDocClient
            mock_client = AsyncMock()
            mock_client.analyze_diff.return_value = "Documentation patch"
            mock_client.propose_via_slack.return_value = "approval_123"
            mock_client_class.return_value = mock_client

            # Run the pre-commit hook function
            from scripts.pre_commit_auto_docs import main

            result = main()

            assert result == 0

            # Verify git commands were called
            assert mock_subprocess.call_count >= 1

            # Note: The actual async flow would need to be tested with proper async mocking

    @pytest.mark.asyncio
    async def test_github_app_check_run_lifecycle(self, mock_env, mock_github_api_responses):
        """Test the complete lifecycle of a GitHub check run."""

        with (
            patch("requests.post") as mock_post,
            patch("requests.patch") as mock_patch,
            patch("jwt.encode") as mock_jwt,
        ):

            mock_jwt.return_value = "test_jwt"

            # Mock installation token request
            token_response = Mock()
            token_response.json.return_value = mock_github_api_responses["installation_token"]

            # Mock check run creation
            create_response = Mock()
            create_response.json.return_value = mock_github_api_responses["create_check_run"]

            # Mock check run update
            update_response = Mock()
            update_response.json.return_value = mock_github_api_responses["update_check_run"]

            mock_post.return_value = token_response
            mock_patch.return_value = update_response

            # Create GitHub App instance
            app = GitHubApp()

            # Get installation token
            token = app.get_installation_token()
            assert token == "ghs_test_token"

            # Switch mock for check run creation
            mock_post.return_value = create_response

            # Create check run
            check_run = app.create_check_run(
                owner="owner",
                repo="docs-repo",
                name="Docs Approval",
                head_sha="abc123",
                status=CheckRunStatus.IN_PROGRESS,
                details_url="https://dashboard.example.com/approvals/123",
            )

            assert check_run["id"] == 12345
            assert check_run["status"] == "in_progress"

            # Update check run to completed
            updated = app.update_check_run(
                owner="owner",
                repo="docs-repo",
                check_run_id=12345,
                status=CheckRunStatus.COMPLETED,
                conclusion=CheckRunConclusion.SUCCESS,
                output={"title": "Documentation Approved", "summary": "The documentation changes have been approved."},
            )

            assert updated["status"] == "completed"
            assert updated["conclusion"] == "success"

    @pytest.mark.asyncio
    async def test_ai_integration_standardized_api(self, mock_env):
        """Test the standardized AI integration without branchy code."""

        with patch("app.integrations.ai_integration_v2.AsyncOpenAI") as mock_openai_class:
            mock_client = AsyncMock()
            mock_openai_class.return_value = mock_client

            # Mock chat completion
            mock_response = AsyncMock()
            mock_response.choices = [
                Mock(message=Mock(content=json.dumps({"estimated_hours": 4.0, "complexity_score": 7})))
            ]
            mock_client.chat.completions.create.return_value = mock_response

            # Mock embeddings
            mock_embedding = AsyncMock()
            mock_embedding.data = [Mock(embedding=[0.1] * 3072)]
            mock_client.embeddings.create.return_value = mock_embedding

            # Create AI integration
            ai = AIIntegrationV2()

            # Test standardized commit analysis (no gpt-5 branching)
            result = await ai.analyze_commit_diff({"diff": "test diff", "message": "test message"})

            assert result["estimated_hours"] == 4.0
            assert result["complexity_score"] == 7

            # Test embedding generation with new model
            embeddings = await ai.generate_embeddings("Test text")
            assert len(embeddings) == 3072  # text-embedding-3-large dimension

            # Verify API calls use standardized interface
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            assert "response_format" in call_args[1]
            assert call_args[1]["response_format"] == {"type": "json_object"}

            # Verify embedding model
            mock_client.embeddings.create.assert_called_once_with(
                model="text-embedding-3-large", input="Test text", encoding_format="float"
            )

    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, mock_env):
        """Test error recovery in the documentation agent flow."""

        with (
            patch("doc_agent.client_v2.AsyncOpenAI") as mock_openai_class,
            patch("doc_agent.client_v2.GitHubApp") as mock_github_class,
        ):

            # Set up OpenAI to fail initially then succeed
            mock_openai = AsyncMock()
            mock_openai_class.return_value = mock_openai

            # First call fails, second succeeds
            mock_openai.chat.completions.create.side_effect = [
                Exception("API rate limit"),
                AsyncMock(choices=[Mock(message=Mock(content="Recovered patch"))]),
            ]

            # Set up GitHub App
            mock_github = Mock()
            mock_github_class.return_value = mock_github

            client = AutoDocClientV2(openai_api_key="test_key", docs_repo="owner/repo", use_github_app=True)

            # First attempt fails
            result1 = await client.analyze_diff("test diff")
            assert result1 == ""  # Returns empty on error

            # Second attempt succeeds
            result2 = await client.analyze_diff("test diff")
            assert result2 == "Recovered patch"

            # Verify retry logic was used
            assert mock_openai.chat.completions.create.call_count == 2
