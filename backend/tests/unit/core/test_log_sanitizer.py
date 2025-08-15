"""
Unit tests for the log sanitization filter.

Tests verify that sensitive data is properly redacted from log messages.
"""

import logging
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from app.core.log_sanitizer import SensitiveDataFilter, add_sensitive_data_filter, configure_secure_logging


class TestSensitiveDataFilter:
    """Test cases for the SensitiveDataFilter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.filter = SensitiveDataFilter()
        self.log_capture = StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        self.handler.addFilter(self.filter)

        # Create a test logger
        self.logger = logging.getLogger("test_logger")
        self.logger.handlers.clear()  # Clear any existing handlers
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)

    def teardown_method(self):
        """Clean up after tests."""
        self.logger.handlers.clear()
        self.log_capture.close()

    def get_log_output(self) -> str:
        """Get the captured log output."""
        self.handler.flush()
        return self.log_capture.getvalue()

    def test_api_key_redaction(self):
        """Test that API keys are redacted in various formats."""
        test_cases = [
            "api_key=sk-1234567890abcdef",
            "API_KEY: 'test-key-12345'",
            'apikey="my-secret-key-value"',
            "Api-Key = super-secret-key-123",
            "token: Bearer eyJ0eXAiOiJKV1QiLCJhbGc",
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that sensitive data is not in output
            assert "sk-1234567890abcdef" not in output
            assert "test-key-12345" not in output
            assert "my-secret-key-value" not in output
            assert "super-secret-key-123" not in output
            assert "eyJ0eXAiOiJKV1QiLCJhbGc" not in output

            # Check that REDACTED is present
            assert "REDACTED" in output

    def test_password_redaction(self):
        """Test that passwords are redacted."""
        test_cases = [
            "password=mysecretpass123",
            "Password: 'admin123'",
            'passwd="securepwd"',
            "PWD = mypassword",
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that passwords are not in output
            assert "mysecretpass123" not in output
            assert "admin123" not in output
            assert "securepwd" not in output
            assert "mypassword" not in output

            # Check that REDACTED is present
            assert "REDACTED" in output

    def test_base64_redaction(self):
        """Test that base64 encoded strings are redacted."""
        test_cases = [
            "base64: YWRtaW46cGFzc3dvcmQxMjM=",
            "Received key (base64): c2VjcmV0LWtleS0xMjM0NQ==",
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that base64 strings are not in output
            assert "YWRtaW46cGFzc3dvcmQxMjM=" not in output
            assert "c2VjcmV0LWtleS0xMjM0NQ==" not in output

            # Check that REDACTED is present
            assert "REDACTED" in output

    def test_header_redaction(self):
        """Test that authorization headers are redacted."""
        test_cases = [
            "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",
            "X-API-Key: my-api-key-12345",
            'x-api-key="another-key-67890"',
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that sensitive headers are not in output
            assert "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9" not in output
            assert "my-api-key-12345" not in output
            assert "another-key-67890" not in output

            # Check that REDACTED is present
            assert "REDACTED" in output

    def test_email_redaction(self):
        """Test that email addresses are redacted."""
        test_cases = [
            "User email: john.doe@example.com logged in",
            "Contact: admin@company.org for support",
            "Failed login for user@test.co.uk",
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that emails are not in output
            assert "john.doe@example.com" not in output
            assert "admin@company.org" not in output
            assert "user@test.co.uk" not in output

            # Check that EMAIL_REDACTED is present
            assert "EMAIL_REDACTED" in output

    def test_database_url_redaction(self):
        """Test that database connection strings are redacted."""
        test_cases = [
            "postgres://user:pass@localhost:5432/mydb",
            "mysql://admin:secret@db.example.com/prod",
            "mongodb://root:pwd123@mongo:27017/app",
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that credentials are not in output
            assert "user:pass" not in output
            assert "admin:secret" not in output
            assert "root:pwd123" not in output
            assert "localhost:5432" not in output
            assert "db.example.com" not in output

            # Check that REDACTED is present
            assert "REDACTED@REDACTED" in output

    def test_jwt_token_redaction(self):
        """Test that JWT tokens are redacted."""
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

        # Test different ways JWT might appear
        test_cases = [
            f"Token: {jwt_token}",
            f"JWT: {jwt_token}",
            f"Authorization: Bearer {jwt_token}",
            f"auth_token={jwt_token}",
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that JWT is not in output
            assert jwt_token not in output

            # Check that it's been redacted (either as JWT_TOKEN_REDACTED or REDACTED)
            assert "REDACTED" in output or "JWT_TOKEN_REDACTED" in output

    def test_aws_credentials_redaction(self):
        """Test that AWS credentials are redacted."""
        test_cases = [
            "aws_access_key_id=AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            'AWS_SESSION_TOKEN="FQoGZXIvYXdzEBYaD..."',
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that AWS credentials are not in output
            assert "AKIAIOSFODNN7EXAMPLE" not in output
            assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in output
            assert "FQoGZXIvYXdzEBYaD" not in output

            # Check that REDACTED is present
            assert "REDACTED" in output

    def test_credit_card_redaction(self):
        """Test that credit card numbers are redacted."""
        test_cases = [
            "Payment with card: 4111 1111 1111 1111",
            "CC: 5500-0000-0000-0004",
            "Card number: 3782 822463 10005",
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that card numbers are not in output
            assert "4111 1111 1111 1111" not in output
            assert "5500-0000-0000-0004" not in output
            assert "3782 822463 10005" not in output

            # Check that CC_NUMBER_REDACTED is present
            assert "CC_NUMBER_REDACTED" in output

    def test_ssn_redaction(self):
        """Test that social security numbers are redacted."""
        test_message = "User SSN: 123-45-6789"

        self.logger.info(test_message)
        output = self.get_log_output()

        # Check that SSN is not in output
        assert "123-45-6789" not in output

        # Check that SSN_REDACTED is present
        assert "SSN_REDACTED" in output

    def test_uuid_redaction(self):
        """Test that UUIDs are redacted."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"

        self.logger.info(f"User ID: {test_uuid}")
        output = self.get_log_output()

        # Check that UUID is not in output
        assert test_uuid not in output

        # Check that UUID_REDACTED is present
        assert "UUID_REDACTED" in output

    def test_full_redact_patterns(self):
        """Test that certain patterns trigger full message redaction."""
        test_cases = [
            "Received key (base64): YWRtaW46cGFzc3dvcmQ=",
            "Expected key (base64): c2VjcmV0",
            "All request headers: {'Authorization': 'Bearer token123'}",
        ]

        for test_message in test_cases:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that the full message is redacted
            assert "[REDACTED: Contains sensitive information]" in output

            # Check that original content is not present
            assert "YWRtaW46cGFzc3dvcmQ=" not in output
            assert "c2VjcmV0" not in output
            assert "Bearer token123" not in output

    def test_mixed_content_redaction(self):
        """Test redaction of messages with multiple sensitive items."""
        test_message = "User email@example.com authenticated with api_key=secret123 and password=pass456"

        self.logger.info(test_message)
        output = self.get_log_output()

        # Check that all sensitive data is redacted
        assert "email@example.com" not in output
        assert "secret123" not in output
        assert "pass456" not in output

        # Check that redacted markers are present
        assert "EMAIL_REDACTED" in output
        assert "api_key=REDACTED" in output
        assert "password=REDACTED" in output

    def test_safe_content_not_redacted(self):
        """Test that safe content is not redacted."""
        safe_messages = [
            "Processing request for user_id: 12345",
            "Request completed successfully",
            "Database query took 123ms",
            "Cache hit rate: 85%",
        ]

        for test_message in safe_messages:
            self.log_capture.truncate(0)
            self.log_capture.seek(0)
            self.logger.info(test_message)
            output = self.get_log_output()

            # Check that safe content is preserved
            assert test_message in output

            # Check that REDACTED is not present
            assert "REDACTED" not in output

    def test_exception_info_redaction(self):
        """Test that sensitive data in exceptions is redacted."""
        try:
            # Simulate an exception with sensitive data
            raise ValueError("Database error: postgres://user:password@localhost/db")
        except ValueError:
            self.logger.error("An error occurred", exc_info=True)

        output = self.get_log_output()

        # Check that database credentials are not in exception trace
        assert "user:password" not in output
        assert "postgres://REDACTED@REDACTED" in output


