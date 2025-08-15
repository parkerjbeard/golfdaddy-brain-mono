from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from app.models.commit import Commit
from app.models.daily_commit_analysis import DailyCommitAnalysis, DailyCommitAnalysisCreate
from app.models.daily_report import DailyReport
from app.services.daily_commit_analysis_service import DailyCommitAnalysisService


@pytest.fixture
def mock_dependencies():
    """Mock all dependencies for DailyCommitAnalysisService"""
    with patch.multiple(
        "app.services.daily_commit_analysis_service",
        DailyCommitAnalysisRepository=Mock,
        CommitRepository=Mock,
        DailyReportRepository=Mock,
        UserRepository=Mock,
        AIIntegration=Mock,
    ) as mocks:
        yield mocks


@pytest.fixture
def service(mock_dependencies):
    """Create service instance with mocked dependencies"""
    service = DailyCommitAnalysisService()

    # Setup mocks
    service.repository = Mock()
    service.commit_repo = Mock()
    service.daily_report_repo = Mock()
    service.user_repo = Mock()
    service.ai_integration = Mock()

    return service


@pytest.fixture
def sample_user_id():
    return uuid4()


@pytest.fixture
def sample_date():
    return date(2025, 1, 15)


@pytest.fixture
def sample_commits():
    """Sample commits for testing"""
    user_id = uuid4()
    return [
        Commit(
            id=uuid4(),
            commit_hash="abc123",
            commit_message="Add new feature",
            author_id=user_id,
            repository="test/repo",
            additions=50,
            deletions=10,
            ai_estimated_hours=Decimal("2.5"),
            commit_timestamp=datetime(2025, 1, 15, 10, 30),
        ),
        Commit(
            id=uuid4(),
            commit_hash="def456",
            commit_message="Fix bug in feature",
            author_id=user_id,
            repository="test/repo",
            additions=25,
            deletions=5,
            ai_estimated_hours=Decimal("1.0"),
            commit_timestamp=datetime(2025, 1, 15, 14, 30),
        ),
    ]


@pytest.fixture
def sample_daily_report():
    """Sample daily report for testing"""
    return DailyReport(
        id=uuid4(),
        user_id=uuid4(),
        summary="Worked on new feature and bug fixes",
        additional_hours=Decimal("0.5"),
        report_date=date(2025, 1, 15),
    )


@pytest.fixture
def sample_ai_analysis():
    """Sample AI analysis result"""
    return {
        "total_estimated_hours": 4.2,
        "average_complexity_score": 6,
        "average_seniority_score": 7,
        "work_summary": "Implemented new feature with comprehensive testing and bug fixes",
        "key_achievements": [
            "Added new authentication feature",
            "Fixed critical performance bug",
            "Improved test coverage",
        ],
        "hour_estimation_reasoning": "Based on file complexity and code review requirements",
        "consistency_with_report": True,
        "recommendations": ["Consider adding more unit tests", "Document new API endpoints"],
    }


@pytest.mark.asyncio
async def test_analyze_for_report_new_analysis(
    service, sample_user_id, sample_date, sample_commits, sample_daily_report, sample_ai_analysis
):
    """Test analyzing commits when daily report is submitted (new analysis)"""

    # Setup mocks
    service.repository.get_by_user_and_date.return_value = None  # No existing analysis
    service._get_user_commits_for_date = AsyncMock(return_value=sample_commits)
    service._prepare_analysis_context = AsyncMock(return_value={"mock": "context"})
    service.ai_integration.analyze_daily_work = AsyncMock(return_value=sample_ai_analysis)
    service.repository.create = AsyncMock(
        return_value=DailyCommitAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_estimated_hours=Decimal("4.2"),
            commit_count=2,
            daily_report_id=sample_daily_report.id,
            analysis_type="with_report",
            ai_analysis=sample_ai_analysis,
        )
    )
    service._link_commits_to_analysis = AsyncMock()

    # Execute
    result = await service.analyze_for_report(sample_user_id, sample_date, sample_daily_report)

    # Verify
    assert result is not None
    assert result.total_estimated_hours == Decimal("4.2")
    assert result.analysis_type == "with_report"
    assert result.daily_report_id == sample_daily_report.id

    # Verify method calls
    service.repository.get_by_user_and_date.assert_called_once_with(sample_user_id, sample_date)
    service.ai_integration.analyze_daily_work.assert_called_once()
    service.repository.create.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_for_report_existing_analysis(service, sample_user_id, sample_date, sample_daily_report):
    """Test analyzing commits when analysis already exists"""

    existing_analysis = DailyCommitAnalysis(
        id=uuid4(),
        user_id=sample_user_id,
        analysis_date=sample_date,
        total_estimated_hours=Decimal("3.0"),
        commit_count=1,
        daily_report_id=None,
        analysis_type="automatic",
        ai_analysis={},
    )

    updated_analysis = DailyCommitAnalysis(
        id=existing_analysis.id,
        user_id=sample_user_id,
        analysis_date=sample_date,
        total_estimated_hours=Decimal("3.0"),
        commit_count=1,
        daily_report_id=sample_daily_report.id,
        analysis_type="automatic",
        ai_analysis={},
    )

    # Setup mocks
    service.repository.get_by_user_and_date.return_value = existing_analysis
    service.repository.update = AsyncMock(return_value=updated_analysis)

    # Execute
    result = await service.analyze_for_report(sample_user_id, sample_date, sample_daily_report)

    # Verify
    assert result == updated_analysis
    assert result.daily_report_id == sample_daily_report.id

    # Verify update was called, not create
    service.repository.update.assert_called_once()
    service.repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_for_report_no_commits(service, sample_user_id, sample_date, sample_daily_report):
    """Test analyzing when no commits exist for the date"""

    # Setup mocks
    service.repository.get_by_user_and_date.return_value = None
    service._get_user_commits_for_date = AsyncMock(return_value=[])
    service._create_zero_hour_analysis = AsyncMock(
        return_value=DailyCommitAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_estimated_hours=Decimal("0.0"),
            commit_count=0,
            daily_report_id=sample_daily_report.id,
            analysis_type="with_report",
            ai_analysis={"message": "No commits found for this date"},
        )
    )

    # Execute
    result = await service.analyze_for_report(sample_user_id, sample_date, sample_daily_report)

    # Verify
    assert result is not None
    assert result.total_estimated_hours == Decimal("0.0")
    assert result.commit_count == 0

    # Verify zero-hour analysis was created
    service._create_zero_hour_analysis.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_for_date_automatic(service, sample_user_id, sample_date, sample_commits, sample_ai_analysis):
    """Test automatic analysis for a date without daily report"""

    # Setup mocks
    service.repository.get_by_user_and_date.return_value = None
    service.daily_report_repo.get_user_report_for_date.return_value = None
    service._get_user_commits_for_date = AsyncMock(return_value=sample_commits)
    service._prepare_analysis_context = AsyncMock(return_value={"mock": "context"})
    service.ai_integration.analyze_daily_work = AsyncMock(return_value=sample_ai_analysis)
    service.repository.create = AsyncMock(
        return_value=DailyCommitAnalysis(
            id=uuid4(),
            user_id=sample_user_id,
            analysis_date=sample_date,
            total_estimated_hours=Decimal("4.2"),
            commit_count=2,
            daily_report_id=None,
            analysis_type="automatic",
            ai_analysis=sample_ai_analysis,
        )
    )
    service._link_commits_to_analysis = AsyncMock()

    # Execute
    result = await service.analyze_for_date(sample_user_id, sample_date)

    # Verify
    assert result is not None
    assert result.analysis_type == "automatic"
    assert result.daily_report_id is None

    # Verify daily report check was made
    service.daily_report_repo.get_user_report_for_date.assert_called_once()


