"""
Integration tests for the Unified Daily Analysis system.
Tests the full flow from EOD report submission through AI analysis and storage.
"""
import pytest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
import json

from app.services.unified_daily_analysis_service import UnifiedDailyAnalysisService
from app.services.slack_conversation_handler import SlackConversationHandler
from app.models.daily_work_analysis import DailyWorkAnalysis
from app.models.user import User
from app.models.commit import Commit
from app.models.daily_report import DailyReport, DailyReportCreate
from app.repositories.daily_work_analysis_repository import DailyWorkAnalysisRepository
from app.repositories.commit_repository import CommitRepository
from app.repositories.daily_report_repository import DailyReportRepository


class TestUnifiedAnalysisIntegration:
    """Integration tests for the unified analysis system."""
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client."""
        client = MagicMock()
        
        # Mock table operations
        client.table.return_value = client
        client.select.return_value = client
        client.insert.return_value = client
        client.update.return_value = client
        client.delete.return_value = client
        client.eq.return_value = client
        client.gte.return_value = client
        client.lte.return_value = client
        client.order.return_value = client
        client.limit.return_value = client
        client.single.return_value = client
        
        return client
    
    @pytest.fixture
    def sample_user(self):
        """Create a sample user for testing."""
        return User(
            id=uuid4(),
            email="john.doe@example.com",
            name="John Doe",
            slack_id="U123456",
            github_username="johndoe",
            is_active=True,
            preferences={"timezone": "America/Los_Angeles"}
        )
    
    @pytest.fixture
    async def mock_ai_response(self):
        """Mock OpenAI response for unified analysis."""
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "total_productive_hours": 8.0,
                        "commit_hours": 5.5,
                        "additional_report_hours": 2.5,
                        "work_items": [
                            {
                                "description": "Implemented user authentication system with OAuth",
                                "source": "both",
                                "estimated_hours": 4.0,
                                "category": "feature_development",
                                "confidence": 0.95,
                                "related_commits": ["abc123", "def456"],
                                "related_report_text": "Worked on authentication system"
                            },
                            {
                                "description": "Fixed critical bug in payment processing",
                                "source": "commit",
                                "estimated_hours": 1.5,
                                "category": "bug_fixes",
                                "confidence": 0.9,
                                "related_commits": ["ghi789"],
                                "related_report_text": None
                            },
                            {
                                "description": "Daily standup and sprint planning",
                                "source": "report",
                                "estimated_hours": 1.0,
                                "category": "meetings",
                                "confidence": 1.0,
                                "related_commits": [],
                                "related_report_text": "Attended daily standup and sprint planning"
                            },
                            {
                                "description": "Code review for team members",
                                "source": "report",
                                "estimated_hours": 1.5,
                                "category": "code_review",
                                "confidence": 1.0,
                                "related_commits": [],
                                "related_report_text": "Reviewed 3 PRs from team"
                            }
                        ],
                        "deduplicated_items": [
                            {
                                "commit_description": "Add OAuth authentication",
                                "report_description": "Worked on authentication system with OAuth integration",
                                "unified_description": "Implemented user authentication system with OAuth",
                                "hours_allocated": 4.0,
                                "reasoning": "Both describe the same OAuth authentication implementation"
                            }
                        ],
                        "work_categories": {
                            "feature_development": 4.0,
                            "bug_fixes": 1.5,
                            "code_review": 1.5,
                            "meetings": 1.0,
                            "documentation": 0.0,
                            "devops": 0.0,
                            "other": 0.0
                        },
                        "key_achievements": [
                            "Successfully implemented OAuth authentication system",
                            "Resolved critical payment processing bug",
                            "Contributed to team productivity through code reviews"
                        ],
                        "challenges_faced": [
                            "OAuth integration required more time than estimated due to provider API changes"
                        ],
                        "confidence_score": 0.93,
                        "analysis_reasoning": "Identified OAuth work in both commits and report, allocated 4 hours. Payment bug only in commits (1.5h). Meetings and reviews only in report (2.5h total)."
                    })
                }
            }]
        }
    
    @pytest.mark.asyncio
    async def test_full_eod_submission_flow(
        self, mock_supabase_client, sample_user, mock_ai_response
    ):
        """Test the complete flow from EOD submission to unified analysis."""
        # Patch Supabase client
        with patch('app.core.supabase_client.get_supabase_client', return_value=mock_supabase_client):
            # Setup repositories
            report_repo = DailyReportRepository()
            commit_repo = CommitRepository()
            analysis_repo = DailyWorkAnalysisRepository()
            
            # Mock repository responses
            report_id = uuid4()
            analysis_date = date(2024, 1, 15)
            
            # Mock commits for the day
            mock_commits = [
                {
                    "id": str(uuid4()),
                    "user_id": str(sample_user.id),
                    "commit_hash": "abc123",
                    "repository": "myapp",
                    "commit_message": "Add OAuth authentication",
                    "commit_date": "2024-01-15T10:30:00Z",
                    "additions": 200,
                    "deletions": 50,
                    "files_changed": ["auth.py", "oauth.py", "tests/test_auth.py"],
                    "ai_analysis": {"estimated_hours": 3.0}
                },
                {
                    "id": str(uuid4()),
                    "user_id": str(sample_user.id),
                    "commit_hash": "def456",
                    "repository": "myapp",
                    "commit_message": "Update OAuth scopes and permissions",
                    "commit_date": "2024-01-15T14:15:00Z",
                    "additions": 50,
                    "deletions": 20,
                    "files_changed": ["oauth.py", "config.py"],
                    "ai_analysis": {"estimated_hours": 1.0}
                },
                {
                    "id": str(uuid4()),
                    "user_id": str(sample_user.id),
                    "commit_hash": "ghi789",
                    "repository": "myapp",
                    "commit_message": "Fix payment processing timeout bug",
                    "commit_date": "2024-01-15T16:45:00Z",
                    "additions": 30,
                    "deletions": 10,
                    "files_changed": ["payment.py"],
                    "ai_analysis": {"estimated_hours": 1.5}
                }
            ]
            
            # Mock daily report
            mock_report = {
                "id": str(report_id),
                "user_id": str(sample_user.id),
                "report_date": "2024-01-15T17:00:00Z",
                "raw_text_input": """
                Today's work:
                - Worked on authentication system with OAuth integration
                - Attended daily standup and sprint planning (1 hour)
                - Reviewed 3 PRs from team members
                - Started investigating performance issues (will continue tomorrow)
                """,
                "ai_analysis": {
                    "estimated_hours": 8.0,
                    "key_achievements": [
                        "OAuth authentication implementation",
                        "Team collaboration through PR reviews"
                    ]
                },
                "final_estimated_hours": 8.0
            }
            
            # Setup Supabase mock responses
            mock_supabase_client.execute.side_effect = [
                MagicMock(data=[]),  # No existing analysis
                MagicMock(data=mock_commits),  # Commits query
                MagicMock(data=[mock_report]),  # Report query
                MagicMock(data=[{"id": str(uuid4())}]),  # Create analysis
                MagicMock(data=[]),  # Create work items
                MagicMock(data=[]),  # Create dedup results
            ]
            
            # Mock single() responses
            mock_supabase_client.single.side_effect = [
                MagicMock(data=None),  # No existing analysis
                MagicMock(data=mock_report),  # Get report
            ]
            
            # Patch AI integration
            with patch('app.integrations.ai_integration.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create.return_value = mock_ai_response
                
                # Create service and analyze
                service = UnifiedDailyAnalysisService()
                result = await service.analyze_daily_work(
                    sample_user.id,
                    analysis_date
                )
                
                # Verify AI was called once with all data
                assert mock_client.chat.completions.create.call_count == 1
                
                # Check the prompt contains both commits and report
                ai_call = mock_client.chat.completions.create.call_args
                messages = ai_call.kwargs['messages']
                user_message = messages[1]['content']
                
                # Verify prompt includes deduplication instructions
                assert "DO NOT double-count" in user_message
                assert "OAuth authentication" in user_message  # From commits
                assert "Attended daily standup" in user_message  # From report
                assert "3 commits" in user_message
                
                # Verify result
                assert result is not None
                assert result.total_productive_hours == 8.0
                assert result.commit_hours == 5.5
                assert result.additional_report_hours == 2.5
    
    @pytest.mark.asyncio
    async def test_slack_eod_triggers_unified_analysis(
        self, mock_supabase_client, sample_user, mock_ai_response
    ):
        """Test that Slack EOD submission triggers unified analysis."""
        with patch('app.core.supabase_client.get_supabase_client', return_value=mock_supabase_client):
            # Setup Slack handler with mocked dependencies
            slack_handler = SlackConversationHandler()
            slack_handler.slack_service = AsyncMock()
            slack_handler.daily_report_service = AsyncMock()
            slack_handler.user_service = AsyncMock()
            
            # Mock user service
            slack_handler.user_service.get_user_by_slack_id.return_value = sample_user
            
            # Mock report creation
            report_id = uuid4()
            created_report = DailyReport(
                id=report_id,
                user_id=sample_user.id,
                report_date=datetime.now(timezone.utc),
                raw_text_input="Test EOD report",
                final_estimated_hours=0.0
            )
            slack_handler.daily_report_service.submit_daily_report.return_value = created_report
            slack_handler.daily_report_service.process_report_with_ai.return_value = created_report
            
            # Mock Slack DM channel
            slack_handler.slack_service.open_dm.return_value = "D123456"
            
            # Create unified analysis service mock
            with patch('app.services.slack_conversation_handler.UnifiedDailyAnalysisService') as mock_unified_service:
                mock_service_instance = AsyncMock()
                mock_unified_service.return_value = mock_service_instance
                
                mock_analysis = DailyWorkAnalysis(
                    id=uuid4(),
                    user_id=sample_user.id,
                    analysis_date=date.today(),
                    total_productive_hours=8.0,
                    commit_hours=6.0,
                    additional_report_hours=2.0,
                    confidence_score=0.9,
                    status="completed"
                )
                mock_service_instance.analyze_daily_work.return_value = mock_analysis
                
                # Simulate modal submission
                view_data = {
                    "state": {
                        "values": {
                            "report_block": {
                                "report_input": {
                                    "value": "Worked on OAuth authentication and fixed bugs"
                                }
                            }
                        }
                    }
                }
                
                # Execute
                result = await slack_handler.handle_modal_submission(
                    sample_user.slack_id,
                    view_data
                )
                
                # Verify unified analysis was triggered
                mock_service_instance.analyze_daily_work.assert_called_once_with(
                    user_id=sample_user.id,
                    date=date.today(),
                    eod_report=created_report
                )
                
                # Verify Slack message includes unified analysis
                slack_handler.slack_service.post_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_commit_webhook_triggers_analysis(
        self, mock_supabase_client, sample_user, mock_ai_response
    ):
        """Test that commit webhooks can trigger unified analysis."""
        with patch('app.core.supabase_client.get_supabase_client', return_value=mock_supabase_client):
            # Mock the commit repository
            commit_repo = CommitRepository()
            
            # Create commits that should trigger analysis
            commits = []
            for i in range(5):  # 5 commits should trigger analysis
                commit = {
                    "id": str(uuid4()),
                    "user_id": str(sample_user.id),
                    "commit_hash": f"hash{i}",
                    "repository": "myapp",
                    "commit_message": f"Commit {i}",
                    "commit_date": datetime.now(timezone.utc).isoformat(),
                    "additions": 50,
                    "deletions": 20,
                    "files_changed": [f"file{i}.py"]
                }
                commits.append(commit)
            
            # Mock Supabase responses
            mock_supabase_client.execute.side_effect = [
                MagicMock(data=commits),  # Return commits
                MagicMock(data=[]),  # No existing analysis
                MagicMock(data=commits),  # Commits for analysis
                MagicMock(data=[]),  # No daily report
                MagicMock(data=[{"id": str(uuid4())}]),  # Create analysis
            ]
            
            # Create unified analysis service
            with patch('app.integrations.ai_integration.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create.return_value = mock_ai_response
                
                service = UnifiedDailyAnalysisService()
                
                # Simulate checking if analysis should be triggered
                today_commits = await commit_repo.get_commits_by_user_date_range(
                    sample_user.id,
                    datetime.now(timezone.utc).replace(hour=0, minute=0),
                    datetime.now(timezone.utc)
                )
                
                # Should trigger analysis with 5+ commits
                if len(today_commits) >= 5:
                    result = await service.analyze_daily_work(
                        sample_user.id,
                        date.today()
                    )
                    
                    assert result is not None
                    assert mock_client.chat.completions.create.called
    
    @pytest.mark.asyncio 
    async def test_weekly_aggregate_with_unified_analysis(
        self, mock_supabase_client, sample_user
    ):
        """Test weekly aggregate using unified analysis data."""
        with patch('app.core.supabase_client.get_supabase_client', return_value=mock_supabase_client):
            # Create mock analyses for a week
            week_start = date(2024, 1, 15)  # Monday
            mock_analyses = []
            
            for i in range(7):
                day = week_start + timedelta(days=i)
                hours = 8.0 if i < 5 else 0.0  # Work Mon-Fri
                
                analysis = {
                    "id": str(uuid4()),
                    "user_id": str(sample_user.id),
                    "analysis_date": day.isoformat(),
                    "total_productive_hours": hours,
                    "commit_hours": hours * 0.7,
                    "additional_report_hours": hours * 0.3,
                    "meeting_hours": 1.0 if hours > 0 else 0.0,
                    "work_categories": {
                        "feature_development": hours * 0.5,
                        "bug_fixes": hours * 0.2,
                        "meetings": hours * 0.15,
                        "code_review": hours * 0.15
                    } if hours > 0 else {},
                    "confidence_score": 0.9,
                    "status": "completed"
                }
                mock_analyses.append(analysis)
            
            # Mock repository response
            mock_supabase_client.execute.return_value = MagicMock(data=mock_analyses)
            
            # Create service and get weekly aggregate
            service = UnifiedDailyAnalysisService()
            result = await service.get_weekly_aggregate(sample_user.id, week_start)
            
            # Verify aggregate calculations
            assert result["total_hours"] == 40.0  # 5 days * 8 hours
            assert result["working_days"] == 5
            assert result["average_hours_per_day"] == 8.0
            assert result["most_productive_day"] == "Monday"
            assert result["least_productive_day"] in ["Saturday", "Sunday"]
            
            # Verify category breakdown
            categories = result["category_totals"]
            assert categories["feature_development"] == 20.0  # 40 * 0.5
            assert categories["bug_fixes"] == 8.0  # 40 * 0.2
            assert categories["meetings"] == 6.0  # 40 * 0.15
            assert categories["code_review"] == 6.0  # 40 * 0.15
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_retry(
        self, mock_supabase_client, sample_user, mock_ai_response
    ):
        """Test error handling and recovery in unified analysis."""
        with patch('app.core.supabase_client.get_supabase_client', return_value=mock_supabase_client):
            # Setup initial failure then success
            mock_supabase_client.execute.side_effect = [
                Exception("Database connection error"),  # First call fails
                MagicMock(data=[]),  # Second attempt succeeds
                MagicMock(data=[]),  # No commits
                MagicMock(data=[]),  # No report
            ]
            
            service = UnifiedDailyAnalysisService()
            
            # First attempt should fail
            with pytest.raises(Exception):
                await service.analyze_daily_work(sample_user.id, date.today())
            
            # Reset side effects for retry
            mock_supabase_client.execute.side_effect = [
                MagicMock(data=[]),  # No existing analysis
                MagicMock(data=[]),  # No commits
                MagicMock(data=[]),  # No report
                MagicMock(data=[{"id": str(uuid4())}]),  # Create zero-hour analysis
            ]
            
            # Retry should succeed with zero-hour analysis
            result = await service.analyze_daily_work(sample_user.id, date.today())
            assert result is not None
            assert result.total_productive_hours == 0.0
            assert result.status == "completed"