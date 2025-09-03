"""
Direct webhook endpoints for external integrations.

This module replaces Make.com webhook forwarding with direct webhook handling.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

# Import Slack interactions router
from app.config.database import get_db
from app.config.settings import settings
from app.core.exceptions import BadRequestError, ConfigurationError, DatabaseError, ExternalServiceError
from app.webhooks.base import WebhookVerificationError
from app.webhooks.github import GitHubWebhookHandler
from supabase import Client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])

# Slack interactions removed with documentation agent cleanup


def get_github_webhook_handler(db: Client = Depends(get_db)) -> GitHubWebhookHandler:
    """
    Dependency to get GitHub webhook handler.

    Args:
        db: Database session

    Returns:
        Configured GitHubWebhookHandler instance

    Raises:
        ConfigurationError: If webhook secret is not configured
    """
    webhook_secret = settings.github_webhook_secret
    if not webhook_secret:
        raise ConfigurationError("GITHUB_WEBHOOK_SECRET not configured")

    return GitHubWebhookHandler(webhook_secret, db)


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
    handler: GitHubWebhookHandler = Depends(get_github_webhook_handler),
):
    """
    Handle GitHub webhook events directly.

    This endpoint receives webhooks from GitHub and processes them without
    going through Make.com. It verifies the webhook signature and processes
    push events to analyze commits.

    Headers:
        X-Hub-Signature-256: HMAC signature for verification
        X-GitHub-Event: Type of GitHub event
        X-GitHub-Delivery: Unique delivery ID

    Returns:
        202 Accepted with processing status
    """
    logger.info(f"Received GitHub webhook: event={x_github_event}, delivery={x_github_delivery}")

    # Get raw body for signature verification
    body = await request.body()

    # Verify webhook signature
    try:
        await handler.verify_signature(body, x_hub_signature_256 or "")
    except WebhookVerificationError as e:
        logger.error(f"GitHub webhook verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    # Parse JSON body
    try:
        event_data = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook body: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    # Process the event
    try:
        result = await handler.process_event(x_github_event or "unknown", event_data)

        logger.info(f"GitHub webhook processed successfully: {result}")
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "accepted",
                "delivery_id": x_github_delivery,
                "event_type": x_github_event,
                "result": result,
            },
        )

    except ExternalServiceError as e:
        logger.error(f"External service error processing webhook: {e}")
        # Return 202 to prevent GitHub from retrying
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "error",
                "delivery_id": x_github_delivery,
                "error": str(e),
                "message": "Webhook accepted but processing failed",
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {e}", exc_info=True)
        # Return 202 to prevent GitHub from retrying
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "error",
                "delivery_id": x_github_delivery,
                "error": "Internal error",
                "message": "Webhook accepted but processing failed",
            },
        )


@router.get("/github/status", status_code=status.HTTP_200_OK)
async def github_webhook_status():
    """
    Check GitHub webhook configuration status.

    Returns:
        Configuration status and health information
    """
    is_configured = bool(settings.github_webhook_secret)

    return {
        "status": "healthy" if is_configured else "not_configured",
        "webhook_secret_configured": is_configured,
        "endpoint": "/api/v1/webhooks/github",
        "supported_events": ["push"],
        "signature_header": "X-Hub-Signature-256",
        "signature_algorithm": "HMAC-SHA256",
    }
