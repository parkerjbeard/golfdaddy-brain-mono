"""
Unit tests for GitHub webhook handler.
"""
import hmac
import hashlib
import json
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from app.webhooks.github import GitHubWebhookHandler
from app.webhooks.base import WebhookVerificationError
from app.schemas.github_event import CommitPayload
from app.core.exceptions import ExternalServiceError


class TestGitHubWebhookHandler:
    """Test cases for GitHub webhook handler."""
    
    @pytest.fixture
    def webhook_secret(self):
        """Test webhook secret."""
        return "test-webhook-secret-123"
    
    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client."""
        return Mock()
    
    @pytest.fixture
    def handler(self, webhook_secret, mock_supabase):
        """Create GitHub webhook handler instance."""
        return GitHubWebhookHandler(webhook_secret, mock_supabase)
    
    @pytest.fixture
    def sample_push_event(self):
        """Sample GitHub push event payload."""
        return {
            "ref": "refs/heads/main",
            "before": "abc123",
            "after": "def456",
            "repository": {
                "id": 123456,
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "html_url": "https://github.com/testuser/test-repo"
            },
            "pusher": {
                "name": "testuser",
                "email": "test@example.com"
            },
            "commits": [
                {
                    "id": "commit123",
                    "message": "Fix: Update user authentication flow",
                    "url": "https://github.com/testuser/test-repo/commit/commit123",
                    "timestamp": "2024-01-20T10:30:00Z",
                    "author": {
                        "name": "Test User",
                        "email": "test@example.com",
                        "username": "testuser"
                    },
                    "added": ["src/auth.py"],
                    "removed": [],
                    "modified": ["src/user.py", "tests/test_auth.py"]
                }
            ],
            "head_commit": {
                "id": "commit123",
                "message": "Fix: Update user authentication flow",
                "url": "https://github.com/testuser/test-repo/commit/commit123",
                "timestamp": "2024-01-20T10:30:00Z",
                "author": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "username": "testuser"
                }
            }
        }
    
    async def test_verify_signature_valid(self, handler, webhook_secret):
        """Test signature verification with valid signature."""
        payload = b'{"test": "data"}'
        valid_signature = "sha256=" + hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        result = await handler.verify_signature(payload, valid_signature)
        assert result is True
    
    async def test_verify_signature_invalid(self, handler):
        """Test signature verification with invalid signature."""
        payload = b'{"test": "data"}'
        invalid_signature = "sha256=invalid"
        
        with pytest.raises(WebhookVerificationError, match="Invalid webhook signature"):
            await handler.verify_signature(payload, invalid_signature)
    
    async def test_verify_signature_missing(self, handler):
        """Test signature verification with missing signature."""
        payload = b'{"test": "data"}'
        
        with pytest.raises(WebhookVerificationError, match="Missing X-Hub-Signature-256 header"):
            await handler.verify_signature(payload, "")
    
    async def test_verify_signature_wrong_format(self, handler):
        """Test signature verification with wrong format."""
        payload = b'{"test": "data"}'
        wrong_format = "md5=somehash"
        
        with pytest.raises(WebhookVerificationError, match="Invalid signature format"):
            await handler.verify_signature(payload, wrong_format)
    
    def test_extract_event_type(self, handler):
        """Test extracting GitHub event type from headers."""
        headers = {"x-github-event": "push"}
        body = {}
        
        event_type = handler.extract_event_type(headers, body)
        assert event_type == "push"
    
    def test_extract_event_type_missing(self, handler):
        """Test extracting event type with missing header."""
        headers = {}
        body = {}
        
        event_type = handler.extract_event_type(headers, body)
        assert event_type == "unknown"
    
    async def test_process_event_non_push(self, handler):
        """Test processing non-push events."""
        result = await handler.process_event("pull_request", {})
        
        assert result["status"] == "ignored"
        assert "pull_request" in result["reason"]
    
    @patch('app.webhooks.github.CommitAnalysisService')
    async def test_process_push_event_success(self, mock_commit_service, handler, sample_push_event):
        """Test successful push event processing."""
        # Mock commit analysis service
        mock_service_instance = AsyncMock()
        mock_service_instance.process_commit = AsyncMock(return_value={"status": "analyzed"})
        mock_commit_service.return_value = mock_service_instance
        handler.commit_analysis_service = mock_service_instance
        
        result = await handler.process_event("push", sample_push_event)
        
        assert result["status"] == "success"
        assert result["repository"] == "testuser/test-repo"
        assert result["branch"] == "main"
        assert result["commits_processed"] == 1
        assert result["commits_failed"] == 0
        
        # Verify commit analysis was called
        mock_service_instance.process_commit.assert_called_once()
        call_args = mock_service_instance.process_commit.call_args[0][0]
        assert isinstance(call_args, CommitPayload)
        assert call_args.commit_hash == "commit123"
    
    @patch('app.webhooks.github.CommitAnalysisService')
    async def test_process_push_event_with_merge_commits(self, mock_commit_service, handler):
        """Test push event processing filters merge commits."""
        mock_service_instance = AsyncMock()
        mock_service_instance.process_commit = AsyncMock(return_value={"status": "analyzed"})
        mock_commit_service.return_value = mock_service_instance
        handler.commit_analysis_service = mock_service_instance
        
        push_event = {
            "ref": "refs/heads/main",
            "repository": {
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "html_url": "https://github.com/testuser/test-repo"
            },
            "commits": [
                {
                    "id": "merge123",
                    "message": "Merge pull request #42 from feature-branch",
                    "url": "https://github.com/testuser/test-repo/commit/merge123",
                    "timestamp": "2024-01-20T10:30:00Z",
                    "author": {"username": "testuser", "email": "test@example.com"}
                },
                {
                    "id": "commit456",
                    "message": "Add new feature",
                    "url": "https://github.com/testuser/test-repo/commit/commit456",
                    "timestamp": "2024-01-20T10:31:00Z",
                    "author": {"username": "testuser", "email": "test@example.com"}
                }
            ]
        }
        
        result = await handler.process_event("push", push_event)
        
        # Should only process non-merge commit
        assert result["commits_processed"] == 1
        assert mock_service_instance.process_commit.call_count == 1
        
        # Verify it processed the right commit
        call_args = mock_service_instance.process_commit.call_args[0][0]
        assert call_args.commit_hash == "commit456"
    
    @patch('app.webhooks.github.CommitAnalysisService')
    async def test_process_push_event_analysis_failure(self, mock_commit_service, handler, sample_push_event):
        """Test push event processing with analysis failure."""
        mock_service_instance = AsyncMock()
        mock_service_instance.process_commit = AsyncMock(return_value=None)
        mock_commit_service.return_value = mock_service_instance
        handler.commit_analysis_service = mock_service_instance
        
        result = await handler.process_event("push", sample_push_event)
        
        assert result["status"] == "success"
        assert result["commits_processed"] == 0
        assert result["commits_failed"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["hash"] == "commit123"
    
    @patch('app.webhooks.github.CommitAnalysisService')
    async def test_process_push_event_exception(self, mock_commit_service, handler, sample_push_event):
        """Test push event processing with exception."""
        mock_service_instance = AsyncMock()
        mock_service_instance.process_commit = AsyncMock(side_effect=Exception("Test error"))
        mock_commit_service.return_value = mock_service_instance
        handler.commit_analysis_service = mock_service_instance
        
        result = await handler.process_event("push", sample_push_event)
        
        assert result["status"] == "success"
        assert result["commits_failed"] == 1
        assert "Test error" in result["errors"][0]["error"]
    
    async def test_process_push_event_no_commits(self, handler):
        """Test push event with no commits."""
        push_event = {
            "ref": "refs/heads/main",
            "repository": {
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "html_url": "https://github.com/testuser/test-repo"
            },
            "commits": []
        }
        
        result = await handler.process_event("push", push_event)
        
        assert result["status"] == "success"
        assert result["commits_processed"] == 0
    
    def test_convert_to_commit_payload(self, handler):
        """Test converting GitHub commit to CommitPayload."""
        commit = {
            "id": "abc123",
            "message": "Test commit message",
            "url": "https://github.com/test/repo/commit/abc123",
            "timestamp": "2024-01-20T10:30:00Z",
            "author": {
                "name": "Test User",
                "email": "test@example.com",
                "username": "testuser"
            }
        }
        
        payload = handler._convert_to_commit_payload(
            commit,
            repository="testuser/test-repo",
            repo_url="https://github.com/testuser/test-repo",
            branch="main"
        )
        
        assert isinstance(payload, CommitPayload)
        assert payload.commit_hash == "abc123"
        assert payload.commit_message == "Test commit message"
        assert payload.commit_url == "https://github.com/test/repo/commit/abc123"
        assert payload.author_github_username == "testuser"
        assert payload.author_email == "test@example.com"
        assert payload.repository_name == "test-repo"
        assert payload.repository == "testuser/test-repo"
        assert payload.branch == "main"
        assert payload.diff_url == "https://github.com/test/repo/commit/abc123.diff"
    
    def test_convert_to_commit_payload_minimal(self, handler):
        """Test converting minimal GitHub commit data."""
        commit = {
            "id": "xyz789",
            "message": "",
            "author": {}
        }
        
        payload = handler._convert_to_commit_payload(
            commit,
            repository="owner/repo",
            repo_url="https://github.com/owner/repo",
            branch="develop"
        )
        
        assert payload.commit_hash == "xyz789"
        assert payload.commit_message == ""
        assert payload.author_github_username == ""
        assert payload.author_email == ""
        assert payload.diff_url is None