"""
Simple unit tests for Unified Daily Analysis Service without full app initialization.
"""

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest


# Mock the models to avoid SQLAlchemy initialization issues
class MockDailyWorkAnalysis:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.user_id = kwargs.get("user_id")
        self.analysis_date = kwargs.get("analysis_date")
        self.total_productive_hours = kwargs.get("total_productive_hours", 0.0)
        self.commit_hours = kwargs.get("commit_hours", 0.0)
        self.additional_report_hours = kwargs.get("additional_report_hours", 0.0)
        self.meeting_hours = kwargs.get("meeting_hours", 0.0)
        self.work_items = kwargs.get("work_items", [])
        self.deduplicated_items = kwargs.get("deduplicated_items", [])
        self.work_categories = kwargs.get("work_categories", {})
        self.key_achievements = kwargs.get("key_achievements", [])
        self.challenges_faced = kwargs.get("challenges_faced", [])
        self.confidence_score = kwargs.get("confidence_score", 0.0)
        self.analysis_reasoning = kwargs.get("analysis_reasoning", "")
        self.raw_ai_response = kwargs.get("raw_ai_response", {})
        self.status = kwargs.get("status", "pending")


class MockCommit:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.user_id = kwargs.get("user_id")
        self.commit_hash = kwargs.get("commit_hash")
        self.repository = kwargs.get("repository")
        self.commit_message = kwargs.get("commit_message")
        self.commit_date = kwargs.get("commit_date")
        self.additions = kwargs.get("additions", 0)
        self.deletions = kwargs.get("deletions", 0)
        self.files_changed = kwargs.get("files_changed", [])
        self.ai_analysis = kwargs.get("ai_analysis", {})


class MockDailyReport:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.user_id = kwargs.get("user_id")
        self.report_date = kwargs.get("report_date")
        self.raw_text_input = kwargs.get("raw_text_input")
        self.ai_analysis = kwargs.get("ai_analysis", {})
        self.final_estimated_hours = kwargs.get("final_estimated_hours", 0.0)


