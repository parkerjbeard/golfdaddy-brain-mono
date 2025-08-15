import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from app.core.exceptions import DatabaseError, ExternalServiceError
from app.integrations.ai_integration_v2 import AIIntegrationV2
from app.models.commit import Commit
from app.models.daily_commit_analysis import DailyCommitAnalysis, DailyCommitAnalysisCreate, DailyCommitAnalysisUpdate
from app.models.daily_report import DailyReport
from app.repositories.commit_repository import CommitRepository
from app.repositories.daily_commit_analysis_repository import DailyCommitAnalysisRepository
from app.repositories.daily_report_repository import DailyReportRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class DailyCommitAnalysisService:
    """Service for managing daily commit analyses"""

    def __init__(self):
        self.repository = DailyCommitAnalysisRepository()
        self.commit_repo = CommitRepository()
        self.daily_report_repo = DailyReportRepository()
        self.user_repo = UserRepository()
        self.ai_integration = AIIntegrationV2()

    async def analyze_for_report(
        self, user_id: UUID, report_date: date, daily_report: DailyReport
    ) -> DailyCommitAnalysis:
        """
        Analyze commits for a user when they submit their daily report.
        This is the primary entry point for analysis.
        """
        try:
            logger.info(f"Starting daily commit analysis for user {user_id} on {report_date} with report")

            # Check if analysis already exists
            existing = await self.repository.get_by_user_and_date(user_id, report_date)
            if existing:
                logger.info(f"Analysis already exists for user {user_id} on {report_date}, updating...")
                # Update with new daily report reference
                update_data = DailyCommitAnalysisUpdate(daily_report_id=daily_report.id)
                return await self.repository.update(existing.id, update_data)

            # Fetch all commits for the user on this date
            commits = await self._get_user_commits_for_date(user_id, report_date)

            if not commits:
                logger.info(f"No commits found for user {user_id} on {report_date}")
                # Still create an analysis entry with 0 hours
                return await self._create_zero_hour_analysis(user_id, report_date, daily_report.id, "with_report")

            # Prepare context for AI analysis
            context = await self._prepare_analysis_context(commits, daily_report, user_id, report_date)

            # Call AI for holistic analysis
            ai_result = await self.ai_integration.analyze_daily_work(context)

            # Create the analysis record
            analysis_data = DailyCommitAnalysisCreate(
                user_id=user_id,
                analysis_date=report_date,
                total_estimated_hours=Decimal(str(ai_result.get("total_estimated_hours", 0))),
                commit_count=len(commits),
                daily_report_id=daily_report.id,
                analysis_type="with_report",
                ai_analysis=ai_result,
                complexity_score=ai_result.get("average_complexity_score"),
                seniority_score=ai_result.get("average_seniority_score"),
                repositories_analyzed=list(set(c.repository for c in commits if c.repository)),
                total_lines_added=sum(c.additions or 0 for c in commits),
                total_lines_deleted=sum(c.deletions or 0 for c in commits),
            )

            analysis = await self.repository.create(analysis_data)

            # Update commits to link to this analysis
            await self._link_commits_to_analysis(commits, analysis.id)

            logger.info(f"✓ Daily analysis created: {analysis.id} with {analysis.total_estimated_hours} hours")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing commits for report: {e}", exc_info=True)
            raise ExternalServiceError(
                service_name="Daily Commit Analysis", original_message=f"Failed to analyze commits: {str(e)}"
            )

    async def analyze_for_date(self, user_id: UUID, analysis_date: date) -> DailyCommitAnalysis:
        """
        Analyze commits for a user on a specific date (without daily report).
        This is used by the midnight cron job.
        """
        try:
            logger.info(f"Starting automatic daily commit analysis for user {user_id} on {analysis_date}")

            # Check if analysis already exists
            existing = await self.repository.get_by_user_and_date(user_id, analysis_date)
            if existing:
                logger.info(f"Analysis already exists for user {user_id} on {analysis_date}")
                return existing

            # Check if user has a daily report (they might have submitted late)
            try:
                daily_report = await self.daily_report_repo.get_daily_reports_by_user_and_date(
                    user_id, datetime.combine(analysis_date, datetime.min.time())
                )
            except Exception as e:
                logger.warning(f"Could not fetch daily report for {user_id} on {analysis_date}: {e}")
                daily_report = None

            if daily_report:
                # Use the report-based analysis instead
                return await self.analyze_for_report(user_id, analysis_date, daily_report)

            # Fetch all commits for the user on this date
            commits = await self._get_user_commits_for_date(user_id, analysis_date)

            if not commits:
                logger.info(f"No commits found for user {user_id} on {analysis_date}")
                return None  # Don't create zero-hour analysis for automatic runs

            # Prepare context for AI analysis (without daily report)
            context = await self._prepare_analysis_context(commits, None, user_id, analysis_date)

            # Call AI for holistic analysis
            ai_result = await self.ai_integration.analyze_daily_work(context)

            # Create the analysis record
            analysis_data = DailyCommitAnalysisCreate(
                user_id=user_id,
                analysis_date=analysis_date,
                total_estimated_hours=Decimal(str(ai_result.get("total_estimated_hours", 0))),
                commit_count=len(commits),
                daily_report_id=None,
                analysis_type="automatic",
                ai_analysis=ai_result,
                complexity_score=ai_result.get("average_complexity_score"),
                seniority_score=ai_result.get("average_seniority_score"),
                repositories_analyzed=list(set(c.repository for c in commits if c.repository)),
                total_lines_added=sum(c.additions or 0 for c in commits),
                total_lines_deleted=sum(c.deletions or 0 for c in commits),
            )

            analysis = await self.repository.create(analysis_data)

            # Update commits to link to this analysis
            await self._link_commits_to_analysis(commits, analysis.id)

            logger.info(
                f"✓ Automatic daily analysis created: {analysis.id} with {analysis.total_estimated_hours} hours"
            )
            return analysis

        except Exception as e:
            logger.error(f"Error in automatic daily analysis: {e}", exc_info=True)
            raise ExternalServiceError(
                service_name="Daily Commit Analysis", original_message=f"Failed to analyze commits: {str(e)}"
            )

    async def run_midnight_analysis(self) -> Dict[str, int]:
        """
        Run analysis for all users who have commits but no daily report.
        This should be called by a cron job at midnight.
        """
        try:
            yesterday = date.today() - timedelta(days=1)
            logger.info(f"Running midnight analysis for {yesterday}")

            # Get users who need analysis
            users_needing_analysis = await self.repository.get_users_without_analysis(yesterday)

            if not users_needing_analysis:
                logger.info("No users need midnight analysis")
                return {"analyzed": 0, "failed": 0}

            logger.info(f"Found {len(users_needing_analysis)} users needing analysis")

            # Analyze each user
            analyzed = 0
            failed = 0

            for user_id in users_needing_analysis:
                try:
                    analysis = await self.analyze_for_date(user_id, yesterday)
                    if analysis:
                        analyzed += 1
                except Exception as e:
                    logger.error(f"Failed to analyze user {user_id}: {e}")
                    failed += 1

            logger.info(f"✓ Midnight analysis complete: {analyzed} analyzed, {failed} failed")
            return {"analyzed": analyzed, "failed": failed}

        except Exception as e:
            logger.error(f"Error in midnight analysis: {e}", exc_info=True)
            raise

    async def get_user_analysis_history(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> List[DailyCommitAnalysis]:
        """Get analysis history for a user within a date range"""
        try:
            return await self.repository.get_user_analyses_in_range(user_id, start_date, end_date)
        except Exception as e:
            logger.error(f"Error fetching analysis history: {e}", exc_info=True)
            raise

    async def get_analysis_by_id(self, analysis_id: UUID) -> Optional[DailyCommitAnalysis]:
        """Get a specific analysis by ID"""
        try:
            return await self.repository.get_by_id(analysis_id)
        except Exception as e:
            logger.error(f"Error fetching analysis: {e}", exc_info=True)
            raise

    # Private helper methods

    async def _get_user_commits_for_date(self, user_id: UUID, commit_date: date) -> List[Commit]:
        """Fetch all commits for a user on a specific date"""
        try:
            # Use the existing commit repository method
            commits = await self.commit_repo.get_commits_by_user_in_range(
                author_id=user_id, start_date=commit_date, end_date=commit_date
            )
            return commits
        except Exception as e:
            logger.error(f"Error fetching commits: {e}", exc_info=True)
            return []

    async def _prepare_analysis_context(
        self, commits: List[Commit], daily_report: Optional[DailyReport], user_id: UUID, analysis_date: date
    ) -> Dict:
        """Prepare context for AI analysis"""
        # Get user info for context
        user = await self.user_repo.get_by_id(user_id)
        user_name = user.name if user else "Unknown"

        # Prepare commit summaries
        commit_summaries = []
        for commit in commits:
            commit_summaries.append(
                {
                    "hash": commit.commit_hash[:8],
                    "message": commit.commit_message,
                    "timestamp": commit.commit_timestamp.isoformat() if commit.commit_timestamp else None,
                    "repository": commit.repository,
                    "files_changed": commit.files_changed or [],
                    "additions": commit.additions or 0,
                    "deletions": commit.deletions or 0,
                    "ai_estimated_hours": float(commit.ai_estimated_hours) if commit.ai_estimated_hours else None,
                }
            )

        context = {
            "analysis_date": analysis_date.isoformat(),
            "user_name": user_name,
            "commits": commit_summaries,
            "total_commits": len(commits),
            "repositories": list(set(c.repository for c in commits if c.repository)),
            "total_lines_changed": sum((c.additions or 0) + (c.deletions or 0) for c in commits),
        }

        # Add daily report context if available
        if daily_report:
            context["daily_report"] = {
                "summary": daily_report.clarified_tasks_summary or daily_report.raw_text_input,
                "hours_reported": float(daily_report.additional_hours) if daily_report.additional_hours else 0,
                "raw_text": daily_report.raw_text_input,
                "ai_analysis": daily_report.ai_analysis.model_dump() if daily_report.ai_analysis else None,
            }

        return context

    async def _create_zero_hour_analysis(
        self, user_id: UUID, analysis_date: date, daily_report_id: Optional[UUID], analysis_type: str
    ) -> DailyCommitAnalysis:
        """Create an analysis entry with zero hours when no commits exist"""
        analysis_data = DailyCommitAnalysisCreate(
            user_id=user_id,
            analysis_date=analysis_date,
            total_estimated_hours=Decimal("0.0"),
            commit_count=0,
            daily_report_id=daily_report_id,
            analysis_type=analysis_type,
            ai_analysis={"message": "No commits found for this date", "total_estimated_hours": 0},
        )
        return await self.repository.create(analysis_data)

    async def _link_commits_to_analysis(self, commits: List[Commit], analysis_id: UUID) -> None:
        """Update commits to reference the daily analysis"""
        try:
            # We need to update each commit to set daily_analysis_id
            # This would require adding an update method to commit repository
            # For now, we'll log this as a TODO
            logger.info(f"TODO: Link {len(commits)} commits to analysis {analysis_id}")
            # In a real implementation:
            # for commit in commits:
            #     await self.commit_repo.update(
            #         commit.id,
            #         {"daily_analysis_id": analysis_id}
            #     )
        except Exception as e:
            logger.error(f"Error linking commits to analysis: {e}", exc_info=True)
            # Non-critical error, don't fail the whole analysis