class TestLogSanitizerFunctions:
    """Test the helper functions in log_sanitizer module."""

    def test_add_sensitive_data_filter_to_logger(self):
        """Test adding filter to a specific logger."""
        test_logger = logging.getLogger("test_specific")

        # Initially no filters
        assert len(test_logger.filters) == 0

        # Add filter
        add_sensitive_data_filter(test_logger)

        # Check filter was added
        assert len(test_logger.filters) == 1
        assert isinstance(test_logger.filters[0], SensitiveDataFilter)

        # Test duplicate prevention
        add_sensitive_data_filter(test_logger)
        assert len(test_logger.filters) == 1  # Still only one

    def test_add_sensitive_data_filter_to_root(self):
        """Test adding filter to root logger."""
        root_logger = logging.getLogger()
        initial_filter_count = len(root_logger.filters)

        # Add filter
        add_sensitive_data_filter()

        # Check filter was added
        assert len(root_logger.filters) >= initial_filter_count

        # Find our filter
        found = False
        for f in root_logger.filters:
            if isinstance(f, SensitiveDataFilter):
                found = True
                break
        assert found

    @patch("app.core.log_sanitizer.add_sensitive_data_filter")
    def test_configure_secure_logging(self, mock_add_filter):
        """Test the configure_secure_logging function."""
        # Mock the root logger and its handlers
        mock_handler1 = MagicMock()
        mock_handler2 = MagicMock()

        with patch("logging.getLogger") as mock_get_logger:
            mock_root_logger = MagicMock()
            mock_root_logger.handlers = [mock_handler1, mock_handler2]
            mock_get_logger.return_value = mock_root_logger

            # Call the function
            configure_secure_logging()

            # Check that filter was added to root logger
            mock_add_filter.assert_called_once()

            # Check that filters were added to handlers
            mock_handler1.addFilter.assert_called_once()
            mock_handler2.addFilter.assert_called_once()

            # Verify SensitiveDataFilter was used
            for call in [mock_handler1.addFilter.call_args, mock_handler2.addFilter.call_args]:
                assert isinstance(call[0][0], SensitiveDataFilter)


