"""
Comprehensive tests for the Unified Daily Analysis Service.
Tests the integration of EOD reports and commits with AI-powered deduplication.
"""

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import AIIntegrationError, DatabaseError
from app.models.commit import Commit
from app.models.daily_commit_analysis import DailyCommitAnalysis, DailyCommitAnalysisCreate
from app.models.daily_report import AiAnalysis, DailyReport
from app.models.daily_work_analysis import DailyWorkAnalysis
from app.services.unified_daily_analysis_service import UnifiedDailyAnalysisService


class TestUnifiedDailyAnalysisService:
    """Test suite for UnifiedDailyAnalysisService."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked dependencies."""
        service = UnifiedDailyAnalysisService()
        # Mock dependencies of the delegate since logic is delegated
        service._delegate.repository = AsyncMock()
        service._delegate.commit_repo = AsyncMock()
        service._delegate.daily_report_repo = AsyncMock()
        service._delegate.user_repo = AsyncMock()
        service._delegate.ai_integration = AsyncMock()

        # Setup user repo to return a mock user (needed for context building)
        mock_user = Mock()
        mock_user.name = "Test User"
        service._delegate.user_repo.get_by_id.return_value = mock_user

        # Alias service attributes to delegate attributes so tests continue to work
        service.ai_integration = service._delegate.ai_integration
        service.commit_repo = service._delegate.commit_repo
        service.report_repo = service._delegate.daily_report_repo
        service.analysis_repo = service._delegate.repository
        
        return service

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing."""
        return uuid4()

    @pytest.fixture
    def sample_date(self):
        """Sample date for testing."""
        return date(2024, 1, 15)

    @pytest.fixture
    def sample_commits(self, sample_user_id):
        """Create sample commits for testing."""
        return [
            Commit(
                id=uuid4(),
                author_id=sample_user_id,
                commit_hash="abc123",
                repository_name="myapp",
                commit_message="Fix user authentication bug",
                author_github_username="john-doe",
                author_email="john@example.com",
                commit_timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
                lines_added=50,
                lines_deleted=20,
                changed_files=["auth.py", "tests/test_auth.py"],
                ai_estimated_hours=Decimal("2.5"),
                complexity_score=6,
                created_at=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
            ),
            Commit(
                id=uuid4(),
                author_id=sample_user_id,
                commit_hash="def456",
                repository_name="myapp",
                commit_message="Add user profile feature",
                author_github_username="john-doe",
                author_email="john@example.com",
                commit_timestamp=datetime(2024, 1, 15, 14, 45, tzinfo=timezone.utc),
                lines_added=150,
                lines_deleted=10,
                changed_files=["profile.py", "views.py", "templates/profile.html"],
                ai_estimated_hours=Decimal("3.5"),
                complexity_score=7,
                created_at=datetime(2024, 1, 15, 14, 45, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 15, 14, 45, tzinfo=timezone.utc),
            ),
        ]

    @pytest.fixture
    def sample_daily_report(self, sample_user_id):
        """Create sample daily report for testing."""
        return DailyReport(
            id=uuid4(),
            user_id=sample_user_id,
            report_date=datetime(2024, 1, 15, 17, 0, tzinfo=timezone.utc),
            raw_text_input="""
            Today I worked on:
            - Fixed the authentication bug that was preventing users from logging in
            - Implemented the new user profile feature with avatar uploads
            - Attended standup meeting and discussed sprint goals
            - Code review for teammate's PR on payment integration
            """,
            ai_analysis=AiAnalysis(
                estimated_hours=8.0,
                difficulty_level="medium",
                key_achievements=[
                    "Fixed authentication bug",
                    "Implemented user profile feature",
                    "Attended standup meeting",
                    "Code review",
                ],
                blockers_challenges=[],
                sentiment_score=0.8,
            ),
            final_estimated_hours=8.0,
        )

    @pytest.fixture
    def sample_ai_response(self):
        """Create sample AI response for unified analysis."""
        return {
            "total_productive_hours": 7.5,
            "commit_hours": 6.0,
            "additional_report_hours": 1.5,
            "work_items": [
                {
                    "description": "Fixed user authentication bug preventing login",
                    "source": "both",
                    "estimated_hours": 2.5,
                    "category": "bug_fixes",
                    "confidence": 0.9,
                    "related_commits": ["abc123"],
                    "related_report_text": "Fixed the authentication bug",
                },
                {
                    "description": "Implemented user profile feature with avatar uploads",
                    "source": "both",
                    "estimated_hours": 3.5,
                    "category": "feature_development",
                    "confidence": 0.95,
                    "related_commits": ["def456"],
                    "related_report_text": "Implemented the new user profile feature",
                },
                {
                    "description": "Attended standup meeting and discussed sprint goals",
                    "source": "report",
                    "estimated_hours": 0.5,
                    "category": "meetings",
                    "confidence": 1.0,
                    "related_commits": [],
                    "related_report_text": "Attended standup meeting",
                },
                {
                    "description": "Code review for payment integration PR",
                    "source": "report",
                    "estimated_hours": 1.0,
                    "category": "code_review",
                    "confidence": 1.0,
                    "related_commits": [],
                    "related_report_text": "Code review for teammate's PR",
                },
            ],
            "deduplicated_items": [
                {
                    "commit_description": "Fix user authentication bug",
                    "report_description": "Fixed the authentication bug that was preventing users from logging in",
                    "unified_description": "Fixed user authentication bug preventing login",
                    "hours_allocated": 2.5,
                    "reasoning": "Both describe fixing the same authentication issue",
                },
                {
                    "commit_description": "Add user profile feature",
                    "report_description": "Implemented the new user profile feature with avatar uploads",
                    "unified_description": "Implemented user profile feature with avatar uploads",
                    "hours_allocated": 3.5,
                    "reasoning": "Both describe implementing the user profile feature",
                },
            ],
            "work_categories": {
                "feature_development": 3.5,
                "bug_fixes": 2.5,
                "code_review": 1.0,
                "meetings": 0.5,
                "documentation": 0.0,
                "devops": 0.0,
                "other": 0.0,
            },
            "key_achievements": [
                "Fixed critical authentication bug",
                "Launched user profile feature",
                "Contributed to team code quality through reviews",
            ],
            "challenges_faced": [],
            "confidence_score": 0.92,
            "analysis_reasoning": "Identified 2 work items appearing in both commits and report. Allocated 6 hours to commit work and 1.5 hours to additional report items (meetings and code review).",
        }

    @pytest.mark.asyncio
    async def test_analyze_daily_work_with_commits_and_report(
        self, service, sample_user_id, sample_date, sample_commits, sample_daily_report, sample_ai_response
    ):
        """Test analyzing daily work with both commits and report."""
        # Setup mocks
        service.analysis_repo.get_by_user_and_date.return_value = None
        service.commit_repo.get_commits_by_user_in_range.return_value = sample_commits
        service.report_repo.get_daily_reports_by_user_and_date.return_value = sample_daily_report
        service.ai_integration.analyze_daily_work.return_value = sample_ai_response

        expected_analysis = DailyWorkAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=7.5,
            commit_hours=6.0,
            additional_report_hours=1.5,
            meeting_hours=0.5,
            work_items=sample_ai_response["work_items"],
            deduplicated_items=sample_ai_response["deduplicated_items"],
            work_categories=sample_ai_response["work_categories"],
            key_achievements=sample_ai_response["key_achievements"],
            challenges_faced=[],
            confidence_score=0.92,
            analysis_reasoning=sample_ai_response["analysis_reasoning"],
            raw_ai_response=sample_ai_response,
            status="completed",
        )
        service.analysis_repo.create.return_value = expected_analysis

        # Execute
        result = await service.analyze_daily_work(sample_user_id, sample_date)

        # Verify
        assert result == expected_analysis

        # Verify AI was called with proper prompt
        ai_call_args = service.ai_integration.analyze_daily_work.call_args
        prompt = ai_call_args[0][0]

        # Check prompt contains key elements
        assert "DO NOT double-count" in prompt
        assert "Fix user authentication bug" in prompt
        assert "Add user profile feature" in prompt
        assert "Fixed the authentication bug" in prompt
        assert "2 commits" in prompt

        # Verify repository calls
        service.commit_repo.get_commits_by_user_in_range.assert_called_once()
        service.report_repo.get_daily_reports_by_user_and_date.assert_called_once()
        service.analysis_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_daily_work_commits_only(self, service, sample_user_id, sample_date, sample_commits):
        """Test analyzing daily work with only commits (no report)."""
        # Setup mocks
        service.analysis_repo.get_by_user_and_date.return_value = None
        service.commit_repo.get_commits_by_user_in_range.return_value = sample_commits
        service.report_repo.get_daily_reports_by_user_and_date.return_value = None

        ai_response = {
            "total_productive_hours": 6.0,
            "commit_hours": 6.0,
            "additional_report_hours": 0.0,
            "work_items": [
                {
                    "description": "Fix user authentication bug",
                    "source": "commit",
                    "estimated_hours": 2.5,
                    "category": "bug_fixes",
                    "confidence": 0.9,
                    "related_commits": ["abc123"],
                },
                {
                    "description": "Add user profile feature",
                    "source": "commit",
                    "estimated_hours": 3.5,
                    "category": "feature_development",
                    "confidence": 0.9,
                    "related_commits": ["def456"],
                },
            ],
            "deduplicated_items": [],
            "work_categories": {
                "feature_development": 3.5,
                "bug_fixes": 2.5,
                "code_review": 0.0,
                "meetings": 0.0,
                "documentation": 0.0,
                "devops": 0.0,
                "other": 0.0,
            },
            "key_achievements": ["Fixed authentication bug", "Implemented user profile feature"],
            "challenges_faced": [],
            "confidence_score": 0.9,
            "analysis_reasoning": "Analysis based on commits only. No daily report available.",
        }
        service.ai_integration.analyze_daily_work.return_value = ai_response

        expected_analysis = DailyWorkAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=6.0,
            commit_hours=6.0,
            additional_report_hours=0.0,
            meeting_hours=0.0,
            work_items=ai_response["work_items"],
            deduplicated_items=[],
            work_categories=ai_response["work_categories"],
            key_achievements=ai_response["key_achievements"],
            challenges_faced=[],
            confidence_score=0.9,
            analysis_reasoning=ai_response["analysis_reasoning"],
            raw_ai_response=ai_response,
            status="completed",
        )
        service.analysis_repo.create.return_value = expected_analysis

        # Execute
        result = await service.analyze_daily_work(sample_user_id, sample_date)

        # Verify
        assert result == expected_analysis
        assert result.additional_report_hours == 0.0
        assert len(result.deduplicated_items) == 0

    @pytest.mark.asyncio
    async def test_analyze_daily_work_report_only(self, service, sample_user_id, sample_date, sample_daily_report):
        """Test analyzing daily work with only report (no commits)."""
        # Setup mocks
        service.analysis_repo.get_by_user_and_date.return_value = None
        service.commit_repo.get_commits_by_user_in_range.return_value = []
        service.report_repo.get_daily_reports_by_user_and_date.return_value = sample_daily_report

        ai_response = {
            "total_productive_hours": 8.0,
            "commit_hours": 0.0,
            "additional_report_hours": 8.0,
            "work_items": [
                {
                    "description": "Fixed authentication bug",
                    "source": "report",
                    "estimated_hours": 3.0,
                    "category": "bug_fixes",
                    "confidence": 0.8,
                    "related_report_text": "Fixed the authentication bug",
                },
                {
                    "description": "Implemented user profile feature",
                    "source": "report",
                    "estimated_hours": 3.5,
                    "category": "feature_development",
                    "confidence": 0.8,
                    "related_report_text": "Implemented the new user profile feature",
                },
                {
                    "description": "Attended standup meeting",
                    "source": "report",
                    "estimated_hours": 0.5,
                    "category": "meetings",
                    "confidence": 1.0,
                    "related_report_text": "Attended standup meeting",
                },
                {
                    "description": "Code review for payment integration",
                    "source": "report",
                    "estimated_hours": 1.0,
                    "category": "code_review",
                    "confidence": 1.0,
                    "related_report_text": "Code review for teammate's PR",
                },
            ],
            "deduplicated_items": [],
            "work_categories": {
                "feature_development": 3.5,
                "bug_fixes": 3.0,
                "code_review": 1.0,
                "meetings": 0.5,
                "documentation": 0.0,
                "devops": 0.0,
                "other": 0.0,
            },
            "key_achievements": sample_daily_report.ai_analysis.key_achievements,
            "challenges_faced": [],
            "confidence_score": 0.85,
            "analysis_reasoning": "Analysis based on daily report only. No commits found.",
        }
        service.ai_integration.analyze_daily_work.return_value = ai_response

        expected_analysis = DailyWorkAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=8.0,
            commit_hours=0.0,
            additional_report_hours=8.0,
            meeting_hours=0.5,
            work_items=ai_response["work_items"],
            deduplicated_items=[],
            work_categories=ai_response["work_categories"],
            key_achievements=ai_response["key_achievements"],
            challenges_faced=[],
            confidence_score=0.85,
            analysis_reasoning=ai_response["analysis_reasoning"],
            raw_ai_response=ai_response,
            status="completed",
        )
        service.analysis_repo.create.return_value = expected_analysis

        # Execute
        result = await service.analyze_daily_work(sample_user_id, sample_date)

        # Verify
        assert result == expected_analysis
        assert result.commit_hours == 0.0
        assert result.additional_report_hours == 8.0

    @pytest.mark.asyncio
    async def test_analyze_daily_work_no_activity(self, service, sample_user_id, sample_date):
        """Test analyzing daily work with no commits or report."""
        # Setup mocks
        service.analysis_repo.get_by_user_and_date.return_value = None
        service.commit_repo.get_commits_by_user_in_range.return_value = []
        service.report_repo.get_daily_reports_by_user_and_date.return_value = None

        # Execute
        result = await service.analyze_daily_work(sample_user_id, sample_date)

        # Verify zero-hour analysis was created
        assert result.total_productive_hours == 0.0
        assert result.commit_hours == 0.0
        assert result.additional_report_hours == 0.0
        assert result.status == "completed"
        assert len(result.work_items) == 0
        assert len(result.deduplicated_items) == 0

        # AI should not be called for zero activity
        service.ai_integration.analyze_daily_work.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_daily_work_existing_analysis(self, service, sample_user_id, sample_date):
        """Test that existing analysis is returned without reprocessing."""
        # Setup existing analysis
        existing_analysis = DailyWorkAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=7.0,
            commit_hours=5.0,
            additional_report_hours=2.0,
            status="completed",
        )
        service.analysis_repo.get_by_user_and_date.return_value = existing_analysis

        # Execute without force
        result = await service.analyze_daily_work(sample_user_id, sample_date)

        # Verify
        assert result == existing_analysis

        # No other methods should be called
        service.commit_repo.get_commits_by_user_in_range.assert_not_called()
        service.report_repo.get_daily_reports_by_user_and_date.assert_not_called()
        service.ai_integration.analyze_daily_work.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_daily_work_force_reanalysis(
        self, service, sample_user_id, sample_date, sample_commits, sample_daily_report, sample_ai_response
    ):
        """Test force reanalysis overwrites existing analysis."""
        # Setup existing analysis
        existing_analysis = DailyWorkAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=5.0,
            commit_hours=5.0,
            additional_report_hours=0.0,
            status="completed",
        )
        service.analysis_repo.get_by_user_and_date.return_value = existing_analysis
        service.commit_repo.get_commits_by_user_in_range.return_value = sample_commits
        service.report_repo.get_daily_reports_by_user_and_date.return_value = sample_daily_report
        service.ai_integration.analyze_daily_work.return_value = sample_ai_response

        new_analysis = DailyWorkAnalysis(
            id=existing_analysis.id,
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=7.5,
            commit_hours=6.0,
            additional_report_hours=1.5,
            status="completed",
        )
        service.analysis_repo.update.return_value = new_analysis

        # Execute with force
        result = await service.analyze_daily_work(sample_user_id, sample_date, force_reanalysis=True)

        # Verify update was called
        service.analysis_repo.update.assert_called_once()
        assert result.total_productive_hours == 7.5

    @pytest.mark.asyncio
    async def test_parse_ai_response_validation(self, service):
        """Test AI response parsing and validation."""
        # Test with invalid hours (>24)
        invalid_response = {
            "total_productive_hours": 30.0,  # Invalid
            "commit_hours": 25.0,  # Invalid
            "additional_report_hours": 5.0,
            "work_items": [],
            "deduplicated_items": [],
            "work_categories": {},
            "key_achievements": [],
            "challenges_faced": [],
            "confidence_score": 1.5,  # Invalid (>1)
            "analysis_reasoning": "Test",
        }

        parsed = service._parse_ai_response(invalid_response)

        # Verify validation
        assert parsed["total_productive_hours"] == 24.0  # Capped at 24
        assert parsed["commit_hours"] == 24.0  # Capped at 24
        assert parsed["confidence_score"] == 1.0  # Capped at 1

    @pytest.mark.asyncio
    async def test_ai_error_handling(self, service, sample_user_id, sample_date, sample_commits, sample_daily_report):
        """Test handling of AI integration errors."""
        # Setup mocks
        service.analysis_repo.get_by_user_and_date.return_value = None
        service.commit_repo.get_commits_by_user_in_range.return_value = sample_commits
        service.report_repo.get_daily_reports_by_user_and_date.return_value = sample_daily_report

        # Simulate AI error
        service.ai_integration.analyze_daily_work.side_effect = AIIntegrationError("OpenAI API error")

        # Execute and expect error
        with pytest.raises(AIIntegrationError):
            await service.analyze_daily_work(sample_user_id, sample_date)

    @pytest.mark.asyncio
    async def test_get_weekly_aggregate(self, service, sample_user_id):
        """Test weekly aggregate calculation."""
        week_start = date(2024, 1, 15)  # Monday

        # Create sample analyses for the week
        daily_analyses = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            hours = 8.0 if i < 5 else 0.0  # Work Mon-Fri

            analysis = DailyWorkAnalysis(
                id=uuid4(),
                user_id=sample_user_id,
                analysis_date=day,
                total_productive_hours=hours,
                commit_hours=hours * 0.75,
                additional_report_hours=hours * 0.25,
                meeting_hours=0.5 if hours > 0 else 0.0,
                work_categories=(
                    {
                        "feature_development": hours * 0.5,
                        "bug_fixes": hours * 0.3,
                        "meetings": hours * 0.1,
                        "code_review": hours * 0.1,
                    }
                    if hours > 0
                    else {}
                ),
                confidence_score=0.9,
                status="completed",
            )
            daily_analyses.append(analysis)

        service.analysis_repo.get_analyses_for_date_range.return_value = daily_analyses

        # Execute
        result = await service.get_weekly_aggregate(sample_user_id, week_start)

        # Verify
        assert result["total_hours"] == 40.0
        assert result["working_days"] == 5
        assert result["average_hours_per_day"] == 8.0
        assert result["most_productive_day"] == "Monday"
        assert result["least_productive_day"] == "Saturday"
        assert len(result["daily_breakdown"]) == 7

        # Verify category totals
        categories = result["category_totals"]
        assert categories["feature_development"] == 20.0  # 5 days * 8 hours * 0.5
        assert categories["bug_fixes"] == 12.0  # 5 days * 8 hours * 0.3

    @pytest.mark.asyncio
    async def test_handle_clarification_needed(self, service, sample_user_id, sample_date):
        """Test handling when AI needs clarification."""
        analysis_id = uuid4()
        clarification_request = "Please provide more details about the authentication bug fix."

        existing_analysis = DailyWorkAnalysis(
            id=analysis_id,
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=0.0,
            status="pending_clarification",
        )

        updated_analysis = DailyWorkAnalysis(
            id=analysis_id,
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=0.0,
            status="pending_clarification",
            pending_clarification=clarification_request,
        )

        service.analysis_repo.update.return_value = updated_analysis

        # Execute
        result = await service.handle_clarification_needed(existing_analysis.id, clarification_request)

        # Verify
        assert result == updated_analysis
        service.analysis_repo.update.assert_called_once_with(
            analysis_id, {"status": "pending_clarification", "pending_clarification": clarification_request}
        )

    @pytest.mark.asyncio
    async def test_provide_clarification(
        self, service, sample_user_id, sample_date, sample_commits, sample_daily_report, sample_ai_response
    ):
        """Test providing clarification and re-running analysis."""
        analysis_id = uuid4()

        # Setup pending analysis
        pending_analysis = DailyWorkAnalysis(
            id=analysis_id,
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=0.0,
            status="pending_clarification",
            pending_clarification="Please provide more details about the bug fix.",
        )

        service.analysis_repo.get_by_id.return_value = pending_analysis
        service.commit_repo.get_commits_by_user_in_range.return_value = sample_commits
        service.report_repo.get_daily_reports_by_user_and_date.return_value = sample_daily_report

        # Update AI response based on clarification
        service.ai_integration.analyze_daily_work.return_value = sample_ai_response

        updated_analysis = DailyWorkAnalysis(
            id=analysis_id,
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_productive_hours=7.5,
            commit_hours=6.0,
            additional_report_hours=1.5,
            status="completed",
        )
        service.analysis_repo.update.return_value = updated_analysis

        # Execute
        clarification = "The authentication bug was related to JWT token expiration handling."
        result = await service.provide_clarification(analysis_id, clarification)

        # Verify
        assert result == updated_analysis
        assert result.status == "completed"

        # Verify AI was called with clarification in prompt
        ai_call_args = service.ai_integration.analyze_daily_work.call_args
        prompt = ai_call_args[0][0]
        assert "JWT token expiration" in prompt
        assert "CLARIFICATION PROVIDED" in prompt

    @pytest.mark.asyncio
    async def test_deduplication_in_prompt(
        self, service, sample_user_id, sample_date, sample_commits, sample_daily_report
    ):
        """Test that deduplication instructions are properly included in prompt."""
        # Setup
        service.analysis_repo.get_by_user_and_date.return_value = None
        service.commit_repo.get_commits_by_user_in_range.return_value = sample_commits
        service.report_repo.get_daily_reports_by_user_and_date.return_value = sample_daily_report
        service.ai_integration.analyze_daily_work.return_value = {
            "total_productive_hours": 7.5,
            "commit_hours": 6.0,
            "additional_report_hours": 1.5,
            "work_items": [],
            "deduplicated_items": [],
            "work_categories": {},
            "key_achievements": [],
            "challenges_faced": [],
            "confidence_score": 0.9,
            "analysis_reasoning": "Test",
        }

        # Execute
        await service.analyze_daily_work(sample_user_id, sample_date)

        # Get the prompt that was sent to AI
        ai_call_args = service.ai_integration.analyze_unified_daily_work.call_args
        prompt = ai_call_args[0][0]

        # Verify deduplication instructions
        assert "DO NOT double-count these items" in prompt
        assert "Identify overlaps and count each piece of work only once" in prompt
        assert "If an item appears in both, merge them into a single work item" in prompt
        assert "If work appears in both commits AND report, count it ONLY ONCE" in prompt

        # Verify both data sources are included
        assert "Git Commits for the day:" in prompt
        assert "End of Day Report:" in prompt
        assert "Fix user authentication bug" in prompt  # From commits
        assert "Fixed the authentication bug that was preventing users from logging in" in prompt  # From report
