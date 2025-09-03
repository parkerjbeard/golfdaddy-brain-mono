"""
Simple tests for the Unified Daily Analysis Service.
Tests the current implementation functionality.
"""

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from app.models.commit import Commit
from app.models.daily_commit_analysis import DailyCommitAnalysis, DailyCommitAnalysisCreate
from app.models.daily_report import AiAnalysis, DailyReport
from app.services.unified_daily_analysis_service import UnifiedDailyAnalysisService


class TestUnifiedDailyAnalysisServiceSimple:
    """Simple test suite for UnifiedDailyAnalysisService."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked dependencies."""
        service = UnifiedDailyAnalysisService()
        service.ai_integration = AsyncMock()
        service.commit_repo = AsyncMock()
        service.daily_report_repo = AsyncMock()
        service.analysis_repo = AsyncMock()
        service.user_repo = AsyncMock()
        return service

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing."""
        return uuid4()

    @pytest.fixture
    def sample_date(self):
        """Sample date for testing."""
        return date(2024, 1, 15)

    @pytest.mark.asyncio
    async def test_analyze_daily_work_no_existing_analysis(self, service, sample_user_id, sample_date):
        """Test analyzing daily work when no existing analysis exists, creates zero-hour analysis."""
        # Setup mocks for zero-hour scenario
        service.analysis_repo.get_by_user_and_date.return_value = None
        service.commit_repo.get_commits_by_user_date_range.return_value = []
        service.daily_report_repo.get_daily_reports_by_user_and_date.return_value = None

        # Mock the zero-hour analysis creation
        expected_analysis = DailyCommitAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_estimated_hours=Decimal("0.0"),
            commit_count=0,
            daily_report_id=None,
            analysis_type="automatic",
            ai_analysis={},
            complexity_score=None,
            seniority_score=None,
            repositories_analyzed=[],
            total_lines_added=0,
            total_lines_deleted=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        service.analysis_repo.create.return_value = expected_analysis

        # Execute
        result = await service.analyze_daily_work(sample_user_id, sample_date)

        # Verify zero-hour analysis was created
        assert result == expected_analysis
        assert result.total_estimated_hours == Decimal("0.0")
        assert result.commit_count == 0
        service.analysis_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_daily_work_existing_analysis(self, service, sample_user_id, sample_date):
        """Test that existing analysis is returned without reprocessing."""
        existing_analysis = DailyCommitAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_estimated_hours=Decimal("8.0"),
            commit_count=5,
            daily_report_id=None,
            analysis_type="automatic",
            ai_analysis={"test": "data"},
            complexity_score=7,
            seniority_score=8,
            repositories_analyzed=["repo1"],
            total_lines_added=100,
            total_lines_deleted=50,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        service.analysis_repo.get_by_user_and_date.return_value = existing_analysis

        # Execute
        result = await service.analyze_daily_work(sample_user_id, sample_date)

        # Verify
        assert result == existing_analysis
        # Should not create new analysis
        service.analysis_repo.create.assert_not_called()
        service.ai_integration.analyze_daily_work.assert_not_called()
