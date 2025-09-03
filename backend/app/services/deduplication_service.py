"""
Intelligent deduplication service for preventing double-counting between commits and daily reports.
Uses AI to analyze semantic similarity and identify overlapping work items.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import settings
from app.integrations.ai_integration_v2 import AIIntegrationV2
from app.models.commit import Commit
from app.models.daily_report import DailyReport
from app.repositories.commit_repository import CommitRepository

logger = logging.getLogger(__name__)


@dataclass
class WorkItem:
    """Represents a unit of work from either commits or daily reports."""

    source: str  # "commit" or "report"
    description: str
    estimated_hours: float
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class DeduplicationMatch:
    """Represents a match between commit and report work items."""

    commit_item: WorkItem
    report_item: WorkItem
    confidence_score: float
    explanation: str


@dataclass
class DeduplicationResult:
    """Result of deduplication analysis."""

    matched_items: List[DeduplicationMatch]
    unmatched_items: List[WorkItem]
    total_confidence: float
    unique_hours: float
    duplicate_hours: float


@dataclass
class DeduplicationRule:
    """Rule for deduplication matching."""

    name: str
    pattern: str
    confidence_boost: float
    enabled: bool = True


class WorkType:
    """Enum-like class for work item types."""

    COMMIT = "commit"
    REPORT = "report"
    BOTH = "both"


class DeduplicationService:
    """Service for intelligent work deduplication between commits and daily reports."""

    def __init__(self):
        self.ai_integration = AIIntegrationV2()
        self.commit_repo = CommitRepository()

        # Configurable thresholds
        self.confidence_threshold = float(getattr(settings, "DEDUP_CONFIDENCE_THRESHOLD", 0.8))
        self.time_window_hours = int(getattr(settings, "DEDUP_TIME_WINDOW_HOURS", 24))

    async def deduplicate_daily_report(
        self, report: DailyReport, user_commits: Optional[List[Commit]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a daily report against user's commits to prevent double-counting.

        Args:
            report: The daily report to analyze
            user_commits: Optional list of commits (will fetch if not provided)

        Returns:
            Dictionary containing deduplication results
        """
        try:
            # Get commits if not provided
            if user_commits is None:
                # Get commits within the time window
                end_time = report.report_date
                start_time = end_time - timedelta(hours=self.time_window_hours)

                user_commits = await self.commit_repo.get_commits_by_user_date_range(
                    user_id=report.user_id, start_date=start_time, end_date=end_time
                )

            # Extract work items from commits
            commit_items = self._extract_commit_work_items(user_commits)

            # Extract work items from report
            report_items = self._extract_report_work_items(report)

            # Perform deduplication matching
            matches = await self._find_matches(commit_items, report_items)

            # Calculate hours
            matched_items = []
            unmatched_report_items = []
            total_confidence = 0.0

            matched_report_indices = set()

            for match in matches:
                if match.confidence_score >= self.confidence_threshold:
                    matched_items.append(
                        {
                            "commit_description": match.commit_item.description,
                            "report_description": match.report_item.description,
                            "confidence": match.confidence_score,
                            "explanation": match.explanation,
                            "hours_in_commit": match.commit_item.estimated_hours,
                        }
                    )
                    matched_report_indices.add(report_items.index(match.report_item))
                    total_confidence += match.confidence_score

            # Find unmatched report items
            for i, item in enumerate(report_items):
                if i not in matched_report_indices:
                    unmatched_report_items.append(
                        {"description": item.description, "estimated_hours": item.estimated_hours}
                    )

            # Calculate totals
            commit_hours = sum(item.estimated_hours for item in commit_items)
            matched_hours = sum(item["hours_in_commit"] for item in matched_items)
            additional_hours = sum(item["estimated_hours"] for item in unmatched_report_items)
            total_hours = commit_hours + additional_hours

            # Average confidence for matched items
            avg_confidence = total_confidence / len(matched_items) if matched_items else 0

            results = {
                "commit_hours": commit_hours,
                "matched_hours": matched_hours,
                "additional_hours": additional_hours,
                "total_hours": total_hours,
                "matched_items": matched_items,
                "unmatched_items": unmatched_report_items,
                "deduplication_count": len(matched_items),
                "average_confidence": avg_confidence,
                "commit_count": len(user_commits),
                "report_item_count": len(report_items),
            }

            logger.info(
                f"Deduplication complete for report {report.id}: "
                f"{len(matched_items)} matches found, "
                f"{additional_hours:.1f} additional hours"
            )

            return results

        except Exception as e:
            logger.error(f"Error in deduplication: {e}")
            raise

    def _extract_commit_work_items(self, commits: List[Commit]) -> List[WorkItem]:
        """Extract work items from commits."""
        items = []

        for commit in commits:
            # Use AI analysis if available
            estimated_hours = 0.5  # Default
            if commit.ai_analysis:
                estimated_hours = commit.ai_analysis.get("estimated_hours", 0.5)

            items.append(
                WorkItem(
                    source="commit",
                    description=f"{commit.commit_message}\n\nFiles changed: {', '.join(commit.files_changed[:5])}",
                    estimated_hours=estimated_hours,
                    timestamp=commit.commit_date,
                    metadata={
                        "commit_hash": commit.commit_hash,
                        "repository": commit.repository,
                        "ai_analysis": commit.ai_analysis,
                    },
                )
            )

        return items

    def _extract_report_work_items(self, report: DailyReport) -> List[WorkItem]:
        """Extract work items from daily report."""
        items = []

        # Parse the raw text input
        # This is a simple implementation - could be enhanced with NLP
        lines = report.raw_text_input.strip().split("\n")

        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):  # Skip empty lines and headers
                # Simple heuristic: each line is a work item
                # Could enhance this with AI parsing
                items.append(
                    WorkItem(
                        source="report",
                        description=line,
                        estimated_hours=1.0,  # Default, will be refined by AI
                        timestamp=report.report_date,
                        metadata={"report_id": str(report.id)},
                    )
                )

        # If AI analysis is available, use it to refine hours
        if report.ai_analysis and report.ai_analysis.key_achievements:
            # Match achievements to items and update hours
            pass  # TODO: Implement more sophisticated matching

        return items

    async def _find_matches(
        self, commit_items: List[WorkItem], report_items: List[WorkItem]
    ) -> List[DeduplicationMatch]:
        """Find matches between commit and report work items using AI."""
        matches = []

        # For each report item, check against all commit items
        for report_item in report_items:
            for commit_item in commit_items:
                match = await self._check_similarity(commit_item, report_item)
                if match:
                    matches.append(match)

        # Sort by confidence score
        matches.sort(key=lambda x: x.confidence_score, reverse=True)

        # Remove duplicate matches (each item should only match once)
        used_commits = set()
        used_reports = set()
        filtered_matches = []

        for match in matches:
            if match.commit_item not in used_commits and match.report_item not in used_reports:
                filtered_matches.append(match)
                used_commits.add(match.commit_item)
                used_reports.add(match.report_item)

        return filtered_matches

    async def _check_similarity(self, commit_item: WorkItem, report_item: WorkItem) -> Optional[DeduplicationMatch]:
        """Check if two work items describe the same work using AI."""
        try:
            prompt = f"""
            Compare these two work descriptions and determine if they describe the same work:

            1. From git commit:
            {commit_item.description}

            2. From daily report:
            {report_item.description}

            Analyze whether these describe the same work activity. Consider:
            - Are they talking about the same feature, bug fix, or task?
            - Do they reference the same files, components, or functionality?
            - Is the daily report item a high-level description of the commit work?

            Respond with:
            - confidence_score: A number between 0 and 1 (1 being certain match)
            - is_match: true/false
            - explanation: Brief explanation of your reasoning

            Format as JSON.
            """

            # Use similarity API to compare items
            response = await self.ai_integration.analyze_semantic_similarity(
                commit_item.description, report_item.description
            )

            # Parse response
            if response and response.get("similarity_score", 0) is not None:
                confidence = float(response.get("similarity_score", 0))
                is_match = bool(response.get("is_duplicate", confidence >= 0.7))
                explanation = response.get("reasoning", "")
                if is_match and confidence > 0.5:
                    return DeduplicationMatch(
                        commit_item=commit_item,
                        report_item=report_item,
                        confidence_score=confidence,
                        explanation=explanation,
                    )

            return None

        except Exception as e:
            logger.error(f"Error checking similarity: {e}")
            return None

    async def generate_weekly_aggregate(self, user_id: str, week_start: datetime, week_end: datetime) -> Dict[str, Any]:
        """
        Generate a weekly aggregate of hours worked, combining commits and daily reports.

        Args:
            user_id: User to generate aggregate for
            week_start: Start of the week
            week_end: End of the week

        Returns:
            Dictionary containing weekly aggregate data
        """
        try:
            # Get all commits for the week
            commits = await self.commit_repo.get_commits_by_user_date_range(
                user_id=user_id, start_date=week_start, end_date=week_end
            )

            # Get all daily reports for the week
            from app.repositories.daily_report_repository import DailyReportRepository

            report_repo = DailyReportRepository()

            daily_aggregates = []
            current_date = week_start.date()
            week_end_date = week_end.date()

            total_commit_hours = 0
            total_additional_hours = 0
            total_dedup_count = 0

            while current_date <= week_end_date:
                # Get report for this day
                report = await report_repo.get_by_user_and_date(user_id, current_date)

                if report:
                    # Get commits for this specific day
                    day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                    day_end = day_start + timedelta(days=1)

                    day_commits = [c for c in commits if day_start <= c.commit_date < day_end]

                    # Run deduplication
                    dedup_results = await self.deduplicate_daily_report(report, day_commits)

                    daily_aggregates.append(
                        {
                            "date": current_date.isoformat(),
                            "commit_hours": dedup_results["commit_hours"],
                            "additional_hours": dedup_results["additional_hours"],
                            "total_hours": dedup_results["total_hours"],
                            "deduplication_count": dedup_results["deduplication_count"],
                        }
                    )

                    total_commit_hours += dedup_results["commit_hours"]
                    total_additional_hours += dedup_results["additional_hours"]
                    total_dedup_count += dedup_results["deduplication_count"]
                else:
                    # No report, just count commit hours
                    day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                    day_end = day_start + timedelta(days=1)

                    day_commits = [c for c in commits if day_start <= c.commit_date < day_end]
                    day_commit_hours = sum(
                        c.ai_analysis.get("estimated_hours", 0.5) if c.ai_analysis else 0.5 for c in day_commits
                    )

                    if day_commit_hours > 0:
                        daily_aggregates.append(
                            {
                                "date": current_date.isoformat(),
                                "commit_hours": day_commit_hours,
                                "additional_hours": 0,
                                "total_hours": day_commit_hours,
                                "deduplication_count": 0,
                            }
                        )
                        total_commit_hours += day_commit_hours

                current_date += timedelta(days=1)

            # Calculate work breakdown by analyzing all items
            work_breakdown = await self._calculate_work_breakdown(commits, week_start, week_end, user_id)

            return {
                "user_id": user_id,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "total_hours": total_commit_hours + total_additional_hours,
                "commit_hours": total_commit_hours,
                "additional_hours": total_additional_hours,
                "deduplication_count": total_dedup_count,
                "daily_breakdown": daily_aggregates,
                "work_breakdown": work_breakdown,
                "commit_count": len(commits),
                "average_daily_hours": (total_commit_hours + total_additional_hours) / 7,
            }

        except Exception as e:
            logger.error(f"Error generating weekly aggregate: {e}")
            raise

    async def _calculate_work_breakdown(
        self, commits: List[Commit], week_start: datetime, week_end: datetime, user_id: str
    ) -> Dict[str, float]:
        """Calculate breakdown of work by category."""
        breakdown = {
            "feature_development": 0,
            "bug_fixes": 0,
            "code_reviews": 0,
            "meetings": 0,
            "documentation": 0,
            "other": 0,
        }

        # Analyze commits
        for commit in commits:
            hours = commit.ai_analysis.get("estimated_hours", 0.5) if commit.ai_analysis else 0.5

            # Simple categorization based on commit message
            # Could be enhanced with AI
            message_lower = commit.commit_message.lower()

            if any(word in message_lower for word in ["fix", "bug", "issue", "error"]):
                breakdown["bug_fixes"] += hours
            elif any(word in message_lower for word in ["feat", "feature", "add", "implement"]):
                breakdown["feature_development"] += hours
            elif any(word in message_lower for word in ["doc", "readme", "comment"]):
                breakdown["documentation"] += hours
            else:
                breakdown["other"] += hours

        # Add daily report categories
        # This would analyze the daily reports for the week
        # For now, returning commit-based breakdown

        return breakdown
