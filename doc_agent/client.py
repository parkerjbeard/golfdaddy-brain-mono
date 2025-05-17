import os
import subprocess
import tempfile
import logging
from typing import Optional

from github import Github
from github import GithubException

# Placeholder import for OpenAI
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)

class AutoDocClient:
    """Thin layer between Git and OpenAI for automated documentation."""

    def __init__(self, openai_api_key: str, github_token: str, docs_repo: str,
                 slack_webhook: Optional[str] = None) -> None:
        self.openai_api_key = openai_api_key
        self.github_token = github_token
        self.docs_repo = docs_repo
        self.slack_webhook = slack_webhook
        self.github = Github(github_token) if github_token else None
        self.openai_client = OpenAI(api_key=openai_api_key) if OpenAI else None

    def get_commit_diff(self, repo_path: str, commit_hash: str) -> str:
        """Return the diff for the given commit."""
        diff = subprocess.check_output(
            ["git", "-C", repo_path, "show", commit_hash], text=True
        )
        return diff

    def analyze_diff(self, diff: str) -> str:
        """Use OpenAI to generate a documentation patch from a commit diff."""
        if not self.openai_client:
            logger.warning("OpenAI client not available, returning placeholder diff")
            return ""  # In testing environments

        prompt = (
            "You are an expert technical writer. Given the following git diff, "
            "suggest documentation updates as a unified diff."
        )

        response = self.openai_client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[{"role": "system", "content": prompt},
                     {"role": "user", "content": diff}],
            temperature=0.2,
        )
        return response.choices[0].message.content

    def propose_via_slack(self, diff: str) -> bool:
        """Send the proposed diff to Slack for manual approval (placeholder)."""
        if not diff:
            return False
        logger.info("Proposing documentation changes via Slack (placeholder)...")
        # Placeholder Slack logic - print to stdout
        print("Proposed documentation diff:\n", diff)
        # In real implementation, send to Slack and wait for approval
        return True

    def apply_patch(self, diff: str, commit_hash: str, branch_name: Optional[str] = None) -> Optional[str]:
        """Apply the diff to the docs repository and create a PR."""
        if not self.github:
            logger.error("GitHub client not configured")
            return None

        if not branch_name:
            branch_name = f"auto-docs-{commit_hash[:7]}"

        repo = self.github.get_repo(self.docs_repo)
        base = repo.default_branch

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_url = f"https://{self.github_token}@github.com/{self.docs_repo}.git"
            subprocess.check_call(["git", "clone", repo_url, tmpdir])
            subprocess.check_call(["git", "-C", tmpdir, "checkout", "-b", branch_name])
            patch_file = os.path.join(tmpdir, "patch.diff")
            with open(patch_file, "w") as f:
                f.write(diff)
            try:
                subprocess.check_call(["git", "-C", tmpdir, "apply", "patch.diff"], cwd=tmpdir)
            except subprocess.CalledProcessError:
                logger.error("Failed to apply documentation patch")
                return None
            subprocess.check_call(["git", "-C", tmpdir, "commit", "-am", "Automated documentation update"])
            subprocess.check_call(["git", "-C", tmpdir, "push", "origin", branch_name])

        pr = repo.create_pull(
            title=f"Automated docs update for {commit_hash}",
            body="This PR contains automated documentation updates.",
            head=branch_name,
            base=base,
        )
        return pr.html_url
