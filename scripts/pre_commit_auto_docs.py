#!/usr/bin/env python3
"""Pre-commit hook for documentation automation."""
import os
import subprocess
import logging
import asyncio
from doc_agent.client import AutoDocClient

logging.basicConfig(level=logging.INFO)


async def analyze_and_propose(client: AutoDocClient, diff: str) -> bool:
    """
    Async wrapper for analyzing diff and proposing changes.
    
    Args:
        client: AutoDocClient instance
        diff: Git diff content
        
    Returns:
        True if proposal was sent, False otherwise
    """
    # Analyze the diff
    patch = await client.analyze_diff(diff)
    if not patch:
        logging.info("No documentation changes suggested")
        return False
    
    # Get commit information for better context
    commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    commit_message = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], text=True).strip()
    
    # Propose via Slack
    approval_id = await client.propose_via_slack(
        diff=diff,
        patch=patch,
        commit_hash=commit_hash,
        commit_message=commit_message
    )
    
    if approval_id:
        logging.info(f"Documentation suggestions sent to Slack for review (ID: {approval_id})")
        return True
    else:
        logging.info("Documentation update skipped")
        return False


def main() -> int:
    """Main entry point for pre-commit hook."""
    # Get the staged diff
    diff = subprocess.check_output(["git", "diff", "--cached"], text=True)
    if not diff.strip():
        return 0
    
    # Get configuration from environment
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    docs_repo = os.environ.get("DOCS_REPOSITORY", "")
    slack_webhook = os.environ.get("SLACK_WEBHOOK")
    
    # Create client
    client = AutoDocClient(openai_key, github_token, docs_repo, slack_webhook)
    
    # Run async function
    try:
        asyncio.run(analyze_and_propose(client, diff))
    except Exception as e:
        logging.error(f"Error during documentation analysis: {e}")
        # Don't block the commit on errors
        return 0
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
