"""Unit tests for GitHub App authentication service."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from app.integrations.github_app import CheckRunConclusion, CheckRunStatus, GitHubApp


class TestGitHubApp:
    """Test cases for GitHub App integration."""

    @pytest.fixture
    def github_app(self):
        """Create a GitHub App instance for testing."""
        return GitHubApp(
            app_id="123456",
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest_key\n-----END RSA PRIVATE KEY-----",
            installation_id="789012",
            webhook_secret="test_secret",
        )

    def test_init(self):
        """Test GitHub App initialization."""
        app = GitHubApp(app_id="123", private_key="key", installation_id="456", webhook_secret="secret")

        assert app.app_id == "123"
        assert app.private_key == "key"
        assert app.installation_id == "456"
        assert app.webhook_secret == "secret"
        assert app.base_url == "https://api.github.com"

    @patch("jwt.encode")
    def test_generate_jwt(self, mock_encode, github_app):
        """Test JWT generation."""
        mock_encode.return_value = "test_jwt_token"

        token = github_app.generate_jwt()

        assert token == "test_jwt_token"
        mock_encode.assert_called_once()

        # Verify JWT payload structure
        call_args = mock_encode.call_args
        payload = call_args[0][0]
        assert "iat" in payload
        assert "exp" in payload
        assert payload["iss"] == "123456"

    def test_generate_jwt_missing_credentials(self):
        """Test JWT generation with missing credentials."""
        app = GitHubApp(installation_id="123")

        with pytest.raises(ValueError, match="App ID and private key required"):
            app.generate_jwt()

    @patch("requests.post")
    @patch.object(GitHubApp, "generate_jwt")
    def test_get_installation_token(self, mock_jwt, mock_post, github_app):
        """Test getting installation access token."""
        mock_jwt.return_value = "test_jwt"

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "token": "installation_token",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
        }
        mock_post.return_value = mock_response

        token = github_app.get_installation_token()

        assert token == "installation_token"
        assert github_app._installation_token == "installation_token"
        mock_jwt.assert_called_once()
        mock_post.assert_called_once_with(
            "https://api.github.com/app/installations/789012/access_tokens",
            headers={"Authorization": "Bearer test_jwt", "Accept": "application/vnd.github.v3+json"},
        )

    @patch("requests.post")
    @patch.object(GitHubApp, "generate_jwt")
    def test_get_installation_token_cached(self, mock_jwt, mock_post, github_app):
        """Test using cached installation token."""
        # Set up cached token
        github_app._installation_token = "cached_token"
        github_app._token_expires_at = datetime.now() + timedelta(minutes=10)

        token = github_app.get_installation_token()

        assert token == "cached_token"
        mock_jwt.assert_not_called()
        mock_post.assert_not_called()

    def test_verify_webhook_valid(self, github_app):
        """Test webhook signature verification with valid signature."""
        body = b"test webhook body"
        import hashlib
        import hmac

        # Generate valid signature
        signature = "sha256=" + hmac.new(b"test_secret", body, hashlib.sha256).hexdigest()

        assert github_app.verify_webhook(signature, body) is True

    def test_verify_webhook_invalid(self, github_app):
        """Test webhook signature verification with invalid signature."""
        body = b"test webhook body"
        signature = "sha256=invalid_signature"

        assert github_app.verify_webhook(signature, body) is False

    def test_verify_webhook_no_secret(self):
        """Test webhook verification without secret configured."""
        app = GitHubApp(app_id="123", private_key="key", installation_id="456")

        assert app.verify_webhook("signature", b"body") is False

    @patch("requests.post")
    @patch.object(GitHubApp, "get_headers")
    def test_create_pull_request(self, mock_headers, mock_post, github_app):
        """Test creating a pull request."""
        mock_headers.return_value = {"Authorization": "token test"}

        mock_response = Mock()
        mock_response.json.return_value = {
            "number": 42,
            "html_url": "https://github.com/owner/repo/pull/42",
            "head": {"sha": "abc123"},
        }
        mock_post.return_value = mock_response

        pr_data = github_app.create_pull_request(
            owner="owner", repo="repo", title="Test PR", head="feature", base="main", body="Test description"
        )

        assert pr_data["number"] == 42
        assert pr_data["html_url"] == "https://github.com/owner/repo/pull/42"

        mock_post.assert_called_once_with(
            "https://api.github.com/repos/owner/repo/pulls",
            json={"title": "Test PR", "head": "feature", "base": "main", "body": "Test description", "draft": False},
            headers={"Authorization": "token test"},
        )

    @patch("requests.post")
    @patch.object(GitHubApp, "get_headers")
    def test_create_check_run(self, mock_headers, mock_post, github_app):
        """Test creating a check run."""
        mock_headers.return_value = {"Authorization": "token test"}

        mock_response = Mock()
        mock_response.json.return_value = {"id": 12345, "name": "Docs Approval", "status": "in_progress"}
        mock_post.return_value = mock_response

        check_run = github_app.create_check_run(
            owner="owner",
            repo="repo",
            name="Docs Approval",
            head_sha="abc123",
            status=CheckRunStatus.IN_PROGRESS,
            details_url="https://example.com/details",
            external_id="approval_123",
        )

        assert check_run["id"] == 12345
        assert check_run["name"] == "Docs Approval"

        expected_data = {
            "name": "Docs Approval",
            "head_sha": "abc123",
            "status": "in_progress",
            "details_url": "https://example.com/details",
            "external_id": "approval_123",
        }

        mock_post.assert_called_once()
        actual_call = mock_post.call_args
        assert actual_call[1]["json"] == expected_data

    @patch("requests.patch")
    @patch.object(GitHubApp, "get_headers")
    def test_update_check_run(self, mock_headers, mock_patch, github_app):
        """Test updating a check run."""
        mock_headers.return_value = {"Authorization": "token test"}

        mock_response = Mock()
        mock_response.json.return_value = {"id": 12345, "status": "completed", "conclusion": "success"}
        mock_patch.return_value = mock_response

        check_run = github_app.update_check_run(
            owner="owner",
            repo="repo",
            check_run_id=12345,
            status=CheckRunStatus.COMPLETED,
            conclusion=CheckRunConclusion.SUCCESS,
        )

        assert check_run["status"] == "completed"
        assert check_run["conclusion"] == "success"

        mock_patch.assert_called_once()
        actual_call = mock_patch.call_args
        assert "completed" in actual_call[1]["json"]["status"]
        assert "success" in actual_call[1]["json"]["conclusion"]

    @patch("requests.get")
    @patch.object(GitHubApp, "get_headers")
    def test_get_file_contents(self, mock_headers, mock_get, github_app):
        """Test getting file contents."""
        mock_headers.return_value = {"Authorization": "token test"}

        mock_response = Mock()
        mock_response.json.return_value = {
            "name": "README.md",
            "path": "README.md",
            "sha": "abc123",
            "content": "base64_content",
        }
        mock_get.return_value = mock_response

        contents = github_app.get_file_contents(owner="owner", repo="repo", path="README.md", ref="main")

        assert contents["name"] == "README.md"
        assert contents["sha"] == "abc123"

        mock_get.assert_called_once_with(
            "https://api.github.com/repos/owner/repo/contents/README.md",
            headers={"Authorization": "token test"},
            params={"ref": "main"},
        )

    @patch("requests.put")
    @patch.object(GitHubApp, "get_headers")
    def test_create_or_update_file(self, mock_headers, mock_put, github_app):
        """Test creating or updating a file."""
        mock_headers.return_value = {"Authorization": "token test"}

        mock_response = Mock()
        mock_response.json.return_value = {"content": {"name": "test.md"}, "commit": {"sha": "new_sha"}}
        mock_put.return_value = mock_response

        result = github_app.create_or_update_file(
            owner="owner",
            repo="repo",
            path="test.md",
            message="Update test file",
            content="Test content",
            branch="main",
            sha="old_sha",
        )

        assert "content" in result
        assert "commit" in result

        mock_put.assert_called_once()
        actual_call = mock_put.call_args
        assert actual_call[1]["json"]["message"] == "Update test file"
        assert actual_call[1]["json"]["branch"] == "main"
        assert actual_call[1]["json"]["sha"] == "old_sha"

    @patch("requests.get")
    @patch.object(GitHubApp, "get_headers")
    def test_get_pull_request_diff(self, mock_headers, mock_get, github_app):
        """Test getting pull request diff."""
        mock_headers.return_value = {"Authorization": "token test", "Accept": "application/vnd.github.v3+json"}

        mock_response = Mock()
        mock_response.text = "diff --git a/file.txt b/file.txt\n+added line"
        mock_get.return_value = mock_response

        diff = github_app.get_pull_request_diff(owner="owner", repo="repo", pr_number=42)

        assert "diff --git" in diff
        assert "+added line" in diff

        mock_get.assert_called_once()
        # Check that Accept header was updated for diff format
        call_headers = mock_get.call_args[1]["headers"]
        assert call_headers["Accept"] == "application/vnd.github.v3.diff"