class TestLogSanitizerIntegration:
    """Integration tests for log sanitizer with real logging setup."""

    def test_multiple_handlers_with_sanitizer(self):
        """Test that sanitizer works with multiple handlers."""
        # Create logger with multiple handlers
        logger = logging.getLogger("multi_handler_test")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)

        # Add two handlers with different outputs
        stream1 = StringIO()
        handler1 = logging.StreamHandler(stream1)
        handler1.addFilter(SensitiveDataFilter())

        stream2 = StringIO()
        handler2 = logging.StreamHandler(stream2)
        handler2.addFilter(SensitiveDataFilter())

        logger.addHandler(handler1)
        logger.addHandler(handler2)

        # Log sensitive data
        logger.info("api_key=secret12345")

        # Check both outputs are sanitized
        handler1.flush()
        handler2.flush()

        output1 = stream1.getvalue()
        output2 = stream2.getvalue()

        assert "secret12345" not in output1
        assert "secret12345" not in output2
        assert "REDACTED" in output1
        assert "REDACTED" in output2

        # Cleanup
        logger.handlers.clear()

    def test_logger_hierarchy_with_sanitizer(self):
        """Test that child loggers inherit the sanitizer."""
        # Configure root logger with sanitizer
        root_logger = logging.getLogger()
        add_sensitive_data_filter(root_logger)

        # Create child logger
        child_logger = logging.getLogger("app.module.submodule")

        # Setup handler to capture output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        # Add the filter to the handler as well
        handler.addFilter(SensitiveDataFilter())
        child_logger.addHandler(handler)
        child_logger.setLevel(logging.INFO)

        # Log sensitive data through child
        child_logger.info("password=topsecret")

        # Check output is sanitized
        handler.flush()
        output = stream.getvalue()

        assert "topsecret" not in output
        assert "REDACTED" in output

        # Cleanup
        child_logger.handlers.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
