"""
Integration tests for GitHub webhook processing.
"""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.commit import Commit
from app.models.user import User
from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService
from app.webhooks.github import GitHubWebhookHandler


class TestGitHubWebhookIntegration:
    """Integration tests for GitHub webhook flow."""

    @pytest.fixture
    def webhook_secret(self):
        """Test webhook secret."""
        return "integration-test-secret"

    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client with test data."""
        mock = Mock()

        # Mock user repository responses
        test_user = User(
            id="user-123", email="test@example.com", name="Test User", github_username="testuser", slack_id="U123456"
        )

        # Mock commit repository responses
        mock.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
        mock.table.return_value.insert.return_value.execute.return_value.data = {
            "id": "commit-123",
            "commit_hash": "abc123",
            "user_id": "user-123",
        }

        # Mock user lookup
        mock.table.return_value.select.return_value.or_.return_value.single.return_value.execute.return_value.data = {
            "id": "user-123",
            "email": "test@example.com",
            "name": "Test User",
            "github_username": "testuser",
            "slack_id": "U123456",
        }

        return mock

    @pytest.fixture
    def handler(self, webhook_secret, mock_supabase):
        """Create webhook handler with mocked services."""
        return GitHubWebhookHandler(webhook_secret, mock_supabase)

    @pytest.fixture
    def github_push_event(self):
        """Complete GitHub push event."""
        return {
            "ref": "refs/heads/main",
            "before": "0000000000000000000000000000000000000000",
            "after": "abc123def456",
            "repository": {
                "id": 123456789,
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "owner": {"name": "testuser", "email": "test@example.com"},
                "html_url": "https://github.com/testuser/test-repo",
                "description": "Test repository",
                "fork": False,
                "url": "https://api.github.com/repos/testuser/test-repo",
            },
            "pusher": {"name": "testuser", "email": "test@example.com"},
            "sender": {
                "login": "testuser",
                "id": 1234567,
                "avatar_url": "https://avatars.githubusercontent.com/u/1234567",
                "type": "User",
            },
            "commits": [
                {
                    "id": "abc123",
                    "tree_id": "tree123",
                    "distinct": True,
                    "message": "feat: Add new authentication module\n\nImplemented OAuth2 flow with refresh tokens",
                    "timestamp": "2024-01-20T10:30:00Z",
                    "url": "https://github.com/testuser/test-repo/commit/abc123",
                    "author": {"name": "Test User", "email": "test@example.com", "username": "testuser"},
                    "committer": {"name": "Test User", "email": "test@example.com", "username": "testuser"},
                    "added": ["src/auth/oauth.py", "tests/test_oauth.py"],
                    "removed": [],
                    "modified": ["src/auth/__init__.py", "requirements.txt"],
                },
                {
                    "id": "def456",
                    "tree_id": "tree456",
                    "distinct": True,
                    "message": "test: Add comprehensive tests for OAuth module",
                    "timestamp": "2024-01-20T10:35:00Z",
                    "url": "https://github.com/testuser/test-repo/commit/def456",
                    "author": {"name": "Test User", "email": "test@example.com", "username": "testuser"},
                    "committer": {"name": "Test User", "email": "test@example.com", "username": "testuser"},
                    "added": ["tests/integration/test_oauth_flow.py"],
                    "removed": [],
                    "modified": ["tests/test_oauth.py"],
                },
            ],
            "head_commit": {
                "id": "def456",
                "message": "test: Add comprehensive tests for OAuth module",
                "timestamp": "2024-01-20T10:35:00Z",
                "url": "https://github.com/testuser/test-repo/commit/def456",
            },
        }

    @patch("app.services.commit_analysis_service.AIIntegration")
    @patch("app.services.commit_analysis_service.GitHubIntegration")
    async def test_full_webhook_flow(self, mock_github_integration, mock_ai_integration, handler, github_push_event):
        """Test complete webhook processing flow from GitHub to database."""
        # Mock GitHub diff fetching
        mock_github = Mock()
        mock_github.get_commit_diff.return_value = """
