"""
GitHub webhook handler for direct integration.
"""

import asyncio
import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any, Dict

from app.core.exceptions import ExternalServiceError
from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService
from app.webhooks.base import WebhookHandler, WebhookVerificationError
from supabase import Client

logger = logging.getLogger(__name__)


class GitHubWebhookHandler(WebhookHandler):
    """Handler for GitHub webhook events."""

    def __init__(self, webhook_secret: str, supabase: Client):
        """
        Initialize GitHub webhook handler.

        Args:
            webhook_secret: GitHub webhook secret for signature verification
            supabase: Supabase client for database operations
        """
        self.webhook_secret = webhook_secret
        self.supabase = supabase
        self.commit_analysis_service = CommitAnalysisService(supabase)

    async def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify GitHub webhook signature using HMAC-SHA256.

        Args:
            payload: Raw request body
            signature: Signature from X-Hub-Signature-256 header

        Returns:
            True if signature is valid

        Raises:
            WebhookVerificationError: If signature is invalid
        """
        if not signature:
            raise WebhookVerificationError("Missing X-Hub-Signature-256 header")

        # GitHub sends signature as "sha256=<signature>"
        if not signature.startswith("sha256="):
            raise WebhookVerificationError("Invalid signature format")

        expected_signature = "sha256=" + hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            logger.error(
                f"Signature verification failed. Expected: {expected_signature[:10]}..., Got: {signature[:10]}..."
            )
            raise WebhookVerificationError("Invalid webhook signature")

        logger.info("GitHub webhook signature verified successfully")
        return True

    def extract_event_type(self, headers: Dict[str, str], body: Dict[str, Any]) -> str:
        """
        Extract GitHub event type from headers.

        Args:
            headers: Request headers containing X-GitHub-Event
            body: Request body (unused for GitHub)

        Returns:
            GitHub event type
        """
        return headers.get("x-github-event", "unknown")

    async def process_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process GitHub webhook event.

        Args:
            event_type: GitHub event type (e.g., "push", "pull_request")
            event_data: Event payload from GitHub

        Returns:
            Processing result with commit analysis details
        """
        logger.info(f"Processing GitHub {event_type} event")

        if event_type == "push":
            try:
                return await self._process_push_event(event_data)
            except Exception as e:
                logger.error(f"Error processing push event: {e}", exc_info=True)
                raise ExternalServiceError(
                    service_name="GitHub Webhook", original_message=f"Failed to process push event: {str(e)}"
                )
        elif event_type == "pull_request":
            try:
                return await self._process_pull_request_event(event_data)
            except Exception as e:
                logger.error(f"Error processing pull_request event: {e}", exc_info=True)
                return {"status": "error", "reason": str(e)}
        elif event_type == "check_run":
            try:
                return await self._process_check_run_event(event_data)
            except Exception as e:
                logger.error(f"Error processing check_run event: {e}", exc_info=True)
                return {"status": "error", "reason": str(e)}
        elif event_type == "check_suite":
            try:
                return await self._process_check_suite_event(event_data)
            except Exception as e:
                logger.error(f"Error processing check_suite event: {e}", exc_info=True)
                return {"status": "error", "reason": str(e)}
        else:
            logger.info(f"Ignoring unsupported event: {event_type}")
            return {"status": "ignored", "reason": f"Event type {event_type} not processed"}

        try:
            return await self._process_push_event(event_data)
        except Exception as e:
            logger.error(f"Error processing push event: {e}", exc_info=True)
            raise ExternalServiceError(
                service_name="GitHub Webhook", original_message=f"Failed to process push event: {str(e)}"
            )

    async def _process_push_event(self, push_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a push event and analyze commits.

        Args:
            push_data: Push event payload from GitHub

        Returns:
            Processing result with analyzed commits
        """
        repository = push_data.get("repository", {})
        branch = push_data.get("ref", "").split("/")[-1]  # Extract branch name from refs/heads/branch

        # Extract repository info
        repository.get("name")
        repo_full_name = repository.get("full_name")  # owner/repo format
        repo_url = repository.get("html_url")

        logger.info(f"Processing push to {repo_full_name} on branch {branch}")

        # Process commits
        commits = push_data.get("commits", [])
        if not commits:
            logger.info("No commits in push event")
            return {"status": "success", "commits_processed": 0}

        # Filter out merge commits if needed
        non_merge_commits = [commit for commit in commits if not commit.get("message", "").startswith("Merge")]

        processed_commits = []
        errors = []

        # Process commits concurrently but with bounded concurrency to protect upstreams
        semaphore = asyncio.Semaphore(3)

        async def analyze_single(commit_data: Dict[str, Any]):
            async with semaphore:
                try:
                    commit_payload = self._convert_to_commit_payload(
                        commit_data, repository=repo_full_name, repo_url=repo_url, branch=branch
                    )
                    logger.info(f"Analyzing commit {commit_payload.commit_hash}")
                    result = await asyncio.wait_for(
                        self.commit_analysis_service.process_commit(commit_payload, scan_docs=True), timeout=90
                    )
                    if result:
                        processed_commits.append(
                            {
                                "hash": commit_payload.commit_hash,
                                "message": commit_payload.commit_message,
                                "status": "analyzed",
                            }
                        )
                    else:
                        errors.append({"hash": commit_payload.commit_hash, "error": "Analysis failed"})
                except asyncio.TimeoutError:
                    logger.error(f"Commit analysis timed out for {commit_data.get('id')}")
                    errors.append({"hash": commit_data.get("id"), "error": "Analysis timed out"})
                except Exception as e:
                    logger.error(f"Error processing commit {commit_data.get('id')}: {e}", exc_info=True)
                    errors.append({"hash": commit_data.get("id"), "error": str(e)})

        await asyncio.gather(*(analyze_single(commit) for commit in non_merge_commits))

        return {
            "status": "success",
            "repository": repo_full_name,
            "branch": branch,
            "commits_processed": len(processed_commits),
            "commits_failed": len(errors),
            "processed": processed_commits,
            "errors": errors,
        }

    def _convert_to_commit_payload(
        self, commit: Dict[str, Any], repository: str, repo_url: str, branch: str
    ) -> CommitPayload:
        """
        Convert GitHub commit data to CommitPayload format.

        Args:
            commit: Commit data from GitHub push event
            repository: Repository full name (owner/repo)
            repo_url: Repository HTML URL
            branch: Branch name

        Returns:
            CommitPayload object
        """
        # Extract author information
        author = commit.get("author", {})

        # Parse timestamp
        timestamp_str = commit.get("timestamp")
        if timestamp_str:
            # GitHub sends ISO format timestamps
            commit_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            commit_timestamp = datetime.utcnow()

        # Build diff URL
        diff_url = f"{commit.get('url', '')}.diff" if commit.get("url") else None

        return CommitPayload(
            commit_hash=commit.get("id"),
            commit_message=commit.get("message", ""),
            commit_url=commit.get("url") or f"{repo_url}/commit/{commit.get('id', '')}",
            commit_timestamp=commit_timestamp,
            author_github_username=author.get("username", ""),
            author_email=author.get("email", ""),
            repository_name=repository.split("/")[-1] if "/" in repository else repository,
            repository_url=repo_url,
            branch=branch,
            diff_url=diff_url,
            # Additional fields for full compatibility
            repository=repository,  # Full name in owner/repo format
            diff_data=None,  # Will be fetched by commit analysis service if needed
        )

    async def _process_pull_request_event(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        action = pr_data.get("action")
        pr = pr_data.get("pull_request", {})
        number = pr.get("number") or pr_data.get("number")
        repo = pr_data.get("repository", {}).get("full_name")
        logger.info(f"PR event: {repo}#{number} action={action}")
        # Mirror to logs for now; in future, sync to dashboard cache
        return {"status": "ok", "pr": number, "action": action}

    async def _process_check_run_event(self, cr_data: Dict[str, Any]) -> Dict[str, Any]:
        # Listen to requested_action from GitHub UI
        action = cr_data.get("action")
        check_run = cr_data.get("check_run", {})
        requested_action = check_run.get("requested_action")
        logger.info(f"check_run event action={action} requested_action={requested_action}")
        return {"status": "ok"}

    async def _process_check_suite_event(self, cs_data: Dict[str, Any]) -> Dict[str, Any]:
        action = cs_data.get("action")
        logger.info(f"check_suite event action={action}")
        return {"status": "ok"}
