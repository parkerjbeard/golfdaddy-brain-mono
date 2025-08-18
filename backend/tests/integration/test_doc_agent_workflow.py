"""
Integration tests for the complete documentation agent workflow.
"""

import asyncio
import json
import subprocess
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.api.webhooks.slack_interactions import handle_slack_interactions
from app.config.settings import settings
from app.doc_agent.client import AutoDocClient
from app.models.doc_approval import DocApproval


@pytest.mark.integration
class TestDocAgentWorkflow:
    """Test the complete documentation agent workflow."""

    @pytest.fixture
    def mock_env(self):
        """Set up test environment variables."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "test-openai-key",
                "GITHUB_TOKEN": "test-github-token",
                "DOCS_REPOSITORY": "test-owner/test-docs",
                "SLACK_BOT_TOKEN": "test-slack-token",
                "SLACK_CHANNEL": "#test-docs",
            },
        ):
            yield

    @pytest.fixture
    def mock_git_repo(self, tmp_path):
        """Create a mock git repository."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)

        # Create initial commit
        test_file = repo_path / "README.md"
        test_file.write_text("# Test Project\n\nInitial content.")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

        # Create a change
        test_file.write_text("# Test Project\n\nInitial content.\n\n## New Section\n\nAdded content.")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Add new section"], cwd=repo_path, check=True)

        # Get latest commit hash
        commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_path, text=True).strip()

        return str(repo_path), commit_hash

    @pytest.mark.asyncio
    async def test_full_workflow_from_commit_to_pr(self, mock_env, mock_git_repo, db_session):
        """Test the complete workflow from commit analysis to PR creation."""
        repo_path, commit_hash = mock_git_repo

        # Step 1: Initialize doc agent client
        client = AutoDocClient(
            openai_api_key=settings.OPENAI_API_KEY,
            github_token=settings.GITHUB_TOKEN,
            docs_repo=settings.DOCS_REPOSITORY,
            slack_channel=settings.SLACK_CHANNEL,
        )

        # Step 2: Get commit diff
        diff = client.get_commit_diff(repo_path, commit_hash)
        assert diff != ""
        assert "New Section" in diff

        # Step 3: Mock OpenAI analysis
        mock_patch = """--- a/docs/README.md
+++ b/docs/README.md
@@ -2,3 +2,7 @@
 
 Initial content.
+
+## New Section
+
+Documentation for the new section that was added."""

        with patch.object(client, "analyze_diff", AsyncMock(return_value=mock_patch)):
            patch = await client.analyze_diff(diff)
            assert patch == mock_patch

        # Step 4: Send to Slack for approval
        with patch("app.services.slack_service.SlackService.send_message", AsyncMock(return_value={"ts": "123.456"})):
            approval_id = await client.propose_via_slack(
                diff=diff, patch=patch, commit_hash=commit_hash, commit_message="Add new section", db=db_session
            )

            assert approval_id is not None

            # Verify approval was created in database
            approval = await db_session.get(DocApproval, approval_id)
            assert approval is not None
            assert approval.status == "pending"
            assert approval.commit_hash == commit_hash

        # Step 5: Simulate Slack approval
        slack_payload = {
            "type": "block_actions",
            "user": {"id": "U123", "name": "approver"},
            "channel": {"id": "C123"},
            "message": {
                "ts": "123.456",
                "blocks": [{"type": "header", "text": {"text": "Documentation Update Request"}}],
            },
            "actions": [{"action_id": "approve_doc_update", "value": approval_id}],
        }

        # Mock the request object
        mock_request = Mock()
        mock_request.body = AsyncMock(return_value=json.dumps(slack_payload).encode())
        mock_request.headers = {
            "X-Slack-Request-Timestamp": str(int(datetime.now().timestamp())),
            "X-Slack-Signature": "valid",
        }
        mock_request.form = AsyncMock(return_value={"payload": json.dumps(slack_payload)})

        # Mock GitHub PR creation
        with patch(
            "doc_agent.client.AutoDocClient.apply_patch",
            return_value="https://github.com/test-owner/test-docs/pull/123",
        ):
            with patch("app.api.webhooks.slack_interactions.verify_slack_signature", return_value=True):
                with patch("app.services.slack_service.SlackService") as mock_slack:
                    mock_slack_instance = Mock()
                    mock_slack_instance.client = Mock()
                    mock_slack_instance.client.chat_update = AsyncMock()
                    mock_slack.return_value = mock_slack_instance

                    # Handle the approval
                    response = await handle_slack_interactions(mock_request, db_session)

                    assert "approved" in response["text"]
                    assert "https://github.com/test-owner/test-docs/pull/123" in response["text"]

        # Step 6: Verify approval was updated
        await db_session.refresh(approval)
        assert approval.status == "approved"
        assert approval.approved_by == "U123"
        assert approval.pr_url == "https://github.com/test-owner/test-docs/pull/123"

    @pytest.mark.asyncio
    async def test_workflow_with_rejection(self, mock_env, db_session):
        """Test workflow when documentation update is rejected."""
        # Create a pending approval
        approval = DocApproval(
            id=uuid.uuid4(),
            commit_hash="test123",
            repository="test-owner/test-repo",
            diff_content="test diff",
            patch_content="test patch",
            status="pending",
            slack_channel="#test",
            slack_message_ts="123.456",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            metadata={"commit_message": "Test commit"},
        )
        db_session.add(approval)
        await db_session.commit()

        # Simulate rejection
        slack_payload = {
            "type": "block_actions",
            "user": {"id": "U456", "name": "reviewer"},
            "channel": {"id": "C123"},
            "message": {"ts": "123.456", "blocks": []},
            "actions": [{"action_id": "reject_doc_update", "value": str(approval.id)}],
        }

        mock_request = Mock()
        mock_request.body = AsyncMock(return_value=json.dumps(slack_payload).encode())
        mock_request.headers = {
            "X-Slack-Request-Timestamp": str(int(datetime.now().timestamp())),
            "X-Slack-Signature": "valid",
        }
        mock_request.form = AsyncMock(return_value={"payload": json.dumps(slack_payload)})

        with patch("app.api.webhooks.slack_interactions.verify_slack_signature", return_value=True):
            with patch("app.services.slack_service.SlackService") as mock_slack:
                mock_slack_instance = Mock()
                mock_slack_instance.client = Mock()
                mock_slack_instance.client.chat_update = AsyncMock()
                mock_slack.return_value = mock_slack_instance

                response = await handle_slack_interactions(mock_request, db_session)

                assert "rejected" in response["text"]

        # Verify approval was rejected
        await db_session.refresh(approval)
        assert approval.status == "rejected"
        assert approval.approved_by == "U456"
        assert approval.pr_url is None

    @pytest.mark.asyncio
    async def test_workflow_expiration_handling(self, db_session):
        """Test handling of expired approvals."""
        # Create an expired approval
        approval = DocApproval(
            id=uuid.uuid4(),
            commit_hash="expired123",
            repository="test-owner/test-repo",
            diff_content="test diff",
            patch_content="test patch",
            status="pending",
            slack_channel="#test",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Already expired
            metadata={},
        )
        db_session.add(approval)
        await db_session.commit()

        # Try to approve expired request
        slack_payload = {
            "type": "block_actions",
            "user": {"id": "U789", "name": "late_approver"},
            "actions": [{"action_id": "approve_doc_update", "value": str(approval.id)}],
        }

        mock_request = Mock()
        mock_request.body = AsyncMock(return_value=json.dumps(slack_payload).encode())
        mock_request.headers = {
            "X-Slack-Request-Timestamp": str(int(datetime.now().timestamp())),
            "X-Slack-Signature": "valid",
        }
        mock_request.form = AsyncMock(return_value={"payload": json.dumps(slack_payload)})

        with patch("app.api.webhooks.slack_interactions.verify_slack_signature", return_value=True):
            response = await handle_slack_interactions(mock_request, db_session)

            # Should get ephemeral response about expiration
            assert response["response_type"] == "ephemeral"
            assert "expired" in response["text"].lower()

        # Verify status was updated to expired
        await db_session.refresh(approval)
        assert approval.status == "expired"

    @pytest.mark.asyncio
    async def test_concurrent_approval_handling(self, db_session):
        """Test handling of concurrent approval attempts."""
        # Create a pending approval
        approval = DocApproval(
            id=uuid.uuid4(),
            commit_hash="concurrent123",
            repository="test-owner/test-repo",
            diff_content="test diff",
            patch_content="test patch",
            status="pending",
            slack_channel="#test",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            metadata={},
        )
        db_session.add(approval)
        await db_session.commit()

        # Simulate two concurrent approval attempts
        async def approve_attempt(user_id: str):
            payload = {
                "type": "block_actions",
                "user": {"id": user_id, "name": f"user_{user_id}"},
                "channel": {"id": "C123"},
                "message": {"ts": "123.456", "blocks": []},
                "actions": [{"action_id": "approve_doc_update", "value": str(approval.id)}],
            }

            mock_request = Mock()
            mock_request.body = AsyncMock(return_value=json.dumps(payload).encode())
            mock_request.headers = {
                "X-Slack-Request-Timestamp": str(int(datetime.now().timestamp())),
                "X-Slack-Signature": "valid",
            }
            mock_request.form = AsyncMock(return_value={"payload": json.dumps(payload)})

            with patch("app.api.webhooks.slack_interactions.verify_slack_signature", return_value=True):
                with patch(
                    "doc_agent.client.AutoDocClient.apply_patch", return_value=f"https://github.com/test/pr/{user_id}"
                ):
                    with patch("app.services.slack_service.SlackService") as mock_slack:
                        mock_slack_instance = Mock()
                        mock_slack_instance.client = Mock()
                        mock_slack_instance.client.chat_update = AsyncMock()
                        mock_slack.return_value = mock_slack_instance

                        return await handle_slack_interactions(mock_request, db_session)

        # Run concurrent approvals
        results = await asyncio.gather(approve_attempt("U1"), approve_attempt("U2"), return_exceptions=True)

        # One should succeed, one should get "already processed" message
        success_count = sum(1 for r in results if not isinstance(r, Exception) and "approved" in r.get("text", ""))
        already_processed_count = sum(
            1 for r in results if not isinstance(r, Exception) and "already been" in r.get("text", "")
        )

        assert success_count == 1
        assert already_processed_count == 1

        # Verify only one approval was recorded
        await db_session.refresh(approval)
        assert approval.status == "approved"
        assert approval.approved_by in ["U1", "U2"]
