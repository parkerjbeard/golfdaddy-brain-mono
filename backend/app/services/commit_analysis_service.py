from typing import Dict, Any, Optional, List, Tuple
from supabase import Client
from datetime import datetime
import math
import json
import logging
from uuid import UUID
import requests

from app.repositories.commit_repository import CommitRepository
from app.repositories.user_repository import UserRepository
from app.integrations.ai_integration import AIIntegration
from app.integrations.github_integration import GitHubIntegration
from app.schemas.github_event import CommitPayload
from app.models.commit import Commit
from app.models.user import User
from app.services.documentation_update_service import DocumentationUpdateService
# TODO: Import DailyReportService if direct interaction is needed, or pass data through other means
# from app.services.daily_report_service import DailyReportService 
from app.config.settings import settings

logger = logging.getLogger(__name__)

class CommitAnalysisService:
    """Service for analyzing commits and calculating points."""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.commit_repository = CommitRepository(supabase)
        self.user_repository = UserRepository(supabase)
        self.ai_integration = AIIntegration()
        self.github_integration = GitHubIntegration()
        self.docs_update_service = None  # Lazy-loaded when needed
        # self.daily_report_service = DailyReportService() # Placeholder if needed for direct calls
        
        # Simplified point calculation weights
        self.complexity_weight = 2.0  # Base weight for complexity score
        
        # Simplified risk factors - used only for minor adjustments
        self.risk_factors = {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5
        }
        
        # Documentation repository name (format: "owner/repo")
        self.docs_repository = settings.docs_repository
        self.enable_docs_updates = settings.enable_docs_updates
    
    def _log_separator(self, message="", char="=", length=80):
        """Print a separator line with optional message for visual log grouping."""
        if not message:
            logger.info(char * length)
            return
        
        side_length = (length - len(message) - 2) // 2
        if side_length <= 0:
            logger.info(message)
            return
            
        left = char * side_length
        right = char * (length - side_length - len(message) - 2)
        logger.info(f"{left} {message} {right}")
    
    def analyze_commit(self, commit_hash: str, commit_data: Dict[str, Any], fetch_diff: bool = True) -> Optional[Commit]:
        """Analyzes a single commit using AI, optionally fetching the diff first.
        
        Args:
            commit_hash: The unique hash of the commit.
            commit_data: Dictionary containing commit metadata (author email/name, timestamp, repo info, etc.).
            fetch_diff: Whether to fetch the diff from GitHub (if not provided in commit_data).
            
        Returns:
            The analyzed commit or None if analysis fails
        """
        try:
            self._log_separator(f"ANALYZING COMMIT: {commit_hash}")
            logger.info(f"Repository: {commit_data.get('repository', 'N/A')}")
            logger.info(f"Author: {commit_data.get('author', {}).get('name', 'N/A')} <{commit_data.get('author', {}).get('email', 'N/A')}>")
            
            diff_data = commit_data.get("diff_data")
            repository = commit_data.get("repository") # Repository name in owner/repo format
            
            # 1. Fetch diff if necessary
            if fetch_diff and not diff_data and repository:
                try:
                    logger.info(f"Fetching diff from GitHub: {repository}/{commit_hash}")
                    # Use the updated GitHub integration to get commit details
                    diff_data = self.github_integration.get_commit_diff(repository, commit_hash)
                    
                    if diff_data:
                        logger.info(f"✓ Diff fetched successfully ({diff_data.get('additions', 0)} additions, {diff_data.get('deletions', 0)} deletions)")
                        # Update commit_data with diff information
                        commit_data["diff_data"] = diff_data
                        commit_data["files_changed"] = diff_data.get("files_changed", [])
                        commit_data["additions"] = diff_data.get("additions", 0)
                        commit_data["deletions"] = diff_data.get("deletions", 0)
                        
                        # If author info is not already provided, use info from GitHub
                        if "author" not in commit_data or not commit_data.get("author"):
                            commit_data["author"] = diff_data.get("author", {})
                            
                        # If message is not already provided, use message from GitHub
                        if "message" not in commit_data or not commit_data.get("message"):
                            commit_data["message"] = diff_data.get("message", "")
                    else:
                        logger.warning(f"❌ Could not fetch diff from GitHub")
                except Exception as github_err:
                    logger.error(f"❌ GitHub error: {github_err}")

            # Prepare the diff content for AI analysis
            diff_content = ""
            
            # If we have detailed file data, format a proper diff
            if diff_data and "files" in diff_data:
                for file in diff_data.get("files", []):
                    diff_content += f"File: {file.get('filename')}\n"
                    diff_content += f"Status: {file.get('status')}\n"
                    diff_content += f"Changes: +{file.get('additions', 0)} -{file.get('deletions', 0)}\n"
                    if file.get("patch"):
                        diff_content += file.get("patch") + "\n\n"
                    else:
                        diff_content += "(No patch data available)\n\n"
            
            # If we don't have formatted diff content, try other sources
            if not diff_content:
                # Try using the plain diff or aggregated info
                if "diff" in commit_data:
                    diff_content = commit_data.get("diff", "")
                else:
                    # Create a basic summary if we don't have actual diff content
                    diff_content = f"Files changed: {len(commit_data.get('files_changed', []))}\n"
                    diff_content += f"Additions: {commit_data.get('additions', 0)}\n"
                    diff_content += f"Deletions: {commit_data.get('deletions', 0)}\n"
                    diff_content += f"Files: {', '.join(commit_data.get('files_changed', []))}\n"
            
            if not diff_content:
                logger.error(f"❌ Cannot analyze commit without diff content")
                return None
            
            # 2. Call AI for analysis
            # Prepare the commit data dictionary for AI analysis
            ai_commit_data = {
                "commit_hash": commit_hash,
                "diff": diff_content,
                "message": commit_data.get("message", ""),
                "repository": commit_data.get("repository", ""),
                "author_name": commit_data.get("author", {}).get("name", ""),
                "author_email": commit_data.get("author", {}).get("email", ""),
                "files_changed": commit_data.get("files_changed", []),
                "additions": commit_data.get("additions", 0),
                "deletions": commit_data.get("deletions", 0)
            }
            
            # Call AI integration with the structured data
            logger.info("Sending commit data to AI for analysis...")
            analysis_result = self.ai_integration.analyze_commit_diff(ai_commit_data)

            # --- New EOD/Code Quality Integration Point --- 
            # TODO: Fetch relevant EOD report from DailyReportService for this user & date.
            # eod_report = await self.daily_report_service.get_user_report_for_date(author_id, commit_timestamp)
            
            # TODO: Pass commit diff and message to the new AI code quality analysis method.
            # code_quality_analysis = await self.ai_integration.analyze_commit_code_quality(diff_content, commit_data.get("message", ""))
            
            # TODO: Compare commit analysis (lines, files, complexity from `analysis_result`) 
            #       with `eod_report` (if found) and `code_quality_analysis`.
            #       This comparison logic will be part of the new performance metrics generation.
            #       The results of this comparison might update the Commit model or be stored elsewhere.
            # For now, we are keeping the original commit analysis flow for ai_points and ai_hours.
            # The new code_quality_analysis will likely produce its own set of metrics.
            # --- End New EOD/Code Quality Integration Point ---

            if not analysis_result:
                logger.error(f"❌ AI analysis failed")
                return None

            # Extract points and estimated_hours from the analysis result
            # The AI might return complexity_score which we can map to points
            ai_points = analysis_result.get("complexity_score") or analysis_result.get("points", 0)
            ai_hours = analysis_result.get("estimated_hours", 0)
            seniority_score = analysis_result.get("seniority_score", 0)
            
            logger.info(f"✓ Analysis complete: Points={ai_points}, Hours={ai_hours}, Seniority={seniority_score}")

            # 3. Map commit author to internal user ID
            author_data = commit_data.get("author", {})
            author_id = self._map_commit_author(author_data)
            if not author_id:
                logger.warning(f"⚠ Could not map author to internal user")
                # Continue without author mapping if it fails

            # 4. Prepare commit data for saving
            commit_to_save = Commit(
                commit_hash=commit_hash,
                author_id=author_id, # May be None if mapping failed
                ai_points=ai_points,
                ai_estimated_hours=ai_hours,
                seniority_score=seniority_score,
                commit_timestamp=commit_data.get("timestamp") or commit_data.get("commit_timestamp") or 
                                diff_data.get("author", {}).get("date")
                # Add other relevant fields from commit_data if needed in the model/DB
            )
            
            # Parse timestamp string if necessary
            ts = commit_to_save.commit_timestamp
            if isinstance(ts, str):
                try:
                    commit_to_save.commit_timestamp = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except ValueError:
                    logger.error(f"❌ Could not parse commit timestamp: {ts}")
                    return None 
            elif isinstance(ts, datetime):
                commit_to_save.commit_timestamp = ts
            else:
                logger.error(f"❌ Missing or invalid commit timestamp")
                return None

            # 5. Save analysis results to DB (Upsert)
            logger.info(f"Saving commit analysis to database...")
            saved_commit = self.commit_repository.save_commit(commit_to_save)
            
            if saved_commit:
                logger.info(f"✓ Successfully saved commit analysis to database")
                self._log_separator(f"END OF ANALYSIS: {commit_hash}")
            else:
                logger.error(f"❌ Failed to save commit to database")
                
            return saved_commit

        except Exception as e:
            logger.exception(f"❌ Error during commit analysis: {e}")
            self._log_separator(f"ERROR IN ANALYSIS: {commit_hash}")
            return None
    
    def _map_commit_author(self, author_data: Optional[Dict[str, str]]) -> Optional[UUID]:
        """Tries to map commit author info (email, name) to an internal user ID.
        
        Args:
            author_data: Dictionary containing author information
            
        Returns:
            The internal user ID or None if mapping fails
        """
        if not author_data:
            return None
        
        # Prioritize mapping by email if available
        email = author_data.get("email")
        if email:
            # This requires the users table to store email, which wasn't in the final schema.
            # Alternative: Map by Slack ID if GitHub email matches Slack email, or use name.
            # For now, let's assume we can't map reliably by email.
            pass 
        
        # Fallback: Map by name or other available identifiers (e.g., GitHub username if stored)
        # This requires a robust mapping strategy, possibly involving fuzzy matching or a lookup table.
        # Example placeholder: Lookup by Slack ID if available
        slack_id = author_data.get("slack_id") # If available from GitHub event somehow
        if slack_id:
            user = self.user_repository.get_user_by_slack_id(slack_id)
            if user:
                return user.id

        logger.debug(f"Author mapping fallback needed for: {author_data}")
        # Cannot map reliably with current info
        return None
    
    def batch_analyze_commits(self, commits_payload: List[Dict[str, Any]]) -> List[Optional[Commit]]:
        """Analyzes a batch of commits, potentially fetching diffs.
        
        Args:
            commits_payload: List of dictionaries containing commit metadata
            
        Returns:
            List of analyzed commits or None if analysis fails
        """
        results = []
        self._log_separator("BATCH COMMIT ANALYSIS", "=")
        logger.info(f"Processing batch of {len(commits_payload)} commits")
        
        for i, commit_item in enumerate(commits_payload):
            commit_hash = commit_item.get("hash") or commit_item.get("id") # Adapt based on webhook payload
            if commit_hash:
                logger.info(f"Processing commit {i+1}/{len(commits_payload)}: {commit_hash}")
                # Assume commit_item contains necessary metadata like author, timestamp, repo
                # Decide if diff fetching is needed per commit
                fetch_diff_needed = "diff" not in commit_item 
                result = self.analyze_commit(commit_hash, commit_item, fetch_diff=fetch_diff_needed)
                results.append(result)
            else:
                logger.warning(f"⚠ Skipping commit {i+1}/{len(commits_payload)} - missing hash")
                results.append(None)
                
        success_count = sum(1 for r in results if r is not None)
        logger.info(f"Batch processing complete: {success_count}/{len(commits_payload)} commits successfully analyzed")
        self._log_separator("END OF BATCH ANALYSIS", "=")
        return results

    def _find_user_for_commit(self, payload: CommitPayload) -> Optional[User]:
        """Attempts to find the internal user associated with the commit author."""
        # Prioritize finding by email, then by GitHub username if available
        user = None
        logger.info(f"Finding user for commit {payload.commit_hash}")
        logger.info(f"Author info: email={payload.author_email}, github_username={payload.author_github_username}")
        
        if payload.author_email:
            try:
                logger.info(f"Searching for user by email: {payload.author_email}")
                user = self.user_repository.get_user_by_email(payload.author_email)
                if user:
                    logger.info(f"✓ Found user: {user.id}")
                    # Log user details for debugging (no sensitive data)
                    user_info = {
                        "id": str(user.id),
                        "role": user.role,
                        "team": user.team
                    }
                    logger.info(f"User details: {json.dumps(user_info, default=str)}")
                    return user
                else:
                    logger.warning(f"⚠ No user found with email {payload.author_email}")
            except AttributeError as ae:
                logger.error(f"❌ User repository error: {ae}")
            except Exception as e:
                logger.error(f"❌ Error finding user by email: {e}")
        
        # Add logic here to find user by GitHub username if email lookup fails and username is provided
        # This might require a 'github_username' field on your User model
        if payload.author_github_username:
            logger.info(f"Trying GitHub username: {payload.author_github_username}")
            # Currently commented out as feature may not be implemented
            # try:
            #     user = self.user_repository.get_user_by_github_username(payload.author_github_username)
            #     if user:
            #         logger.info(f"Found user {user.id} by GitHub username {payload.author_github_username}...")
            #         return user
            # except Exception as e:
            #     logger.error(f"Error finding user by GitHub username: {e}")

        logger.warning(f"⚠ Could not map commit author to internal user")
        return None
    
    async def process_commit(self, commit_data: Dict[str, Any], scan_docs: Optional[bool] = None) -> Optional[Commit]:
        """
        Processes an incoming commit payload.
        
        Args:
            commit_data: Dictionary containing commit metadata including repository and diff URL
            scan_docs: Whether to scan documentation after commit analysis
                       (None = use global setting, True = force enable, False = force disable)
        
        Returns:
            The processed and analyzed commit, or None if processing fails
        """
        # Log the full payload for debugging (with sanitization)
        commit_hash = commit_data.get("commit_hash")
        repository = commit_data.get("repository")
        
        self._log_separator(f"PROCESSING COMMIT: {commit_hash}", "=")
        logger.info(f"Repository: {repository or 'N/A'}")
        
        try:
            # Create a sanitized version of the data for logging
            log_data = commit_data.copy()
            if "token" in log_data:
                log_data["token"] = "***REDACTED***"
            
            # Only log essential fields for clarity
            essential_data = {
                "commit_hash": log_data.get("commit_hash"),
                "repository": log_data.get("repository"),
                "author": {
                    "name": log_data.get("author", {}).get("name"),
                    "email": log_data.get("author", {}).get("email"),
                },
                "files_changed": len(log_data.get("files_changed", [])),
                "has_diff": bool(log_data.get("diff") or log_data.get("diff_data")),
            }
            logger.info(f"Commit metadata: {json.dumps(essential_data, default=str)}")
        except Exception as e:
            logger.error(f"❌ Error logging payload: {e}")

        # 1. Check if commit already exists (idempotency)
        existing_commit = self.commit_repository.get_commit_by_hash(commit_hash)
        if existing_commit:
            logger.warning(f"⚠ Commit {commit_hash} already exists in database")
            # Optionally, check if AI analysis is missing and run it
            if existing_commit.ai_points is None:
                 logger.info(f"Existing commit missing AI analysis - will analyze")
                 # Prepare data for re-analysis, using existing info where possible
                 re_analysis_data = commit_data.copy() # Start with incoming data
                 if existing_commit.author_id:
                     re_analysis_data['author_id'] = existing_commit.author_id
                 
                 # We might already have diff data, prioritize existing commit if needed
                 # For simplicity, assume incoming commit_data might have newer webhook info
                 
                 logger.info(f"Calling analyze_commit for existing commit {commit_hash}")
                 # Call analyze_commit to perform analysis and upsert
                 analyzed_commit = self.analyze_commit(
                     commit_hash=commit_hash,
                     commit_data=re_analysis_data, # Pass potentially updated data
                     fetch_diff=not (re_analysis_data.get("diff") or re_analysis_data.get("diff_data")) # Fetch diff only if not provided
                 )
                 
                 if analyzed_commit:
                     logger.info(f"✓ Re-analysis and save successful for {commit_hash}")
                     
                     # After successful analysis, check if documentation updates are needed
                     self._scan_documentation_for_updates(analyzed_commit, repository, re_analysis_data, scan_docs)
                     
                     self._log_separator(f"END: RE-ANALYZED COMMIT {commit_hash}", "=")
                 else:
                     logger.error(f"❌ Re-analysis failed for {commit_hash}")
                     self._log_separator(f"END: RE-ANALYSIS FAILED {commit_hash}", "=")
                 return analyzed_commit # Return result of re-analysis
            else:
                logger.info(f"✓ Commit already analyzed - returning existing record")
                self._log_separator(f"END: EXISTING COMMIT {commit_hash}", "=")
                return existing_commit
        
        # --- If commit does NOT exist, continue with original flow ---
        logger.info(f"Commit {commit_hash} not found in DB. Processing as new.")

        # 2. Find the user associated with the commit author
        user = None
        author_email = commit_data.get("author", {}).get("email")
        author_github_username = commit_data.get("author", {}).get("github_username")
        
        if author_email:
            logger.info(f"Looking up user by email: {author_email}")
            try:
                user = self.user_repository.get_user_by_email(author_email)
                if user:
                    logger.info(f"✓ Found user: {user.id}")
                    commit_data["author_id"] = user.id
            except Exception as e:
                logger.error(f"❌ Error finding user by email: {e}")
        
        if not user and author_github_username:
            logger.info(f"Looking up user by GitHub username: {author_github_username}")
            # If you have a method to find by GitHub username, uncomment and use it
            # try:
            #     user = self.user_repository.get_user_by_github_username(author_github_username)
            #     if user:
            #         logger.info(f"Found user {user.id} by GitHub username {author_github_username}")
            #         commit_data["author_id"] = user.id
            # except Exception as e:
            #     logger.error(f"Error finding user by GitHub username: {e}")
        
        if not user:
            logger.warning(f"⚠ No user found - commit will be saved without user association")

        # 3. Fetch diff from GitHub if not included and we have repository info
        if not commit_data.get("diff") and not commit_data.get("diff_data") and repository:
            diff_url = commit_data.get("diff_url")
            logger.info(f"Fetching diff from GitHub")
            
            try:
                # Attempt to fetch commit diff using our GitHub integration
                diff_data = self.github_integration.get_commit_diff(repository, commit_hash)
                if diff_data:
                    logger.info(f"✓ GitHub API diff fetched successfully")
                    commit_data["diff_data"] = diff_data
                else:
                    # If direct API fetch fails, try using the diff URL if provided
                    if diff_url:
                        logger.info(f"Trying diff URL: {diff_url}")
                        response = requests.get(diff_url)
                        if response.status_code == 200:
                            commit_data["diff"] = response.text
                            logger.info(f"✓ Diff URL fetch succeeded")
                        else:
                            logger.error(f"❌ Failed to fetch diff. Status: {response.status_code}")
            except Exception as e:
                logger.error(f"❌ Error fetching diff: {e}")
        
        # 4. Call analyze_commit to process the data and perform AI analysis
        logger.info(f"Starting commit analysis...")
        analyzed_commit = self.analyze_commit(
            commit_hash=commit_hash,
            commit_data=commit_data,
            fetch_diff=not (commit_data.get("diff") or commit_data.get("diff_data"))
        )
        
        if analyzed_commit:
            logger.info(f"✓ Commit analysis completed successfully")
            
            # After successful analysis, check if documentation updates are needed
            self._scan_documentation_for_updates(analyzed_commit, repository, commit_data, scan_docs)
            
            self._log_separator(f"END: COMMIT {commit_hash} PROCESSED", "=")
            return analyzed_commit
        else:
            logger.error(f"❌ Commit analysis failed")
            self._log_separator(f"END: COMMIT {commit_hash} FAILED", "=")
            return None
    
    def _scan_documentation_for_updates(self, analyzed_commit: Commit, repository: str, commit_data: Dict[str, Any], scan_docs: Optional[bool] = None) -> None:
        """
        Scan documentation and propose updates based on commit analysis.
        
        Args:
            analyzed_commit: The analyzed commit object
            repository: Repository name in owner/repo format
            commit_data: Original commit data
            scan_docs: Whether to scan documentation (None = use global setting, True = force enable, False = force disable)
        """
        try:
            # Determine if we should scan documentation
            should_scan = self.enable_docs_updates if scan_docs is None else scan_docs
            
            # Skip if documentation scanning is disabled
            if not should_scan:
                logger.info("Documentation scanning skipped - feature is disabled")
                return
                
            # Skip if no docs repository is configured
            docs_repo = self.docs_repository
            if not docs_repo:
                # Try to determine docs repository from environment or settings
                # Format: If main repo is 'owner/repo', docs repo could be 'owner/repo-docs'
                if repository:
                    parts = repository.split('/')
                    if len(parts) == 2:
                        owner, repo = parts
                        docs_repo = f"{owner}/{repo}-docs"
                        logger.info(f"Using derived docs repository: {docs_repo}")
                
                if not docs_repo:
                    logger.info("Documentation scanning skipped - no docs repository configured")
                    return
            
            # Initialize documentation update service if not already done
            if self.docs_update_service is None:
                try:
                    self.docs_update_service = DocumentationUpdateService()
                except Exception as e:
                    logger.error(f"❌ Could not initialize DocumentationUpdateService: {e}")
                    return
            
            logger.info(f"Scanning documentation in {docs_repo} for potential updates...")
            
            # Prepare the commit analysis result data for the documentation scan
            analysis_data = {
                "commit_hash": analyzed_commit.commit_hash,
                "message": commit_data.get("message", ""),
                "repository": repository,
                "files_changed": commit_data.get("files_changed", []),
                "complexity_score": analyzed_commit.ai_points,
                "seniority_score": analyzed_commit.seniority_score,
                "key_changes": commit_data.get("diff_data", {}).get("key_changes", []),
                "technical_debt": commit_data.get("diff_data", {}).get("technical_debt", []),
                "suggestions": commit_data.get("diff_data", {}).get("suggestions", [])
            }
            
            # Call the documentation update service to analyze the documentation
            docs_analysis = self.docs_update_service.analyze_documentation(
                docs_repo_name=docs_repo,
                commit_analysis_result=analysis_data,
                source_repo_name=repository
            )
            
            # If documentation changes are needed, create a pull request
            if docs_analysis and docs_analysis.get("changes_needed", False):
                proposed_changes = docs_analysis.get("proposed_changes", [])
                if proposed_changes:
                    logger.info(f"Documentation changes needed: {len(proposed_changes)} files")
                    
                    # Create a pull request with the proposed changes
                    pr_result = self.docs_update_service.create_pull_request(
                        docs_repo_name=docs_repo,
                        proposed_changes=proposed_changes,
                        commit_analysis=analysis_data
                    )
                    
                    if pr_result.get("status") == "success":
                        logger.info(f"✓ Created documentation update PR: {pr_result.get('pull_request_url')}")
                    else:
                        logger.warning(f"⚠ Failed to create documentation PR: {pr_result.get('message')}")
                else:
                    logger.info("No specific documentation changes proposed")
            else:
                logger.info("No documentation updates needed")
        
        except Exception as e:
            logger.exception(f"❌ Error during documentation scan: {e}")
            # Don't fail the whole process if documentation scanning fails