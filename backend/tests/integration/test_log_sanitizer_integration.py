"""
Integration tests for log sanitization in the FastAPI application.

Tests verify that sensitive data is properly redacted in real API scenarios.
"""

import json
import logging
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.log_sanitizer import SensitiveDataFilter
from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def log_capture():
    """Fixture to capture log output."""
    # Create a string buffer to capture logs
    log_buffer = StringIO()
    handler = logging.StreamHandler(log_buffer)
    handler.setLevel(logging.INFO)

    # Add our sanitizer filter
    handler.addFilter(SensitiveDataFilter())

    # Get the app logger and add our handler
    app_logger = logging.getLogger("app")
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)

    # Also capture uvicorn logs
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.addHandler(handler)

    yield log_buffer

    # Cleanup
    app_logger.removeHandler(handler)
    uvicorn_logger.removeHandler(handler)
    handler.close()
    log_buffer.close()


class TestAPIKeyAuthLogging:
    """Test that API key authentication doesn't log sensitive data."""

    @pytest.mark.asyncio
    async def test_api_key_middleware_no_sensitive_logs(self, client, log_capture):
        """Test that API key middleware doesn't log sensitive keys."""
        # Make a request with an API key
        headers = {"X-API-Key": "super-secret-api-key-12345"}

        # Mock the API keys configuration
        with patch("app.middleware.api_key_auth.ApiKeyMiddleware.__init__") as mock_init:
            mock_init.return_value = None

            # Make request that would trigger API key validation
            response = client.get("/api/v1/health", headers=headers)

        # Get log output
        log_output = log_capture.getvalue()

        # Verify sensitive data is not in logs
        assert "super-secret-api-key-12345" not in log_output
        assert "X-API-Key" in log_output or "x-api-key" in log_output  # Header name is OK

    @pytest.mark.asyncio
    async def test_invalid_api_key_no_sensitive_logs(self, client, log_capture):
        """Test that invalid API key attempts don't log the key."""
        # Make a request with an invalid API key
        headers = {"X-API-Key": "invalid-key-that-should-not-be-logged"}

        # Make request (will fail, but that's OK for this test)
        response = client.get("/api/v1/users", headers=headers)

        # Get log output
        log_output = log_capture.getvalue()

        # Verify the invalid key is not in logs
        assert "invalid-key-that-should-not-be-logged" not in log_output


class TestGitHubWebhookLogging:
    """Test that GitHub webhook endpoint doesn't log sensitive data."""

    @pytest.mark.asyncio
    async def test_github_webhook_no_api_key_logs(self, client, log_capture):
        """Test that GitHub webhook doesn't log API keys."""
        # Prepare webhook payload
        payload = {
            "commit_hash": "abc123",
            "message": "Test commit",
            "author_email": "test@example.com",
            "author_name": "Test User",
            "repository": "test/repo",
            "branch": "main",
            "timestamp": "2023-01-01T00:00:00Z",
            "url": "https://github.com/test/repo/commit/abc123",
            "added": [],
            "modified": ["test.py"],
            "removed": [],
        }

        headers = {"X-API-Key": "webhook-secret-key-98765", "Content-Type": "application/json"}

        # Mock settings to enable API auth
        with patch("app.config.settings.settings.enable_api_auth", True):
            with patch("app.config.settings.settings.make_integration_api_key", "webhook-secret-key-98765"):
                # Make the webhook request
                response = client.post("/api/v1/integrations/github/commit", json=payload, headers=headers)

        # Get log output
        log_output = log_capture.getvalue()

        # Verify sensitive data is not in logs
        assert "webhook-secret-key-98765" not in log_output
        assert "base64" not in log_output or "REDACTED" in log_output

        # Verify email is redacted
        assert "test@example.com" not in log_output

    @pytest.mark.asyncio
    async def test_github_webhook_auth_failure_no_logs(self, client, log_capture):
        """Test that failed auth doesn't log sensitive data."""
        payload = {
            "commit_hash": "def456",
            "message": "Another commit",
            "author_email": "user@company.org",
            "author_name": "User",
            "repository": "test/repo",
            "branch": "main",
            "timestamp": "2023-01-01T00:00:00Z",
            "url": "https://github.com/test/repo/commit/def456",
            "added": [],
            "modified": [],
            "removed": [],
        }

        headers = {"X-API-Key": "wrong-api-key-should-not-appear-in-logs", "Content-Type": "application/json"}

        with patch("app.config.settings.settings.enable_api_auth", True):
            with patch("app.config.settings.settings.make_integration_api_key", "correct-key"):
                # Make request with wrong key
                response = client.post("/api/v1/integrations/github/commit", json=payload, headers=headers)

        # Get log output
        log_output = log_capture.getvalue()

        # Verify wrong key is not in logs
        assert "wrong-api-key-should-not-appear-in-logs" not in log_output
        assert "correct-key" not in log_output

        # Verify email is redacted
        assert "user@company.org" not in log_output


class TestDatabaseConnectionLogging:
    """Test that database connection strings are sanitized."""

    @pytest.mark.asyncio
    async def test_database_error_no_connection_string(self, client, log_capture):
        """Test that database errors don't expose connection strings."""
        # Simulate a database error with connection string in message
        error_msg = "Failed to connect to postgresql://user:password@localhost:5432/testdb"

        # Log the error
        logger = logging.getLogger("app.db")
        logger.error(error_msg)

        # Get log output
        log_output = log_capture.getvalue()

        # Verify credentials are not exposed
        assert "user:password" not in log_output
        assert "postgresql://REDACTED@REDACTED" in log_output


