#!/usr/bin/env python3
"""Entry point for CI documentation automation."""
import os
import subprocess
import logging
from doc_agent.client import AutoDocClient

logging.basicConfig(level=logging.INFO)


def main() -> None:
    commit_hash = os.environ.get("COMMIT_HASH")
    if not commit_hash:
        commit_hash = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        )

    repo_dir = os.environ.get("REPO_DIR", ".")

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    docs_repo = os.environ.get("DOCS_REPOSITORY", "")
    slack_webhook = os.environ.get("SLACK_WEBHOOK")

    client = AutoDocClient(openai_key, github_token, docs_repo, slack_webhook)

    diff = client.get_commit_diff(repo_dir, commit_hash)
    patch = client.analyze_diff(diff)
    if not patch:
        logging.info("No documentation changes proposed")
        return
    if client.propose_via_slack(patch):
        url = client.apply_patch(patch, commit_hash)
        if url:
            logging.info("Created documentation PR: %s", url)
        else:
            logging.error("Failed to create documentation PR")
    else:
        logging.info("Documentation update rejected")


if __name__ == "__main__":
    main()
