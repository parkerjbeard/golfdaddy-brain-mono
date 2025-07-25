import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID

from app.core.exceptions import DatabaseError, ExternalServiceError
from app.integrations.ai_integration import AIIntegration
from app.models.commit import Commit
from app.models.daily_commit_analysis import (
    DailyCommitAnalysis,
    DailyCommitAnalysisCreate,
    DailyCommitAnalysisUpdate
)
from app.models.daily_report import DailyReport
from app.repositories.commit_repository import CommitRepository
from app.repositories.daily_commit_analysis_repository import DailyCommitAnalysisRepository
from app.repositories.daily_report_repository import DailyReportRepository
from app.repositories.user_repository import UserRepository
import logging

logger = logging.getLogger(__name__)


class UnifiedDailyAnalysisService:
    """Service for unified analysis of daily commits and EOD reports"""
    
    def __init__(self):
        self.analysis_repo = DailyCommitAnalysisRepository()
        self.commit_repo = CommitRepository()
        self.daily_report_repo = DailyReportRepository()
        self.user_repo = UserRepository()
        self.ai_integration = AIIntegration()
    
    async def analyze_daily_work(
        self,
        user_id: UUID,
        analysis_date: date,
        force_reanalysis: bool = False
    ) -> DailyCommitAnalysis:
        """
        Analyze a user's complete work for a given day, combining commits and EOD reports.
        This method prevents double-counting by creating a unified analysis.
        
        Args:
            user_id: The user's UUID
            analysis_date: The date to analyze
            force_reanalysis: If True, will reanalyze even if analysis exists
            
        Returns:
            DailyCommitAnalysis object with comprehensive analysis
        """
        try:
            logger.info(f"Starting unified daily analysis for user {user_id} on {analysis_date}")
            
            # Check for existing analysis
            if not force_reanalysis:
                existing = await self.analysis_repo.get_by_user_and_date(user_id, analysis_date)
                if existing:
                    logger.info(f"Analysis already exists for user {user_id} on {analysis_date}")
                    return existing
            
            # Gather all data for the day
            commits = await self._get_daily_commits(user_id, analysis_date)
            daily_report = await self._get_daily_report(user_id, analysis_date)
            
            # If no work was done, create a zero-hour analysis
            if not commits and not daily_report:
                logger.info(f"No work found for user {user_id} on {analysis_date}")
                return await self._create_zero_hour_analysis(user_id, analysis_date)
            
            # Build comprehensive prompt for AI
            analysis_prompt = await self._build_analysis_prompt(
                user_id, analysis_date, commits, daily_report
            )
            
            # Get AI analysis
            ai_result = await self.ai_integration.analyze_daily_work(analysis_prompt)
            
            # Parse and validate the AI response
            parsed_result = self._parse_ai_response(ai_result)
            
            # Create or update the analysis record
            analysis_data = DailyCommitAnalysisCreate(
                user_id=user_id,
                analysis_date=analysis_date,
                total_estimated_hours=Decimal(str(parsed_result['total_estimated_hours'])),
                commit_count=len(commits),
                daily_report_id=daily_report.id if daily_report else None,
                analysis_type="with_report" if daily_report else "automatic",
                ai_analysis=ai_result,
                complexity_score=parsed_result.get('average_complexity_score'),
                seniority_score=parsed_result.get('average_seniority_score'),
                repositories_analyzed=list(set(c.repository for c in commits if c.repository)),
                total_lines_added=sum(c.additions or 0 for c in commits),
                total_lines_deleted=sum(c.deletions or 0 for c in commits)
            )
            
            # Check if we need to update existing or create new
            existing = await self.analysis_repo.get_by_user_and_date(user_id, analysis_date)
            if existing and force_reanalysis:
                update_data = DailyCommitAnalysisUpdate(
                    total_estimated_hours=analysis_data.total_estimated_hours,
                    ai_analysis=analysis_data.ai_analysis,
                    complexity_score=analysis_data.complexity_score,
                    seniority_score=analysis_data.seniority_score
                )
                analysis = await self.analysis_repo.update(existing.id, update_data)
            else:
                analysis = await self.analysis_repo.create(analysis_data)
            
            logger.info(f"✓ Unified daily analysis complete: {analysis.id} with {analysis.total_estimated_hours} hours")
            return analysis
            
        except Exception as e:
            logger.error(f"Error in unified daily analysis: {e}", exc_info=True)
            raise ExternalServiceError(
                service_name="Unified Daily Analysis",
                original_message=f"Failed to analyze daily work: {str(e)}"
            )
    
    async def _get_daily_commits(self, user_id: UUID, commit_date: date) -> List[Commit]:
        """Fetch all commits for a user on a specific date"""
        try:
            commits = await self.commit_repo.get_commits_by_user_in_range(
                author_id=user_id,
                start_date=commit_date,
                end_date=commit_date
            )
            logger.info(f"Found {len(commits)} commits for user {user_id} on {commit_date}")
            return commits
        except Exception as e:
            logger.error(f"Error fetching commits: {e}", exc_info=True)
            return []
    
    async def _get_daily_report(self, user_id: UUID, report_date: date) -> Optional[DailyReport]:
        """Fetch the daily report for a user on a specific date"""
        try:
            # Convert date to datetime for the repository method
            report_datetime = datetime.combine(report_date, datetime.min.time())
            report = await self.daily_report_repo.get_daily_reports_by_user_and_date(
                user_id, report_datetime
            )
            if report:
                logger.info(f"Found daily report for user {user_id} on {report_date}")
            return report
        except Exception as e:
            logger.error(f"Error fetching daily report: {e}", exc_info=True)
            return None
    
    async def _build_analysis_prompt(
        self,
        user_id: UUID,
        analysis_date: date,
        commits: List[Commit],
        daily_report: Optional[DailyReport]
    ) -> Dict[str, Any]:
        """
        Build a comprehensive prompt for AI analysis that explicitly prevents double-counting
        """
        # Get user info for context
        user = await self.user_repo.get_by_id(user_id)
        user_name = user.name if user else "Unknown"
        
        # Prepare commit summaries
        commit_summaries = []
        for commit in commits:
            commit_summaries.append({
                "hash": commit.commit_hash[:8],
                "message": commit.commit_message,
                "timestamp": commit.commit_timestamp.isoformat() if commit.commit_timestamp else None,
                "repository": commit.repository,
                "files_changed": commit.files_changed or [],
                "additions": commit.additions or 0,
                "deletions": commit.deletions or 0,
                "ai_estimated_hours": float(commit.ai_estimated_hours) if commit.ai_estimated_hours else None
            })
        
        context = {
            "analysis_date": analysis_date.isoformat(),
            "user_name": user_name,
            "commits": commit_summaries,
            "total_commits": len(commits),
            "repositories": list(set(c.repository for c in commits if c.repository)),
            "total_lines_changed": sum((c.additions or 0) + (c.deletions or 0) for c in commits),
        }
        
        # Add daily report context with explicit deduplication instructions
        if daily_report:
            context["daily_report"] = {
                "summary": daily_report.summary,
                "raw_text": daily_report.raw_text_input,
                "hours_reported": float(daily_report.additional_hours) if daily_report.additional_hours else 0,
                "challenges": daily_report.challenges,
                "support_needed": daily_report.support_needed,
                "ai_analysis": daily_report.ai_analysis.model_dump() if daily_report.ai_analysis else None
            }
            
            # Add explicit deduplication instruction
            context["deduplication_instruction"] = (
                "IMPORTANT: When analyzing, identify work that appears in BOTH commits and the daily report. "
                "Do NOT double-count hours for the same work. If a task is mentioned in the daily report "
                "and also has corresponding commits, count it only ONCE in your total hour estimation. "
                "Look for overlaps such as: same feature names, same bug fixes, same documentation updates. "
                "The daily report might provide additional context or non-commit work (meetings, reviews, planning) "
                "that should be added to the commit-based work, but the same implementation work should not be counted twice."
            )
        
        return context
    
    def _parse_ai_response(self, ai_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and validate the AI response, ensuring all required fields are present
        """
        # Ensure required fields with defaults
        parsed = {
            'total_estimated_hours': float(ai_result.get('total_estimated_hours', 0.0)),
            'average_complexity_score': ai_result.get('average_complexity_score', 5),
            'average_seniority_score': ai_result.get('average_seniority_score', 5),
            'work_summary': ai_result.get('work_summary', ''),
            'key_achievements': ai_result.get('key_achievements', []),
            'hour_estimation_reasoning': ai_result.get('hour_estimation_reasoning', ''),
            'consistency_with_report': ai_result.get('consistency_with_report', True),
            'recommendations': ai_result.get('recommendations', [])
        }
        
        # Validate hour estimation is reasonable (0-24 hours)
        if parsed['total_estimated_hours'] < 0:
            parsed['total_estimated_hours'] = 0.0
        elif parsed['total_estimated_hours'] > 24:
            logger.warning(f"AI estimated {parsed['total_estimated_hours']} hours, capping at 24")
            parsed['total_estimated_hours'] = 24.0
        
        # Validate scores are in range 1-10
        for score_field in ['average_complexity_score', 'average_seniority_score']:
            if parsed[score_field] is not None:
                parsed[score_field] = max(1, min(10, int(parsed[score_field])))
        
        return parsed
    
    async def _create_zero_hour_analysis(
        self,
        user_id: UUID,
        analysis_date: date
    ) -> DailyCommitAnalysis:
        """Create an analysis entry with zero hours when no work exists"""
        analysis_data = DailyCommitAnalysisCreate(
            user_id=user_id,
            analysis_date=analysis_date,
            total_estimated_hours=Decimal("0.0"),
            commit_count=0,
            daily_report_id=None,
            analysis_type="automatic",
            ai_analysis={
                "message": "No commits or daily report found for this date",
                "total_estimated_hours": 0,
                "work_summary": "No work recorded for this date"
            }
        )
        return await self.analysis_repo.create(analysis_data)
    
    async def get_weekly_aggregate(
        self,
        user_id: UUID,
        week_start: date
    ) -> Dict[str, Any]:
        """
        Get a weekly aggregate of work analysis for a user
        
        Args:
            user_id: The user's UUID
            week_start: The start date of the week (Monday)
            
        Returns:
            Dictionary containing weekly summary with daily breakdowns
        """
        try:
            week_end = week_start + timedelta(days=6)
            logger.info(f"Getting weekly aggregate for user {user_id} from {week_start} to {week_end}")
            
            # Get all analyses for the week
            analyses = await self.analysis_repo.get_user_analyses_in_range(
                user_id, week_start, week_end
            )
            
            # Build daily breakdown
            daily_breakdown = []
            total_hours = Decimal("0.0")
            total_commits = 0
            all_repositories = set()
            
            for day_offset in range(7):
                current_date = week_start + timedelta(days=day_offset)
                day_analysis = next(
                    (a for a in analyses if a.analysis_date == current_date),
                    None
                )
                
                if day_analysis:
                    daily_breakdown.append({
                        "date": current_date.isoformat(),
                        "day_name": current_date.strftime("%A"),
                        "hours": float(day_analysis.total_estimated_hours),
                        "commits": day_analysis.commit_count,
                        "has_daily_report": day_analysis.daily_report_id is not None,
                        "repositories": day_analysis.repositories_analyzed,
                        "complexity_score": day_analysis.complexity_score,
                        "key_achievements": day_analysis.ai_analysis.get("key_achievements", [])
                    })
                    total_hours += day_analysis.total_estimated_hours
                    total_commits += day_analysis.commit_count
                    all_repositories.update(day_analysis.repositories_analyzed)
                else:
                    daily_breakdown.append({
                        "date": current_date.isoformat(),
                        "day_name": current_date.strftime("%A"),
                        "hours": 0.0,
                        "commits": 0,
                        "has_daily_report": False,
                        "repositories": [],
                        "complexity_score": None,
                        "key_achievements": []
                    })
            
            # Calculate averages
            working_days = len([d for d in daily_breakdown if d["hours"] > 0])
            avg_hours_per_day = float(total_hours) / 7 if total_hours > 0 else 0.0
            avg_hours_per_working_day = float(total_hours) / working_days if working_days > 0 else 0.0
            
            # Get user info
            user = await self.user_repo.get_by_id(user_id)
            
            return {
                "user_id": str(user_id),
                "user_name": user.name if user else "Unknown",
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "total_hours": float(total_hours),
                "total_commits": total_commits,
                "working_days": working_days,
                "average_hours_per_day": round(avg_hours_per_day, 1),
                "average_hours_per_working_day": round(avg_hours_per_working_day, 1),
                "repositories": list(all_repositories),
                "daily_breakdown": daily_breakdown,
                "summary": {
                    "most_productive_day": max(daily_breakdown, key=lambda d: d["hours"])["day_name"] if working_days > 0 else None,
                    "least_productive_day": min(
                        [d for d in daily_breakdown if d["hours"] > 0], 
                        key=lambda d: d["hours"]
                    )["day_name"] if working_days > 0 else None,
                    "days_with_reports": len([d for d in daily_breakdown if d["has_daily_report"]]),
                    "days_with_commits": len([d for d in daily_breakdown if d["commits"] > 0])
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting weekly aggregate: {e}", exc_info=True)
            raise ExternalServiceError(
                service_name="Weekly Aggregate Analysis",
                original_message=f"Failed to get weekly aggregate: {str(e)}"
            )
    
    async def handle_clarification_needed(
        self,
        analysis_id: UUID,
        clarification_request: str
    ) -> Dict[str, Any]:
        """
        Handle cases where the AI needs clarification to complete the analysis
        
        Args:
            analysis_id: The analysis ID that needs clarification
            clarification_request: The specific clarification needed
            
        Returns:
            Dictionary with clarification details and next steps
        """
        try:
            logger.info(f"Handling clarification request for analysis {analysis_id}")
            
            # Get the analysis
            analysis = await self.analysis_repo.get_by_id(analysis_id)
            if not analysis:
                raise ResourceNotFoundError(f"Analysis {analysis_id} not found")
            
            # Update the analysis with clarification request
            updated_ai_analysis = analysis.ai_analysis.copy()
            updated_ai_analysis["clarification_needed"] = True
            updated_ai_analysis["clarification_request"] = clarification_request
            updated_ai_analysis["clarification_status"] = "pending"
            
            update_data = DailyCommitAnalysisUpdate(
                ai_analysis=updated_ai_analysis
            )
            
            await self.analysis_repo.update(analysis_id, update_data)
            
            return {
                "analysis_id": str(analysis_id),
                "clarification_needed": True,
                "clarification_request": clarification_request,
                "instructions": "Please provide the requested clarification to complete the analysis",
                "status": "pending_clarification"
            }
            
        except Exception as e:
            logger.error(f"Error handling clarification: {e}", exc_info=True)
            raise
    
    async def provide_clarification(
        self,
        analysis_id: UUID,
        clarification_response: str
    ) -> DailyCommitAnalysis:
        """
        Provide clarification for a pending analysis and re-run the analysis
        
        Args:
            analysis_id: The analysis ID that needs clarification
            clarification_response: The user's response to the clarification request
            
        Returns:
            Updated DailyCommitAnalysis with clarification incorporated
        """
        try:
            logger.info(f"Processing clarification for analysis {analysis_id}")
            
            # Get the analysis
            analysis = await self.analysis_repo.get_by_id(analysis_id)
            if not analysis:
                raise ResourceNotFoundError(f"Analysis {analysis_id} not found")
            
            # Re-run analysis with clarification
            return await self.analyze_daily_work(
                analysis.user_id,
                analysis.analysis_date,
                force_reanalysis=True
            )
            
        except Exception as e:
            logger.error(f"Error providing clarification: {e}", exc_info=True)
            raise