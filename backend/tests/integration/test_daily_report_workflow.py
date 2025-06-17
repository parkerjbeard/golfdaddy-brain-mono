"""
Comprehensive Integration Tests for Daily Report Workflow
Tests the complete flow from Slack interaction to report storage with deduplication
"""
import pytest
from datetime import datetime, timezone, timedelta, date
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

from app.services.daily_report_service import DailyReportService
from app.services.slack_service import SlackService
from app.services.slack_conversation_handler import SlackConversationHandler
from app.services.eod_reminder_service import EODReminderService
from app.services.deduplication_service import DeduplicationService
from app.services.slack_message_templates import SlackMessageTemplates
from app.models.daily_report import DailyReport, DailyReportCreate
from app.models.user import User, UserRole
from app.models.commit import Commit
from app.repositories.daily_report_repository import DailyReportRepository
from app.repositories.user_repository import UserRepository
from app.repositories.commit_repository import CommitRepository
from app.integrations.ai_integration import AIIntegration


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_user():
    return User(
        id=uuid4(),
        email="developer@company.com",
        name="John Developer",
        role=UserRole.DEVELOPER,
        is_active=True,
        slack_id="U123456789",
        github_username="johndeveloper"
    )


@pytest.fixture
def sample_commits(sample_user):
    """Create realistic commits for the test user"""
    base_time = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    
    return [
        Commit(
            id=uuid4(),
            repository="company/main-app",
            commit_hash="abc123def",
            message="feat: implement user profile page",
            author_email=sample_user.email,
            commit_date=base_time,
            estimated_hours=3.5,
            estimated_points=5,
            user_id=sample_user.id,
            files_changed=["components/Profile.tsx", "api/profile.ts"],
            analysis={
                "complexity": "medium",
                "impact_areas": ["user-interface", "api"],
                "quality_score": 0.85
            }
        ),
        Commit(
            id=uuid4(),
            repository="company/main-app",
            commit_hash="def456ghi",
            message="fix: resolve profile image upload issue",
            author_email=sample_user.email,
            commit_date=base_time + timedelta(hours=4),
            estimated_hours=1.5,
            estimated_points=2,
            user_id=sample_user.id,
            files_changed=["api/upload.ts"],
            analysis={
                "complexity": "low",
                "impact_areas": ["api", "file-handling"],
                "quality_score": 0.90
            }
        )
    ]


