"""
Comprehensive tests for EOD Reminder Service
"""
import pytest
from datetime import datetime, time, timedelta, timezone, date
from zoneinfo import ZoneInfo
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.services.eod_reminder_service import EODReminderService, send_daily_eod_reminders
from app.models.user import User, UserRole
from app.models.daily_report import DailyReport
from app.models.commit import Commit


@pytest.fixture
def mock_user_repo():
    return Mock()


@pytest.fixture
def mock_commit_repo():
    return Mock()


@pytest.fixture
def mock_slack_service():
    return Mock()


@pytest.fixture
def mock_slack_templates():
    return Mock()


@pytest.fixture
def mock_daily_report_repo():
    return Mock()


@pytest.fixture
def eod_reminder_service(mock_user_repo, mock_commit_repo, mock_slack_service, mock_slack_templates):
    service = EODReminderService()
    service.user_repo = mock_user_repo
    service.commit_repo = mock_commit_repo
    service.slack_service = mock_slack_service
    service.templates = mock_slack_templates
    return service


@pytest.fixture
def sample_users():
    return [
        User(
            id=uuid4(),
            email="dev1@test.com",
            name="Developer One",
            role=UserRole.DEVELOPER,
            is_active=True,
            slack_id="U123456"
        ),
        User(
            id=uuid4(),
            email="dev2@test.com",
            name="Developer Two",
            role=UserRole.DEVELOPER,
            is_active=True,
            slack_id="U234567"
        ),
        User(
            id=uuid4(),
            email="inactive@test.com",
            name="Inactive User",
            role=UserRole.DEVELOPER,
            is_active=False,
            slack_id="U345678"
        ),
        User(
            id=uuid4(),
            email="no-slack@test.com",
            name="No Slack User",
            role=UserRole.DEVELOPER,
            is_active=True,
            slack_id=None
        )
    ]


@pytest.fixture
def sample_commits():
    base_time = datetime.now(timezone.utc)
    return [
        Commit(
            id=uuid4(),
            repository="test/repo",
            commit_hash="abc123",
            message="feat: implement new feature",
            author_email="dev1@test.com",
            commit_date=base_time - timedelta(hours=2),
            estimated_hours=2.5,
            estimated_points=3,
            user_id=uuid4()
        ),
        Commit(
            id=uuid4(),
            repository="test/repo",
            commit_hash="def456",
            message="fix: resolve critical bug",
            author_email="dev1@test.com",
            commit_date=base_time - timedelta(hours=1),
            estimated_hours=1.5,
            estimated_points=2,
            user_id=uuid4()
        )
    ]