class TestUnifiedAnalysisLogic:
    """Test the core logic of unified analysis without database dependencies."""

    def test_build_analysis_prompt_with_deduplication(self):
        """Test that the prompt includes proper deduplication instructions."""
        # Import the service
        with patch("app.services.unified_daily_analysis_service.AIIntegration"):
            with patch("app.services.unified_daily_analysis_service.CommitRepository"):
                with patch("app.services.unified_daily_analysis_service.DailyReportRepository"):
                    with patch("app.services.unified_daily_analysis_service.DailyWorkAnalysisRepository"):
                        from app.services.unified_daily_analysis_service import UnifiedDailyAnalysisService

                        service = UnifiedDailyAnalysisService()

                        # Create test data
                        commits = [
                            MockCommit(
                                commit_hash="abc123",
                                repository="myapp",
                                commit_message="Fix authentication bug",
                                commit_date=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
                                additions=50,
                                deletions=20,
                                files_changed=["auth.py", "tests/test_auth.py"],
                            ),
                            MockCommit(
                                commit_hash="def456",
                                repository="myapp",
                                commit_message="Add user profile feature",
                                commit_date=datetime(2024, 1, 15, 14, 45, tzinfo=timezone.utc),
                                additions=150,
                                deletions=10,
                                files_changed=["profile.py", "views.py"],
                            ),
                        ]

                        report = MockDailyReport(
                            raw_text_input="""
                            - Fixed the authentication bug that was preventing login
                            - Implemented new user profile feature
                            - Attended team standup meeting
                            - Reviewed code for payment integration
                            """
                        )

                        # Build prompt
                        prompt = service._build_analysis_prompt(
                            commits=commits, report=report, user_id=uuid4(), analysis_date=date(2024, 1, 15)
                        )

                        # Verify deduplication instructions
                        assert "DO NOT double-count these items" in prompt
                        assert "Identify overlaps and count each piece of work only once" in prompt
                        assert "If work appears in both commits AND report, count it ONLY ONCE" in prompt

                        # Verify both data sources are included
                        assert "Fix authentication bug" in prompt
                        assert "Fixed the authentication bug that was preventing login" in prompt
                        assert "2 commits" in prompt
                        assert "End of Day Report:" in prompt

    def test_parse_ai_response_validation(self):
        """Test AI response parsing and validation."""
        with patch("app.services.unified_daily_analysis_service.AIIntegration"):
            with patch("app.services.unified_daily_analysis_service.CommitRepository"):
                with patch("app.services.unified_daily_analysis_service.DailyReportRepository"):
                    with patch("app.services.unified_daily_analysis_service.DailyWorkAnalysisRepository"):
                        from app.services.unified_daily_analysis_service import UnifiedDailyAnalysisService

                        service = UnifiedDailyAnalysisService()

                        # Test with invalid hours
                        invalid_response = {
                            "total_productive_hours": 30.0,  # > 24
                            "commit_hours": 25.0,  # > 24
                            "additional_report_hours": 5.0,
                            "work_items": [],
                            "deduplicated_items": [],
                            "work_categories": {},
                            "key_achievements": [],
                            "challenges_faced": [],
                            "confidence_score": 1.5,  # > 1
                            "analysis_reasoning": "Test",
                        }

                        parsed = service._parse_ai_response(invalid_response)

                        # Verify validation
                        assert parsed["total_productive_hours"] == 24.0
                        assert parsed["commit_hours"] == 24.0
                        assert parsed["confidence_score"] == 1.0

                        # Test with missing fields
                        minimal_response = {
                            "total_productive_hours": 8.0,
                            "commit_hours": 6.0,
                            "additional_report_hours": 2.0,
                        }

                        parsed = service._parse_ai_response(minimal_response)

                        # Verify defaults are added
                        assert "work_items" in parsed
                        assert "deduplicated_items" in parsed
                        assert "work_categories" in parsed
                        assert parsed["confidence_score"] == 0.5  # default

    @pytest.mark.asyncio
    async def test_deduplication_in_ai_response(self):
        """Test that AI properly deduplicates work items."""
        with patch("app.services.unified_daily_analysis_service.AIIntegration") as mock_ai:
            with patch("app.services.unified_daily_analysis_service.CommitRepository") as mock_commit_repo:
                with patch("app.services.unified_daily_analysis_service.DailyReportRepository") as mock_report_repo:
                    with patch(
                        "app.services.unified_daily_analysis_service.DailyWorkAnalysisRepository"
                    ) as mock_analysis_repo:
                        from app.services.unified_daily_analysis_service import UnifiedDailyAnalysisService

                        service = UnifiedDailyAnalysisService()

                        # Setup mocks
                        user_id = uuid4()
                        analysis_date = date(2024, 1, 15)

                        # Mock no existing analysis
                        mock_analysis_repo.return_value.get_by_user_and_date = AsyncMock(return_value=None)

                        # Mock commits
                        commits = [
                            MockCommit(
                                commit_hash="abc123",
                                repository="myapp",
                                commit_message="Fix authentication bug",
                                commit_date=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
                                additions=50,
                                deletions=20,
                                files_changed=["auth.py"],
                            )
                        ]
                        mock_commit_repo.return_value.get_commits_by_user_date_range = AsyncMock(return_value=commits)

                        # Mock report
                        report = MockDailyReport(raw_text_input="Fixed the authentication bug and attended standup")
                        mock_report_repo.return_value.get_daily_reports_by_user_and_date = AsyncMock(
                            return_value=report
                        )

                        # Mock AI response with deduplication
                        ai_response = {
                            "total_productive_hours": 3.0,
                            "commit_hours": 2.5,
                            "additional_report_hours": 0.5,
                            "work_items": [
                                {
                                    "description": "Fixed authentication bug",
                                    "source": "both",
                                    "estimated_hours": 2.5,
                                    "category": "bug_fixes",
                                    "confidence": 0.95,
                                    "related_commits": ["abc123"],
                                    "related_report_text": "Fixed the authentication bug",
                                },
                                {
                                    "description": "Attended standup meeting",
                                    "source": "report",
                                    "estimated_hours": 0.5,
                                    "category": "meetings",
                                    "confidence": 1.0,
                                    "related_commits": [],
                                    "related_report_text": "attended standup",
                                },
                            ],
                            "deduplicated_items": [
                                {
                                    "commit_description": "Fix authentication bug",
                                    "report_description": "Fixed the authentication bug",
                                    "unified_description": "Fixed authentication bug",
                                    "hours_allocated": 2.5,
                                    "reasoning": "Both describe the same bug fix",
                                }
                            ],
                            "work_categories": {"bug_fixes": 2.5, "meetings": 0.5},
                            "key_achievements": ["Fixed critical authentication bug"],
                            "challenges_faced": [],
                            "confidence_score": 0.95,
                            "analysis_reasoning": "Identified authentication bug in both sources, allocated 2.5 hours once",
                        }

                        mock_ai.return_value.analyze_unified_daily_work = AsyncMock(return_value=ai_response)

                        # Mock creating analysis
                        created_analysis = MockDailyWorkAnalysis(
                            id=uuid4(),
                            user_id=user_id,
                            analysis_date=analysis_date,
                            total_productive_hours=3.0,
                            commit_hours=2.5,
                            additional_report_hours=0.5,
                            deduplicated_items=ai_response["deduplicated_items"],
                        )
                        mock_analysis_repo.return_value.create = AsyncMock(return_value=created_analysis)

                        # Execute
                        result = await service.analyze_daily_work(user_id, analysis_date)

                        # Verify deduplication occurred
                        assert result.total_productive_hours == 3.0  # Not 3.0 (2.5 + 0.5 from standup)
                        assert result.commit_hours == 2.5
                        assert result.additional_report_hours == 0.5
                        assert len(result.deduplicated_items) == 1
                        assert result.deduplicated_items[0]["reasoning"] == "Both describe the same bug fix"

    def test_prompt_includes_clarification(self):
        """Test that clarifications are included in the prompt when provided."""
        with patch("app.services.unified_daily_analysis_service.AIIntegration"):
            with patch("app.services.unified_daily_analysis_service.CommitRepository"):
                with patch("app.services.unified_daily_analysis_service.DailyReportRepository"):
                    with patch("app.services.unified_daily_analysis_service.DailyWorkAnalysisRepository"):
                        from app.services.unified_daily_analysis_service import UnifiedDailyAnalysisService

                        service = UnifiedDailyAnalysisService()

                        commits = []
                        report = MockDailyReport(raw_text_input="Worked on authentication system")

                        # Build prompt with clarification
                        prompt = service._build_analysis_prompt(
                            commits=commits,
                            report=report,
                            user_id=uuid4(),
                            analysis_date=date(2024, 1, 15),
                            clarification="The authentication work involved implementing OAuth2 with Google",
                        )

                        # Verify clarification is included
                        assert "CLARIFICATION PROVIDED" in prompt
                        assert "OAuth2 with Google" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
