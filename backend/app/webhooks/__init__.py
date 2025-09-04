"""
Webhook handlers for direct integrations with external services.
"""

from .base import WebhookHandler, WebhookVerificationError
from .github import GitHubWebhookHandler

__all__ = [
    "WebhookHandler",
    "WebhookVerificationError",
    "GitHubWebhookHandler",
]