class TestEODReminderService:
    """Test cases for EODReminderService"""

    @pytest.mark.asyncio
    async def test_send_eod_reminders_success(self, eod_reminder_service, mock_user_repo, mock_daily_report_repo, mock_commit_repo, mock_slack_service, mock_slack_templates, sample_users, sample_commits):
        """Test successful sending of EOD reminders"""
        # Arrange
        with patch('app.repositories.daily_report_repository.DailyReportRepository') as mock_repo_class:
            mock_repo_instance = Mock()
            mock_repo_class.return_value = mock_repo_instance
            
            # Only active users with Slack IDs
            active_users = [u for u in sample_users if u.is_active and u.slack_id]
            mock_user_repo.list_all_users.return_value = (active_users, len(active_users))
            
            # First user has already submitted report
            mock_repo_instance.get_by_user_and_date.side_effect = [
                DailyReport(id=uuid4(), user_id=active_users[0].id, date=date.today()),  # User 1 already submitted
                None  # User 2 hasn't submitted
            ]
            
            # User 2 has commits today
            mock_commit_repo.get_commits_by_user_date_range.return_value = sample_commits
            
            # Mock Slack message template
            mock_slack_templates.eod_reminder.return_value = {
                "text": "Time for your EOD report!",
                "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "EOD reminder"}}]
            }
            
            # Mock Slack DM opening and sending
            mock_slack_service.open_dm.return_value = "D123456"
            mock_slack_service.send_message = AsyncMock()
            
            # Act
            result = await eod_reminder_service.send_eod_reminders(dry_run=False)
            
            # Assert
            assert result["total_users"] == 2
            assert result["reminders_sent"] == 1  # Only one user needs reminder
            assert len(result["skipped"]) == 1  # One user already submitted
            assert result["skipped"][0]["reason"] == "already_submitted"
            assert len(result["errors"]) == 0
            
            # Verify Slack interactions
            mock_slack_service.open_dm.assert_called_once_with("U234567")
            mock_slack_service.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_eod_reminders_dry_run(self, eod_reminder_service, mock_user_repo, mock_daily_report_repo, sample_users):
        """Test EOD reminders in dry run mode"""
        # Arrange
        with patch('app.repositories.daily_report_repository.DailyReportRepository') as mock_repo_class:
            mock_repo_instance = Mock()
            mock_repo_class.return_value = mock_repo_instance
            
            active_users = [u for u in sample_users if u.is_active and u.slack_id]
            mock_user_repo.list_all_users.return_value = (active_users, len(active_users))
            mock_repo_instance.get_by_user_and_date.return_value = None
            
            # Act
            result = await eod_reminder_service.send_eod_reminders(dry_run=True)
            
            # Assert
            assert result["reminders_sent"] == 2  # Both users would get reminders
            assert len(result["errors"]) == 0
            # Verify no actual Slack messages sent
            eod_reminder_service.slack_service.open_dm.assert_not_called()
            eod_reminder_service.slack_service.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_eod_reminders_with_errors(self, eod_reminder_service, mock_user_repo, mock_slack_service, sample_users):
        """Test EOD reminders with Slack DM failures"""
        # Arrange
        with patch('app.repositories.daily_report_repository.DailyReportRepository') as mock_repo_class:
            mock_repo_instance = Mock()
            mock_repo_class.return_value = mock_repo_instance
            
            active_users = [u for u in sample_users if u.is_active and u.slack_id]
            mock_user_repo.list_all_users.return_value = (active_users, len(active_users))
            mock_repo_instance.get_by_user_and_date.return_value = None
            
            # Mock Slack DM opening failure
            mock_slack_service.open_dm.return_value = None
            
            # Act
            result = await eod_reminder_service.send_eod_reminders(dry_run=False)
            
            # Assert
            assert result["reminders_sent"] == 0
            assert len(result["errors"]) == 2
            assert all(e["error"] == "failed_to_open_dm" for e in result["errors"])

    @pytest.mark.asyncio
    async def test_schedule_user_reminder_success(self, eod_reminder_service, mock_commit_repo, mock_slack_service, mock_slack_templates, sample_users):
        """Test scheduling a reminder for a specific user"""
        # Arrange
        user = sample_users[0]
        reminder_time = time(17, 30)  # 5:30 PM
        timezone_str = "America/New_York"
        
        # Mock commits for context
        mock_commit_repo.get_commits_by_user_date_range.return_value = sample_commits
        
        # Mock template
        mock_slack_templates.eod_reminder.return_value = {
            "text": "EOD reminder",
            "blocks": []
        }
        
        # Mock Slack operations
        mock_slack_service.open_dm.return_value = "D123456"
        mock_slack_service.schedule_message = AsyncMock(return_value="scheduled_123")
        
        # Act
        with patch('app.services.eod_reminder_service.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=ZoneInfo(timezone_str))
            mock_datetime.now.return_value = mock_now
            
            result = await eod_reminder_service.schedule_user_reminder(
                user=user,
                reminder_time=reminder_time,
                timezone_str=timezone_str
            )
        
        # Assert
        assert result == "scheduled_123"
        mock_slack_service.open_dm.assert_called_once_with(user.slack_id)
        mock_slack_service.schedule_message.assert_called_once()
        
        # Verify scheduled time is correct (should be same day at 5:30 PM)
        call_args = mock_slack_service.schedule_message.call_args[1]
        scheduled_timestamp = call_args["post_at"]
        scheduled_dt = datetime.fromtimestamp(scheduled_timestamp, tz=ZoneInfo(timezone_str))
        assert scheduled_dt.hour == 17
        assert scheduled_dt.minute == 30

    @pytest.mark.asyncio
    async def test_schedule_user_reminder_next_day(self, eod_reminder_service, mock_commit_repo, mock_slack_service, mock_slack_templates, sample_users):
        """Test scheduling reminder for next day when time has passed"""
        # Arrange
        user = sample_users[0]
        reminder_time = time(17, 0)  # 5:00 PM
        
        mock_commit_repo.get_commits_by_user_date_range.return_value = []
        mock_slack_templates.eod_reminder.return_value = {"text": "EOD", "blocks": []}
        mock_slack_service.open_dm.return_value = "D123456"
        mock_slack_service.schedule_message = AsyncMock(return_value="scheduled_456")
        
        # Act - Current time is 6 PM, so should schedule for tomorrow
        with patch('app.services.eod_reminder_service.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 18, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
            mock_datetime.now.return_value = mock_now
            
            result = await eod_reminder_service.schedule_user_reminder(user=user)
        
        # Assert
        assert result == "scheduled_456"
        call_args = mock_slack_service.schedule_message.call_args[1]
        scheduled_timestamp = call_args["post_at"]
        scheduled_dt = datetime.fromtimestamp(scheduled_timestamp, tz=ZoneInfo("America/Los_Angeles"))
        
        # Should be scheduled for tomorrow at 5 PM
        assert scheduled_dt.day == 16
        assert scheduled_dt.hour == 17

    @pytest.mark.asyncio
    async def test_schedule_user_reminder_no_slack_id(self, eod_reminder_service, sample_users):
        """Test scheduling reminder for user without Slack ID"""
        # Arrange
        user = sample_users[3]  # User without Slack ID
        
        # Act
        result = await eod_reminder_service.schedule_user_reminder(user=user)
        
        # Assert
        assert result is None
        eod_reminder_service.slack_service.open_dm.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_preferences_default(self, eod_reminder_service, mock_user_repo, sample_users):
        """Test getting default user preferences"""
        # Arrange
        user = sample_users[0]
        user.preferences = None
        mock_user_repo.get_user_by_id.return_value = user
        
        # Act
        result = await eod_reminder_service.get_user_preferences(str(user.id))
        
        # Assert
        assert result["reminder_enabled"] is True
        assert result["reminder_time"] == "17:00"
        assert result["timezone"] == "America/Los_Angeles"
        assert result["include_commit_summary"] is True

    @pytest.mark.asyncio
    async def test_get_user_preferences_custom(self, eod_reminder_service, mock_user_repo, sample_users):
        """Test getting custom user preferences"""
        # Arrange
        user = sample_users[0]
        user.preferences = {
            "eod_reminder": {
                "reminder_enabled": False,
                "reminder_time": "18:30",
                "timezone": "Europe/London",
                "include_commit_summary": False
            }
        }
        mock_user_repo.get_user_by_id.return_value = user
        
        # Act
        result = await eod_reminder_service.get_user_preferences(str(user.id))
        
        # Assert
        assert result["reminder_enabled"] is False
        assert result["reminder_time"] == "18:30"
        assert result["timezone"] == "Europe/London"
        assert result["include_commit_summary"] is False

    @pytest.mark.asyncio
    async def test_send_daily_eod_reminders_task(self):
        """Test the daily EOD reminder task function"""
        # Arrange
        with patch('app.services.eod_reminder_service.EODReminderService') as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            mock_service.send_eod_reminders = AsyncMock(return_value={
                "reminders_sent": 10,
                "errors": ["error1", "error2"]
            })
            
            # Act
            result = await send_daily_eod_reminders()
            
            # Assert
            assert result["reminders_sent"] == 10
            assert len(result["errors"]) == 2
            mock_service.send_eod_reminders.assert_called_once()

    @pytest.mark.asyncio
    async def test_reminder_with_commit_context(self, eod_reminder_service, mock_commit_repo, mock_slack_templates, sample_commits):
        """Test reminder includes commit context when available"""
        # Arrange
        user = User(
            id=uuid4(),
            email="test@example.com",
            name="Test User",
            slack_id="U123456",
            is_active=True
        )
        
        mock_commit_repo.get_commits_by_user_date_range.return_value = sample_commits
        
        # Act
        with patch('app.services.eod_reminder_service.datetime') as mock_datetime:
            mock_now = datetime.now(ZoneInfo("America/Los_Angeles"))
            mock_datetime.now.return_value = mock_now
            
            # Trigger template generation through schedule_user_reminder
            eod_reminder_service.slack_service.open_dm.return_value = "D123"
            await eod_reminder_service.schedule_user_reminder(user)
        
        # Assert
        template_call = mock_slack_templates.eod_reminder.call_args
        assert template_call[1]["today_commits_count"] == 2
        assert template_call[1]["last_commit_time"] == sample_commits[1].commit_date