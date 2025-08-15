"""
Unit tests for Slack webhook interactions endpoint.
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.webhooks.slack_interactions import (
    handle_block_actions,
    handle_doc_approval,
    handle_doc_rejection,
    handle_slack_interactions,
    handle_view_full_diff,
    verify_slack_signature,
)
from app.models.doc_approval import DocApproval


class TestSlackSignatureVerification:
    """Test Slack signature verification."""

    def test_verify_slack_signature_valid(self):
        """Test valid Slack signature verification."""
        secret = "test_secret"
        timestamp = str(int(time.time()))
        body = b"test_body"

        # Create valid signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        signature = "v0=" + hmac.new(secret.encode("utf-8"), sig_basestring.encode("utf-8"), hashlib.sha256).hexdigest()

        with patch("app.config.settings.settings.SLACK_SIGNING_SECRET", secret):
            assert verify_slack_signature(body, timestamp, signature) is True

    def test_verify_slack_signature_invalid(self):
        """Test invalid Slack signature verification."""
        with patch("app.config.settings.settings.SLACK_SIGNING_SECRET", "secret"):
            assert verify_slack_signature(b"body", "123", "invalid_sig") is False

    def test_verify_slack_signature_expired_timestamp(self):
        """Test signature with expired timestamp."""
        secret = "test_secret"
        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time() - 600))
        body = b"test_body"

        sig_basestring = f"v0:{old_timestamp}:{body.decode('utf-8')}"
        signature = "v0=" + hmac.new(secret.encode("utf-8"), sig_basestring.encode("utf-8"), hashlib.sha256).hexdigest()

        with patch("app.config.settings.settings.SLACK_SIGNING_SECRET", secret):
            assert verify_slack_signature(body, old_timestamp, signature) is False

    def test_verify_slack_signature_no_secret(self):
        """Test signature verification without secret configured."""
        with patch("app.config.settings.settings.SLACK_SIGNING_SECRET", None):
            assert verify_slack_signature(b"body", "123", "sig") is False


@pytest.mark.asyncio
class TestSlackInteractionsEndpoint:
    """Test Slack interactions endpoint."""

    async def test_handle_slack_interactions_invalid_signature(self):
        """Test endpoint rejects invalid signature."""
        mock_request = Mock()
        mock_request.body = AsyncMock(return_value=b"test_body")
        mock_request.headers = {"X-Slack-Request-Timestamp": "123", "X-Slack-Signature": "invalid"}

        mock_db = AsyncMock()

        with patch("app.api.webhooks.slack_interactions.verify_slack_signature", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await handle_slack_interactions(mock_request, mock_db)

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == "Invalid signature"

    async def test_handle_slack_interactions_no_payload(self):
        """Test endpoint handles missing payload."""
        mock_request = Mock()
        mock_request.body = AsyncMock(return_value=b"test_body")
        mock_request.headers = {"X-Slack-Request-Timestamp": "123", "X-Slack-Signature": "valid"}
        mock_request.form = AsyncMock(return_value={"not_payload": "value"})

        mock_db = AsyncMock()

        with patch("app.api.webhooks.slack_interactions.verify_slack_signature", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await handle_slack_interactions(mock_request, mock_db)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "No payload"

    async def test_handle_slack_interactions_invalid_json(self):
        """Test endpoint handles invalid JSON payload."""
        mock_request = Mock()
        mock_request.body = AsyncMock(return_value=b"test_body")
        mock_request.headers = {"X-Slack-Request-Timestamp": "123", "X-Slack-Signature": "valid"}
        mock_request.form = AsyncMock(return_value={"payload": "invalid json"})

        mock_db = AsyncMock()

        with patch("app.api.webhooks.slack_interactions.verify_slack_signature", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await handle_slack_interactions(mock_request, mock_db)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "Invalid JSON payload"

    async def test_handle_slack_interactions_block_actions(self):
        """Test handling block actions."""
        payload = {"type": "block_actions", "actions": [{"action_id": "test_action", "value": "test_value"}]}

        mock_request = Mock()
        mock_request.body = AsyncMock(return_value=b"test_body")
        mock_request.headers = {"X-Slack-Request-Timestamp": "123", "X-Slack-Signature": "valid"}
        mock_request.form = AsyncMock(return_value={"payload": json.dumps(payload)})

        mock_db = AsyncMock()

        with patch("app.api.webhooks.slack_interactions.verify_slack_signature", return_value=True):
            with patch(
                "app.api.webhooks.slack_interactions.handle_block_actions", return_value={"text": "handled"}
            ) as mock_handler:
                result = await handle_slack_interactions(mock_request, mock_db)

                assert result == {"text": "handled"}
                mock_handler.assert_called_once_with(payload, mock_db)


@pytest.mark.asyncio
class TestDocApprovalHandlers:
    """Test document approval handlers."""

    @pytest.fixture
    def mock_approval(self):
        """Create a mock approval."""
        return DocApproval(
            id=uuid.uuid4(),
            commit_hash="abc123def456",
            repository="test-owner/test-repo",
            diff_content="diff content",
            patch_content="patch content",
            status="pending",
            slack_channel="#test",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            metadata={"commit_message": "Test commit", "files_affected": 2, "additions": 10, "deletions": 5},
        )

    async def test_handle_doc_approval_success(self, mock_approval):
        """Test successful document approval."""
        approval_id = str(mock_approval.id)
        payload = {
            "user": {"id": "U123", "name": "testuser"},
            "channel": {"id": "C123"},
            "message": {"ts": "123.456", "blocks": [{"type": "header"}]},
        }

        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_approval
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock AutoDocClient
        with patch("app.api.webhooks.slack_interactions.AutoDocClient") as mock_client_class:
            mock_client = Mock()
            mock_client.apply_patch = Mock(return_value="https://github.com/test/pr/1")
            mock_client_class.return_value = mock_client

            # Mock SlackService
            with patch("app.api.webhooks.slack_interactions.SlackService") as mock_slack_class:
                mock_slack = Mock()
                mock_slack.client = Mock()
                mock_slack.client.chat_update = AsyncMock()
                mock_slack_class.return_value = mock_slack

                result = await handle_doc_approval(approval_id, payload, mock_db)

                assert result["response_type"] == "in_channel"
                assert "approved by testuser" in result["text"]
                assert "https://github.com/test/pr/1" in result["text"]

                # Verify approval was updated
                assert mock_approval.status == "approved"
                assert mock_approval.approved_by == "U123"
                assert mock_approval.pr_url == "https://github.com/test/pr/1"
                mock_db.commit.assert_called()

    async def test_handle_doc_approval_not_found(self):
        """Test approval handler when approval not found."""
        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await handle_doc_approval("nonexistent", {}, mock_db)

        assert result["response_type"] == "ephemeral"
        assert "not found" in result["text"]

    async def test_handle_doc_approval_already_processed(self, mock_approval):
        """Test approval handler when already processed."""
        mock_approval.status = "approved"

        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_approval
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await handle_doc_approval(str(mock_approval.id), {}, mock_db)

        assert result["response_type"] == "ephemeral"
        assert "already been approved" in result["text"]

    async def test_handle_doc_approval_expired(self, mock_approval):
        """Test approval handler when expired."""
        mock_approval.expires_at = datetime.utcnow() - timedelta(hours=1)

        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_approval
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await handle_doc_approval(str(mock_approval.id), {}, mock_db)

        assert result["response_type"] == "ephemeral"
        assert "expired" in result["text"]
        assert mock_approval.status == "expired"

    async def test_handle_doc_rejection_success(self, mock_approval):
        """Test successful document rejection."""
        approval_id = str(mock_approval.id)
        payload = {
            "user": {"id": "U123", "name": "testuser"},
            "channel": {"id": "C123"},
            "message": {"ts": "123.456", "blocks": [{"type": "header"}]},
        }

        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_approval
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.webhooks.slack_interactions.SlackService") as mock_slack_class:
            mock_slack = Mock()
            mock_slack.client = Mock()
            mock_slack.client.chat_update = AsyncMock()
            mock_slack_class.return_value = mock_slack

            result = await handle_doc_rejection(approval_id, payload, mock_db)

            assert result["response_type"] == "in_channel"
            assert "rejected by testuser" in result["text"]

            # Verify approval was updated
            assert mock_approval.status == "rejected"
            assert mock_approval.approved_by == "U123"
            mock_db.commit.assert_called()

    async def test_handle_view_full_diff(self, mock_approval):
        """Test viewing full diff."""
        approval_id = str(mock_approval.id)
        payload = {"user": {"id": "U123"}}

        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_approval
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await handle_view_full_diff(approval_id, payload, mock_db)

        assert result["response_type"] == "ephemeral"
        assert "Full Documentation Diff" in str(result["blocks"])
        assert mock_approval.diff_content in str(result["blocks"])

    async def test_handle_block_actions_unknown_action(self):
        """Test handling unknown action."""
        payload = {"actions": [{"action_id": "unknown_action", "value": "test"}]}
        mock_db = AsyncMock()

        result = await handle_block_actions(payload, mock_db)

        assert result["text"] == "Action received"

    async def test_handle_block_actions_no_actions(self):
        """Test handling payload with no actions."""
        payload = {"actions": []}
        mock_db = AsyncMock()

        result = await handle_block_actions(payload, mock_db)

        assert result["text"] == "No actions found"
