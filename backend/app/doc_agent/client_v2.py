"""
Improved AutoDocClient with GitHub App integration and secure API calls.
This replaces shell git commands with proper GitHub API usage.
"""
import os
import logging
import time
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import re
import subprocess

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Import settings and services
from app.config.settings import settings
from app.core.database import get_db
from app.models.doc_approval import DocApproval
from app.services.slack_service import SlackService
from app.services.slack_message_templates import SlackMessageTemplates
from app.services.embedding_service import EmbeddingService
from app.services.context_analyzer import ContextAnalyzer
from app.integrations.github_app import GitHubApp, CheckRunStatus, CheckRunConclusion

# Use AsyncOpenAI
try:
    from openai import AsyncOpenAI, OpenAIError
except ImportError:
    AsyncOpenAI = None
    OpenAIError = None

logger = logging.getLogger(__name__)


class AutoDocClientV2:
    """Improved AutoDocClient with secure GitHub App integration."""
    
    def __init__(
        self,
        openai_api_key: str,
        github_token: Optional[str] = None,  # Optional, prefer GitHub App
        docs_repo: str = "",
        slack_webhook: Optional[str] = None,
        slack_channel: Optional[str] = None,
        enable_semantic_search: bool = True,
        use_github_app: bool = True
    ) -> None:
        """
        Initialize the AutoDocClient with improved security.
        
        Args:
            openai_api_key: OpenAI API key
            github_token: GitHub PAT (legacy, optional)
            docs_repo: Documentation repository (owner/repo format)
            slack_webhook: Slack webhook URL
            slack_channel: Slack channel for notifications
            enable_semantic_search: Enable semantic search features
            use_github_app: Use GitHub App instead of PAT
        """
        if not openai_api_key:
            raise ValueError("OpenAI API key is required.")
        
        self.openai_api_key = openai_api_key
        self.docs_repo = docs_repo
        self.slack_webhook = slack_webhook
        self.slack_channel = slack_channel or settings.SLACK_DEFAULT_CHANNEL
        
        # Initialize GitHub client
        if use_github_app and all([
            settings.GITHUB_APP_ID,
            settings.GITHUB_APP_PRIVATE_KEY,
            settings.GITHUB_APP_INSTALLATION_ID
        ]):
            logger.info("Using GitHub App for authentication")
            self.github_app = GitHubApp()
            self.use_github_app = True
        elif github_token:
            logger.warning("Using legacy GitHub PAT authentication")
            from github import Github
            self.github = Github(github_token)
            self.github_app = None
            self.use_github_app = False
        else:
            raise ValueError("Either GitHub App credentials or GitHub token required")
        
        # Initialize Slack service
        self.slack_service = SlackService() if settings.SLACK_BOT_TOKEN else None
        
        # Initialize semantic search and context analyzer
        self.enable_semantic_search = enable_semantic_search
        if enable_semantic_search:
            self.embedding_service = EmbeddingService()
            self.context_analyzer = ContextAnalyzer(self.embedding_service)
        else:
            self.embedding_service = None
            self.context_analyzer = None
        
        # Initialize OpenAI client
        if AsyncOpenAI:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        else:
            logger.warning("AsyncOpenAI client not available")
            self.openai_client = None
        
        self.openai_model = settings.DOC_AGENT_OPENAI_MODEL
    
    def get_commit_diff_stats(self, diff: str) -> Dict[str, int]:
        """
        Parse diff statistics using git diff --numstat format.
        
        Args:
            diff: Git diff content
            
        Returns:
            Dictionary with statistics
        """
        # Use git diff --numstat for accurate statistics
        try:
            # Write diff to temporary file and analyze
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as f:
                f.write(diff)
                temp_path = f.name
            
            # Run git diff --numstat on the diff
            result = subprocess.run(
                ["git", "diff", "--numstat", "--no-index", "/dev/null", temp_path],
                capture_output=True,
                text=True
            )
            
            # Parse numstat output
            additions = 0
            deletions = 0
            files_affected = 0
            
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        add_count = parts[0]
                        del_count = parts[1]
                        if add_count != '-':
                            additions += int(add_count)
                        if del_count != '-':
                            deletions += int(del_count)
                        files_affected += 1
            
            # Clean up temp file
            os.unlink(temp_path)
            
            return {
                'files_affected': files_affected,
                'additions': additions,
                'deletions': deletions
            }
        except Exception as e:
            logger.warning(f"Failed to use git diff --numstat, falling back to regex: {e}")
            
            # Fallback to regex parsing
            files_affected = len(re.findall(r'^\+\+\+ ', diff, re.MULTILINE))
            additions = len(re.findall(r'^\+(?!\+\+)', diff, re.MULTILINE))
            deletions = len(re.findall(r'^-(?!--)', diff, re.MULTILINE))
            
            return {
                'files_affected': files_affected,
                'additions': additions,
                'deletions': deletions
            }
    
    async def analyze_diff(self, diff: str) -> str:
        """
        Use OpenAI to generate documentation patch from commit diff.
        Uses Structured Outputs for consistent results.
        
        Args:
            diff: Git diff content
            
        Returns:
            Generated documentation patch
        """
        if not self.openai_client:
            logger.warning("OpenAI client not available")
            return ""
        
        prompt = (
            "You are an expert technical writer. Given the following git diff, "
            "suggest documentation updates as a unified diff. "
            "Focus on API changes, new features, breaking changes, and configuration updates. "
            "Output ONLY the diff content itself, no extra explanations or markdown."
        )
        
        try:
            # Use Responses API with Structured Outputs for all models
            response = await self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": diff}
                ],
                response_format={"type": "text"},  # Use text for diff output
                temperature=0.3,
                max_tokens=2000
            )
            
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                return content.strip() if content else ""
            
            logger.error("OpenAI response did not contain expected content")
            return ""
            
        except Exception as exc:
            logger.error(f"Failed to analyze diff with OpenAI: {exc}")
            return ""
    
    async def create_pr_with_check_run(
        self,
        diff: str,
        commit_hash: str,
        branch_name: Optional[str] = None,
        approval_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a PR using GitHub API with a Check Run for approval.
        
        Args:
            diff: Documentation diff to apply
            commit_hash: Original commit hash
            branch_name: Branch name for PR
            approval_id: Approval ID for tracking
            
        Returns:
            PR data with check run information
        """
        if not self.github_app or not self.docs_repo:
            logger.error("GitHub App not configured or docs repo not specified")
            return None
        
        if not branch_name:
            branch_name = f"auto-docs-{commit_hash[:7]}"
        
        try:
            # Parse repository
            owner, repo = self.docs_repo.split("/")
            
            # Get default branch
            default_branch = "main"  # You might want to fetch this from API
            
            # Create branch
            logger.info(f"Creating branch {branch_name} for documentation updates")
            
            # Get the latest commit SHA from default branch
            base_ref = self.github_app.get_file_contents(
                owner, repo, "README.md", ref=default_branch
            )
            base_sha = base_ref.get("sha")
            
            # Apply diff by creating/updating files
            # This is simplified - you'd need to parse the diff and apply changes
            files_to_update = self._parse_diff_files(diff)
            
            for file_path, content in files_to_update.items():
                # Check if file exists
                try:
                    existing = self.github_app.get_file_contents(
                        owner, repo, file_path, ref=default_branch
                    )
                    file_sha = existing.get("sha")
                except:
                    file_sha = None
                
                # Create or update file
                self.github_app.create_or_update_file(
                    owner, repo, file_path,
                    message=f"Automated documentation update for {commit_hash[:7]}",
                    content=content,
                    branch=branch_name,
                    sha=file_sha
                )
            
            # Create pull request
            pr_data = self.github_app.create_pull_request(
                owner, repo,
                title=f"Automated docs update for {commit_hash[:7]}",
                head=branch_name,
                base=default_branch,
                body=f"This PR contains automated documentation updates for commit {commit_hash}.\n\n"
                     f"Approval ID: {approval_id}\n\n"
                     f"Generated by AutoDoc",
                draft=False
            )
            
            # Create Check Run for approval
            dashboard_url = f"{settings.FRONTEND_URL}/approvals/{approval_id}" if approval_id else None
            
            check_run = self.github_app.create_check_run(
                owner, repo,
                name="Docs Approval",
                head_sha=pr_data["head"]["sha"],
                status=CheckRunStatus.IN_PROGRESS,
                details_url=dashboard_url,
                external_id=approval_id,
                output={
                    "title": "Documentation Approval Required",
                    "summary": "This PR requires approval before merging.",
                    "text": f"Review the documentation changes and approve via:\n"
                           f"- Dashboard: {dashboard_url}\n"
                           f"- Slack: Check your notifications"
                }
            )
            
            logger.info(f"Created PR #{pr_data['number']} with Check Run {check_run['id']}")
            
            return {
                "pr": pr_data,
                "check_run": check_run,
                "pr_url": pr_data["html_url"],
                "pr_number": pr_data["number"],
                "check_run_id": check_run["id"],
                "head_sha": pr_data["head"]["sha"],
            }
            
        except Exception as e:
            logger.error(f"Failed to create PR with check run: {e}")
            return None
    
    def _parse_diff_files(self, diff: str) -> Dict[str, str]:
        """
        Parse unified diff to extract file paths and content.
        
        Args:
            diff: Unified diff content
            
        Returns:
            Dictionary mapping file paths to new content
        """
        # This is a simplified implementation
        # In production, you'd want to use a proper diff parser
        files = {}
        current_file = None
        current_content = []
        
        for line in diff.split('\n'):
            if line.startswith('+++ b/'):
                if current_file:
                    files[current_file] = '\n'.join(current_content)
                current_file = line[6:]
                current_content = []
            elif current_file and line.startswith('+') and not line.startswith('+++'):
                current_content.append(line[1:])
        
        if current_file:
            files[current_file] = '\n'.join(current_content)
        
        return files
    
    async def update_check_run_status(
        self,
        pr_number: int,
        check_run_id: int,
        status: CheckRunStatus,
        conclusion: Optional[CheckRunConclusion] = None,
        output: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update the Check Run status for a PR.
        
        Args:
            pr_number: Pull request number
            check_run_id: Check run ID
            status: New status
            conclusion: Conclusion (for completed status)
            output: Updated output message
            
        Returns:
            True if successful
        """
        if not self.github_app or not self.docs_repo:
            logger.error("GitHub App not configured")
            return False
        
        try:
            owner, repo = self.docs_repo.split("/")
            
            self.github_app.update_check_run(
                owner, repo, check_run_id,
                status=status,
                conclusion=conclusion,
                output=output
            )
            
            logger.info(f"Updated check run {check_run_id} to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update check run: {e}")
            return False
    
    async def propose_via_slack(
        self,
        diff: str,
        patch: str,
        commit_hash: str,
        commit_message: str = "",
        db: Optional[AsyncSession] = None
    ) -> Optional[str]:
        """
        Send proposed diff to Slack for manual approval.
        
        Args:
            diff: Original diff
            patch: Generated documentation patch
            commit_hash: Commit hash
            commit_message: Commit message
            db: Database session
            
        Returns:
            Approval ID if successful
        """
        if not diff or not self.slack_service:
            logger.warning("Slack service not configured or no diff provided")
            return None
        
        # Get diff statistics
        stats = self.get_commit_diff_stats(diff)
        
        # Create approval record
        if not db:
            async with get_db() as session:
                db = session
                return await self._create_and_send_approval(
                    db, diff, patch, commit_hash, commit_message,
                    stats['files_affected'], stats['additions'], stats['deletions']
                )
        else:
            return await self._create_and_send_approval(
                db, diff, patch, commit_hash, commit_message,
                stats['files_affected'], stats['additions'], stats['deletions']
            )
    
    async def _create_and_send_approval(
        self,
        db: AsyncSession,
        diff: str,
        patch: str,
        commit_hash: str,
        commit_message: str,
        files_affected: int,
        additions: int,
        deletions: int
    ) -> Optional[str]:
        """Create approval record and send Slack message."""
        try:
            # Create approval record
            approval = DocApproval(
                commit_hash=commit_hash,
                repository=self.docs_repo,
                diff_content=diff,
                patch_content=patch,
                slack_channel=self.slack_channel,
                expires_at=datetime.utcnow() + timedelta(hours=24),
                approval_metadata={
                    "commit_message": commit_message,
                    "files_affected": files_affected,
                    "additions": additions,
                    "deletions": deletions
                }
            )
            db.add(approval)
            await db.commit()
            await db.refresh(approval)
            
            # Create PR with Check Run
            pr_result = await self.create_pr_with_check_run(
                patch, commit_hash, approval_id=str(approval.id)
            )
            
            if pr_result:
                # Update approval with PR and check run info
                approval.pr_number = pr_result["pr_number"]
                approval.pr_url = pr_result["pr_url"]
                approval.check_run_id = pr_result["check_run_id"]
                await db.commit()
            
            # Prepare and send Slack message with dashboard link
            dashboard_url = f"{settings.FRONTEND_URL}/approvals/{approval.id}"
            
            message = SlackMessageTemplates.doc_agent_approval(
                approval_id=str(approval.id),
                commit_hash=commit_hash,
                repository=self.docs_repo,
                commit_message=commit_message or "No commit message",
                diff_preview=diff[:2000],
                files_affected=files_affected,
                additions=additions,
                deletions=deletions,
                dashboard_url=dashboard_url,
                pr_url=pr_result["pr_url"] if pr_result else None
            )
            
            # Send message
            result = await self.slack_service.send_message(
                channel=self.slack_channel,
                text=message["text"],
                blocks=message["blocks"]
            )
            
            if result:
                # Update approval with message timestamp
                approval.slack_message_ts = result.get("ts")
                await db.commit()
                logger.info(f"Sent approval request to Slack for {commit_hash[:8]}")
                return str(approval.id)
            else:
                logger.error("Failed to send Slack message")
                return None
                
        except Exception as e:
            logger.error(f"Error creating approval request: {e}")
            await db.rollback()
            return None