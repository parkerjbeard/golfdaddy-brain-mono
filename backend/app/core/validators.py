"""
Validators for user input, particularly for EOD reports.
"""

import logging
import re
import unicodedata
from datetime import datetime
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class ReportValidator:
    """Validates EOD report content for quality and security."""

    # Content requirements
    MIN_WORDS = 10  # Minimum meaningful words
    MIN_CHARACTERS = 50  # Absolute minimum characters
    MAX_CHARACTERS = 5000  # Maximum report length
    MIN_UNIQUE_WORDS = 5  # Prevent repeated word spam

    # Suspicious patterns that might indicate prompt injection
    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+previous",
        r"disregard\s+previous",
        r"forget\s+everything",
        r"system\s*:\s*you\s+are",
        r"assistant\s*:\s*i\s+am",
        r"\\n\s*system\s*:",
        r"\\n\s*assistant\s*:",
        r"new\s+instructions\s*:",
        r"you\s+are\s+now",
        r"act\s+as\s+if",
        r"pretend\s+to\s+be",
        r"<\|.*?\|>",  # Special tokens
        r"\[\[.*?\]\]",  # Instruction markers
    ]

    # Meaningless content patterns
    SPAM_PATTERNS = [
        r"^[asdfjkl;]+$",  # Keyboard mashing
        r"^(.)\1{10,}$",  # Repeated characters
        r"^(test\s*)+$",  # Just "test test test"
        r"^[\W_]+$",  # Only special characters
        r"^[\d\s]+$",  # Only numbers
    ]

    # Valid work-related keywords (at least one should be present)
    WORK_KEYWORDS = [
        "worked",
        "completed",
        "finished",
        "implemented",
        "fixed",
        "reviewed",
        "met",
        "discussed",
        "analyzed",
        "created",
        "updated",
        "tested",
        "debugged",
        "deployed",
        "designed",
        "wrote",
        "built",
        "configured",
        "investigated",
        "resolved",
        "attended",
        "presented",
        "documented",
        "merged",
        "submitted",
        "approved",
        "planned",
        "researched",
        "optimized",
        "refactored",
        "meeting",
        "task",
        "feature",
        "bug",
        "issue",
        "project",
        "code",
        "review",
        "pull request",
        "pr",
        "commit",
        "branch",
        "ticket",
    ]

    @classmethod
    def validate_report_content(cls, content: str) -> Tuple[bool, List[str]]:
        """
        Validate report content for quality and security.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if not content or not content.strip():
            errors.append("Report content cannot be empty")
            return False, errors

        # Clean content for analysis
        cleaned_content = cls._clean_content(content)

        # Length checks
        if len(cleaned_content) < cls.MIN_CHARACTERS:
            errors.append(f"Report must be at least {cls.MIN_CHARACTERS} characters long")

        if len(cleaned_content) > cls.MAX_CHARACTERS:
            errors.append(f"Report cannot exceed {cls.MAX_CHARACTERS} characters")

        # Word count and uniqueness
        words = cls._extract_words(cleaned_content)
        if len(words) < cls.MIN_WORDS:
            errors.append(f"Report must contain at least {cls.MIN_WORDS} words")

        unique_words = set(word.lower() for word in words)
        if len(unique_words) < cls.MIN_UNIQUE_WORDS:
            errors.append("Report must contain more diverse content")

        # Check for spam patterns
        if cls._contains_spam(cleaned_content):
            errors.append("Report appears to contain meaningless content")

        # Check for work-related content
        if not cls._contains_work_content(cleaned_content, words):
            errors.append("Report must describe work-related activities")

        # Security checks
        if cls._contains_prompt_injection(content):
            errors.append("Report contains suspicious patterns")
            logger.warning(f"Potential prompt injection detected in report")

        return len(errors) == 0, errors

    @classmethod
    def sanitize_for_ai(cls, content: str) -> str:
        """
        Sanitize content before sending to AI.
        Removes potential prompt injection attempts.
        """
        # Remove suspicious patterns
        sanitized = content
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "[REMOVED]", sanitized, flags=re.IGNORECASE)

        # Remove excessive whitespace
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

        # Limit consecutive newlines
        sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)

        return sanitized

    @classmethod
    def _clean_content(cls, content: str) -> str:
        """Clean content for validation."""
        # Normalize unicode
        content = unicodedata.normalize("NFKC", content)

        # Remove excessive whitespace but preserve structure
        content = re.sub(r"[ \t]+", " ", content)
        content = re.sub(r"\n{3,}", "\n\n", content)

        return content.strip()

    @classmethod
    def _extract_words(cls, content: str) -> List[str]:
        """Extract meaningful words from content."""
        # Remove URLs
        content = re.sub(r"https?://\S+", "", content)

        # Extract words (including contractions)
        words = re.findall(r"\b[\w']+\b", content)

        # Filter out very short words and numbers
        words = [w for w in words if len(w) > 2 or w.lower() in ["i", "me", "we", "us"]]

        return words

    @classmethod
    def _contains_spam(cls, content: str) -> bool:
        """Check if content matches spam patterns."""
        content_lower = content.lower()

        for pattern in cls.SPAM_PATTERNS:
            if re.match(pattern, content_lower):
                return True

        # Check for excessive repetition
        words = cls._extract_words(content)
        if words:
            word_freq: Dict[str, int] = {}
            for word in words:
                word_lower = word.lower()
                word_freq[word_lower] = word_freq.get(word_lower, 0) + 1

            # If one word makes up more than 50% of content, it's spam
            max_freq = max(word_freq.values())
            if max_freq > len(words) * 0.5 and len(words) > 5:
                return True

        return False

    @classmethod
    def _contains_work_content(cls, content: str, words: List[str]) -> bool:
        """Check if content contains work-related keywords."""
        content_lower = content.lower()
        words_lower = [w.lower() for w in words]

        # Check for work keywords
        for keyword in cls.WORK_KEYWORDS:
            if keyword in content_lower or keyword in words_lower:
                return True

        # Check for time-related content (hours, time spent, etc.)
        time_patterns = [
            r"\b\d+\s*hours?\b",
            r"\b\d+\s*minutes?\b",
            r"\bspent\s+time\b",
            r"\bworked\s+on\b",
        ]

        for pattern in time_patterns:
            if re.search(pattern, content_lower):
                return True

        return False

    @classmethod
    def _contains_prompt_injection(cls, content: str) -> bool:
        """Check for potential prompt injection attempts."""
        content_lower = content.lower()

        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return True

        return False


class DateValidator:
    """Validates dates with timezone awareness."""

    @staticmethod
    def is_same_day_user_timezone(dt1: datetime, dt2: datetime, timezone_str: str) -> bool:
        """
        Check if two datetimes are on the same day in user's timezone.

        Args:
            dt1: First datetime (timezone-aware)
            dt2: Second datetime (timezone-aware)
            timezone_str: User's timezone (e.g., 'America/Los_Angeles')
        """
        try:
            from zoneinfo import ZoneInfo

            # Convert to user's timezone
            user_tz = ZoneInfo(timezone_str)
            dt1_local = dt1.astimezone(user_tz)
            dt2_local = dt2.astimezone(user_tz)

            # Compare dates
            return dt1_local.date() == dt2_local.date()

        except Exception as e:
            logger.error(f"Error comparing dates in timezone {timezone_str}: {e}")
            # Fallback to UTC comparison
            return dt1.date() == dt2.date()

    @staticmethod
    def get_user_midnight_utc(date: datetime, timezone_str: str) -> datetime:
        """
        Get midnight in user's timezone converted to UTC.

        Args:
            date: Date to get midnight for
            timezone_str: User's timezone

        Returns:
            UTC datetime representing midnight in user's timezone
        """
        try:
            from zoneinfo import ZoneInfo

            user_tz = ZoneInfo(timezone_str)

            # Create midnight in user's timezone
            local_midnight = date.replace(hour=0, minute=0, second=0, microsecond=0)
            if local_midnight.tzinfo is None:
                local_midnight = local_midnight.replace(tzinfo=user_tz)
            else:
                local_midnight = local_midnight.astimezone(user_tz)

            # Convert to UTC
            return local_midnight.astimezone(ZoneInfo("UTC"))

        except Exception as e:
            logger.error(f"Error calculating midnight for timezone {timezone_str}: {e}")
            # Fallback to UTC midnight
            return date.replace(hour=0, minute=0, second=0, microsecond=0)
