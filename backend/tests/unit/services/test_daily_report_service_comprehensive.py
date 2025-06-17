"""
Comprehensive tests for Daily Report Service
"""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

from app.services.daily_report_service import DailyReportService
from app.models.daily_report import DailyReport, DailyReportCreate, DailyReportUpdate
from app.models.user import User, UserRole
from app.core.exceptions import ResourceNotFoundError, ValidationError, DuplicateResourceError


@pytest.fixture
def mock_daily_report_repo():
    return Mock()


@pytest.fixture
def mock_commit_repo():
    return Mock()


@pytest.fixture
def mock_ai_integration():
    return Mock()


@pytest.fixture
def mock_deduplication_service():
    return Mock()


@pytest.fixture
def daily_report_service(mock_daily_report_repo, mock_commit_repo, mock_ai_integration, mock_deduplication_service):
    service = DailyReportService()
    service.daily_report_repo = mock_daily_report_repo
    service.commit_repo = mock_commit_repo
    service.ai_integration = mock_ai_integration
    service.deduplication_service = mock_deduplication_service
    return service


@pytest.fixture
def sample_user():
    return User(
        id=uuid4(),
        email="developer@test.com",
        name="Test Developer",
        role=UserRole.DEVELOPER,
        is_active=True,
        slack_id="U123456"
    )