diff --git a/src/auth/oauth.py b/src/auth/oauth.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/auth/oauth.py
@@ -0,0 +1,50 @@
+import requests
+from typing import Dict, Optional
+
+class OAuth2Client:
+    def __init__(self, client_id: str, client_secret: str):
+        self.client_id = client_id
+        self.client_secret = client_secret
+    
+    def get_authorization_url(self, redirect_uri: str) -> str:
+        return f"https://auth.example.com/authorize?client_id={self.client_id}&redirect_uri={redirect_uri}"
"""
        mock_github_integration.return_value = mock_github

        # Mock AI analysis
        mock_ai = Mock()
        mock_ai.analyze_commit.return_value = {
            "points": 8,
            "categories": ["feature", "authentication"],
            "complexity": "medium",
            "risk_level": "low",
            "estimated_hours": 2.5,
            "ai_summary": "Implemented OAuth2 authentication with proper token handling",
        }
        mock_ai_integration.return_value = mock_ai

        # Process the webhook event
        result = await handler.process_event("push", github_push_event)

        # Verify results
        assert result["status"] == "success"
        assert result["repository"] == "testuser/test-repo"
        assert result["branch"] == "main"
        assert result["commits_processed"] == 2
        assert result["commits_failed"] == 0

        # Verify the processed commits
        processed = result["processed"]
        assert len(processed) == 2
        assert processed[0]["hash"] == "abc123"
        assert processed[0]["status"] == "analyzed"
        assert processed[1]["hash"] == "def456"
        assert processed[1]["status"] == "analyzed"

    async def test_webhook_signature_verification_flow(self, handler, webhook_secret, github_push_event):
        """Test the complete signature verification flow."""
        # Create payload and signature
        payload_bytes = json.dumps(github_push_event).encode()
        valid_signature = "sha256=" + hmac.new(webhook_secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

        # Verify signature
        is_valid = await handler.verify_signature(payload_bytes, valid_signature)
        assert is_valid is True

        # Test with tampered payload
        tampered_payload = payload_bytes + b"tampered"
        with pytest.raises(Exception):
            await handler.verify_signature(tampered_payload, valid_signature)

    @patch("app.services.commit_analysis_service.AIIntegration")
    async def test_webhook_with_ai_failure(self, mock_ai_integration, handler, github_push_event):
        """Test webhook processing when AI analysis fails."""
        # Mock AI failure
        mock_ai = Mock()
        mock_ai.analyze_commit.side_effect = Exception("AI service unavailable")
        mock_ai_integration.return_value = mock_ai

        # Process should continue despite AI failure
        result = await handler.process_event("push", github_push_event)

        assert result["status"] == "success"
        # Commits should fail due to AI error
        assert result["commits_failed"] == 2
        assert len(result["errors"]) == 2
        assert "AI service unavailable" in result["errors"][0]["error"]

    async def test_webhook_filters_merge_commits(self, handler):
        """Test that merge commits are properly filtered."""
        push_event = {
            "ref": "refs/heads/main",
            "repository": {
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "html_url": "https://github.com/testuser/test-repo",
            },
            "commits": [
                {
                    "id": "merge123",
                    "message": "Merge pull request #42 from feature/oauth\n\nAdd OAuth support",
                    "timestamp": "2024-01-20T10:30:00Z",
                    "url": "https://github.com/testuser/test-repo/commit/merge123",
                    "author": {"username": "github", "email": "noreply@github.com"},
                },
                {
                    "id": "regular123",
                    "message": "fix: Handle token expiration",
                    "timestamp": "2024-01-20T10:31:00Z",
                    "url": "https://github.com/testuser/test-repo/commit/regular123",
                    "author": {"username": "testuser", "email": "test@example.com"},
                },
                {
                    "id": "merge456",
                    "message": "Merge branch 'develop' into main",
                    "timestamp": "2024-01-20T10:32:00Z",
                    "url": "https://github.com/testuser/test-repo/commit/merge456",
                    "author": {"username": "testuser", "email": "test@example.com"},
                },
            ],
        }

        with patch.object(handler.commit_analysis_service, "process_commit", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"status": "analyzed"}

            result = await handler.process_event("push", push_event)

            # Should only process the non-merge commit
            assert result["commits_processed"] == 1
            assert mock_process.call_count == 1

            # Verify it processed the right commit
            call_args = mock_process.call_args[0][0]
            assert call_args.commit_hash == "regular123"

    async def test_commit_payload_conversion(self, handler):
        """Test accurate conversion of GitHub commit to CommitPayload."""
        commit = {
            "id": "abc123def456789",
            "message": "feat: Add user profile page\n\nImplemented profile viewing and editing",
            "url": "https://github.com/testuser/test-repo/commit/abc123def456789",
            "timestamp": "2024-01-20T15:30:45Z",
            "author": {"name": "John Doe", "email": "john@example.com", "username": "johndoe"},
            "added": ["src/pages/profile.tsx"],
            "removed": ["src/pages/old-profile.js"],
            "modified": ["src/router.tsx", "src/api/user.ts"],
        }

        payload = handler._convert_to_commit_payload(
            commit,
            repository="testuser/test-repo",
            repo_url="https://github.com/testuser/test-repo",
            branch="feature/user-profile",
        )

        # Verify all fields are correctly mapped
        assert payload.commit_hash == "abc123def456789"
        assert payload.commit_message == "feat: Add user profile page\n\nImplemented profile viewing and editing"
        assert payload.commit_url == "https://github.com/testuser/test-repo/commit/abc123def456789"
        assert payload.author_github_username == "johndoe"
        assert payload.author_email == "john@example.com"
        assert payload.repository_name == "test-repo"
        assert payload.repository == "testuser/test-repo"
        assert payload.repository_url == "https://github.com/testuser/test-repo"
        assert payload.branch == "feature/user-profile"
        assert payload.diff_url == "https://github.com/testuser/test-repo/commit/abc123def456789.diff"

        # Verify timestamp parsing
        assert isinstance(payload.commit_timestamp, datetime)
        assert payload.commit_timestamp.year == 2024
        assert payload.commit_timestamp.month == 1
        assert payload.commit_timestamp.day == 20
