"""
Comprehensive tests for Slack Service
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from slack_sdk.errors import SlackApiError

from app.config.settings import settings
from app.core.exceptions import ConfigurationError, ExternalServiceError
from app.services.slack_service import SlackService


@pytest.fixture
def mock_slack_client():
    """Mock Slack WebClient"""
    client = Mock()
    client.auth_test = AsyncMock()
    client.chat_postMessage = AsyncMock()
    client.conversations_open = AsyncMock()
    client.users_info = AsyncMock()
    client.users_list = AsyncMock()
    client.conversations_info = AsyncMock()
    client.chat_scheduleMessage = AsyncMock()
    client.views_open = AsyncMock()
    client.views_update = AsyncMock()
    return client


@pytest.fixture
def mock_circuit_breaker():
    """Mock circuit breaker"""
    breaker = Mock()
    breaker.call = AsyncMock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
    return breaker


@pytest.fixture
def slack_service(mock_slack_client, mock_circuit_breaker):
    """Create SlackService instance with mocks"""
    with patch("app.services.slack_service.WebClient", return_value=mock_slack_client):
        with patch("app.services.slack_service.CircuitBreaker", return_value=mock_circuit_breaker):
            service = SlackService()
            return service


@pytest.fixture
def slack_error_response():
    """Sample Slack error response"""
    return {"ok": False, "error": "channel_not_found", "response_metadata": {"messages": ["Channel not found"]}}


class TestSlackService:
    """Test cases for SlackService"""

    @pytest.mark.asyncio
    async def test_send_message_success(self, slack_service, mock_slack_client):
        """Test successful message sending"""
        # Arrange
        channel = "#general"
        text = "Test message"
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]

        mock_slack_client.chat_postMessage.return_value = {"ok": True, "ts": "1234567890.123456", "channel": "C123456"}

        # Act
        result = await slack_service.send_message(channel=channel, text=text, blocks=blocks)

        # Assert
        assert result is True
        mock_slack_client.chat_postMessage.assert_called_once_with(channel=channel, text=text, blocks=blocks)

    @pytest.mark.asyncio
    async def test_send_message_with_thread(self, slack_service, mock_slack_client):
        """Test sending message in thread"""
        # Arrange
        channel = "C123456"
        text = "Thread reply"
        thread_ts = "1234567890.123456"

        mock_slack_client.chat_postMessage.return_value = {"ok": True}

        # Act
        result = await slack_service.send_message(channel=channel, text=text, thread_ts=thread_ts)

        # Assert
        assert result is True
        mock_slack_client.chat_postMessage.assert_called_once_with(
            channel=channel, text=text, blocks=None, thread_ts=thread_ts
        )

    @pytest.mark.asyncio
    async def test_send_message_error(self, slack_service, mock_slack_client):
        """Test message sending with Slack API error"""
        # Arrange
        mock_slack_client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found", response={"error": "channel_not_found"}
        )

        # Act
        result = await slack_service.send_message(channel="#nonexistent", text="Test")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_send_direct_message_success(self, slack_service, mock_slack_client):
        """Test successful direct message sending"""
        # Arrange
        user_id = "U123456"
        text = "Direct message"

        mock_slack_client.conversations_open.return_value = {"ok": True, "channel": {"id": "D123456"}}
        mock_slack_client.chat_postMessage.return_value = {"ok": True}

        # Act
        result = await slack_service.send_direct_message(user_id=user_id, text=text)

        # Assert
        assert result is True
        mock_slack_client.conversations_open.assert_called_once_with(users=user_id)
        mock_slack_client.chat_postMessage.assert_called_once_with(channel="D123456", text=text, blocks=None)

    @pytest.mark.asyncio
    async def test_send_direct_message_open_dm_fails(self, slack_service, mock_slack_client):
        """Test direct message when opening DM fails"""
        # Arrange
        mock_slack_client.conversations_open.side_effect = SlackApiError(
            message="user_not_found", response={"error": "user_not_found"}
        )

        # Act
        result = await slack_service.send_direct_message(user_id="U999999", text="Test")

        # Assert
        assert result is False
        mock_slack_client.chat_postMessage.assert_not_called()

    @pytest.mark.asyncio
    async def test_open_dm_success(self, slack_service, mock_slack_client):
        """Test successfully opening a DM channel"""
        # Arrange
        user_id = "U123456"
        mock_slack_client.conversations_open.return_value = {"ok": True, "channel": {"id": "D123456"}}

        # Act
        result = await slack_service.open_dm(user_id)

        # Assert
        assert result == "D123456"

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, slack_service, mock_slack_client):
        """Test getting user information"""
        # Arrange
        user_id = "U123456"
        mock_slack_client.users_info.return_value = {
            "ok": True,
            "user": {
                "id": user_id,
                "name": "testuser",
                "real_name": "Test User",
                "profile": {"email": "test@example.com", "display_name": "Test"},
            },
        }

        # Act
        result = await slack_service.get_user_info(user_id)

        # Assert
        assert result["id"] == user_id
        assert result["profile"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_find_user_by_email_success(self, slack_service, mock_slack_client):
        """Test finding user by email"""
        # Arrange
        email = "test@example.com"
        mock_slack_client.users_list.return_value = {
            "ok": True,
            "members": [
                {"id": "U123456", "profile": {"email": "other@example.com"}},
                {"id": "U234567", "profile": {"email": email}},
            ],
        }

        # Act
        result = await slack_service.find_user_by_email(email)

        # Assert
        assert result["id"] == "U234567"
        assert result["profile"]["email"] == email

    @pytest.mark.asyncio
    async def test_find_user_by_email_not_found(self, slack_service, mock_slack_client):
        """Test finding user by email when not found"""
        # Arrange
        mock_slack_client.users_list.return_value = {"ok": True, "members": []}

        # Act
        result = await slack_service.find_user_by_email("notfound@example.com")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_find_user_by_github_username(self, slack_service, mock_slack_client):
        """Test finding user by GitHub username"""
        # Arrange
        github_username = "octocat"
        mock_slack_client.users_list.return_value = {
            "ok": True,
            "members": [{"id": "U123456", "profile": {"fields": {"github": {"value": github_username}}}}],
        }

        # Act
        with patch("app.repositories.user_repository.UserRepository") as mock_user_repo_class:
            mock_user_repo = Mock()
            mock_user_repo_class.return_value = mock_user_repo
            mock_user_repo.get_user_by_github_username.return_value = Mock(slack_id="U123456")

            result = await slack_service.find_user_by_github_username(github_username, Mock())

        # Assert
        assert result["id"] == "U123456"

    @pytest.mark.asyncio
    async def test_schedule_message_success(self, slack_service, mock_slack_client):
        """Test scheduling a message"""
        # Arrange
        channel = "C123456"
        post_at = int(datetime.now(timezone.utc).timestamp()) + 3600  # 1 hour from now
        text = "Scheduled message"

        mock_slack_client.chat_scheduleMessage.return_value = {
            "ok": True,
            "scheduled_message_id": "Q123456",
            "post_at": post_at,
        }

        # Act
        result = await slack_service.schedule_message(channel=channel, post_at=post_at, text=text)

        # Assert
        assert result == "Q123456"
        mock_slack_client.chat_scheduleMessage.assert_called_once_with(
            channel=channel, post_at=post_at, text=text, blocks=None
        )

    @pytest.mark.asyncio
    async def test_open_modal_success(self, slack_service, mock_slack_client):
        """Test opening a modal"""
        # Arrange
        trigger_id = "123456.789012"
        view = {"type": "modal", "title": {"type": "plain_text", "text": "Test Modal"}, "blocks": []}

        mock_slack_client.views_open.return_value = {"ok": True, "view": {"id": "V123456"}}

        # Act
        result = await slack_service.open_modal(trigger_id=trigger_id, view=view)

        # Assert
        assert result is True
        mock_slack_client.views_open.assert_called_once_with(trigger_id=trigger_id, view=view)

    @pytest.mark.asyncio
    async def test_update_modal_success(self, slack_service, mock_slack_client):
        """Test updating a modal"""
        # Arrange
        view_id = "V123456"
        view = {"type": "modal", "title": {"type": "plain_text", "text": "Updated Modal"}, "blocks": []}

        mock_slack_client.views_update.return_value = {"ok": True}

        # Act
        result = await slack_service.update_modal(view_id=view_id, view=view)

        # Assert
        assert result is True
        mock_slack_client.views_update.assert_called_once_with(view_id=view_id, view=view)

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, slack_service, mock_slack_client, mock_circuit_breaker):
        """Test that circuit breaker is used for API calls"""
        # Arrange
        mock_slack_client.chat_postMessage.return_value = {"ok": True}

        # Act
        await slack_service.send_message(channel="#test", text="Test")

        # Assert
        mock_circuit_breaker.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_test_on_init(self, mock_slack_client):
        """Test that auth test is performed on initialization"""
        # Arrange
        mock_slack_client.auth_test.return_value = {"ok": True, "team": "Test Team"}

        # Act
        with patch("app.services.slack_service.WebClient", return_value=mock_slack_client):
            with patch("app.services.slack_service.CircuitBreaker"):
                service = SlackService()

        # Assert
        mock_slack_client.auth_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_configuration_error_no_token(self):
        """Test configuration error when no token is provided"""
        # Arrange
        with patch("app.config.settings.settings.SLACK_BOT_TOKEN", None):

            # Act & Assert
            with pytest.raises(ConfigurationError) as exc:
                SlackService()

            assert "SLACK_BOT_TOKEN not configured" in str(exc.value)

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, slack_service, mock_slack_client):
        """Test retry behavior on rate limit errors"""
        # Arrange
        # First call fails with rate limit, second succeeds
        mock_slack_client.chat_postMessage.side_effect = [
            SlackApiError(message="rate_limited", response={"error": "rate_limited", "retry_after": 1}),
            {"ok": True},
        ]

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await slack_service.send_message(channel="#test", text="Test")

        # Assert
        assert result is True
        assert mock_slack_client.chat_postMessage.call_count == 2

    @pytest.mark.asyncio
    async def test_pagination_in_user_list(self, slack_service, mock_slack_client):
        """Test pagination handling in user list"""
        # Arrange
        # First page
        mock_slack_client.users_list.side_effect = [
            {
                "ok": True,
                "members": [{"id": f"U{i}", "profile": {"email": f"user{i}@test.com"}} for i in range(100)],
                "response_metadata": {"next_cursor": "next_page_cursor"},
            },
            # Second page
            {
                "ok": True,
                "members": [{"id": f"U{i}", "profile": {"email": f"user{i}@test.com"}} for i in range(100, 150)],
                "response_metadata": {"next_cursor": ""},
            },
        ]

        # Act
        # This would be called internally by find_user_by_email
        result = await slack_service.find_user_by_email("user125@test.com")

        # Assert
        assert result["id"] == "U125"
        assert mock_slack_client.users_list.call_count == 2
