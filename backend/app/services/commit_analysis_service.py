import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from app.config.settings import settings

# TODO: Import DailyReportService if direct interaction is needed, or pass data through other means
from app.core.exceptions import (  # New imports for context and future use
    AIIntegrationError,
    AppExceptionBase,
    BadRequestError,
    ConfigurationError,
    DatabaseError,
    ExternalServiceError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.integrations.commit_analysis import CommitAnalyzer
from app.integrations.github_integration import GitHubIntegration
from app.models.commit import Commit
from app.models.daily_report import DailyReport
from app.models.user import User
from app.repositories.commit_repository import CommitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.github_event import CommitPayload
from app.services.daily_report_service import DailyReportService
from supabase import Client

logger = logging.getLogger(__name__)


class CommitAnalysisService:
    """Service for analyzing commits and calculating points."""

    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.commit_repository = CommitRepository(supabase)
        self.user_repository = UserRepository(supabase)
        self.commit_analyzer = CommitAnalyzer()
        # Alias retained for backward compatibility with callers/tests that expect `ai_integration`
        self.ai_integration = self.commit_analyzer
        self.github_integration = GitHubIntegration()
        self.daily_report_service = DailyReportService()  # Uncommented and initialized

        # Simplified point calculation weights
        self.complexity_weight = 2.0  # Base weight for complexity score

        # Simplified risk factors - used only for minor adjustments
        self.risk_factors = {"low": 1.0, "medium": 1.2, "high": 1.5}

        # Documentation repository name (format: "owner/repo")
        # self.docs_repository = settings.docs_repository # Removed
        # self.enable_docs_updates = settings.enable_docs_updates # Removed

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

    async def analyze_commit(
        self, commit_hash: str, commit_data: Dict[str, Any], fetch_diff: bool = True
    ) -> Optional[Commit]:
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
            logger.info(
                f"Author: {commit_data.get('author', {}).get('name', 'N/A')} <{commit_data.get('author', {}).get('email', 'N/A')}>"
            )

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
                        github_username_from_author = commit_author_info.get("login")  # often from github webhook

                        if commit_data.get("author_github_username"):  # from CommitPayload
                            owner = commit_data.get("author_github_username")
                        elif github_username_from_author:
                            owner = github_username_from_author
                        else:  # Fallback to a default if no author information can be derived
                            owner = "golfdaddy"  # Default owner, adjust if necessary

                        repository = f"{owner}/{repo_name_only}"
                        logger.info(
                            f"Reformatted repository name to: {repository} (owner: {owner}, repo: {repo_name_only})"
                        )

                    logger.info(
                        f"Attempting to fetch diff from GitHub. Original repo input: '{commit_data.get('repository')}', Derived/Used repo: '{repository}', Commit SHA: '{commit_hash}'"
                    )

                    # Run blocking GitHub request off the event loop
                    diff_data = await asyncio.to_thread(
                        self.github_integration.get_commit_diff, repository, commit_hash
                    )

                    if diff_data:
                        logger.info(
                            f"✓ Diff fetched successfully ({diff_data.get('additions', 0)} additions, {diff_data.get('deletions', 0)} deletions)"
                        )
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
                    logger.error(
                        f"❌ GitHub error during diff fetch for commit {commit_hash} on repo {repository}: {github_err}",
                        exc_info=True,
                    )

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
                "deletions": commit_data.get("deletions", 0),
            }

            # Check if individual commit analysis should be skipped in favor of daily batch analysis
            if settings.SKIP_INDIVIDUAL_COMMIT_ANALYSIS:
                logger.info("Skipping individual commit AI analysis (daily batch analysis enabled)")
                # Create a minimal analysis result without AI call
                analysis_result = {
                    "complexity_score": 5,  # Default value
                    "estimated_hours": 0.0,  # Will be overridden by daily analysis
                    "risk_level": "medium",
                    "seniority_score": 5,
                    "seniority_rationale": "Skipped individual analysis - will be analyzed in daily batch",
                    "key_changes": [],
                    "analyzed_at": datetime.now().isoformat(),
                    "commit_hash": commit_hash,
                    "repository": commit_data.get("repository", ""),
                    "model_used": "none (batch analysis mode)",
                    "batch_analysis_pending": True,
                }
            else:
                # Call AI integration with the structured data
                logger.info("Sending commit data to CommitAnalyzer (Impact Points v2.0)...")
                analysis_result = await self.commit_analyzer.analyze_commit_diff(ai_commit_data)

            # --- New EOD/Code Quality Integration Point ---
            # TODO: Fetch relevant EOD report from DailyReportService for this user & date.
            eod_report: Optional[DailyReport] = None
            code_quality_analysis: Optional[Dict[str, Any]] = None  # Define type for code_quality_analysis

            author_id_for_eod = commit_data.get("author_id")
            commit_timestamp_for_eod = commit_data.get("timestamp") or commit_data.get("commit_timestamp")

            # Ensure commit_timestamp_for_eod is a datetime object
            if isinstance(commit_timestamp_for_eod, str):
                try:
                    commit_timestamp_for_eod = datetime.fromisoformat(commit_timestamp_for_eod.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"Could not parse commit_timestamp_for_eod: {commit_timestamp_for_eod}")
                    commit_timestamp_for_eod = None

            if author_id_for_eod and commit_timestamp_for_eod:
                logger.info(f"Fetching EOD report for user {author_id_for_eod} on {commit_timestamp_for_eod.date()}")
                try:
                    eod_report = await self.daily_report_service.get_user_report_for_date(
                        author_id_for_eod, commit_timestamp_for_eod
                    )
                    if eod_report:
                        logger.info(f"✓ EOD report found: {eod_report.id}")
                    else:
                        logger.info(
                            f"No EOD report found for user {author_id_for_eod} on {commit_timestamp_for_eod.date()}"
                        )
                except Exception as e_eod:
                    logger.error(
                        f"Error fetching EOD report for user {author_id_for_eod} on {commit_timestamp_for_eod.date() if commit_timestamp_for_eod else 'N/A'}: {e_eod}",
                        exc_info=True,
                    )

            # TODO: Pass commit diff and message to the new AI code quality analysis method.
            # Assuming ai_integration.analyze_commit_code_quality is an async method
            try:
                logger.info("Performing AI code quality analysis...")
                # This method needs to be implemented in AIIntegration service and made async
                # For now, assuming it exists and is async:
                # code_quality_analysis = await self.ai_integration.analyze_commit_code_quality(diff_content, commit_data.get("message", ""))
                # Placeholder for now:
                if hasattr(self.ai_integration, "analyze_commit_code_quality") and callable(
                    getattr(self.ai_integration, "analyze_commit_code_quality")
                ):
                    code_quality_analysis = await self.ai_integration.analyze_commit_code_quality(
                        diff_content, commit_data.get("message", "")
                    )
                    logger.info(f"✓ Code quality analysis result: {code_quality_analysis}")
                else:
                    logger.warning(
                        "ai_integration.analyze_commit_code_quality method not found or not callable. Skipping."
                    )
                    code_quality_analysis = {"placeholder_quality_score": 0.0, "issues": []}

            except Exception as e_cqa:
                logger.error(f"Error during AI code quality analysis for commit {commit_hash}: {e_cqa}", exc_info=True)
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
                "eod_report_ai_analysis_summary": (
                    eod_report.ai_analysis.summary if eod_report and eod_report.ai_analysis else None
                ),
                "eod_report_ai_estimated_hours": (
                    eod_report.ai_analysis.estimated_hours if eod_report and eod_report.ai_analysis else None
                ),
                "code_quality_analysis_retrieved": code_quality_analysis,
            }
            logger.info(f"Detailed EOD/Quality Integration Log: {json.dumps(detailed_comparison_log, default=str)}")

            current_comparison_notes = []
            commit_ai_hours = analysis_result.get("estimated_hours", 0.0)

            if eod_report:
                current_comparison_notes.append(
                    f"EOD report {eod_report.id} (date: {eod_report.report_date.strftime('%Y-%m-%d')}) found for user {author_id_for_eod}."
                )
                if eod_report.ai_analysis:
                    eod_ai_hours = (
                        eod_report.ai_analysis.estimated_hours
                        if eod_report.ai_analysis.estimated_hours is not None
                        else 0.0
                    )
                    current_comparison_notes.append(
                        f"  - EOD AI Analysis: Estimated Hours: {eod_ai_hours:.2f}, Summary: {eod_report.ai_analysis.summary}"
                    )
                    current_comparison_notes.append(
                        f"  - Commit AI Analysis: Estimated Hours for this commit: {commit_ai_hours:.2f}."
                    )

                    # Compare hours
                    if abs(commit_ai_hours - eod_ai_hours) > 0.5:  # Example threshold for significant difference
                        current_comparison_notes.append(
                            f"    - Note: Difference in estimated hours between EOD ({eod_ai_hours:.2f}h) and this commit ({commit_ai_hours:.2f}h). This commit is one of possibly multiple for the day."
                        )

                    # Compare key changes/achievements
                    commit_key_changes = set(analysis_result.get("key_changes", []))
                    eod_key_achievements = set(eod_report.ai_analysis.key_achievements or [])

                    if commit_key_changes and eod_key_achievements:
                        common_themes = commit_key_changes.intersection(
                            eod_key_achievements
                        )  # Simple intersection, could be fuzzy match
                        if common_themes:
                            current_comparison_notes.append(
                                f"    - Alignment: Common themes between commit changes and EOD achievements: {'; '.join(list(common_themes)[:3])}."
                            )
                        else:
                            current_comparison_notes.append(
                                "    - Note: Little direct overlap in keywords between commit key changes and EOD key achievements. Manual review may be needed."
                            )

                        # Changes in commit not in EOD
                        commit_specific_details = commit_key_changes - eod_key_achievements
                        if commit_specific_details:
                            current_comparison_notes.append(
                                f"    - Commit Details: Specific items from commit not explicitly in EOD achievements: {'; '.join(list(commit_specific_details)[:2])}."
                            )

                        # Achievements in EOD not in this commit's changes (could be other commits or non-coding tasks)
                        eod_specific_achievements = eod_key_achievements - commit_key_changes
                        if eod_specific_achievements:
                            current_comparison_notes.append(
                                f"    - EOD Details: Achievements in EOD not directly reflected in this commit's key changes: {'; '.join(list(eod_specific_achievements)[:2])}."
                            )
                    elif commit_key_changes:
                        current_comparison_notes.append(
                            "    - Note: Commit has key changes, but EOD report AI analysis provided no specific key achievements for comparison."
                        )
                    elif eod_key_achievements:
                        current_comparison_notes.append(
                            "    - Note: EOD report AI analysis has key achievements, but this commit analysis provided no specific key changes for comparison."
                        )
                else:
                    current_comparison_notes.append(
                        "  - EOD report found, but AI analysis details are not available for comparison."
                    )
            else:
                current_comparison_notes.append(
                    f"No EOD report found for user {author_id_for_eod} on date {commit_timestamp_for_eod.date() if commit_timestamp_for_eod else 'N/A'}."
                )
                current_comparison_notes.append(
                    f"  - Commit AI Analysis: Estimated Hours for this commit: {commit_ai_hours:.2f}."
                )

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

            # Extract impact scoring fields
            impact_score = analysis_result.get("impact_score", 0)
            impact_business_value = analysis_result.get("impact_business_value", 0)
            impact_technical_complexity = analysis_result.get("impact_technical_complexity", 0)
            impact_code_quality_points = analysis_result.get("impact_code_quality_points")
            if impact_code_quality_points is None:
                impact_code_quality_points = analysis_result.get("impact_code_quality", 0)

            impact_risk_penalty = analysis_result.get("impact_risk_penalty")
            if impact_risk_penalty is None:
                impact_risk_penalty = analysis_result.get("impact_risk_factor", 0)

            logger.info(f"✓ Analysis complete: Points={ai_points}, Hours={ai_hours}, Seniority={seniority_score}")
            logger.info(
                f"✓ Impact Score: {impact_score} ((BV:{impact_business_value}×2) + (TC:{impact_technical_complexity}×1.5) + CQ:{impact_code_quality_points} - Risk:{impact_risk_penalty})"
            )

            # 3. Map commit author to internal user ID
            # Prioritize author_id if already provided in commit_data (e.g., by process_commit)
            author_id = commit_data.get("author_id")
            if not author_id:
                author_data = commit_data.get("author", {})
                author_id = await self._map_commit_author(author_data)

            if not author_id:
                logger.warning(f"⚠ Could not map author to internal user for commit {commit_hash}")
                # Continue without author mapping if it fails

            # 4. Prepare commit data for saving
            # Store ALL analysis data in ai_analysis_notes as JSON for full flexibility
            analysis_notes_data = {
                # Traditional hours-based scoring
                "estimated_hours": ai_hours,
                "complexity_score": complexity_score,
                "seniority_score": seniority_score,
                "risk_level": risk_level,
                "key_changes": key_changes,
                "seniority_rationale": seniority_rationale,
                # New structured anchor fields
                "total_lines": analysis_result.get("total_lines"),
                "total_files": analysis_result.get("total_files"),
                "initial_anchor": analysis_result.get("initial_anchor"),
                "major_change_checks": analysis_result.get("major_change_checks"),
                "major_change_count": analysis_result.get("major_change_count"),
                "file_count_override": analysis_result.get("file_count_override"),
                "simplicity_reduction_checks": analysis_result.get("simplicity_reduction_checks"),
                "complexity_cap_applied": analysis_result.get("complexity_cap_applied"),
                "final_anchor": analysis_result.get("final_anchor"),
                "base_hours": analysis_result.get("base_hours"),
                "multipliers_applied": analysis_result.get("multipliers_applied"),
                # Impact scoring data
                "impact_score": impact_score,
                "impact_business_value": impact_business_value,
                "impact_business_value_decision_path": analysis_result.get("impact_business_value_decision_path"),
                "impact_technical_complexity": impact_technical_complexity,
                "impact_code_quality_points": impact_code_quality_points,
                "impact_code_quality_checklist": analysis_result.get("impact_code_quality_checklist"),
                "impact_risk_penalty": impact_risk_penalty,
                "impact_business_value_reasoning": analysis_result.get("impact_business_value_reasoning"),
                "impact_technical_complexity_reasoning": analysis_result.get("impact_technical_complexity_reasoning"),
                "impact_code_quality_reasoning": analysis_result.get("impact_code_quality_reasoning"),
                "impact_risk_reasoning": analysis_result.get("impact_risk_reasoning"),
                # Compatibility aliases for downstream consumers still expecting older field names
                "impact_code_quality": analysis_result.get("impact_code_quality", impact_code_quality_points),
                "impact_risk_factor": analysis_result.get("impact_risk_factor", impact_risk_penalty),
                "impact_dominant_category": analysis_result.get("impact_dominant_category")
                or (analysis_result.get("impact_classification") or {}).get("primary_category"),
                "impact_classification": analysis_result.get("impact_classification"),
                "impact_calculation_breakdown": analysis_result.get("impact_calculation_breakdown"),
                # Metadata
                "model_used": model_used,
                "analyzed_at": analyzed_at.isoformat() if isinstance(analyzed_at, datetime) else analyzed_at,
                "analysis_version": "2.0",  # Version tracking for future changes
            }

            commit_to_save = Commit(
                commit_hash=commit_hash,
                author_id=author_id,  # May be None if mapping failed
                ai_estimated_hours=ai_hours,
                seniority_score=seniority_score,
                commit_timestamp=commit_data.get("timestamp")
                or commit_data.get("commit_timestamp")
                or (diff_data.get("author", {}).get("date") if diff_data else None),
                # Populate fields from AI analysis (including newly added ones)
                complexity_score=complexity_score,
                risk_level=risk_level,
                key_changes=key_changes,
                seniority_rationale=seniority_rationale,
                model_used=model_used,
                analyzed_at=analyzed_at,
                # Store ALL analysis data in ai_analysis_notes as JSON
                ai_analysis_notes=json.dumps(analysis_notes_data),
                # Populate fields from EOD/Code Quality integration
                eod_report_id=eod_report.id if eod_report else None,
                eod_report_summary=(
                    eod_report.summary
                    if eod_report and hasattr(eod_report, "summary")
                    else (eod_report.raw_text_input[:250] + "..." if eod_report and eod_report.raw_text_input else None)
                ),
                code_quality_analysis=(
                    code_quality_analysis if code_quality_analysis and not code_quality_analysis.get("error") else None
                ),
                comparison_notes=commit_comparison_notes,
                # Add other relevant fields from commit_data if needed in the model/DB
            )

            # Parse timestamp string if necessary
            ts = commit_to_save.commit_timestamp
            if isinstance(ts, str):
                try:
                    commit_to_save.commit_timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
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
            saved_commit = await self.commit_repository.save_commit(commit_to_save)

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

    async def _map_commit_author(self, author_data: Optional[Dict[str, Any]]) -> Optional[UUID]:
        """Tries to map commit author info (GitHub username, email, name) to an internal user ID.
        Prioritizes GitHub username, then email.
        This method is more of a fallback and does NOT create new users.
        Args:
            author_data: Dictionary containing author information (e.g., from commit_data.get("author"))
                         Expected keys: 'login' (for github_username), 'email'.

        Returns:
            The internal user ID (UUID) or None if mapping fails.
        """
        if not author_data:
            logger.debug("_map_commit_author: No author_data provided.")
            return None

        user: Optional[User] = None

        # 1. Try to map by GitHub username (author_data might contain 'login' from GitHub webhook)
        github_username = author_data.get("login") or author_data.get("github_username")
        if github_username:
            try:
                logger.info(f"_map_commit_author: Attempting to find user by GitHub username: {github_username}")
                user = await self.user_repository.get_user_by_github_username(github_username)
                if user:
                    logger.info(f"_map_commit_author: Found user {user.id} by GitHub username: {github_username}")
                    return user.id
            except Exception as e:
                logger.error(
                    f"_map_commit_author: Error finding user by GitHub username '{github_username}': {e}", exc_info=True
                )

        # 2. Try to map by email if not found by GitHub username
        email = author_data.get("email")
        if email:
            try:
                logger.info(f"_map_commit_author: Attempting to find user by email: {email}")
                user = await self.user_repository.get_user_by_email(email)
                if user:
                    logger.info(f"_map_commit_author: Found user {user.id} by email: {email}")
                    # If found by email, and we have a github_username from author_data,
                    # consider updating the user record if its github_username is not set.
                    if not user.github_username and github_username:
                        logger.info(
                            f"_map_commit_author: User {user.id} found by email, has no GitHub username. Updating with: {github_username}"
                        )
                        await self.user_repository.update_user(user.id, {"github_username": github_username})
                        # No need to re-fetch, just return the ID.
                    return user.id
            except Exception as e:
                logger.error(f"_map_commit_author: Error finding user by email '{email}': {e}", exc_info=True)

        # Fallback for other identifiers if necessary (e.g., Slack ID if it were present in author_data)
        # slack_id = author_data.get("slack_id")
        # if slack_id:
        #     user = await self.user_repository.get_user_by_slack_id(slack_id) # Note: get_user_by_slack_id is async
        #     if user:
        #         logger.info(f"_map_commit_author: Found user {user.id} by Slack ID: {slack_id}")
        #         return user.id

        logger.warning(f"_map_commit_author: Could not map author to internal user using provided data: {author_data}")
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
            commit_hash = commit_item.get("hash") or commit_item.get("id")  # Adapt based on webhook payload
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
        """Attempts to find the internal user associated with the commit author.
        Prioritizes GitHub username, then email. If no user is found, creates a new one.
        """
        user = None
        logger.info(f"Finding user for commit {payload.commit_hash}")
        logger.info(f"Author info: email={payload.author_email}, github_username={payload.author_github_username}")

        # 1. Try to find user by GitHub username
        if payload.author_github_username:
            try:
                logger.info(f"Searching for user by GitHub username: {payload.author_github_username}")
                user = await self.user_repository.get_user_by_github_username(payload.author_github_username)
                if user:
                    logger.info(f"✓ Found user {user.id} by GitHub username {payload.author_github_username}")
                    return user
                else:
                    logger.info(f"No user found with GitHub username {payload.author_github_username}")
            except Exception as e:
                logger.error(
                    f"❌ Error finding user by GitHub username '{payload.author_github_username}': {e}", exc_info=True
                )

        # 2. If not found by GitHub username, try by email
        if payload.author_email:
            try:
                logger.info(f"Searching for user by email: {payload.author_email}")
                user = await self.user_repository.get_user_by_email(payload.author_email)
                if user:
                    logger.info(f"✓ Found user {user.id} by email {payload.author_email}")
                    # Optionally, update this user's github_username if it's empty and payload.author_github_username is available
                    if not user.github_username and payload.author_github_username:
                        logger.info(
                            f"User {user.id} found by email, updating with GitHub username: {payload.author_github_username}"
                        )
                        updated_user = await self.user_repository.update_user(
                            user.id, {"github_username": payload.author_github_username}
                        )
                        if updated_user:
                            return updated_user
                        else:
                            logger.warning(f"Failed to update user {user.id} with GitHub username.")
                    return user
                else:
                    logger.warning(f"⚠ No user found with email {payload.author_email}")
            except AttributeError as ae:  # Specific error for repository issues
                logger.error(
                    f"❌ User repository attribute error while searching by email '{payload.author_email}': {ae}",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(f"❌ Error finding user by email '{payload.author_email}': {e}", exc_info=True)

        # 3. If no user is found by GitHub username or email, create a new user
        # This part fulfills the requirement: "If a user with a github username is not registered,
        # it should show up as a new user in the user database..."
        if payload.author_github_username:  # Create user only if github_username is present
            logger.info(
                f"No existing user found. Attempting to create a new user for GitHub username: {payload.author_github_username}"
            )
            try:
                from uuid import uuid4  # For generating new user ID

                from app.models.user import UserRole  # For default role

                new_user_data = User(
                    id=uuid4(),  # Generate a new UUID for the user
                    name=payload.author_name
                    or payload.author_github_username,  # Use provided name or fallback to username
                    email=payload.author_email if payload.author_email else None,
                    github_username=payload.author_github_username,
                    role=UserRole.EMPLOYEE,  # Default role for new users
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    is_active=True,  # New users are active by default
                    # Other fields like avatar_url, team, etc., can be None or set to defaults
                )

                created_user = await self.user_repository.create_user(new_user_data)

                if created_user:
                    logger.info(
                        f"✓ Successfully created new user {created_user.id} for GitHub username {created_user.github_username}"
                    )
                    return created_user
                else:
                    logger.error(f"❌ Failed to create new user for GitHub username {payload.author_github_username}")
            except Exception as e:
                logger.exception(
                    f"❌ Exception during new user creation for GitHub username {payload.author_github_username}: {e}"
                )

        logger.warning(
            f"⚠ Could not map or create commit author to internal user for commit {payload.commit_hash}. GitHub username: {payload.author_github_username}, Email: {payload.author_email}"
        )
        return None

    async def process_commit(
        self, commit_data_input: Union[CommitPayload, Dict[str, Any]], scan_docs: Optional[bool] = None
    ) -> Optional[Commit]:
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
                "has_diff": bool(commit_data.commit_diff),  # Whether diff content is provided
            }
            logger.info(f"Commit metadata: {json.dumps(metadata)}")

            # 1. Check if commit is already in DB
            existing_commit = await self.commit_repository.get_commit_by_hash(commit_hash)
            if existing_commit:
                logger.info(f"✓ Commit {commit_hash} already exists in database")
                # If existing and has analysis, we could skip or perform re-analysis
                # based on settings.reanalyze_existing_commits. However, if the commit exists
                # but is missing analysis fields, we should proceed to analyze it.

                has_analysis = (
                    getattr(existing_commit, "ai_estimated_hours", None) is not None
                    or getattr(existing_commit, "seniority_score", None) is not None
                )

                if has_analysis and not settings.reanalyze_existing_commits:
                    logger.info(f"Skipping re-analysis (reanalyze_existing_commits=False)")
                    self._log_separator(f"END: COMMIT {commit_hash} ALREADY PROCESSED", "=")
                    return existing_commit
                elif not has_analysis:
                    logger.info("Existing commit found without analysis; proceeding with analysis to populate fields")
                else:
                    logger.info(f"Re-analyzing existing commit (reanalyze_existing_commits=True)")

            # 2. Find the user associated with the commit author (using _find_user_for_commit helper)
            # _find_user_for_commit already takes CommitPayload
            user = await self._find_user_for_commit(commit_data)
            author_id_to_store = user.id if user else None

            # Prepare data for analyze_commit, which expects a dictionary
            commit_data_dict_for_analysis = commit_data.model_dump(exclude_none=True)
            commit_data_dict_for_analysis["repository"] = (
                commit_data.repository_name
            )  # analyze_commit expects 'repository'
            if author_id_to_store:
                commit_data_dict_for_analysis["author_id"] = author_id_to_store
            # Ensure diff is named as expected by analyze_commit if it comes from commit_diff
            if commit_data.commit_diff and not commit_data_dict_for_analysis.get("diff"):
                commit_data_dict_for_analysis["diff"] = commit_data.commit_diff

            # 3. Fetch diff from GitHub if not included (analyze_commit handles this if fetch_diff=True)
            # The fetch_diff flag will be True if commit_data.commit_diff is None.

            # 4. Call analyze_commit to process the data and perform AI analysis
            logger.info(f"Starting commit analysis...")
            analyzed_commit = await self.analyze_commit(
                commit_hash=commit_hash,
                commit_data=commit_data_dict_for_analysis,
                fetch_diff=not commit_data.commit_diff,  # Fetch only if not provided in CommitPayload
            )

            if analyzed_commit:
                logger.info(f"✓ Commit analysis completed successfully")
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