class TestAuthenticationLogging:
    """Test that authentication flows don't log sensitive data."""

    @pytest.mark.asyncio
    async def test_login_no_password_logs(self, client, log_capture):
        """Test that login attempts don't log passwords."""
        # Attempt login
        login_data = {"email": "admin@example.com", "password": "super-secret-password-123"}

        # Make login request
        response = client.post("/api/v1/auth/login", json=login_data)

        # Get log output
        log_output = log_capture.getvalue()

        # Verify password is not in logs
        assert "super-secret-password-123" not in log_output

        # Verify email is redacted
        assert "admin@example.com" not in log_output
        assert "EMAIL_REDACTED" in log_output

    @pytest.mark.asyncio
    async def test_jwt_token_not_logged(self, client, log_capture):
        """Test that JWT tokens are not logged."""
        # Simulate receiving a JWT token
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

        # Log a message containing the token
        logger = logging.getLogger("app.auth")
        logger.info(f"User authenticated with token: {jwt_token}")

        # Get log output
        log_output = log_capture.getvalue()

        # Verify JWT is not in logs
        assert jwt_token not in log_output
        assert "JWT_TOKEN_REDACTED" in log_output


class TestErrorHandlerLogging:
    """Test that error handlers don't expose sensitive data."""

    @pytest.mark.asyncio
    async def test_exception_handler_sanitizes_logs(self, client, log_capture):
        """Test that exception handlers sanitize sensitive data."""
        # Create an exception with sensitive data
        try:
            raise ValueError("Database error: password=admin123, api_key=secret-key-456")
        except ValueError as e:
            # Log the exception
            logger = logging.getLogger("app.error_handlers")
            logger.error("Caught exception", exc_info=True)

        # Get log output
        log_output = log_capture.getvalue()

        # Verify sensitive data is not in logs
        assert "admin123" not in log_output
        assert "secret-key-456" not in log_output
        assert "password=REDACTED" in log_output
        assert "api_key=REDACTED" in log_output


class TestRequestHeaderLogging:
    """Test that request headers with sensitive data are sanitized."""

    @pytest.mark.asyncio
    async def test_request_headers_sanitized(self, client, log_capture):
        """Test that logged request headers are sanitized."""
        # Make request with sensitive headers
        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "X-API-Key": "my-api-key-12345",
            "X-AWS-Access-Key": "AKIAIOSFODNN7EXAMPLE",
            "Cookie": "session=secret-session-id-789",
        }

        # Log the headers (simulating what might happen in middleware)
        logger = logging.getLogger("app.middleware")
        logger.info(f"Request headers: {headers}")

        # Get log output
        log_output = log_capture.getvalue()

        # Verify all sensitive data is redacted
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in log_output
        assert "my-api-key-12345" not in log_output
        assert "AKIAIOSFODNN7EXAMPLE" not in log_output
        assert "secret-session-id-789" not in log_output

        # Some form of REDACTED should be present
        assert "REDACTED" in log_output


class TestFullMessageRedaction:
    """Test patterns that trigger full message redaction."""

    @pytest.mark.asyncio
    async def test_base64_key_logs_fully_redacted(self, client, log_capture):
        """Test that base64 encoded keys trigger full redaction."""
        # Log messages that should be fully redacted
        logger = logging.getLogger("app.api")

        logger.info("Received key (base64): YWRtaW46cGFzc3dvcmQxMjM=")
        logger.info("Expected key (base64): c2VjcmV0LWtleS0xMjM0NQ==")
        logger.info("All request headers: {'Authorization': 'Bearer token123', 'X-API-Key': 'secret'}")

        # Get log output
        log_output = log_capture.getvalue()

        # Verify full redaction
        assert "[REDACTED: Contains sensitive information]" in log_output

        # Verify sensitive data is not present
        assert "YWRtaW46cGFzc3dvcmQxMjM=" not in log_output
        assert "c2VjcmV0LWtleS0xMjM0NQ==" not in log_output
        assert "Bearer token123" not in log_output
        assert "'X-API-Key': 'secret'" not in log_output


class TestManualTestScenarios:
    """
    Manual test scenarios for verifying log sanitization.

    These tests document the manual testing process for QA.
    """

    def test_manual_scenarios_documentation(self):
        """Document manual test scenarios."""
        scenarios = """
        MANUAL TEST SCENARIOS FOR LOG SANITIZATION
        ==========================================
        
        1. API Key Authentication Test:
           - Start the application with logging enabled
           - Make a request with header: X-API-Key: test-secret-key-123
           - Check logs to ensure 'test-secret-key-123' does not appear
           - Verify 'REDACTED' appears instead
        
        2. Failed Authentication Test:
           - Make a request with an invalid API key
           - Check logs to ensure the invalid key is not logged
           - Only see messages like "Invalid API key provided"
        
        3. Database Connection Test:
           - Trigger a database connection error
           - Check logs for connection string exposure
           - Verify credentials are replaced with 'REDACTED'
        
        4. GitHub Webhook Test:
           - Send a webhook with API key header
           - Check logs to ensure no base64 encoded keys appear
           - Verify commit author emails are redacted
        
        5. Login Flow Test:
           - Attempt login with email/password
           - Check logs to ensure password never appears
           - Verify email is shown as 'EMAIL_REDACTED'
        
        6. Error Scenario Test:
           - Trigger various application errors
           - Check exception traces for sensitive data
           - Verify stack traces are sanitized
        
        7. Performance Test:
           - Run load test with many concurrent requests
           - Verify log sanitization doesn't impact performance
           - Check that all logs are still properly sanitized
        
        8. Log Rotation Test:
           - Let application run until logs rotate
           - Verify new log files also have sanitization
           - Check that no sensitive data leaked during rotation
        """

        assert scenarios is not None  # Just to have an assertion
        print(scenarios)  # This will show in test output with -s flag


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
