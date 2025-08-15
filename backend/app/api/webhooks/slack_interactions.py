"""
Webhook endpoint for handling Slack interactive components.
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.database import get_db
from app.models.doc_approval import DocApproval
from app.services.slack_service import SlackService

from app.integrations.github_app import CheckRunConclusion, CheckRunStatus
from app.doc_agent.client_v2 import AutoDocClientV2

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify the request came from Slack using signing secret."""
    if not settings.SLACK_SIGNING_SECRET:
        logger.warning("SLACK_SIGNING_SECRET not configured")
        return False

    # Check timestamp is recent (within 5 minutes)
    if abs(time.time() - float(timestamp)) > 60 * 5:
        return False

    # Create signature base string
    sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"

    # Create HMAC SHA256 signature
    my_signature = (
        "v0="
        + hmac.new(
            settings.SLACK_SIGNING_SECRET.encode("utf-8"), sig_basestring.encode("utf-8"), hashlib.sha256
        ).hexdigest()
    )

    # Compare signatures
    return hmac.compare_digest(my_signature, signature)


@router.post("/slack/interactions")
async def handle_slack_interactions(request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Handle Slack interactive component callbacks."""
    # Get request body
    body = await request.body()

    # Verify Slack signature
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse payload
    form_data = await request.form()
    payload_str = form_data.get("payload")
    if not payload_str:
        raise HTTPException(status_code=400, detail="No payload")

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Handle different interaction types
    interaction_type = payload.get("type")

    if interaction_type == "block_actions":
        return await handle_block_actions(payload, db)
    elif interaction_type == "view_submission":
        return await handle_view_submission(payload, db)
    else:
        logger.warning(f"Unhandled interaction type: {interaction_type}")
        return {"text": "Interaction received"}


async def handle_block_actions(payload: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Handle block action interactions (button clicks)."""
    actions = payload.get("actions", [])
    if not actions:
        return {"text": "No actions found"}

    action = actions[0]  # Process first action
    action_id = action.get("action_id")
    value = action.get("value")

    if action_id == "approve_doc_update":
        return await handle_doc_approval(value, payload, db)
    elif action_id == "reject_doc_update":
        return await handle_doc_rejection(value, payload, db)
    elif action_id == "view_full_diff":
        return await handle_view_full_diff(value, payload, db)
    else:
        logger.warning(f"Unhandled action_id: {action_id}")
        return {"text": "Action received"}


async def handle_doc_approval(approval_id: str, payload: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Handle documentation approval."""
    try:
        # Get approval record
        result = await db.execute(select(DocApproval).where(DocApproval.id == approval_id))
        approval = result.scalar_one_or_none()

        if not approval:
            return {"response_type": "ephemeral", "text": "❌ Approval request not found or expired."}

        if approval.status != "pending":
            return {"response_type": "ephemeral", "text": f"⚠️ This request has already been {approval.status}."}

        # Check if expired
        if approval.expires_at and approval.expires_at < datetime.utcnow():
            approval.status = "expired"
            await db.commit()
            return {"response_type": "ephemeral", "text": "⏰ This approval request has expired."}

        # Get user info
        user = payload.get("user", {})
        user_id = user.get("id")
        user_name = user.get("name", "Unknown")

        # Create PR using GitHub App-based doc agent (secure, no shelling)
        client = AutoDocClientV2(
            openai_api_key=settings.OPENAI_API_KEY or "",
            docs_repo=approval.repository or (settings.DOCS_REPOSITORY or ""),
            slack_channel=settings.SLACK_DEFAULT_CHANNEL,
            enable_semantic_search=False,
            use_github_app=True,
        )

        pr_data = await client.create_pr_with_check_run(
            approval.patch_content,
            approval.commit_hash,
            approval_id=str(approval.id),
        )

        pr_url = pr_data["pr_url"] if pr_data else None

        if pr_url:
            # Update approval record
            approval.status = "approved"
            approval.approved_by = user_id
            approval.approved_at = datetime.utcnow()
            approval.pr_url = pr_url
            if pr_data:
                approval.pr_number = pr_data.get("pr_number")
                approval.check_run_id = str(pr_data.get("check_run_id")) if pr_data.get("check_run_id") else None
                approval.head_sha = pr_data.get("head_sha")
            await db.commit()

            # Update the original message
            slack_service = SlackService()
            channel = payload.get("channel", {}).get("id")
            message_ts = payload.get("message", {}).get("ts")

            if channel and message_ts:
                # Create updated message
                original_blocks = payload.get("message", {}).get("blocks", [])
                # Update header to show approved
                if original_blocks:
                    original_blocks[0] = {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "✅ Documentation Update Approved", "emoji": True},
                    }
                    # Add approval info
                    original_blocks.append(
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*Approved by:* <@{user_id}>\n*PR:* <{pr_url}>"},
                        }
                    )
                    # Remove action buttons
                    original_blocks = [b for b in original_blocks if b.get("type") != "actions"]

                await slack_service.client.chat_update(channel=channel, ts=message_ts, blocks=original_blocks)

            return {
                "response_type": "in_channel",
                "text": f"✅ Documentation update approved by {user_name}! PR created: {pr_url}",
            }
        else:
            return {"response_type": "ephemeral", "text": "❌ Failed to create PR. Please check the logs."}

    except Exception as e:
        logger.error(f"Error handling doc approval: {e}")
        return {"response_type": "ephemeral", "text": "❌ An error occurred while processing the approval."}


async def handle_doc_rejection(approval_id: str, payload: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Handle documentation rejection."""
    try:
        # Get approval record
        result = await db.execute(select(DocApproval).where(DocApproval.id == approval_id))
        approval = result.scalar_one_or_none()

        if not approval:
            return {"response_type": "ephemeral", "text": "❌ Approval request not found or expired."}

        if approval.status != "pending":
            return {"response_type": "ephemeral", "text": f"⚠️ This request has already been {approval.status}."}

        # Get user info
        user = payload.get("user", {})
        user_id = user.get("id")
        user_name = user.get("name", "Unknown")

        # Open modal for rejection reason
        slack_service = SlackService()
        trigger_id = payload.get("trigger_id")

        if trigger_id:
            modal_view = {
                "type": "modal",
                "callback_id": f"reject_reason_{approval_id}",
                "title": {"type": "plain_text", "text": "Rejection Reason"},
                "submit": {"type": "plain_text", "text": "Submit"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "reason_block",
                        "label": {"type": "plain_text", "text": "Please provide a reason for rejection:"},
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "reason_input",
                            "multiline": True,
                            "placeholder": {"type": "plain_text", "text": "Enter your reason here..."},
                        },
                    }
                ],
            }

            await slack_service.open_modal(trigger_id=trigger_id, view=modal_view)

        # Update the approval record
        approval.status = "rejected"
        approval.approved_by = user_id
        approval.approved_at = datetime.utcnow()
        await db.commit()

        # Update the original message
        slack_service = SlackService()
        channel = payload.get("channel", {}).get("id")
        message_ts = payload.get("message", {}).get("ts")

        if channel and message_ts:
            # Create updated message
            original_blocks = payload.get("message", {}).get("blocks", [])
            # Update header to show rejected
            if original_blocks:
                original_blocks[0] = {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "❌ Documentation Update Rejected", "emoji": True},
                }
                # Add rejection info
                original_blocks.append(
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*Rejected by:* <@{user_id}>"}}
                )
                # Remove action buttons
                original_blocks = [b for b in original_blocks if b.get("type") != "actions"]

            await slack_service.client.chat_update(channel=channel, ts=message_ts, blocks=original_blocks)

        return {"response_type": "in_channel", "text": f"❌ Documentation update rejected by {user_name}."}

    except Exception as e:
        logger.error(f"Error handling doc rejection: {e}")
        return {"response_type": "ephemeral", "text": "❌ An error occurred while processing the rejection."}


