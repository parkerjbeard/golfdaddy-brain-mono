"""
Slack webhook endpoints for daily report collection via bot.
Handles slash commands, interactive messages, and conversation flow.
"""
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
import json
import logging
from datetime import datetime, timezone
import hashlib
import hmac
import time
from uuid import UUID

from app.config.settings import settings
from app.models.daily_report import DailyReport, ConversationState
from app.models.user import User
from app.services.slack_service import SlackService
from app.services.daily_report_service import DailyReportService
from app.services.slack_message_templates import SlackMessageTemplates
from app.services.slack_conversation_handler import SlackConversationHandler
from app.repositories.user_repository import UserRepository
from app.repositories.daily_report_repository import DailyReportRepository
from app.core.exceptions import ExternalServiceError

router = APIRouter(prefix="/slack/daily-reports", tags=["slack-daily-reports"])
logger = logging.getLogger(__name__)

# Initialize services
slack_service = SlackService()
templates = SlackMessageTemplates()
conversation_handler = SlackConversationHandler()


def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify the request came from Slack using signature verification."""
    if not settings.SLACK_SIGNING_SECRET:
        logger.warning("SLACK_SIGNING_SECRET not configured")
        return False
    
    # Check timestamp to prevent replay attacks (must be within 5 minutes)
    if abs(time.time() - float(timestamp)) > 60 * 5:
        logger.warning("Slack request timestamp too old")
        return False
    
    # Create signature base string
    sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    
    # Calculate expected signature
    my_signature = 'v0=' + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(my_signature, signature)


async def get_slack_request_body(request: Request) -> Dict[str, Any]:
    """Get and verify Slack request body."""
    # Get raw body
    body = await request.body()
    
    # Verify signature
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    
    if not verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid request signature")
    
    # Parse body based on content type
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return json.loads(body)
    else:
        # URL-encoded form data (slash commands)
        from urllib.parse import parse_qs
        parsed = parse_qs(body.decode('utf-8'))
        return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}


@router.post("/slash-command")
async def handle_slash_command(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle /eod slash command to start daily report submission.
    """
    try:
        body = await get_slack_request_body(request)
        
        command = body.get("command", "")
        slack_user_id = body.get("user_id", "")
        channel_id = body.get("channel_id", "")
        trigger_id = body.get("trigger_id", "")
        
        if command != "/eod":
            return {"text": "Unknown command"}
        
        # Delegate to conversation handler
        result = await conversation_handler.handle_eod_command(
            slack_user_id=slack_user_id,
            channel_id=channel_id,
            trigger_id=trigger_id
        )
        
        return result
            
    except Exception as e:
        logger.exception(f"Error handling slash command: {e}")
        return {"text": "❌ An error occurred. Please try again later."}


@router.post("/interactive")
async def handle_interactive_message(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle interactive messages (button clicks, message actions, modal submissions).
    """
    try:
        body = await get_slack_request_body(request)
        
        # Slack sends interactive payloads as JSON in a 'payload' field
        payload = json.loads(body.get("payload", "{}"))
        
        action_type = payload.get("type", "")
        user_info = payload.get("user", {})
        slack_user_id = user_info.get("id", "")
        
        if action_type == "view_submission":
            # Handle modal submission
            callback_id = payload.get("view", {}).get("callback_id", "")
            if callback_id in ["eod_report_submission", "eod_report_update"]:
                result = await conversation_handler.handle_modal_submission(
                    slack_user_id=slack_user_id,
                    view_data=payload.get("view", {})
                )
                return result
        
        elif action_type == "block_actions":
            # Handle button clicks
            actions = payload.get("actions", [])
            if actions:
                action = actions[0]
                response_url = payload.get("response_url", "")
                
                result = await conversation_handler.handle_button_interaction(
                    slack_user_id=slack_user_id,
                    action=action,
                    response_url=response_url
                )
                return result
        
        return {"text": "Action processed"}
        
    except Exception as e:
        logger.exception(f"Error handling interactive message: {e}")
        return {"text": "❌ An error occurred. Please try again."}


@router.post("/events")
async def handle_slack_events(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle Slack Events API (messages, app mentions, etc).
    """
    try:
        body = await get_slack_request_body(request)
        
        # Handle URL verification challenge
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge")}
        
        # Process events
        event = body.get("event", {})
        event_type = event.get("type", "")
        
        if event_type == "message":
            # Handle DM messages for report submission
            channel_type = event.get("channel_type", "")
            if channel_type == "im":  # Direct message
                slack_user_id = event.get("user", "")
                text = event.get("text", "")
                thread_ts = event.get("thread_ts", event.get("ts", ""))
                channel_id = event.get("channel", "")
                
                # Skip bot messages
                if event.get("bot_id"):
                    return {"ok": True}
                
                # Delegate to conversation handler
                background_tasks.add_task(
                    conversation_handler.handle_dm_message,
                    slack_user_id=slack_user_id,
                    channel_id=channel_id,
                    message_text=text,
                    thread_ts=thread_ts
                )
        
        return {"ok": True}
        
    except Exception as e:
        logger.exception(f"Error handling Slack event: {e}")
        return {"ok": False}

