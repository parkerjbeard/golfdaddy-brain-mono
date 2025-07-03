#!/usr/bin/env python3
"""Entry point for CI documentation automation."""
import os
import subprocess
import logging
import asyncio
from doc_agent.client import AutoDocClient

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    commit_hash = os.environ.get("COMMIT_HASH")
    if not commit_hash:
        commit_hash = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        )

    repo_dir = os.environ.get("REPO_DIR", ".")

    # Get commit message
    commit_message = subprocess.check_output(
        ["git", "log", "-1", "--pretty=%B", commit_hash], 
        text=True
    ).strip()

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    docs_repo = os.environ.get("DOCS_REPOSITORY", "")
    slack_webhook = os.environ.get("SLACK_WEBHOOK")
    slack_channel = os.environ.get("SLACK_CHANNEL")

    client = AutoDocClient(openai_key, github_token, docs_repo, slack_webhook, slack_channel)

    diff = client.get_commit_diff(repo_dir, commit_hash)
    
    # Use context-aware analysis if available
    if hasattr(client, 'analyze_diff_with_context') and client.enable_semantic_search:
        from app.core.database import get_db
        async with get_db() as db:
            patch = await client.analyze_diff_with_context(diff, repo_dir, commit_hash, db)
    else:
        patch = await client.analyze_diff(diff)
    if not patch:
        logging.info("No documentation changes proposed")
        return
    
    # If Slack is configured, send for approval
    if slack_webhook or os.environ.get("SLACK_BOT_TOKEN"):
        approval_id = await client.propose_via_slack(diff, patch, commit_hash, commit_message)
        if approval_id:
            logging.info(f"Documentation approval request sent to Slack (ID: {approval_id})")
        else:
            logging.warning("Failed to send Slack approval request, creating PR directly")
            url = client.apply_patch(patch, commit_hash)
            if url:
                logging.info("Created documentation PR: %s", url)
            else:
                logging.error("Failed to create documentation PR")
    else:
        # No Slack configured, create PR directly
        url = client.apply_patch(patch, commit_hash)
        if url:
            logging.info("Created documentation PR: %s", url)
        else:
            logging.error("Failed to create documentation PR")


if __name__ == "__main__":
    asyncio.run(main())