@pytest.mark.asyncio
async def test_run_midnight_analysis(service):
    """Test midnight analysis batch process"""

    user_ids = [uuid4(), uuid4(), uuid4()]
    yesterday = date.today() - timedelta(days=1)

    # Setup mocks
    service.repository.get_users_without_analysis.return_value = user_ids
    service.analyze_for_date = AsyncMock(
        side_effect=[
            Mock(total_estimated_hours=Decimal("4.0")),  # Success
            Mock(total_estimated_hours=Decimal("2.5")),  # Success
            Exception("Analysis failed"),  # Failure
        ]
    )

    # Execute
    result = await service.run_midnight_analysis()

    # Verify
    assert result["analyzed"] == 2
    assert result["failed"] == 1

    # Verify all users were processed
    assert service.analyze_for_date.call_count == 3


@pytest.mark.asyncio
async def test_prepare_analysis_context(service, sample_commits, sample_daily_report, sample_user_id, sample_date):
    """Test context preparation for AI analysis"""

    # Setup mock user
    mock_user = Mock()
    mock_user.name = "John Doe"
    service.user_repo.get_by_id.return_value = mock_user

    # Execute
    context = await service._prepare_analysis_context(sample_commits, sample_daily_report, sample_user_id, sample_date)

    # Verify context structure
    assert context["analysis_date"] == sample_date.isoformat()
    assert context["user_name"] == "John Doe"
    assert context["total_commits"] == 2
    assert "commits" in context
    assert "daily_report" in context
    assert "repositories" in context

    # Verify commit summaries
    assert len(context["commits"]) == 2
    assert context["commits"][0]["message"] == "Add new feature"
    assert context["commits"][1]["message"] == "Fix bug in feature"

    # Verify daily report context
    assert context["daily_report"]["summary"] == sample_daily_report.summary


@pytest.mark.asyncio
async def test_get_user_analysis_history(service, sample_user_id):
    """Test retrieving analysis history for a user"""

    start_date = date(2025, 1, 1)
    end_date = date(2025, 1, 31)

    mock_analyses = [Mock(analysis_date=date(2025, 1, 15)), Mock(analysis_date=date(2025, 1, 10))]

    service.repository.get_user_analyses_in_range.return_value = mock_analyses

    # Execute
    result = await service.get_user_analysis_history(sample_user_id, start_date, end_date)

    # Verify
    assert result == mock_analyses
    service.repository.get_user_analyses_in_range.assert_called_once_with(sample_user_id, start_date, end_date)


def test_init_service():
    """Test service initialization"""
    with patch.multiple(
        "app.services.daily_commit_analysis_service",
        DailyCommitAnalysisRepository=Mock,
        CommitRepository=Mock,
        DailyReportRepository=Mock,
        UserRepository=Mock,
        AIIntegration=Mock,
    ):
        service = DailyCommitAnalysisService()

        # Verify all repositories and services are initialized
        assert service.repository is not None
        assert service.commit_repo is not None
        assert service.daily_report_repo is not None
        assert service.user_repo is not None
        assert service.ai_integration is not None
