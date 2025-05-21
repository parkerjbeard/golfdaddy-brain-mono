import os
import subprocess
import tempfile
import logging
import time
import asyncio
from typing import Optional, List, Dict, Any

from github import Github
from github import GithubException

# Import settings
from app.config.settings import settings # Assuming this path

# Use AsyncOpenAI
try:
    from openai import AsyncOpenAI, OpenAIError # Added OpenAIError
except ImportError: # Adjusted for clarity
    AsyncOpenAI = None  # type: ignore
    OpenAIError = None # type: ignore

logger = logging.getLogger(__name__)


def _retry(
    func,
    *args,
    retries: int = 3,
    initial_delay: float = 1.0,
    backoff: int = 2,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs,
) -> Any:
    """Retry a synchronous function with exponential backoff."""
    delay = initial_delay
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as exc:  # pragma: no cover - simple retry logic
            if attempt == retries:
                raise
            logger.warning(
                "Attempt %s/%s failed for %s: %s. Retrying in %.1fs",
                attempt,
                retries,
                getattr(func, "__name__", str(func)),
                exc,
                delay,
            )
            time.sleep(delay)
            delay *= backoff


async def _async_retry(
    func,
    *args,
    retries: int = 3,
    initial_delay: float = 1.0,
    backoff: int = 2,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs,
) -> Any:
    """Retry an async function with exponential backoff."""
    delay = initial_delay
    for attempt in range(1, retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as exc:  # pragma: no cover - simple retry logic
            if attempt == retries:
                raise
            logger.warning(
                "Attempt %s/%s failed for %s: %s. Retrying in %.1fs",
                attempt,
                retries,
                getattr(func, "__name__", str(func)),
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay *= backoff

# Default model if not specified
# DEFAULT_DOC_AGENT_MODEL = "gpt-4.1-2025-04-14" # Example, align with your preferred default

class AutoDocClient:
    """Thin layer between Git and OpenAI for automated documentation."""

    def __init__(self, openai_api_key: str, github_token: str, docs_repo: str,
                 slack_webhook: Optional[str] = None) -> None: # Removed openai_model parameter
        if not openai_api_key:
            raise ValueError("OpenAI API key is required.")
        self.openai_api_key = openai_api_key
        
        if not github_token: # Added check for github_token for consistency
            raise ValueError("GitHub token is required.")
        self.github_token = github_token
        
        self.docs_repo = docs_repo
        self.slack_webhook = slack_webhook
        self.github = Github(github_token)
        
        if AsyncOpenAI:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        else:
            logger.warning("AsyncOpenAI client not available. Functionality will be limited.")
            self.openai_client = None
            
        self.openai_model = settings.doc_agent_openai_model # Use model from settings

    def get_commit_diff(self, repo_path: str, commit_hash: str) -> str:
        """Return the diff for the given commit."""
        diff = subprocess.check_output(
            ["git", "-C", repo_path, "show", commit_hash], text=True
        )
        return diff

    async def analyze_diff(self, diff: str) -> str:
        """Use OpenAI to generate a documentation patch from a commit diff."""
        if not self.openai_client:
            logger.warning("OpenAI client not available, returning empty string.")
            return ""

        prompt = (
            "You are an expert technical writer. Given the following git diff, "
            "suggest documentation updates as a unified diff. Ensure the output is ONLY the diff content itself, no extra explanations or markdown."
        )

        api_params: Dict[str, Any] = {
            "model": self.openai_model,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": diff}],
        }

        async def _call_openai() -> Any:
            return await self.openai_client.chat.completions.create(**api_params)

        try:
            response = await _async_retry(_call_openai, exceptions=(OpenAIError,))
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                return content.strip() if content else ""
            logger.error("OpenAI response did not contain expected content.")
            return ""
        except Exception as exc:
            logger.error("Failed to analyze diff with OpenAI: %s", exc)
            return ""

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

        logger.info(
            "Applying patch for commit %s to repo %s on branch %s",
            commit_hash,
            self.docs_repo,
            branch_name,
        )

        repo = self.github.get_repo(self.docs_repo)
        base = repo.default_branch

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_url = f"https://{self.github_token}@github.com/{self.docs_repo}.git"
            try:
                subprocess.check_call(["git", "clone", repo_url, tmpdir])
            except subprocess.CalledProcessError as exc:
                logger.error("Git clone failed: %s", exc)
                if "authentication" in str(exc).lower() or "permission" in str(exc).lower():
                    logger.error("Git authentication failed. Check GITHUB_TOKEN")
                return None

            try:
                subprocess.check_call(["git", "-C", tmpdir, "checkout", "-b", branch_name])
            except subprocess.CalledProcessError as exc:
                logger.error("Failed to create branch %s: %s", branch_name, exc)
                return None

            patch_file = os.path.join(tmpdir, "patch.diff")
            with open(patch_file, "w") as f:
                f.write(diff)

            try:
                subprocess.check_call(["git", "-C", tmpdir, "apply", "--check", "patch.diff"], cwd=tmpdir)
            except subprocess.CalledProcessError:
                logger.error("Patch does not apply cleanly")
                return None

            try:
                subprocess.check_call(["git", "-C", tmpdir, "apply", "patch.diff"], cwd=tmpdir)
            except subprocess.CalledProcessError as exc:
                logger.error("Failed to apply documentation patch: %s", exc)
                return None

            subprocess.check_call(["git", "-C", tmpdir, "commit", "-am", "Automated documentation update"])

            try:
                subprocess.check_call(["git", "-C", tmpdir, "push", "origin", branch_name])
            except subprocess.CalledProcessError as exc:
                logger.error("Git push failed for branch %s: %s", branch_name, exc)
                return None

        def _create_pull() -> Any:
            return repo.create_pull(
                title=f"Automated docs update for {commit_hash}",
                body="This PR contains automated documentation updates.",
                head=branch_name,
                base=base,
            )

        try:
            pr = _retry(_create_pull, exceptions=(GithubException,))
        except Exception as exc:
            logger.error("Failed to create pull request: %s", exc)
            return None

        logger.info("Created pull request %s for commit %s", pr.html_url, commit_hash)
        return pr.html_url
