"""
Comprehensive tests for Slack Conversation Handler
"""

import json
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.models.daily_report import DailyReport, DailyReportCreate
from app.models.user import User, UserRole
from app.services.slack_conversation_handler import ConversationState, SlackConversationHandler


@pytest.fixture
def mock_slack_service():
    return Mock()


@pytest.fixture
def mock_daily_report_service():
    return Mock()


@pytest.fixture
def mock_user_repo():
    return Mock()


@pytest.fixture
def mock_slack_templates():
    return Mock()


@pytest.fixture
def conversation_handler(mock_slack_service, mock_daily_report_service, mock_user_repo, mock_slack_templates):
    handler = SlackConversationHandler()
    handler.slack_service = mock_slack_service
    handler.daily_report_service = mock_daily_report_service
    handler.user_repo = mock_user_repo
    handler.templates = mock_slack_templates
    return handler


@pytest.fixture
def sample_user():
    return User(
        id=uuid4(),
        email="developer@test.com",
        name="Test Developer",
        role=UserRole.EMPLOYEE,
        is_active=True,
        slack_id="U123456",
    )


@pytest.fixture
def sample_daily_report():
    return DailyReport(
        id=uuid4(),
        user_id=uuid4(),
        date=date.today(),
        content="Initial report content",
        needs_clarification=True,
        clarification_questions=["What specific features did you work on?"],
        conversation_history=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def slack_event_message():
    """Sample Slack message event"""
    return {
        "type": "message",
        "channel": "D123456",  # DM channel
        "user": "U123456",
        "text": "I worked on the authentication feature and fixed login bugs",
        "ts": "1234567890.123456",
        "thread_ts": "1234567890.123456",
    }


@pytest.fixture
def slack_slash_command():
    """Sample Slack slash command"""
    return {
        "token": "verification_token",
        "team_id": "T123456",
        "team_domain": "test-team",
        "channel_id": "D123456",
        "channel_name": "directmessage",
        "user_id": "U123456",
        "user_name": "testuser",
        "command": "/eod",
        "text": "Completed feature X and reviewed PRs",
        "response_url": "https://hooks.slack.com/commands/123/456",
        "trigger_id": "123456.789012",
    }


@pytest.fixture
def slack_view_submission():
    """Sample Slack view submission (modal)"""
    return {
        "type": "view_submission",
        "team": {"id": "T123456", "domain": "test-team"},
        "user": {"id": "U123456", "username": "testuser"},
        "view": {
            "id": "V123456",
            "type": "modal",
            "callback_id": "eod_report_modal",
            "state": {
                "values": {
                    "report_content": {
                        "content": {"type": "plain_text_input", "value": "Worked on API integration and documentation"}
                    },
                    "hours_worked": {"hours": {"type": "plain_text_input", "value": "7.5"}},
                    "blockers": {"blockers": {"type": "plain_text_input", "value": "Waiting for design review"}},
                }
            },
            "private_metadata": json.dumps({"report_date": str(date.today())}),
        },
    }


class TestSlackConversationHandler:
    """Test cases for SlackConversationHandler"""

    @pytest.mark.asyncio
    async def test_handle_slash_command_eod(self, conversation_handler, mock_slack_templates, slack_slash_command):
        """Test handling /eod slash command"""
        # Arrange
        mock_slack_templates.eod_report_modal.return_value = {
            "type": "modal",
            "title": {"type": "plain_text", "text": "End of Day Report"},
            "blocks": [],
        }
        conversation_handler.slack_service.open_modal = AsyncMock(return_value=True)

        # Act
        result = await conversation_handler.handle_slash_command(slack_slash_command)

        # Assert
        assert result["response_type"] == "ephemeral"
        assert "Opening EOD report form" in result["text"]
        conversation_handler.slack_service.open_modal.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_slash_command_with_text(
        self, conversation_handler, mock_user_repo, mock_daily_report_service, sample_user, slack_slash_command
    ):
        """Test handling /eod command with text (quick submission)"""
        # Arrange
        slack_slash_command["text"] = "Completed all tasks for the sprint"
        mock_user_repo.get_user_by_slack_id.return_value = sample_user
        mock_daily_report_service.create_daily_report = AsyncMock(
            return_value=DailyReport(
                id=uuid4(),
                user_id=sample_user.id,
                date=date.today(),
                content=slack_slash_command["text"],
                hours_worked=8.0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

        # Act
        result = await conversation_handler.handle_slash_command(slack_slash_command)

        # Assert
        assert result["response_type"] == "ephemeral"
        assert "report has been submitted" in result["text"]
        mock_daily_report_service.create_daily_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_view_submission_success(
        self, conversation_handler, mock_user_repo, mock_daily_report_service, sample_user, slack_view_submission
    ):
        """Test successful modal submission"""
        # Arrange
        mock_user_repo.get_user_by_slack_id.return_value = sample_user
        created_report = DailyReport(
            id=uuid4(),
            user_id=sample_user.id,
            date=date.today(),
            content="Worked on API integration and documentation",
            hours_worked=7.5,
            blockers=["Waiting for design review"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_daily_report_service.create_daily_report = AsyncMock(return_value=created_report)

        # Act
        result = await conversation_handler.handle_view_submission(slack_view_submission)

        # Assert
        assert result is None  # Successful submission returns None to close modal
        mock_daily_report_service.create_daily_report.assert_called_once()

        # Verify the report data
        call_args = mock_daily_report_service.create_daily_report.call_args[0][0]
        assert call_args.content == "Worked on API integration and documentation"
        assert "7.5" in str(call_args.model_dump())  # Hours should be included
        assert "Waiting for design review" in str(call_args.model_dump())

    @pytest.mark.asyncio
    async def test_handle_view_submission_with_clarification(
        self,
        conversation_handler,
        mock_user_repo,
        mock_daily_report_service,
        mock_slack_service,
        sample_user,
        slack_view_submission,
    ):
        """Test modal submission that needs clarification"""
        # Arrange
        mock_user_repo.get_user_by_slack_id.return_value = sample_user
        report_with_clarification = DailyReport(
            id=uuid4(),
            user_id=sample_user.id,
            date=date.today(),
            content="Did some work",
            needs_clarification=True,
            clarification_questions=["What specific work did you complete?"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_daily_report_service.create_daily_report = AsyncMock(return_value=report_with_clarification)
        mock_slack_service.open_dm = AsyncMock(return_value="D123456")
        mock_slack_service.send_message = AsyncMock(return_value=True)

        # Act
        result = await conversation_handler.handle_view_submission(slack_view_submission)

        # Assert
        assert result is None  # Modal closes
        # Verify clarification message was sent
        mock_slack_service.open_dm.assert_called_once_with(sample_user.slack_id)
        mock_slack_service.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_handle_message_event_clarification_response(
        self,
        conversation_handler,
        mock_user_repo,
        mock_daily_report_service,
        sample_user,
        sample_daily_report,
        slack_event_message,
    ):
        """Test handling clarification response in thread"""
        # Arrange
        mock_user_repo.get_user_by_slack_id.return_value = sample_user

        # Set up conversation state
        conversation_handler.active_conversations[slack_event_message["thread_ts"]] = ConversationState(
            report_id=sample_daily_report.id,
            user_id=sample_user.id,
            thread_ts=slack_event_message["thread_ts"],
            channel_id=slack_event_message["channel"],
            state="awaiting_clarification",
        )

        # Mock the clarification processing
        updated_report = DailyReport(
            **sample_daily_report.model_dump(),
            needs_clarification=False,
            hours_worked=8.0,
            key_achievements=["Implemented authentication", "Fixed login bugs"],
        )
        mock_daily_report_service.process_clarification_response = AsyncMock(return_value=updated_report)
        mock_daily_report_service.get_daily_report = AsyncMock(return_value=updated_report)

        conversation_handler.slack_service.send_message = AsyncMock()

        # Act
        await conversation_handler.handle_message_event(slack_event_message)

        # Assert
        mock_daily_report_service.process_clarification_response.assert_called_once_with(
            report_id=sample_daily_report.id, user_response=slack_event_message["text"]
        )

        # Verify confirmation message sent
        conversation_handler.slack_service.send_message.assert_called()
        assert slack_event_message["thread_ts"] not in conversation_handler.active_conversations

    @pytest.mark.asyncio
    async def test_handle_message_event_no_active_conversation(self, conversation_handler, slack_event_message):
        """Test handling message when no active conversation exists"""
        # Arrange
        conversation_handler.slack_service.send_message = AsyncMock()

        # Act
        await conversation_handler.handle_message_event(slack_event_message)

        # Assert
        # Should not process or respond to random messages
        conversation_handler.slack_service.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_clarification_conversation(
        self, conversation_handler, mock_slack_service, mock_slack_templates, sample_user, sample_daily_report
    ):
        """Test starting a clarification conversation"""
        # Arrange
        mock_slack_service.open_dm = AsyncMock(return_value="D123456")
        mock_slack_service.send_message = AsyncMock(return_value=True)
        mock_slack_templates.clarification_request.return_value = {
            "text": "I need some clarification",
            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "Please clarify"}}],
        }

        # Act
        thread_ts = await conversation_handler.start_clarification_conversation(
            user=sample_user, report=sample_daily_report
        )

        # Assert
        assert thread_ts is not None
        assert thread_ts in conversation_handler.active_conversations

        state = conversation_handler.active_conversations[thread_ts]
        assert state.report_id == sample_daily_report.id
        assert state.user_id == sample_user.id
        assert state.state == "awaiting_clarification"

        mock_slack_service.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_multiple_clarification_rounds(
        self, conversation_handler, mock_daily_report_service, sample_user, sample_daily_report, slack_event_message
    ):
        """Test handling multiple rounds of clarification"""
        # Arrange
        mock_daily_report_service.get_daily_report = AsyncMock(return_value=sample_daily_report)

        # First clarification still needs more info
        sample_daily_report.needs_clarification = True
        sample_daily_report.clarification_questions = ["How many hours exactly?"]

        conversation_handler.active_conversations[slack_event_message["thread_ts"]] = ConversationState(
            report_id=sample_daily_report.id,
            user_id=sample_user.id,
            thread_ts=slack_event_message["thread_ts"],
            channel_id=slack_event_message["channel"],
            state="awaiting_clarification",
        )

        mock_daily_report_service.process_clarification_response = AsyncMock(return_value=sample_daily_report)
        conversation_handler.slack_service.send_message = AsyncMock()

        # Act
        await conversation_handler.handle_message_event(slack_event_message)

        # Assert
        # Conversation should still be active
        assert slack_event_message["thread_ts"] in conversation_handler.active_conversations
        assert (
            conversation_handler.active_conversations[slack_event_message["thread_ts"]].state
            == "awaiting_clarification"
        )

    @pytest.mark.asyncio
    async def test_conversation_timeout_cleanup(self, conversation_handler):
        """Test that old conversations are cleaned up"""
        # Arrange
        old_thread_ts = "1234567890.123456"
        recent_thread_ts = "9999999999.123456"

        # Add old conversation (should be cleaned up)
        conversation_handler.active_conversations[old_thread_ts] = ConversationState(
            report_id=uuid4(),
            user_id=uuid4(),
            thread_ts=old_thread_ts,
            channel_id="D123456",
            state="awaiting_clarification",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),  # Over 24 hours old
        )

        # Add recent conversation (should be kept)
        conversation_handler.active_conversations[recent_thread_ts] = ConversationState(
            report_id=uuid4(),
            user_id=uuid4(),
            thread_ts=recent_thread_ts,
            channel_id="D234567",
            state="awaiting_clarification",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),  # 1 hour old
        )

        # Act
        conversation_handler._cleanup_old_conversations()

        # Assert
        assert old_thread_ts not in conversation_handler.active_conversations
        assert recent_thread_ts in conversation_handler.active_conversations

    @pytest.mark.asyncio
    async def test_error_handling_in_view_submission(
        self, conversation_handler, mock_user_repo, mock_daily_report_service, slack_view_submission
    ):
        """Test error handling during view submission"""
        # Arrange
        mock_user_repo.get_user_by_slack_id.side_effect = Exception("Database error")

        # Act
        result = await conversation_handler.handle_view_submission(slack_view_submission)

        # Assert
        assert result is not None
        assert result["response_action"] == "errors"
        assert "error occurred" in str(result["errors"])

    @pytest.mark.asyncio
    async def test_handle_slash_command_unknown(self, conversation_handler):
        """Test handling unknown slash command"""
        # Arrange
        unknown_command = {"command": "/unknown", "user_id": "U123456", "text": "some text"}

        # Act
        result = await conversation_handler.handle_slash_command(unknown_command)

        # Assert
        assert result["response_type"] == "ephemeral"
        assert "Unknown command" in result["text"]
