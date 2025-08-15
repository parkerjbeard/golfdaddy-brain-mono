"""
Base webhook handler classes and utilities.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class WebhookVerificationError(Exception):
    """Raised when webhook signature verification fails."""

    pass


class WebhookHandler(ABC):
    """Abstract base class for webhook handlers."""

    @abstractmethod
    async def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify the webhook signature.

        Args:
            payload: Raw request body
            signature: Signature from webhook headers

        Returns:
            True if signature is valid

        Raises:
            WebhookVerificationError: If signature is invalid
        """
        pass

    @abstractmethod
    async def process_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the webhook event.

        Args:
            event_type: Type of webhook event
            event_data: Event payload data

        Returns:
            Processing result
        """
        pass

    def extract_event_type(self, headers: Dict[str, str], body: Dict[str, Any]) -> str:
        """
        Extract event type from webhook headers or body.

        Args:
            headers: Request headers
            body: Request body

        Returns:
            Event type string
        """
        # Default implementation - override in subclasses
        return "unknown"
