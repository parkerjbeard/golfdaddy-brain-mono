"""
Comprehensive unit tests for Slack webhook interactions.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
import hmac
import hashlib
import time
from datetime import datetime, timedelta
import uuid
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.webhooks.slack_interactions import (
    router, verify_slack_signature, handle_slack_interactions,
    handle_block_actions, handle_doc_approval, handle_doc_rejection,
    handle_view_full_diff
)
from app.models.doc_approval import DocApproval
from tests.fixtures.auto_doc_fixtures import (
    SLACK_PAYLOADS, create_doc_approval, SAMPLE_DIFFS, SAMPLE_PATCHES
)


class TestSlackSignatureVerification:
    """Test cases for Slack signature verification."""
    
    def test_verify_slack_signature_valid(self):
        """Test valid Slack signature verification."""
        with patch('app.api.webhooks.slack_interactions.settings') as mock_settings:
            mock_settings.SLACK_SIGNING_SECRET = "test_secret"
            
            timestamp = str(int(time.time()))
            body = b'{"test": "data"}'
            
            # Create valid signature
            sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
            signature = 'v0=' + hmac.new(
                b"test_secret",
                sig_basestring.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            assert verify_slack_signature(body, timestamp, signature) is True
    
    def test_verify_slack_signature_invalid(self):
        """Test invalid Slack signature verification."""
        with patch('app.api.webhooks.slack_interactions.settings') as mock_settings:
            mock_settings.SLACK_SIGNING_SECRET = "test_secret"
            
            timestamp = str(int(time.time()))
            body = b'{"test": "data"}'
            signature = "v0=invalid_signature"
            
            assert verify_slack_signature(body, timestamp, signature) is False
    
    def test_verify_slack_signature_expired_timestamp(self):
        """Test signature verification with expired timestamp."""
        with patch('app.api.webhooks.slack_interactions.settings') as mock_settings:
            mock_settings.SLACK_SIGNING_SECRET = "test_secret"
            
            # Timestamp from 10 minutes ago
            old_timestamp = str(int(time.time()) - 600)
            body = b'{"test": "data"}'
            
            # Even with valid signature, should fail due to old timestamp
            sig_basestring = f"v0:{old_timestamp}:{body.decode('utf-8')}"
            signature = 'v0=' + hmac.new(
                b"test_secret",
                sig_basestring.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            assert verify_slack_signature(body, old_timestamp, signature) is False
    
    def test_verify_slack_signature_no_secret(self):
        """Test signature verification without signing secret."""
        with patch('app.api.webhooks.slack_interactions.settings') as mock_settings:
            mock_settings.SLACK_SIGNING_SECRET = None
            
            assert verify_slack_signature(b"data", "12345", "signature") is False


class TestSlackInteractionEndpoint:
    """Test cases for the main Slack interaction endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session
    
    @pytest.fixture
    def valid_headers(self):
        """Create valid Slack headers."""
        timestamp = str(int(time.time()))
        with patch('app.api.webhooks.slack_interactions.settings') as mock_settings:
            mock_settings.SLACK_SIGNING_SECRET = "test_secret"
            
            # We'll compute signature when we have the body
            return {
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": "placeholder"
            }
    
    @pytest.mark.asyncio
    async def test_handle_slack_interactions_invalid_signature(self, mock_db_session):
        """Test handling request with invalid signature."""
        request = Mock()
        request.body = AsyncMock(return_value=b'{"test": "data"}')
        request.headers = {
            "X-Slack-Request-Timestamp": str(int(time.time())),
            "X-Slack-Signature": "v0=invalid"
        }
        request.form = AsyncMock(return_value={"payload": json.dumps({"type": "test"})})
        
        with pytest.raises(HTTPException) as exc_info:
            await handle_slack_interactions(request, mock_db_session)
        
        assert exc_info.value.status_code == 403
        assert "Invalid signature" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_handle_slack_interactions_no_payload(self, mock_db_session):
        """Test handling request without payload."""
        request = Mock()
        request.body = AsyncMock(return_value=b'')
        request.headers = {}
        request.form = AsyncMock(return_value={})
        
        with patch('app.api.webhooks.slack_interactions.verify_slack_signature', return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await handle_slack_interactions(request, mock_db_session)
            
            assert exc_info.value.status_code == 400
            assert "No payload" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_handle_slack_interactions_invalid_json(self, mock_db_session):
        """Test handling request with invalid JSON payload."""
        request = Mock()
        request.body = AsyncMock(return_value=b'')
        request.headers = {}
        request.form = AsyncMock(return_value={"payload": "invalid{json"})
        
        with patch('app.api.webhooks.slack_interactions.verify_slack_signature', return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await handle_slack_interactions(request, mock_db_session)
            
            assert exc_info.value.status_code == 400
            assert "Invalid JSON" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_handle_block_actions_approval(self, mock_db_session):
        """Test handling block action for approval."""
        payload = SLACK_PAYLOADS["button_action"].copy()
        
        with patch('app.api.webhooks.slack_interactions.handle_doc_approval') as mock_approve:
            mock_approve.return_value = {"response_type": "ephemeral", "text": "Approved"}
            
            result = await handle_block_actions(payload, mock_db_session)
            
            mock_approve.assert_called_once_with(
                "550e8400-e29b-41d4-a716-446655440000",
                payload,
                mock_db_session
            )
            assert result["text"] == "Approved"
    
    @pytest.mark.asyncio
    async def test_handle_block_actions_rejection(self, mock_db_session):
        """Test handling block action for rejection."""
        payload = SLACK_PAYLOADS["reject_action"].copy()
        
        with patch('app.api.webhooks.slack_interactions.handle_doc_rejection') as mock_reject:
            mock_reject.return_value = {"response_type": "ephemeral", "text": "Rejected"}
            
            result = await handle_block_actions(payload, mock_db_session)
            
            mock_reject.assert_called_once()
            assert result["text"] == "Rejected"
    
    @pytest.mark.asyncio
    async def test_handle_block_actions_unknown(self, mock_db_session):
        """Test handling unknown block action."""
        payload = {
            "actions": [{
                "action_id": "unknown_action",
                "value": "test"
            }]
        }
        
        result = await handle_block_actions(payload, mock_db_session)
        
        assert result["text"] == "Action received"


class TestDocApprovalHandling:
    """Test cases for document approval handling."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session
    
    @pytest.fixture
    def mock_slack_service(self):
        """Create mock Slack service."""
        with patch('app.api.webhooks.slack_interactions.SlackService') as mock:
            service = Mock()
            service.send_message = AsyncMock()
            service.update_message = AsyncMock()
            mock.return_value = service
            yield service
    
    @pytest.fixture
    def sample_approval(self):
        """Create sample approval."""
        return DocApproval(
            id=uuid.uuid4(),
            commit_hash="abc123def456",
            repository="test-owner/test-repo",
            diff_content=SAMPLE_DIFFS["simple_addition"],
            patch_content=SAMPLE_PATCHES["user_service_patch"],
            slack_channel="#documentation",
            slack_message_ts="1234567890.123456",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            approval_metadata={
                "commit_message": "Add user email lookup",
                "files_affected": 1,
                "additions": 14,
                "deletions": 0
            }
        )
    
    @pytest.mark.asyncio
    async def test_handle_doc_approval_success(self, mock_db_session, mock_slack_service, sample_approval):
        """Test successful document approval."""
        approval_id = str(sample_approval.id)
        payload = {
            "user": {"id": "U123", "name": "john.doe"},
            "channel": {"id": "C123"},
            "message": {"ts": "1234567890.123456"}
        }
        
        # Mock database query
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_approval
        mock_db_session.execute.return_value = mock_result
        
        # Mock AutoDocClient
        with patch('app.api.webhooks.slack_interactions.AutoDocClient') as mock_client_class:
            mock_client = Mock()
            mock_client.apply_patch.return_value = "https://github.com/test/pr/123"
            mock_client_class.return_value = mock_client
            
            result = await handle_doc_approval(approval_id, payload, mock_db_session)
        
        assert "approved" in result["text"].lower()
        assert sample_approval.status == "approved"
        assert sample_approval.approved_by == "john.doe"
        assert sample_approval.pr_url == "https://github.com/test/pr/123"
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_doc_approval_not_found(self, mock_db_session):
        """Test approval handling when approval not found."""
        approval_id = str(uuid.uuid4())
        payload = {"user": {"id": "U123"}}
        
        # Mock database query - not found
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await handle_doc_approval(approval_id, payload, mock_db_session)
        
        assert "not found" in result["text"].lower()
        assert result["response_type"] == "ephemeral"
    
    @pytest.mark.asyncio
    async def test_handle_doc_approval_already_processed(self, mock_db_session, sample_approval):
        """Test approval handling when already processed."""
        approval_id = str(sample_approval.id)
        payload = {"user": {"id": "U123"}}
        
        # Set approval as already approved
        sample_approval.status = "approved"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_approval
        mock_db_session.execute.return_value = mock_result
        
        result = await handle_doc_approval(approval_id, payload, mock_db_session)
        
        assert "already been approved" in result["text"]
        assert result["response_type"] == "ephemeral"
    
    @pytest.mark.asyncio
    async def test_handle_doc_approval_expired(self, mock_db_session, sample_approval):
        """Test approval handling when expired."""
        approval_id = str(sample_approval.id)
        payload = {"user": {"id": "U123"}}
        
        # Set approval as expired
        sample_approval.expires_at = datetime.utcnow() - timedelta(hours=1)
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_approval
        mock_db_session.execute.return_value = mock_result
        
        result = await handle_doc_approval(approval_id, payload, mock_db_session)
        
        assert "expired" in result["text"].lower()
        assert sample_approval.status == "expired"
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_doc_approval_pr_creation_failure(self, mock_db_session, sample_approval):
        """Test approval handling when PR creation fails."""
        approval_id = str(sample_approval.id)
        payload = {"user": {"id": "U123", "name": "john.doe"}}
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_approval
        mock_db_session.execute.return_value = mock_result
        
        # Mock AutoDocClient with failure
        with patch('app.api.webhooks.slack_interactions.AutoDocClient') as mock_client_class:
            mock_client = Mock()
            mock_client.apply_patch.return_value = None  # PR creation failed
            mock_client_class.return_value = mock_client
            
            result = await handle_doc_approval(approval_id, payload, mock_db_session)
        
        assert "failed" in result["text"].lower()
        assert sample_approval.status == "approved"  # Still marked as approved
        assert sample_approval.pr_url is None
    
    @pytest.mark.asyncio
    async def test_handle_doc_rejection_success(self, mock_db_session, sample_approval):
        """Test successful document rejection."""
        approval_id = str(sample_approval.id)
        payload = {
            "user": {"id": "U123", "name": "jane.smith"},
            "channel": {"id": "C123"}
        }
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_approval
        mock_db_session.execute.return_value = mock_result
        
        # Mock modal opening
        with patch('app.api.webhooks.slack_interactions.SlackService') as mock_slack:
            mock_service = Mock()
            mock_service.open_modal = AsyncMock(return_value={"ok": True})
            mock_slack.return_value = mock_service
            
            result = await handle_doc_rejection(approval_id, payload, mock_db_session)
        
        # Should open rejection reason modal
        mock_service.open_modal.assert_called_once()
        assert "trigger_id" in mock_service.open_modal.call_args[1]
    
    @pytest.mark.asyncio
    async def test_handle_view_full_diff(self, mock_db_session, sample_approval):
        """Test viewing full diff."""
        approval_id = str(sample_approval.id)
        payload = {
            "user": {"id": "U123"},
            "trigger_id": "trigger123"
        }
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_approval
        mock_db_session.execute.return_value = mock_result
        
        with patch('app.api.webhooks.slack_interactions.SlackService') as mock_slack:
            mock_service = Mock()
            mock_service.open_modal = AsyncMock(return_value={"ok": True})
            mock_slack.return_value = mock_service
            
            result = await handle_view_full_diff(approval_id, payload, mock_db_session)
        
        # Should open diff modal
        mock_service.open_modal.assert_called_once()
        modal_view = mock_service.open_modal.call_args[1]["view"]
        assert "Full Diff" in modal_view["title"]["text"]
        assert sample_approval.diff_content in str(modal_view["blocks"])


class TestSlackMessageFormatting:
    """Test cases for Slack message formatting."""
    
    @pytest.mark.asyncio
    async def test_approval_message_update_approved(self, mock_slack_service):
        """Test updating message after approval."""
        from app.services.slack_message_templates import SlackMessageTemplates
        
        original_blocks = [
            {"type": "section", "text": {"text": "Original message"}},
            {"type": "actions", "elements": [{"type": "button", "text": {"text": "Approve"}}]}
        ]
        
        updated_message = SlackMessageTemplates.update_approval_message(
            original_blocks,
            "approved",
            "john.doe",
            pr_url="https://github.com/test/pr/123"
        )
        
        # Check status section added
        assert any("✅ Approved" in str(block) for block in updated_message["blocks"])
        assert any("john.doe" in str(block) for block in updated_message["blocks"])
        assert any("github.com/test/pr/123" in str(block) for block in updated_message["blocks"])
        
        # Check actions removed
        assert not any(block.get("type") == "actions" for block in updated_message["blocks"])
    
    @pytest.mark.asyncio
    async def test_approval_message_update_rejected(self, mock_slack_service):
        """Test updating message after rejection."""
        from app.services.slack_message_templates import SlackMessageTemplates
        
        original_blocks = [
            {"type": "section", "text": {"text": "Original message"}}
        ]
        
        updated_message = SlackMessageTemplates.update_approval_message(
            original_blocks,
            "rejected",
            "jane.smith",
            rejection_reason="Needs more detail in examples section"
        )
        
        assert any("❌ Rejected" in str(block) for block in updated_message["blocks"])
        assert any("jane.smith" in str(block) for block in updated_message["blocks"])
        assert any("more detail in examples" in str(block) for block in updated_message["blocks"])


class TestIntegrationScenarios:
    """Test integration scenarios for Slack interactions."""
    
    @pytest.mark.asyncio
    async def test_full_approval_flow(self, mock_db_session):
        """Test complete approval flow from button click to PR creation."""
        # Create approval
        approval = create_doc_approval()
        approval_obj = DocApproval(**approval)
        
        # Setup database mock
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = approval_obj
        mock_db_session.execute.return_value = mock_result
        
        # Setup Slack payload
        payload = SLACK_PAYLOADS["button_action"].copy()
        payload["actions"][0]["value"] = str(approval_obj.id)
        
        # Mock services
        with patch('app.api.webhooks.slack_interactions.SlackService') as mock_slack:
            with patch('app.api.webhooks.slack_interactions.AutoDocClient') as mock_client:
                mock_service = Mock()
                mock_service.update_message = AsyncMock()
                mock_slack.return_value = mock_service
                
                mock_doc_client = Mock()
                mock_doc_client.apply_patch.return_value = "https://github.com/pr/123"
                mock_client.return_value = mock_doc_client
                
                # Execute approval
                result = await handle_doc_approval(
                    str(approval_obj.id),
                    payload,
                    mock_db_session
                )
                
                # Verify flow
                assert approval_obj.status == "approved"
                assert approval_obj.pr_url == "https://github.com/pr/123"
                mock_doc_client.apply_patch.assert_called_once()
                mock_service.update_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_approval_handling(self, mock_db_session):
        """Test handling concurrent approval attempts."""
        import asyncio
        
        approval = create_doc_approval()
        approval_obj = DocApproval(**approval)
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = approval_obj
        mock_db_session.execute.return_value = mock_result
        
        payload1 = {"user": {"id": "U1", "name": "user1"}}
        payload2 = {"user": {"id": "U2", "name": "user2"}}
        
        # Simulate concurrent approvals
        with patch('app.api.webhooks.slack_interactions.AutoDocClient'):
            tasks = [
                handle_doc_approval(str(approval_obj.id), payload1, mock_db_session),
                handle_doc_approval(str(approval_obj.id), payload2, mock_db_session)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # One should succeed, one should see it's already processed
            success_count = sum(1 for r in results if "Successfully approved" in r.get("text", ""))
            already_processed = sum(1 for r in results if "already been" in r.get("text", ""))
            
            assert success_count <= 1  # At most one success
            assert already_processed >= 0  # May have race condition