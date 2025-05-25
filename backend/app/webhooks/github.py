"""
GitHub webhook handler for direct integration.
"""
import hmac
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.webhooks.base import WebhookHandler, WebhookVerificationError
from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService
from app.core.exceptions import (
    ExternalServiceError,
    BadRequestError,
    AIIntegrationError,
    DatabaseError
)
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
        
        expected_signature = "sha256=" + hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, signature):
            logger.error(f"Signature verification failed. Expected: {expected_signature[:10]}..., Got: {signature[:10]}...")
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
        
        if event_type != "push":
            logger.info(f"Ignoring non-push event: {event_type}")
            return {"status": "ignored", "reason": f"Event type {event_type} not processed"}
        
        try:
            return await self._process_push_event(event_data)
        except Exception as e:
            logger.error(f"Error processing push event: {e}", exc_info=True)
            raise ExternalServiceError(
                service_name="GitHub Webhook",
                original_message=f"Failed to process push event: {str(e)}"
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
        repo_name = repository.get("name")
        repo_full_name = repository.get("full_name")  # owner/repo format
        repo_url = repository.get("html_url")
        
        logger.info(f"Processing push to {repo_full_name} on branch {branch}")
        
        # Process commits
        commits = push_data.get("commits", [])
        if not commits:
            logger.info("No commits in push event")
            return {"status": "success", "commits_processed": 0}
        
        # Filter out merge commits if needed
        non_merge_commits = [
            commit for commit in commits 
            if not commit.get("message", "").startswith("Merge")
        ]
        
        processed_commits = []
        errors = []
        
        for commit in non_merge_commits:
            try:
                # Convert GitHub commit to our CommitPayload format
                commit_payload = self._convert_to_commit_payload(
                    commit, 
                    repository=repo_full_name,
                    repo_url=repo_url,
                    branch=branch
                )
                
                # Process through existing commit analysis service
                logger.info(f"Analyzing commit {commit_payload.commit_hash}")
                result = await self.commit_analysis_service.process_commit(
                    commit_payload,
                    scan_docs=True  # Enable documentation scanning by default
                )
                
                if result:
                    processed_commits.append({
                        "hash": commit_payload.commit_hash,
                        "message": commit_payload.commit_message,
                        "status": "analyzed"
                    })
                else:
                    errors.append({
                        "hash": commit_payload.commit_hash,
                        "error": "Analysis failed"
                    })
                    
            except Exception as e:
                logger.error(f"Error processing commit {commit.get('id')}: {e}", exc_info=True)
                errors.append({
                    "hash": commit.get("id"),
                    "error": str(e)
                })
        
        return {
            "status": "success",
            "repository": repo_full_name,
            "branch": branch,
            "commits_processed": len(processed_commits),
            "commits_failed": len(errors),
            "processed": processed_commits,
            "errors": errors
        }
    
    def _convert_to_commit_payload(
        self, 
        commit: Dict[str, Any], 
        repository: str,
        repo_url: str,
        branch: str
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
        diff_url = f"{commit.get('url', '')}.diff" if commit.get('url') else None
        
        return CommitPayload(
            commit_hash=commit.get("id"),
            commit_message=commit.get("message", ""),
            commit_url=commit.get("url", ""),
            commit_timestamp=commit_timestamp,
            author_github_username=author.get("username", ""),
            author_email=author.get("email", ""),
            repository_name=repository.split("/")[-1] if "/" in repository else repository,
            repository_url=repo_url,
            branch=branch,
            diff_url=diff_url,
            # Additional fields for full compatibility
            repository=repository,  # Full name in owner/repo format
            diff_data=None  # Will be fetched by commit analysis service if needed
        )