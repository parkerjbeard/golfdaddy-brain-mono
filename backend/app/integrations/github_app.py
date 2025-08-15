"""GitHub App authentication and API integration service."""

import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import jwt
import requests

from app.config.settings import settings

logger = logging.getLogger(__name__)


class CheckRunStatus(Enum):
    """GitHub Check Run status values."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CheckRunConclusion(Enum):
    """GitHub Check Run conclusion values."""

    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"


class GitHubApp:
    """GitHub App integration for secure server-to-server authentication."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        private_key: Optional[str] = None,
        installation_id: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ):
        """
        Initialize GitHub App with credentials.

        Args:
            app_id: GitHub App ID
            private_key: Private key for JWT generation (PEM format)
            installation_id: Installation ID for the app
            webhook_secret: Secret for webhook signature verification
        """
        self.app_id = app_id or os.getenv("GITHUB_APP_ID")
        self.private_key = private_key or os.getenv("GITHUB_APP_PRIVATE_KEY")
        self.installation_id = installation_id or os.getenv("GITHUB_APP_INSTALLATION_ID")
        self.webhook_secret = webhook_secret or os.getenv("GITHUB_WEBHOOK_SECRET")

        if not all([self.app_id, self.private_key, self.installation_id]):
            logger.warning("GitHub App not fully configured. App ID, private key, and installation ID required.")

        self.base_url = "https://api.github.com"
        self._installation_token = None
        self._token_expires_at = None

    def generate_jwt(self) -> str:
        """
        Generate a JWT for GitHub App authentication.

        Returns:
            JWT token string
        """
        if not self.app_id or not self.private_key:
            raise ValueError("App ID and private key required for JWT generation")

        # JWT expires in 10 minutes (maximum allowed by GitHub)
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60 seconds ago to account for clock drift
            "exp": now + 600,  # Expires in 10 minutes
            "iss": self.app_id,
        }

        # Generate JWT
        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        return token

    def get_installation_token(self, force_refresh: bool = False) -> str:
        """
        Get or refresh installation access token.

        Args:
            force_refresh: Force token refresh even if not expired

        Returns:
            Installation access token
        """
        # Check if we have a valid token
        if (
            not force_refresh
            and self._installation_token
            and self._token_expires_at
            and datetime.now() < self._token_expires_at
        ):
            return self._installation_token

        # Generate new JWT
        jwt_token = self.generate_jwt()

        # Request installation token
        headers = {"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github.v3+json"}

        url = f"{self.base_url}/app/installations/{self.installation_id}/access_tokens"
        response = requests.post(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        self._installation_token = data["token"]

        # Parse expiration time
        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        # Refresh 5 minutes before expiration
        self._token_expires_at = expires_at - timedelta(minutes=5)

        logger.info(f"GitHub App installation token refreshed, expires at {self._token_expires_at}")
        return self._installation_token

    def get_headers(self) -> Dict[str, str]:
        """
        Get headers for authenticated API requests.

        Returns:
            Headers dictionary with authorization
        """
        token = self.get_installation_token()
        return {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    def verify_webhook(self, signature: str, body: bytes) -> bool:
        """
        Verify GitHub webhook signature.

        Args:
            signature: X-Hub-Signature-256 header value
            body: Raw request body bytes

        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured")
            return False

        # Compute expected signature
        expected_signature = "sha256=" + hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(expected_signature, signature)

    def create_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str, body: str = "", draft: bool = False
    ) -> Dict[str, Any]:
        """
        Create a pull request using REST API.

        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            head: Head branch
            base: Base branch
            body: PR description
            draft: Create as draft PR

        Returns:
            Pull request data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        headers = self.get_headers()

        data = {"title": title, "head": head, "base": base, "body": body, "draft": draft}

        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()

        pr_data = response.json()
        logger.info(f"Created PR #{pr_data['number']}: {pr_data['html_url']}")
        return pr_data

    def create_check_run(
        self,
        owner: str,
        repo: str,
        name: str,
        head_sha: str,
        status: CheckRunStatus = CheckRunStatus.IN_PROGRESS,
        details_url: Optional[str] = None,
        external_id: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a check run on a commit.

        Args:
            owner: Repository owner
            repo: Repository name
            name: Check run name (e.g., "Docs Approval")
            head_sha: Commit SHA
            status: Initial status
            details_url: URL to dashboard for details
            external_id: External identifier (e.g., proposal ID)
            output: Check run output (title, summary, text)

        Returns:
            Check run data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/check-runs"
        headers = self.get_headers()

        data = {"name": name, "head_sha": head_sha, "status": status.value}

        if details_url:
            data["details_url"] = details_url

        if external_id:
            data["external_id"] = external_id

        if output:
            data["output"] = output

        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()

        check_run = response.json()
        logger.info(f"Created check run '{name}' (ID: {check_run['id']}) for {head_sha[:8]}")
        return check_run

    def update_check_run(
        self,
        owner: str,
        repo: str,
        check_run_id: int,
        status: Optional[CheckRunStatus] = None,
        conclusion: Optional[CheckRunConclusion] = None,
        output: Optional[Dict[str, Any]] = None,
        completed_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing check run.

        Args:
            owner: Repository owner
            repo: Repository name
            check_run_id: Check run ID
            status: New status
            conclusion: Conclusion (required when status is completed)
            output: Updated output
            completed_at: Completion timestamp (ISO 8601)

        Returns:
            Updated check run data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/check-runs/{check_run_id}"
        headers = self.get_headers()

        data = {}

        if status:
            data["status"] = status.value

        if conclusion:
            data["conclusion"] = conclusion.value

        if output:
            data["output"] = output

        if completed_at:
            data["completed_at"] = completed_at
        elif status == CheckRunStatus.COMPLETED and not completed_at:
            data["completed_at"] = datetime.utcnow().isoformat() + "Z"

        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()

        check_run = response.json()
        logger.info(f"Updated check run {check_run_id}: status={status}, conclusion={conclusion}")
        return check_run

    def get_file_contents(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> Dict[str, Any]:
        """
        Get file contents from repository using Contents API.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path
            ref: Git ref (branch, tag, or SHA)

        Returns:
            File content data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        headers = self.get_headers()

        params = {}
        if ref:
            params["ref"] = ref

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()

    def create_or_update_file(
        self, owner: str, repo: str, path: str, message: str, content: str, branch: str, sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create or update a file using Contents API.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path
            message: Commit message
            content: File content (will be base64 encoded)
            branch: Branch to commit to
            sha: SHA of file being replaced (for updates)

        Returns:
            Commit data
        """
        import base64

        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        headers = self.get_headers()

        # Base64 encode content
        encoded_content = base64.b64encode(content.encode()).decode()

        data = {"message": message, "content": encoded_content, "branch": branch}

        if sha:
            data["sha"] = sha

        response = requests.put(url, json=data, headers=headers)
        response.raise_for_status()

        result = response.json()
        logger.info(f"{'Updated' if sha else 'Created'} file {path} on branch {branch}")
        return result

    def get_pull_request_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """
        Get the diff for a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Diff as string
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = self.get_headers()
        headers["Accept"] = "application/vnd.github.v3.diff"

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        return response.text

    def list_pull_request_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        List files changed in a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of file change data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        headers = self.get_headers()

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        return response.json()

    def create_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        state: str,
        target_url: Optional[str] = None,
        description: Optional[str] = None,
        context: str = "continuous-integration",
    ) -> Dict[str, Any]:
        """
        Create a commit status (legacy API, prefer check runs).

        Args:
            owner: Repository owner
            repo: Repository name
            sha: Commit SHA
            state: Status state (success, failure, error, pending)
            target_url: URL for more details
            description: Short description
            context: Context name

        Returns:
            Status data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/statuses/{sha}"
        headers = self.get_headers()

        data = {"state": state, "context": context}

        if target_url:
            data["target_url"] = target_url

        if description:
            data["description"] = description

        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()

        return response.json()
