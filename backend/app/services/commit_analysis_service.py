from typing import Dict, Any, Optional, List, Tuple, Union
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
from app.services.daily_report_service import DailyReportService
from app.models.daily_report import DailyReport
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
        self.daily_report_service = DailyReportService() # Uncommented and initialized
        
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
    
    async def analyze_commit(self, commit_hash: str, commit_data: Dict[str, Any], fetch_diff: bool = True) -> Optional[Commit]:
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
            repository = commit_data.get("repository")
            
            # 1. Fetch diff if necessary
            if fetch_diff and not diff_data and repository:
                try:
                    # Ensure repository is in "owner/repo" format 
                    owner = None
                    repo_name_only = repository
                    if "/" in repository:
                        owner, repo_name_only = repository.split("/", 1)
                    else:
                        # If no owner in the repository string, try to use author_github_username from commit_data
                        # This is a heuristic and might need adjustment based on actual webhook payload structure
                        commit_author_info = commit_data.get("author", {})
                        github_username_from_author = commit_author_info.get("login") # often from github webhook
                        
                        if commit_data.get("author_github_username"): # from CommitPayload
                            owner = commit_data.get("author_github_username")
                        elif github_username_from_author:
                            owner = github_username_from_author
                        else: # Fallback to a default if no author information can be derived
                            owner = "golfdaddy" # Default owner, adjust if necessary
                        
                        repository = f"{owner}/{repo_name_only}"
                        logger.info(f"Reformatted repository name to: {repository} (owner: {owner}, repo: {repo_name_only})")
                    
                    logger.info(f"Attempting to fetch diff from GitHub. Original repo input: '{commit_data.get('repository')}', Derived/Used repo: '{repository}', Commit SHA: '{commit_hash}'")
                    
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
            analysis_result = await self.ai_integration.analyze_commit_diff(ai_commit_data)

            # --- New EOD/Code Quality Integration Point --- 
            # TODO: Fetch relevant EOD report from DailyReportService for this user & date.
            eod_report: Optional[DailyReport] = None
            code_quality_analysis: Optional[Dict[str, Any]] = None # Define type for code_quality_analysis

            author_id_for_eod = commit_data.get('author_id') 
            commit_timestamp_for_eod = commit_data.get("timestamp") or commit_data.get("commit_timestamp")
            
            # Ensure commit_timestamp_for_eod is a datetime object
            if isinstance(commit_timestamp_for_eod, str):
                try:
                    commit_timestamp_for_eod = datetime.fromisoformat(commit_timestamp_for_eod.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Could not parse commit_timestamp_for_eod: {commit_timestamp_for_eod}")
                    commit_timestamp_for_eod = None
            
            if author_id_for_eod and commit_timestamp_for_eod:
                logger.info(f"Fetching EOD report for user {author_id_for_eod} on {commit_timestamp_for_eod.date()}")
                try:
                    eod_report = await self.daily_report_service.get_user_report_for_date(author_id_for_eod, commit_timestamp_for_eod)
                    if eod_report:
                        logger.info(f"✓ EOD report found: {eod_report.id}")
                    else:
                        logger.info(f"No EOD report found for user {author_id_for_eod} on {commit_timestamp_for_eod.date()}")
                except Exception as e_eod:
                    logger.error(f"Error fetching EOD report: {e_eod}")

            # TODO: Pass commit diff and message to the new AI code quality analysis method.
            # Assuming ai_integration.analyze_commit_code_quality is an async method
            try:
                logger.info("Performing AI code quality analysis...")
                # This method needs to be implemented in AIIntegration service and made async
                # For now, assuming it exists and is async:
                # code_quality_analysis = await self.ai_integration.analyze_commit_code_quality(diff_content, commit_data.get("message", ""))
                # Placeholder for now:
                if hasattr(self.ai_integration, "analyze_commit_code_quality") and callable(getattr(self.ai_integration, "analyze_commit_code_quality")):
                    code_quality_analysis = await self.ai_integration.analyze_commit_code_quality(diff_content, commit_data.get("message", ""))
                    logger.info(f"✓ Code quality analysis result: {code_quality_analysis}")
                else:
                    logger.warning("ai_integration.analyze_commit_code_quality method not found or not callable. Skipping.")
                    code_quality_analysis = {"placeholder_quality_score": 0.0, "issues": []}


            except Exception as e_cqa:
                logger.error(f"Error during AI code quality analysis: {e_cqa}")
                code_quality_analysis = {"error": str(e_cqa)}
            
            # TODO: Compare commit analysis (lines, files, complexity from `analysis_result`) 
            #       with `eod_report` (if found) and `code_quality_analysis`.
            #       This comparison logic will be part of the new performance metrics generation.
            #       The results of this comparison might update the Commit model or be stored elsewhere.
            # For now, we are keeping the original commit analysis flow for ai_points and ai_hours.
            # The new code_quality_analysis will likely produce its own set of metrics.
            
            # Log the detailed comparison summary for debugging/auditing
            detailed_comparison_log = {
                "commit_hash": commit_hash,
                "original_commit_analysis": analysis_result,
                "eod_report_found": bool(eod_report),
                "eod_report_id": str(eod_report.id) if eod_report else None,
                "eod_report_ai_analysis_summary": eod_report.ai_analysis.summary if eod_report and eod_report.ai_analysis else None,
                "eod_report_ai_estimated_hours": eod_report.ai_analysis.estimated_hours if eod_report and eod_report.ai_analysis else None,
                "code_quality_analysis_retrieved": code_quality_analysis
            }
            logger.info(f"Detailed EOD/Quality Integration Log: {json.dumps(detailed_comparison_log, default=str)}")

            current_comparison_notes = []
            commit_ai_hours = analysis_result.get("estimated_hours", 0.0)

            if eod_report:
                current_comparison_notes.append(f"EOD report {eod_report.id} (date: {eod_report.report_date.strftime('%Y-%m-%d')}) found for user {author_id_for_eod}.")
                if eod_report.ai_analysis:
                    eod_ai_hours = eod_report.ai_analysis.estimated_hours if eod_report.ai_analysis.estimated_hours is not None else 0.0
                    current_comparison_notes.append(f"  - EOD AI Analysis: Estimated Hours: {eod_ai_hours:.2f}, Summary: {eod_report.ai_analysis.summary}")
                    current_comparison_notes.append(f"  - Commit AI Analysis: Estimated Hours for this commit: {commit_ai_hours:.2f}.")
                    
                    # Compare hours
                    if abs(commit_ai_hours - eod_ai_hours) > 0.5: # Example threshold for significant difference
                        current_comparison_notes.append(f"    - Note: Difference in estimated hours between EOD ({eod_ai_hours:.2f}h) and this commit ({commit_ai_hours:.2f}h). This commit is one of possibly multiple for the day.")
                    
                    # Compare key changes/achievements
                    commit_key_changes = set(analysis_result.get("key_changes", []))
                    eod_key_achievements = set(eod_report.ai_analysis.key_achievements or [])
                    
                    if commit_key_changes and eod_key_achievements:
                        common_themes = commit_key_changes.intersection(eod_key_achievements) # Simple intersection, could be fuzzy match
                        if common_themes:
                            current_comparison_notes.append(f"    - Alignment: Common themes between commit changes and EOD achievements: {'; '.join(list(common_themes)[:3])}.")
                        else:
                            current_comparison_notes.append("    - Note: Little direct overlap in keywords between commit key changes and EOD key achievements. Manual review may be needed.")
                        
                        # Changes in commit not in EOD
                        commit_specific_details = commit_key_changes - eod_key_achievements
                        if commit_specific_details:
                            current_comparison_notes.append(f"    - Commit Details: Specific items from commit not explicitly in EOD achievements: {'; '.join(list(commit_specific_details)[:2])}.")
                        
                        # Achievements in EOD not in this commit's changes (could be other commits or non-coding tasks)
                        eod_specific_achievements = eod_key_achievements - commit_key_changes
                        if eod_specific_achievements:
                            current_comparison_notes.append(f"    - EOD Details: Achievements in EOD not directly reflected in this commit's key changes: {'; '.join(list(eod_specific_achievements)[:2])}.")
                    elif commit_key_changes:
                        current_comparison_notes.append("    - Note: Commit has key changes, but EOD report AI analysis provided no specific key achievements for comparison.")
                    elif eod_key_achievements:
                        current_comparison_notes.append("    - Note: EOD report AI analysis has key achievements, but this commit analysis provided no specific key changes for comparison.")
                else:
                    current_comparison_notes.append("  - EOD report found, but AI analysis details are not available for comparison.")
            else:
                current_comparison_notes.append(f"No EOD report found for user {author_id_for_eod} on date {commit_timestamp_for_eod.date() if commit_timestamp_for_eod else 'N/A'}.")
                current_comparison_notes.append(f"  - Commit AI Analysis: Estimated Hours for this commit: {commit_ai_hours:.2f}.")

            commit_comparison_notes = "\n".join(current_comparison_notes)

            # --- End New EOD/Code Quality Integration Point ---

            if not analysis_result:
                logger.error(f"❌ AI analysis failed")
                return None

            # Extract points and estimated_hours from the analysis result
            # The AI might return complexity_score which we can map to points
            ai_points = analysis_result.get("complexity_score") or analysis_result.get("points", 0)
            ai_hours = analysis_result.get("estimated_hours", 0)
            seniority_score = analysis_result.get("seniority_score", 0)
            # Extract additional fields from analysis_result
            complexity_score = analysis_result.get("complexity_score")
            risk_level = analysis_result.get("risk_level")
            key_changes = analysis_result.get("key_changes")
            seniority_rationale = analysis_result.get("seniority_rationale")
            model_used = analysis_result.get("model_used")
            analyzed_at_str = analysis_result.get("analyzed_at")
            analyzed_at = None
            if analyzed_at_str:
                try:
                    analyzed_at = datetime.fromisoformat(analyzed_at_str)
                except ValueError:
                    logger.warning(f"Could not parse analyzed_at timestamp: {analyzed_at_str}")
            
            logger.info(f"✓ Analysis complete: Points={ai_points}, Hours={ai_hours}, Seniority={seniority_score}")

            # 3. Map commit author to internal user ID
            # Prioritize author_id if already provided in commit_data (e.g., by process_commit)
            author_id = commit_data.get('author_id') 
            if not author_id:
                author_data = commit_data.get("author", {})
                author_id = self._map_commit_author(author_data)
            
            if not author_id:
                logger.warning(f"⚠ Could not map author to internal user for commit {commit_hash}")
                # Continue without author mapping if it fails

            # 4. Prepare commit data for saving
            commit_to_save = Commit(
                commit_hash=commit_hash,
                author_id=author_id, # May be None if mapping failed
                ai_points=ai_points,
                ai_estimated_hours=ai_hours,
                seniority_score=seniority_score,
                commit_timestamp=commit_data.get("timestamp") or commit_data.get("commit_timestamp") or 
                                diff_data.get("author", {}).get("date"),
                # Populate fields from AI analysis (including newly added ones)
                complexity_score=complexity_score,
                risk_level=risk_level,
                key_changes=key_changes,
                seniority_rationale=seniority_rationale,
                model_used=model_used,
                analyzed_at=analyzed_at,
                # Populate fields from EOD/Code Quality integration
                eod_report_id=eod_report.id if eod_report else None,
                eod_report_summary=eod_report.summary if eod_report and hasattr(eod_report, 'summary') else (eod_report.raw_text_input[:250] + "..." if eod_report and eod_report.raw_text_input else None),
                code_quality_analysis=code_quality_analysis if code_quality_analysis and not code_quality_analysis.get("error") else None,
                comparison_notes=commit_comparison_notes
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
    
    async def batch_analyze_commits(self, commits_payload: List[Dict[str, Any]]) -> List[Optional[Commit]]:
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
                result = await self.analyze_commit(commit_hash, commit_item, fetch_diff=fetch_diff_needed)
                results.append(result)
            else:
                logger.warning(f"⚠ Skipping commit {i+1}/{len(commits_payload)} - missing hash")
                results.append(None)
                
        success_count = sum(1 for r in results if r is not None)
        logger.info(f"Batch processing complete: {success_count}/{len(commits_payload)} commits successfully analyzed")
        self._log_separator("END OF BATCH ANALYSIS", "=")
        return results

    async def _find_user_for_commit(self, payload: CommitPayload) -> Optional[User]:
        """Attempts to find the internal user associated with the commit author."""
        # Prioritize finding by email, then by GitHub username if available
        user = None
        logger.info(f"Finding user for commit {payload.commit_hash}")
        logger.info(f"Author info: email={payload.author_email}, github_username={payload.author_github_username}")
        
        if payload.author_email:
            try:
                logger.info(f"Searching for user by email: {payload.author_email}")
                user = await self.user_repository.get_user_by_email(payload.author_email)
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
            #     user = await self.user_repository.get_user_by_github_username(payload.author_github_username)
            #     if user:
            #         logger.info(f"Found user {user.id} by GitHub username {payload.author_github_username}...")
            #         return user
            # except Exception as e:
            #     logger.error(f"Error finding user by GitHub username: {e}")

        logger.warning(f"⚠ Could not map commit author to internal user")
        return None
    
    async def process_commit(self, commit_data_input: Union[CommitPayload, Dict[str, Any]], scan_docs: Optional[bool] = None) -> Optional[Commit]:
        """Process a commit for analysis, potentially fetching diff data first."""
        try:
            # Support both Dict and CommitPayload cases
            if isinstance(commit_data_input, dict):
                commit_data = CommitPayload(**commit_data_input)
            else:
                commit_data = commit_data_input
                
            commit_hash = commit_data.commit_hash
            self._log_separator(f"PROCESSING COMMIT: {commit_hash}", "=")
            
            logger.info(f"Repository: {commit_data.repository_name}")
            
            # Extract basic metadata for logging
            metadata = {
                "commit_hash": commit_hash,
                "repository_name": commit_data.repository_name,
                "author_email": commit_data.author_email,
                "author_github_username": commit_data.author_github_username,
                "files_changed": len(commit_data.files_changed) if commit_data.files_changed else 0,
                "has_diff": bool(commit_data.commit_diff)  # Whether diff content is provided
            }
            logger.info(f"Commit metadata: {json.dumps(metadata)}")
            
            # 1. Check if commit is already in DB
            existing_commit = self.commit_repository.get_commit_by_hash(commit_hash)
            if existing_commit:
                logger.info(f"✓ Commit {commit_hash} already exists in database")
                # If existing and has analysis, we could skip or perform re-analysis 
                # based on settings.reanalyze_existing_commits
                
                # Opt out early of re-analysis if conditions are met
                if not settings.reanalyze_existing_commits:
                    logger.info(f"Skipping re-analysis (reanalyze_existing_commits=False)")
                    self._log_separator(f"END: COMMIT {commit_hash} ALREADY PROCESSED", "=")
                    return existing_commit
                else:
                    logger.info(f"Re-analyzing existing commit (reanalyze_existing_commits=True)")

            # 2. Find the user associated with the commit author (using _find_user_for_commit helper)
            # _find_user_for_commit already takes CommitPayload
            user = await self._find_user_for_commit(commit_data)
            author_id_to_store = user.id if user else None

            # Prepare data for analyze_commit, which expects a dictionary
            commit_data_dict_for_analysis = commit_data.model_dump(exclude_none=True)
            commit_data_dict_for_analysis['repository'] = commit_data.repository_name # analyze_commit expects 'repository'
            if author_id_to_store:
                commit_data_dict_for_analysis['author_id'] = author_id_to_store
            # Ensure diff is named as expected by analyze_commit if it comes from commit_diff
            if commit_data.commit_diff and not commit_data_dict_for_analysis.get('diff'):
                commit_data_dict_for_analysis['diff'] = commit_data.commit_diff

            # 3. Fetch diff from GitHub if not included (analyze_commit handles this if fetch_diff=True)
            # The fetch_diff flag will be True if commit_data.commit_diff is None.

            # 4. Call analyze_commit to process the data and perform AI analysis
            logger.info(f"Starting commit analysis...")
            analyzed_commit = await self.analyze_commit(
                commit_hash=commit_hash,
                commit_data=commit_data_dict_for_analysis,
                fetch_diff=not commit_data.commit_diff # Fetch only if not provided in CommitPayload
            )
            
            if analyzed_commit:
                logger.info(f"✓ Commit analysis completed successfully")
                self._scan_documentation_for_updates(analyzed_commit, commit_data.repository_name, commit_data_dict_for_analysis, scan_docs)
                self._log_separator(f"END: COMMIT {commit_hash} PROCESSED", "=")
                return analyzed_commit
            else:
                logger.error(f"❌ Commit analysis failed")
                self._log_separator(f"END: COMMIT {commit_hash} FAILED", "=")
                return None
                
        except Exception as e:
            if commit_data_input:
                if isinstance(commit_data_input, dict):
                    ch = commit_data_input.get("commit_hash", "unknown")
                else:
                    ch = commit_data_input.commit_hash
                logger.exception(f"❌ Error processing commit {ch}: {e}")
                self._log_separator(f"ERROR PROCESSING COMMIT: {ch}", "=")
            else:
                logger.exception(f"❌ Error processing commit (unknown hash): {e}")
                self._log_separator("ERROR PROCESSING UNKNOWN COMMIT", "=")
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