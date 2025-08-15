"""
Log sanitization filter to prevent sensitive data from being logged.

This module provides a logging filter that automatically redacts sensitive
information from log messages before they are written to any log handler.
"""

import logging
import re
from typing import List, Optional, Pattern, Tuple


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that redacts sensitive data from log records.

    This filter scans log messages for patterns that match sensitive data
    (API keys, tokens, passwords, etc.) and replaces them with redacted versions.
    """

    # Patterns for detecting sensitive data
    # Each tuple contains: (compiled regex pattern, replacement string)
    SENSITIVE_PATTERNS: List[Tuple[Pattern[str], str]] = [
        # JWT tokens MUST come before generic token patterns
        # JWT tokens (they typically have 3 parts separated by dots)
        (re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", re.IGNORECASE), "JWT_TOKEN_REDACTED"),
        # Partial JWT tokens (at least the header part)
        (re.compile(r"\beyJ[A-Za-z0-9_-]+", re.IGNORECASE), "JWT_TOKEN_REDACTED"),
        # API keys and tokens (various formats)
        (
            re.compile(
                r'(api[_-]?key|apikey|token|secret[_-]?key|auth[_-]?key)\s*[:=]\s*["\']?([^\s"\',}]+)["\']?',
                re.IGNORECASE,
            ),
            r"\1=REDACTED",
        ),
        # Bearer tokens in Authorization headers
        (
            re.compile(r'(Authorization|auth|bearer)\s*[:=]\s*["\']?(Bearer\s+)?([^\s"\',}]+)["\']?', re.IGNORECASE),
            r"\1: Bearer REDACTED",
        ),
        # Standalone Bearer tokens
        (
            re.compile(r"\b(Bearer\s+[A-Za-z0-9\-_\.]+)", re.IGNORECASE),
            "Bearer REDACTED",
        ),
        # Password fields
        (re.compile(r'(password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\',}]+)["\']?', re.IGNORECASE), r"\1=REDACTED"),
        # Base64 encoded strings that might be sensitive (long base64 strings)
        (re.compile(r'base64\s*[:=]\s*["\']?([A-Za-z0-9+/]{20,}={0,2})["\']?', re.IGNORECASE), "base64=REDACTED"),
        # X-API-Key header values
        (re.compile(r'(X-API-Key|x-api-key)\s*[:=]\s*["\']?([^\s"\',}]+)["\']?', re.IGNORECASE), r"\1=REDACTED"),
        # Generic key patterns (catches various key formats)
        (
            re.compile(
                r"([a-zA-Z0-9_-]*(?:key|token|secret|password)[a-zA-Z0-9_-]*)"
                r'\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.\/\+]{10,})["\']?',
                re.IGNORECASE,
            ),
            r"\1=REDACTED",
        ),
        # AWS credentials
        (
            re.compile(
                r'(aws_access_key_id|aws_secret_access_key|aws_session_token)\s*[:=]\s*["\']?([^\s"\',}]+)["\']?',
                re.IGNORECASE,
            ),
            r"\1=REDACTED",
        ),
        # Database connection strings
        (
            re.compile(r"(postgres|postgresql|mysql|mongodb|redis)://[^@]+@[^\s]+", re.IGNORECASE),
            r"\1://REDACTED@REDACTED",
        ),
        # Email addresses (to protect PII)
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "EMAIL_REDACTED"),
        # Credit card numbers (basic pattern)
        (re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b"), "CC_NUMBER_REDACTED"),
        # American Express (15 digits)
        (re.compile(r"\b\d{4}[\s-]?\d{6}[\s-]?\d{5}\b"), "CC_NUMBER_REDACTED"),
        # Social Security Numbers
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN_REDACTED"),
        # Generic UUIDs (might be sensitive IDs)
        (
            re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
            "UUID_REDACTED",
        ),
    ]

    # Patterns for log messages that should be completely redacted
    FULL_REDACT_PATTERNS: List[Pattern[str]] = [
        re.compile(r"received.*key.*base64", re.IGNORECASE),
        re.compile(r"expected.*key.*base64", re.IGNORECASE),
        re.compile(r"all.*request.*headers", re.IGNORECASE),
    ]

    def __init__(self, name: str = ""):
        super().__init__(name)

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter a log record by redacting sensitive information.

        Args:
            record: The log record to filter

        Returns:
            True (always allows the record through, but with redacted content)
        """
        # Get the formatted message
        message = str(record.getMessage())

        # Check if the entire message should be redacted
        for pattern in self.FULL_REDACT_PATTERNS:
            if pattern.search(message):
                record.msg = "[REDACTED: Contains sensitive information]"
                record.args = ()  # Clear any formatting arguments
                return True

        # Apply pattern-based redaction
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            message = pattern.sub(replacement, message)

        # Update the record with the sanitized message
        record.msg = message
        record.args = ()  # Clear any formatting arguments to prevent re-formatting

        # Also sanitize any exception information
        if record.exc_info:
            # Format the exception to get the full traceback
            import traceback

            if record.exc_info[0] is not None:
                exc_lines = traceback.format_exception(*record.exc_info)
                sanitized_lines = []
                for line in exc_lines:
                    sanitized_line = line
                    for pattern, replacement in self.SENSITIVE_PATTERNS:
                        sanitized_line = pattern.sub(replacement, sanitized_line)
                    sanitized_lines.append(sanitized_line)
                # Store sanitized exception text
                record.exc_text = "".join(sanitized_lines).strip()

        return True


def add_sensitive_data_filter(logger: Optional[logging.Logger] = None) -> None:
    """
    Add the sensitive data filter to a logger or to the root logger.

    Args:
        logger: The logger to add the filter to. If None, adds to root logger.
    """
    if logger is None:
        logger = logging.getLogger()

    # Check if filter already exists to avoid duplicates
    for filter in logger.filters:
        if isinstance(filter, SensitiveDataFilter):
            return

    logger.addFilter(SensitiveDataFilter())


def configure_secure_logging() -> None:
    """
    Configure logging with security best practices.

    This function sets up the logging system with:
    - Sensitive data filtering
    - Appropriate log levels
    - Secure formatting
    """
    # Add sensitive data filter to root logger
    add_sensitive_data_filter()

    # Also add to any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(SensitiveDataFilter())
