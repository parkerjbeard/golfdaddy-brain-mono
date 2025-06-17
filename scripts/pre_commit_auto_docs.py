#!/usr/bin/env python3
"""Pre-commit hook for documentation automation."""
import os
import subprocess
import logging
from doc_agent.client import AutoDocClient

logging.basicConfig(level=logging.INFO)


def main() -> int:
    diff = subprocess.check_output(["git", "diff", "--cached"], text=True)
    if not diff.strip():
        return 0

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    docs_repo = os.environ.get("DOCS_REPOSITORY", "")
    slack_webhook = os.environ.get("SLACK_WEBHOOK")

    client = AutoDocClient(openai_key, github_token, docs_repo, slack_webhook)
    patch = client.analyze_diff(diff)
    if not patch:
        logging.info("No documentation changes suggested")
        return 0

    if client.propose_via_slack(patch):
        logging.info("Documentation suggestions sent to Slack for review")
    else:
        logging.info("Documentation update skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
