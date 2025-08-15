"""
Unit tests for Slack service direct integration.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from slack_sdk.errors import SlackApiError

from app.core.circuit_breaker import CircuitBreakerOpenError
from app.services.slack_service import SlackService


@pytest.fixture
def mock_slack_client():
    """Mock Slack WebClient."""
    with patch("app.services.slack_service.WebClient") as mock:
        yield mock


@pytest.fixture
def slack_service(mock_slack_client):
    """Create SlackService instance with mocked client."""
    service = SlackService()
    return service


class TestSlackService:
    """Test suite for SlackService."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, slack_service, mock_slack_client):
        """Test successful message sending."""
        # Mock response
        mock_response = Mock()
        mock_response.data = {"ok": True, "ts": "1234567890.123456"}
        slack_service.client.chat_postMessage.return_value = mock_response

        # Send message
        result = await slack_service.send_message(
            channel="#general",
            text="Test message",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}],
        )

        # Verify
        assert result == {"ok": True, "ts": "1234567890.123456"}
        slack_service.client.chat_postMessage.assert_called_once_with(
            channel="#general",
            text="Test message",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}],
            thread_ts=None,
        )

    @pytest.mark.asyncio
    async def test_send_message_api_error(self, slack_service, mock_slack_client):
        """Test handling of Slack API errors."""
        # Mock error
        error_response = {"error": "channel_not_found"}
        slack_service.client.chat_postMessage.side_effect = SlackApiError("Channel not found", error_response)

        # Send message
        result = await slack_service.send_message(channel="#nonexistent", text="Test message")

        # Verify
        assert result is None

    @pytest.mark.asyncio
    async def test_send_direct_message_success(self, slack_service, mock_slack_client):
        """Test successful direct message sending."""
        # Mock conversation open
        mock_conv_response = {"channel": {"id": "D1234567890"}}
        slack_service.client.conversations_open.return_value = mock_conv_response

        # Mock message send
        mock_msg_response = Mock()
        mock_msg_response.data = {"ok": True, "ts": "1234567890.123456"}
        slack_service.client.chat_postMessage.return_value = mock_msg_response

        # Send DM
        result = await slack_service.send_direct_message(user_id="U1234567890", text="Hello there!")

        # Verify
        assert result == {"ok": True, "ts": "1234567890.123456"}
        slack_service.client.conversations_open.assert_called_once_with(users=["U1234567890"])
        slack_service.client.chat_postMessage.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_user_by_email_success(self, slack_service, mock_slack_client):
        """Test successful user lookup by email."""
        # Mock response
        mock_user = {
            "id": "U1234567890",
            "name": "testuser",
            "real_name": "Test User",
            "profile": {"email": "test@example.com"},
        }
        slack_service.client.users_lookupByEmail.return_value = {"user": mock_user}

        # Find user
        result = await slack_service.find_user_by_email("test@example.com")

        # Verify
        assert result == mock_user
        slack_service.client.users_lookupByEmail.assert_called_once_with(email="test@example.com")

    @pytest.mark.asyncio
    async def test_find_user_by_email_cached(self, slack_service, mock_slack_client):
        """Test user lookup with caching."""
        # Mock response
        mock_user = {"id": "U1234567890", "name": "testuser", "real_name": "Test User"}
        slack_service.client.users_lookupByEmail.return_value = {"user": mock_user}

        # First lookup
        result1 = await slack_service.find_user_by_email("test@example.com")
        assert result1 == mock_user

        # Second lookup (should use cache)
        result2 = await slack_service.find_user_by_email("test@example.com")
        assert result2 == mock_user

        # Verify API called only once
        slack_service.client.users_lookupByEmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_user_by_github_username(self, slack_service, mock_slack_client):
        """Test user lookup by GitHub username."""
        # Mock database response
        mock_db = AsyncMock()
        mock_user = Mock()
        mock_user.email = "test@example.com"

        with patch.object(slack_service.user_repository, "get_by_github_username", return_value=mock_user):
            # Mock Slack response
            mock_slack_user = {"id": "U1234567890", "name": "testuser", "real_name": "Test User"}
            slack_service.client.users_lookupByEmail.return_value = {"user": mock_slack_user}

            # Find user
            result = await slack_service.find_user_by_github_username("octocat", mock_db)

            # Verify
            assert result == mock_slack_user
            slack_service.user_repository.get_by_github_username.assert_called_once_with(mock_db, "octocat")
            slack_service.client.users_lookupByEmail.assert_called_once_with(email="test@example.com")

    @pytest.mark.asyncio
    async def test_circuit_breaker_protection(self, slack_service, mock_slack_client):
        """Test circuit breaker protection for API calls."""
        # Force circuit breaker to open
        slack_service.circuit_breaker._failure_count = 10
        slack_service.circuit_breaker._last_failure_time = datetime.now()
        slack_service.circuit_breaker._state = "open"

        # Try to send message
        result = await slack_service.send_message(channel="#general", text="Test message")

        # Verify
        assert result is None
        slack_service.client.chat_postMessage.assert_not_called()

    def test_format_helpers(self, slack_service):
        """Test Slack formatting helper methods."""
        # Test user mention
        assert slack_service._format_user_mention("U1234567890") == "<@U1234567890>"

        # Test channel mention
        assert slack_service._format_channel_mention("C1234567890") == "<#C1234567890>"

        # Test link formatting
        assert slack_service._format_link("https://example.com", "Example") == "<https://example.com|Example>"

    def test_clear_cache(self, slack_service):
        """Test cache clearing."""
        # Add some cache entries
        slack_service._user_cache = {"email:test@example.com": {"data": {"id": "U123"}, "timestamp": datetime.now()}}

        # Clear cache
        slack_service.clear_cache()

        # Verify
        assert len(slack_service._user_cache) == 0
