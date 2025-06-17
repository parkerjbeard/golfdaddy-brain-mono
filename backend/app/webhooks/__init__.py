"""
Webhook handlers for direct integrations.

This module contains webhook handlers that replace Make.com integrations
with direct webhook processing.
"""

from .base import WebhookHandler, WebhookVerificationError
from .github import GitHubWebhookHandler

__all__ = [
    "WebhookHandler",
    "WebhookVerificationError",
    "GitHubWebhookHandler",
]