@pytest.fixture
def sample_daily_report():
    return DailyReport(
        id=uuid4(),
        user_id=uuid4(),
        date=datetime.now(timezone.utc).date(),
        content="Worked on feature X",
        key_achievements=["Completed feature X", "Fixed bug Y"],
        blockers=["Waiting for API documentation"],
        hours_worked=8.0,
        sentiment_score=0.8,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


class TestDailyReportService:
    """Test cases for DailyReportService"""

    @pytest.mark.asyncio
    async def test_create_daily_report_success(self, daily_report_service, mock_daily_report_repo, mock_ai_integration, sample_user):
        """Test successful daily report creation with AI analysis"""
        # Arrange
        report_data = DailyReportCreate(
            user_id=sample_user.id,
            date=datetime.now(timezone.utc).date(),
            content="Completed feature implementation and code review"
        )
        
        mock_daily_report_repo.get_by_user_and_date.return_value = None
        mock_daily_report_repo.create.return_value = DailyReport(
            **report_data.model_dump(),
            id=uuid4(),
            key_achievements=["Completed feature", "Code review"],
            blockers=[],
            hours_worked=6.5,
            sentiment_score=0.85,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        mock_ai_integration.analyze_daily_report.return_value = {
            "hours_worked": 6.5,
            "key_achievements": ["Completed feature", "Code review"],
            "blockers": [],
            "sentiment_score": 0.85,
            "needs_clarification": False
        }
        
        # Act
        result = await daily_report_service.create_daily_report(report_data)
        
        # Assert
        assert result.user_id == sample_user.id
        assert result.hours_worked == 6.5
        assert result.sentiment_score == 0.85
        assert len(result.key_achievements) == 2
        mock_ai_integration.analyze_daily_report.assert_called_once_with(report_data.content)
        mock_daily_report_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_daily_report_duplicate(self, daily_report_service, mock_daily_report_repo, sample_user, sample_daily_report):
        """Test duplicate daily report creation prevention"""
        # Arrange
        report_data = DailyReportCreate(
            user_id=sample_user.id,
            date=datetime.now(timezone.utc).date(),
            content="Another report"
        )
        
        mock_daily_report_repo.get_by_user_and_date.return_value = sample_daily_report
        
        # Act & Assert
        with pytest.raises(DuplicateResourceError) as exc:
            await daily_report_service.create_daily_report(report_data)
        
        assert "already exists" in str(exc.value)
        mock_daily_report_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_daily_report_with_clarification_needed(self, daily_report_service, mock_daily_report_repo, mock_ai_integration):
        """Test daily report creation when AI requests clarification"""
        # Arrange
        report_data = DailyReportCreate(
            user_id=uuid4(),
            date=datetime.now(timezone.utc).date(),
            content="Did some work"
        )
        
        mock_daily_report_repo.get_by_user_and_date.return_value = None
        mock_ai_integration.analyze_daily_report.return_value = {
            "hours_worked": None,
            "key_achievements": [],
            "blockers": [],
            "sentiment_score": 0.5,
            "needs_clarification": True,
            "clarification_questions": ["What specific tasks did you work on?", "How many hours did you work?"]
        }
        
        created_report = DailyReport(
            **report_data.model_dump(),
            id=uuid4(),
            needs_clarification=True,
            clarification_questions=["What specific tasks did you work on?", "How many hours did you work?"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        mock_daily_report_repo.create.return_value = created_report
        
        # Act
        result = await daily_report_service.create_daily_report(report_data)
        
        # Assert
        assert result.needs_clarification is True
        assert len(result.clarification_questions) == 2
        assert result.hours_worked is None

    @pytest.mark.asyncio
    async def test_update_daily_report_success(self, daily_report_service, mock_daily_report_repo, mock_ai_integration, sample_daily_report):
        """Test successful daily report update"""
        # Arrange
        update_data = DailyReportUpdate(
            content="Updated: Completed feature implementation, code review, and documentation"
        )
        
        mock_daily_report_repo.get_by_id.return_value = sample_daily_report
        mock_ai_integration.analyze_daily_report.return_value = {
            "hours_worked": 8.5,
            "key_achievements": ["Completed feature", "Code review", "Documentation"],
            "blockers": [],
            "sentiment_score": 0.9,
            "needs_clarification": False
        }
        
        updated_report = DailyReport(
            **sample_daily_report.model_dump(),
            content=update_data.content,
            hours_worked=8.5,
            sentiment_score=0.9,
            key_achievements=["Completed feature", "Code review", "Documentation"],
            updated_at=datetime.now(timezone.utc)
        )
        mock_daily_report_repo.update.return_value = updated_report
        
        # Act
        result = await daily_report_service.update_daily_report(sample_daily_report.id, update_data)
        
        # Assert
        assert result.hours_worked == 8.5
        assert len(result.key_achievements) == 3
        assert result.sentiment_score == 0.9

    @pytest.mark.asyncio
    async def test_get_user_reports_with_date_range(self, daily_report_service, mock_daily_report_repo, sample_user):
        """Test getting user reports within date range"""
        # Arrange
        start_date = datetime.now(timezone.utc).date() - timedelta(days=7)
        end_date = datetime.now(timezone.utc).date()
        
        reports = [
            DailyReport(
                id=uuid4(),
                user_id=sample_user.id,
                date=start_date + timedelta(days=i),
                content=f"Day {i} work",
                hours_worked=8.0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            for i in range(5)
        ]
        
        mock_daily_report_repo.get_by_user_date_range.return_value = reports
        
        # Act
        result = await daily_report_service.get_user_reports(
            user_id=sample_user.id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Assert
        assert len(result) == 5
        assert all(r.user_id == sample_user.id for r in result)
        mock_daily_report_repo.get_by_user_date_range.assert_called_once_with(
            user_id=sample_user.id,
            start_date=start_date,
            end_date=end_date
        )

    @pytest.mark.asyncio
    async def test_process_clarification_response(self, daily_report_service, mock_daily_report_repo, mock_ai_integration, sample_daily_report):
        """Test processing clarification response from user"""
        # Arrange
        sample_daily_report.needs_clarification = True
        sample_daily_report.clarification_questions = ["What specific tasks?"]
        sample_daily_report.conversation_history = [
            {"role": "assistant", "content": "What specific tasks did you work on?"}
        ]
        
        mock_daily_report_repo.get_by_id.return_value = sample_daily_report
        mock_ai_integration.process_clarification.return_value = {
            "hours_worked": 7.5,
            "key_achievements": ["Implemented user auth", "Fixed security bugs"],
            "blockers": ["Need code review"],
            "sentiment_score": 0.75,
            "needs_clarification": False
        }
        
        updated_report = DailyReport(
            **sample_daily_report.model_dump(),
            needs_clarification=False,
            hours_worked=7.5,
            key_achievements=["Implemented user auth", "Fixed security bugs"],
            blockers=["Need code review"],
            sentiment_score=0.75,
            conversation_history=[
                {"role": "assistant", "content": "What specific tasks did you work on?"},
                {"role": "user", "content": "I implemented user authentication and fixed security bugs"}
            ]
        )
        mock_daily_report_repo.update.return_value = updated_report
        
        # Act
        result = await daily_report_service.process_clarification_response(
            report_id=sample_daily_report.id,
            user_response="I implemented user authentication and fixed security bugs"
        )
        
        # Assert
        assert result.needs_clarification is False
        assert result.hours_worked == 7.5
        assert len(result.key_achievements) == 2
        assert len(result.conversation_history) == 2

    @pytest.mark.asyncio
    async def test_get_team_summary(self, daily_report_service, mock_daily_report_repo):
        """Test getting team summary for a specific date"""
        # Arrange
        report_date = datetime.now(timezone.utc).date()
        team_reports = [
            DailyReport(
                id=uuid4(),
                user_id=uuid4(),
                date=report_date,
                content=f"Developer {i} work",
                hours_worked=8.0,
                sentiment_score=0.8,
                key_achievements=[f"Task {i}"],
                blockers=[] if i % 2 == 0 else ["Blocker"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            for i in range(5)
        ]
        
        mock_daily_report_repo.get_team_reports_by_date.return_value = team_reports
        
        # Act
        result = await daily_report_service.get_team_summary(
            team_id=uuid4(),
            date=report_date
        )
        
        # Assert
        assert result["total_reports"] == 5
        assert result["total_hours"] == 40.0
        assert result["average_sentiment"] == 0.8
        assert result["reports_with_blockers"] == 2
        assert result["submission_rate"] > 0

    @pytest.mark.asyncio
    async def test_analyze_report_with_deduplication(self, daily_report_service, mock_deduplication_service, mock_commit_repo, sample_user):
        """Test report analysis with commit deduplication"""
        # Arrange
        report_date = datetime.now(timezone.utc).date()
        report = DailyReport(
            id=uuid4(),
            user_id=sample_user.id,
            date=report_date,
            content="Implemented feature X and fixed bug Y",
            hours_worked=8.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        commits = [
            Mock(
                id=uuid4(),
                user_id=sample_user.id,
                message="feat: implement feature X",
                estimated_hours=4.0,
                commit_date=datetime.now(timezone.utc)
            ),
            Mock(
                id=uuid4(),
                user_id=sample_user.id,
                message="fix: resolve bug Y",
                estimated_hours=2.0,
                commit_date=datetime.now(timezone.utc)
            )
        ]
        
        mock_commit_repo.get_commits_by_user_date_range.return_value = commits
        mock_deduplication_service.find_duplicates.return_value = {
            "deduplicated_hours": 6.0,
            "additional_hours": 2.0,
            "duplicates": [
                {
                    "commit_id": str(commits[0].id),
                    "confidence": 0.95,
                    "reason": "Feature X mentioned in both"
                }
            ]
        }
        
        # Act
        result = await daily_report_service.analyze_report_with_deduplication(report)
        
        # Assert
        assert result["total_hours"] == 8.0
        assert result["commit_hours"] == 6.0
        assert result["additional_hours"] == 2.0
        assert len(result["duplicates"]) == 1
        assert result["duplicates"][0]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_ai_analysis_error_handling(self, daily_report_service, mock_daily_report_repo, mock_ai_integration):
        """Test handling of AI analysis errors"""
        # Arrange
        report_data = DailyReportCreate(
            user_id=uuid4(),
            date=datetime.now(timezone.utc).date(),
            content="Test content"
        )
        
        mock_daily_report_repo.get_by_user_and_date.return_value = None
        mock_ai_integration.analyze_daily_report.side_effect = Exception("AI service unavailable")
        
        # Create report without AI analysis
        created_report = DailyReport(
            **report_data.model_dump(),
            id=uuid4(),
            hours_worked=None,
            key_achievements=[],
            blockers=[],
            sentiment_score=None,
            ai_analysis_error="AI service unavailable",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        mock_daily_report_repo.create.return_value = created_report
        
        # Act
        result = await daily_report_service.create_daily_report(report_data)
        
        # Assert
        assert result.hours_worked is None
        assert result.ai_analysis_error == "AI service unavailable"
        assert len(result.key_achievements) == 0