async def handle_view_full_diff(approval_id: str, payload: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Handle view full diff request."""
    try:
        # Get approval record
        result = await db.execute(select(DocApproval).where(DocApproval.id == approval_id))
        approval = result.scalar_one_or_none()

        if not approval:
            return {"response_type": "ephemeral", "text": "❌ Approval request not found."}

        # Open modal with full diff
        slack_service = SlackService()
        user_id = payload.get("user", {}).get("id")
        trigger_id = payload.get("trigger_id")

        if trigger_id:
            # Create modal with diff content
            modal_view = {
                "type": "modal",
                "title": {"type": "plain_text", "text": "Full Diff"},
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "📄 Full Documentation Diff", "emoji": True},
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Repository:* `{approval.repository}`\n*Commit:* `{approval.commit_hash[:8]}`",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"```{approval.diff_content[:2900]}```"},  # Slack limits
                    },
                ],
            }

            await slack_service.open_modal(trigger_id=trigger_id, view=modal_view)

            return {"ok": True}

        # Fallback to sending as message if no trigger_id
        # Split diff into chunks if too long
        diff_content = approval.diff_content
        max_length = 3000

        if len(diff_content) <= max_length:
            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": "📄 Full Documentation Diff", "emoji": True}},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Repository:* `{approval.repository}`\n*Commit:* `{approval.commit_hash[:8]}`",
                    },
                },
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"```\n{diff_content}\n```"}},
            ]

            return {"response_type": "ephemeral", "blocks": blocks}
        else:
            # Send as file attachment for large diffs
            return {
                "response_type": "ephemeral",
                "text": "The diff is too large to display. Please review the approval request or check the repository directly.",
            }

    except Exception as e:
        logger.error(f"Error viewing full diff: {e}")
        return {"response_type": "ephemeral", "text": "❌ An error occurred while retrieving the diff."}


async def handle_view_submission(payload: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Handle modal view submissions."""
    # Placeholder for future modal interactions
    return {"response_action": "clear"}