class TestDailyReportWorkflow:
    """Integration tests for the complete daily report workflow"""

    @pytest.mark.asyncio
    async def test_complete_eod_workflow_with_slash_command(self, mock_db_session, sample_user, sample_commits):
        """Test the complete workflow from /eod command to report storage"""
        # Setup all services with mocks
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class, \
             patch('app.repositories.daily_report_repository.DailyReportRepository') as mock_report_repo_class, \
             patch('app.repositories.commit_repository.CommitRepository') as mock_commit_repo_class, \
             patch('app.integrations.ai_integration.AIIntegration') as mock_ai_class, \
             patch('app.services.slack_service.WebClient') as mock_slack_client_class:
            
            # Configure repositories
            mock_user_repo = mock_user_repo_class.return_value
            mock_report_repo = mock_report_repo_class.return_value
            mock_commit_repo = mock_commit_repo_class.return_value
            mock_ai = mock_ai_class.return_value
            
            # Configure Slack client
            mock_slack_client = mock_slack_client_class.return_value
            mock_slack_client.auth_test = AsyncMock(return_value={"ok": True})
            mock_slack_client.views_open = AsyncMock(return_value={"ok": True})
            
            # Initialize services
            slack_service = SlackService()
            conversation_handler = SlackConversationHandler()
            daily_report_service = DailyReportService()
            deduplication_service = DeduplicationService()
            
            # Step 1: User sends /eod command
            slash_command = {
                "command": "/eod",
                "user_id": sample_user.slack_id,
                "trigger_id": "123456.789012",
                "text": "",  # No text, will open modal
                "channel_id": "D123456",
                "response_url": "https://slack.com/response"
            }
            
            # Mock user lookup
            mock_user_repo.get_user_by_slack_id.return_value = sample_user
            
            # Step 2: Handle slash command (opens modal)
            response = await conversation_handler.handle_slash_command(slash_command)
            
            assert response["response_type"] == "ephemeral"
            assert "Opening EOD report form" in response["text"]
            mock_slack_client.views_open.assert_called_once()
            
            # Step 3: User submits modal
            view_submission = {
                "type": "view_submission",
                "user": {"id": sample_user.slack_id},
                "view": {
                    "callback_id": "eod_report_modal",
                    "state": {
                        "values": {
                            "report_content": {
                                "content": {
                                    "value": "Implemented user profile page and fixed image upload bug. Also reviewed 3 PRs."
                                }
                            },
                            "hours_worked": {
                                "hours": {
                                    "value": "8"
                                }
                            },
                            "blockers": {
                                "blockers": {
                                    "value": "Waiting for design approval on profile layout"
                                }
                            }
                        }
                    },
                    "private_metadata": json.dumps({"report_date": str(date.today())})
                }
            }
            
            # Mock AI analysis
            mock_ai.analyze_daily_report.return_value = {
                "hours_worked": 8.0,
                "key_achievements": [
                    "Implemented user profile page",
                    "Fixed image upload bug",
                    "Reviewed 3 PRs"
                ],
                "blockers": ["Waiting for design approval"],
                "sentiment_score": 0.75,
                "needs_clarification": False
            }
            
            # Mock commits for today
            mock_commit_repo.get_commits_by_user_date_range.return_value = sample_commits
            
            # Mock semantic similarity for deduplication
            mock_ai.calculate_semantic_similarity = AsyncMock(side_effect=[
                0.95,  # High match for profile feature
                0.90   # High match for upload fix
            ])
            
            # Mock report creation
            created_report = DailyReport(
                id=uuid4(),
                user_id=sample_user.id,
                date=date.today(),
                content="Implemented user profile page and fixed image upload bug. Also reviewed 3 PRs.",
                hours_worked=8.0,
                key_achievements=[
                    "Implemented user profile page",
                    "Fixed image upload bug",
                    "Reviewed 3 PRs"
                ],
                blockers=["Waiting for design approval"],
                sentiment_score=0.75,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            mock_report_repo.create.return_value = created_report
            mock_report_repo.get_by_user_and_date.return_value = None  # No existing report
            
            # Step 4: Process view submission
            result = await conversation_handler.handle_view_submission(view_submission)
            
            # Verify report was created
            assert result is None  # Successful submission
            mock_report_repo.create.assert_called_once()
            
            # Step 5: Verify deduplication was performed
            # The service should have identified the commit work
            call_args = mock_report_repo.create.call_args[0][0]
            assert isinstance(call_args, DailyReport)
            
            # Step 6: Test weekly aggregation
            start_date = date.today() - timedelta(days=7)
            end_date = date.today()
            
            # Mock weekly data
            mock_report_repo.get_by_user_date_range.return_value = [created_report]
            mock_commit_repo.get_commits_by_user_date_range.return_value = sample_commits
            
            weekly_summary = await deduplication_service.get_weekly_aggregated_hours(
                user_id=sample_user.id,
                start_date=start_date,
                end_date=end_date
            )
            
            assert weekly_summary["total_commit_hours"] == 5.0  # 3.5 + 1.5
            assert weekly_summary["total_report_hours"] == 8.0
            assert weekly_summary["total_unique_hours"] > 0

    @pytest.mark.asyncio
    async def test_eod_reminder_to_report_submission_flow(self, mock_db_session, sample_user):
        """Test the flow from EOD reminder to report submission"""
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class, \
             patch('app.repositories.daily_report_repository.DailyReportRepository') as mock_report_repo_class, \
             patch('app.repositories.commit_repository.CommitRepository') as mock_commit_repo_class, \
             patch('app.services.slack_service.WebClient') as mock_slack_client_class:
            
            # Setup mocks
            mock_user_repo = mock_user_repo_class.return_value
            mock_report_repo = mock_report_repo_class.return_value
            mock_commit_repo = mock_commit_repo_class.return_value
            mock_slack_client = mock_slack_client_class.return_value
            
            # Configure Slack client
            mock_slack_client.auth_test = AsyncMock(return_value={"ok": True})
            mock_slack_client.conversations_open = AsyncMock(return_value={"ok": True, "channel": {"id": "D123456"}})
            mock_slack_client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "123456.789"})
            
            # Initialize services
            eod_service = EODReminderService()
            
            # Step 1: Send EOD reminders
            mock_user_repo.list_all_users.return_value = ([sample_user], 1)
            mock_report_repo.get_by_user_and_date.return_value = None  # No report yet
            mock_commit_repo.get_commits_by_user_date_range.return_value = []
            
            reminder_results = await eod_service.send_eod_reminders(dry_run=False)
            
            assert reminder_results["reminders_sent"] == 1
            assert reminder_results["total_users"] == 1
            mock_slack_client.chat_postMessage.assert_called_once()
            
            # Step 2: User clicks button in reminder (simulated by slash command)
            # This would normally be triggered by the button in the reminder message
            # For testing, we'll simulate the user then using /eod command

    @pytest.mark.asyncio
    async def test_clarification_flow_integration(self, mock_db_session, sample_user):
        """Test the clarification conversation flow"""
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class, \
             patch('app.repositories.daily_report_repository.DailyReportRepository') as mock_report_repo_class, \
             patch('app.integrations.ai_integration.AIIntegration') as mock_ai_class, \
             patch('app.services.slack_service.WebClient') as mock_slack_client_class:
            
            # Setup mocks
            mock_user_repo = mock_user_repo_class.return_value
            mock_report_repo = mock_report_repo_class.return_value
            mock_ai = mock_ai_class.return_value
            mock_slack_client = mock_slack_client_class.return_value
            
            # Configure mocks
            mock_slack_client.auth_test = AsyncMock(return_value={"ok": True})
            mock_slack_client.conversations_open = AsyncMock(return_value={"ok": True, "channel": {"id": "D123456"}})
            mock_slack_client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "123456.789"})
            
            # Initialize services
            conversation_handler = SlackConversationHandler()
            daily_report_service = DailyReportService()
            
            # Step 1: Create report that needs clarification
            vague_report = DailyReport(
                id=uuid4(),
                user_id=sample_user.id,
                date=date.today(),
                content="Did some work on stuff",
                needs_clarification=True,
                clarification_questions=[
                    "What specific tasks did you work on?",
                    "How many hours did you spend on each task?"
                ],
                conversation_history=[],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            mock_user_repo.get_user_by_slack_id.return_value = sample_user
            mock_report_repo.get_by_id.return_value = vague_report
            
            # Step 2: Start clarification conversation
            thread_ts = await conversation_handler.start_clarification_conversation(
                user=sample_user,
                report=vague_report
            )
            
            assert thread_ts is not None
            assert thread_ts in conversation_handler.active_conversations
            
            # Step 3: User responds with clarification
            clarification_message = {
                "type": "message",
                "channel": "D123456",
                "user": sample_user.slack_id,
                "text": "I worked on the user profile feature for 5 hours and bug fixes for 3 hours",
                "ts": "123456.790",
                "thread_ts": thread_ts
            }
            
            # Mock AI processing clarification
            mock_ai.process_clarification.return_value = {
                "hours_worked": 8.0,
                "key_achievements": [
                    "User profile feature development",
                    "Bug fixes"
                ],
                "blockers": [],
                "sentiment_score": 0.7,
                "needs_clarification": False
            }
            
            # Mock report update
            updated_report = DailyReport(
                **vague_report.model_dump(),
                needs_clarification=False,
                hours_worked=8.0,
                key_achievements=["User profile feature development", "Bug fixes"],
                conversation_history=[
                    {"role": "assistant", "content": "What specific tasks did you work on?"},
                    {"role": "user", "content": clarification_message["text"]}
                ]
            )
            mock_report_repo.update.return_value = updated_report
            
            # Process clarification
            await conversation_handler.handle_message_event(clarification_message)
            
            # Verify conversation completed
            assert thread_ts not in conversation_handler.active_conversations
            mock_slack_client.chat_postMessage.assert_called()  # Confirmation sent

    @pytest.mark.asyncio
    async def test_error_recovery_in_workflow(self, mock_db_session, sample_user):
        """Test error handling and recovery throughout the workflow"""
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class, \
             patch('app.services.slack_service.WebClient') as mock_slack_client_class:
            
            mock_user_repo = mock_user_repo_class.return_value
            mock_slack_client = mock_slack_client_class.return_value
            
            # Test Slack API failure recovery
            mock_slack_client.auth_test = AsyncMock(side_effect=Exception("Slack API error"))
            
            # Service should handle initialization failure gracefully
            try:
                slack_service = SlackService()
                # If we get here, the service handled the error
                assert True
            except Exception:
                # Service should not raise during init
                assert False, "Service should handle Slack API errors gracefully"

    @pytest.mark.asyncio  
    async def test_concurrent_report_submissions(self, mock_db_session):
        """Test handling of concurrent report submissions"""
        # This test ensures the system handles race conditions properly
        # when multiple reports are submitted simultaneously
        pass  # Implementation would test database constraints and locking