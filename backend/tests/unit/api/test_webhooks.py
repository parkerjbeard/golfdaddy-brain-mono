"""
Unit tests for webhook API endpoints.
"""
import json
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.main import app
from app.webhooks.github import GitHubWebhookHandler
from app.core.exceptions import ConfigurationError


class TestWebhookEndpoints:
    """Test cases for webhook API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def webhook_secret(self):
        """Test webhook secret."""
        return "test-webhook-secret-123"
    
    @pytest.fixture
    def github_push_payload(self):
        """Sample GitHub push event payload."""
        return {
            "ref": "refs/heads/main",
            "repository": {
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "html_url": "https://github.com/testuser/test-repo"
            },
            "commits": [
                {
                    "id": "abc123",
                    "message": "Test commit",
                    "url": "https://github.com/testuser/test-repo/commit/abc123",
                    "timestamp": "2024-01-20T10:30:00Z",
                    "author": {
                        "username": "testuser",
                        "email": "test@example.com"
                    }
                }
            ]
        }
    
    def create_github_signature(self, payload: str, secret: str) -> str:
        """Create GitHub webhook signature."""
        return "sha256=" + hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @patch('app.api.webhooks.settings')
    @patch('app.api.webhooks.get_db')
    @patch('app.webhooks.github.GitHubWebhookHandler.verify_signature')
    @patch('app.webhooks.github.GitHubWebhookHandler.process_event')
    async def test_github_webhook_success(
        self,
        mock_process_event,
        mock_verify_signature,
        mock_get_db,
        mock_settings,
        client,
        webhook_secret,
        github_push_payload
    ):
        """Test successful GitHub webhook processing."""
        # Configure mocks
        mock_settings.github_webhook_secret = webhook_secret
        mock_get_db.return_value = Mock()
        mock_verify_signature.return_value = True
        mock_process_event.return_value = {
            "status": "success",
            "repository": "testuser/test-repo",
            "branch": "main",
            "commits_processed": 1,
            "commits_failed": 0
        }
        
        # Prepare request
        payload_json = json.dumps(github_push_payload)
        signature = self.create_github_signature(payload_json, webhook_secret)
        
        # Make request
        response = client.post(
            "/api/v1/webhooks/github",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "12345-67890"
            }
        )
        
        # Verify response
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["delivery_id"] == "12345-67890"
        assert data["event_type"] == "push"
        assert data["result"]["commits_processed"] == 1
    
    @patch('app.api.webhooks.settings')
    async def test_github_webhook_no_secret_configured(
        self,
        mock_settings,
        client,
        github_push_payload
    ):
        """Test GitHub webhook with no secret configured."""
        mock_settings.github_webhook_secret = None
        
        payload_json = json.dumps(github_push_payload)
        
        response = client.post(
            "/api/v1/webhooks/github",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push"
            }
        )
        
        assert response.status_code == 500  # ConfigurationError
    
    @patch('app.api.webhooks.settings')
    @patch('app.api.webhooks.get_db')
    async def test_github_webhook_invalid_signature(
        self,
        mock_get_db,
        mock_settings,
        client,
        webhook_secret,
        github_push_payload
    ):
        """Test GitHub webhook with invalid signature."""
        mock_settings.github_webhook_secret = webhook_secret
        mock_get_db.return_value = Mock()
        
        payload_json = json.dumps(github_push_payload)
        
        response = client.post(
            "/api/v1/webhooks/github",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "push"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]
    
    @patch('app.api.webhooks.settings')
    @patch('app.api.webhooks.get_db')
    async def test_github_webhook_missing_signature(
        self,
        mock_get_db,
        mock_settings,
        client,
        webhook_secret,
        github_push_payload
    ):
        """Test GitHub webhook without signature header."""
        mock_settings.github_webhook_secret = webhook_secret
        mock_get_db.return_value = Mock()
        
        payload_json = json.dumps(github_push_payload)
        
        response = client.post(
            "/api/v1/webhooks/github",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push"
            }
        )
        
        assert response.status_code == 401
    
    @patch('app.api.webhooks.settings')
    @patch('app.api.webhooks.get_db')
    @patch('app.webhooks.github.GitHubWebhookHandler.verify_signature')
    async def test_github_webhook_invalid_json(
        self,
        mock_verify_signature,
        mock_get_db,
        mock_settings,
        client,
        webhook_secret
    ):
        """Test GitHub webhook with invalid JSON payload."""
        mock_settings.github_webhook_secret = webhook_secret
        mock_get_db.return_value = Mock()
        mock_verify_signature.return_value = True
        
        invalid_json = "{'invalid': json}"
        signature = self.create_github_signature(invalid_json, webhook_secret)
        
        response = client.post(
            "/api/v1/webhooks/github",
            content=invalid_json,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push"
            }
        )
        
        assert response.status_code == 400
        assert "Invalid JSON payload" in response.json()["detail"]
    
    @patch('app.api.webhooks.settings')
    @patch('app.api.webhooks.get_db')
    @patch('app.webhooks.github.GitHubWebhookHandler.verify_signature')
    @patch('app.webhooks.github.GitHubWebhookHandler.process_event')
    async def test_github_webhook_processing_error(
        self,
        mock_process_event,
        mock_verify_signature,
        mock_get_db,
        mock_settings,
        client,
        webhook_secret,
        github_push_payload
    ):
        """Test GitHub webhook with processing error."""
        from app.core.exceptions import ExternalServiceError
        
        mock_settings.github_webhook_secret = webhook_secret
        mock_get_db.return_value = Mock()
        mock_verify_signature.return_value = True
        mock_process_event.side_effect = ExternalServiceError(
            service_name="GitHub",
            original_message="Processing failed"
        )
        
        payload_json = json.dumps(github_push_payload)
        signature = self.create_github_signature(payload_json, webhook_secret)
        
        response = client.post(
            "/api/v1/webhooks/github",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push"
            }
        )
        
        # Should return 202 to prevent GitHub retries
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "error"
        assert "Processing failed" in data["error"]
    
    @patch('app.api.webhooks.settings')
    async def test_github_webhook_status_configured(
        self,
        mock_settings,
        client
    ):
        """Test GitHub webhook status endpoint when configured."""
        mock_settings.github_webhook_secret = "configured-secret"
        
        response = client.get("/api/v1/webhooks/github/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["webhook_secret_configured"] is True
        assert data["endpoint"] == "/api/v1/webhooks/github"
        assert "push" in data["supported_events"]
        assert data["signature_header"] == "X-Hub-Signature-256"
    
    @patch('app.api.webhooks.settings')
    async def test_github_webhook_status_not_configured(
        self,
        mock_settings,
        client
    ):
        """Test GitHub webhook status endpoint when not configured."""
        mock_settings.github_webhook_secret = None
        
        response = client.get("/api/v1/webhooks/github/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_configured"
        assert data["webhook_secret_configured"] is False