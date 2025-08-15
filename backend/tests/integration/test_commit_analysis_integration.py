"""
Integration tests for the commit analysis functionality.
These tests verify the actual behavior of the system with real-like scenarios.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.config.settings import settings
from app.integrations.ai_integration import AIIntegration
from app.integrations.github_integration import GitHubIntegration
from app.models.commit import Commit
from app.models.daily_report import AiAnalysis, DailyReport
from app.models.user import User, UserRole
from app.repositories.commit_repository import CommitRepository
from app.repositories.daily_report_repository import DailyReportRepository
from app.repositories.user_repository import UserRepository
from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService
from app.services.daily_commit_analysis_service import DailyCommitAnalysisService
from supabase import Client

# Sample commit diff data for testing
SAMPLE_DIFF_DATA = {
    "commit_hash": "abc123def456",
    "repository": "testorg/testrepo",
    "files_changed": ["src/main.py", "tests/test_main.py"],
    "additions": 150,
    "deletions": 50,
    "author": {
        "name": "Test Developer",
        "email": "test@example.com",
        "date": "2024-01-15T10:30:00Z",
        "login": "testdev",
    },
    "message": "feat: Add new authentication system with JWT tokens",
    "files": [
        {
            "filename": "src/main.py",
            "status": "modified",
            "additions": 100,
            "deletions": 30,
            "patch": """@@ -1,5 +1,105 @@
+import jwt
+from datetime import datetime, timedelta
+
+class AuthService:
+    def __init__(self, secret_key):
+        self.secret_key = secret_key
+    
+    def generate_token(self, user_id):
+        payload = {
+            'user_id': user_id,
+            'exp': datetime.utcnow() + timedelta(hours=24)
+        }
+        return jwt.encode(payload, self.secret_key, algorithm='HS256')
...""",
        },
        {
            "filename": "tests/test_main.py",
            "status": "added",
            "additions": 50,
            "deletions": 20,
            "patch": """@@ -0,0 +50,20 @@
+import pytest
+from src.main import AuthService
+
+def test_token_generation():
+    auth = AuthService('test_secret')
+    token = auth.generate_token('user123')
+    assert token is not None
...""",
        },
    ],
}

# Sample AI analysis response
SAMPLE_AI_ANALYSIS = {
    "complexity_score": 6,
    "estimated_hours": 3.5,
    "risk_level": "medium",
    "seniority_score": 7,
    "seniority_rationale": "Well-structured authentication implementation with proper JWT handling and test coverage. Shows good understanding of security patterns.",
    "key_changes": [
        "Implemented JWT-based authentication",
        "Added token generation and validation",
        "Created comprehensive test suite",
    ],
    "analyzed_at": "2024-01-15T10:35:00Z",
    "model_used": "gpt-4",
}


class TestCommitAnalysisIntegration:
    """Integration tests for commit analysis functionality"""

    @pytest_asyncio.fixture
    async def setup_test_data(self):
        """Set up test data including users, commits, and reports"""
        self.test_user_id = uuid.uuid4()
        self.test_user = User(
            id=self.test_user_id,
            name="Test Developer",
            email="test@example.com",
            github_username="testdev",
            role=UserRole.EMPLOYEE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_active=True,
        )

        self.test_commit_payload = CommitPayload(
            commit_hash="abc123def456",
            commit_message="feat: Add new authentication system with JWT tokens",
            commit_url="https://github.com/testorg/testrepo/commit/abc123def456",
            commit_timestamp=datetime.now(timezone.utc),
            author_github_username="testdev",
            author_email="test@example.com",
            repository_name="testorg/testrepo",
            repository_url="https://github.com/testorg/testrepo",
            branch="main",
            diff_url="https://github.com/testorg/testrepo/commit/abc123def456.diff",
            files_changed=["src/main.py", "tests/test_main.py"],
            additions=150,
            deletions=50,
        )

        self.test_daily_report = DailyReport(
            id=uuid.uuid4(),
            user_id=self.test_user_id,
            report_date=datetime.now(timezone.utc),
            raw_text_input="- Implemented JWT authentication system\n- Added token validation\n- Created test suite\n- Reviewed security patterns",
            clarified_tasks_summary="Implemented JWT authentication system",
            additional_hours=Decimal("2.0"),
            created_at=datetime.now(timezone.utc),
            ai_analysis=AiAnalysis(
                summary="Strong authentication implementation",
                estimated_hours=3.0,
                key_achievements=["JWT implementation", "Test coverage"],
                sentiment="positive",
            ),
        )

    @pytest.mark.asyncio
    async def test_full_commit_analysis_flow(self, setup_test_data):
        """Test the complete flow from webhook to analysis storage"""
        with (
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo,
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo,
            patch("app.repositories.daily_report_repository.DailyReportRepository") as mock_report_repo,
            patch("app.integrations.github_integration.GitHubIntegration") as mock_github,
            patch("app.integrations.ai_integration.AIIntegration") as mock_ai,
            patch("supabase.Client") as mock_supabase,
        ):

            # Configure mocks
            mock_user_repo_instance = AsyncMock()
            mock_commit_repo_instance = AsyncMock()
            mock_report_repo_instance = AsyncMock()
            mock_github_instance = MagicMock()
            mock_ai_instance = AsyncMock()

            mock_user_repo.return_value = mock_user_repo_instance
            mock_commit_repo.return_value = mock_commit_repo_instance
            mock_report_repo.return_value = mock_report_repo_instance
            mock_github.return_value = mock_github_instance
            mock_ai.return_value = mock_ai_instance

            # Set up mock responses
            mock_commit_repo_instance.get_commit_by_hash.return_value = None  # New commit
            mock_user_repo_instance.get_user_by_github_username.return_value = self.test_user
            mock_github_instance.get_commit_diff.return_value = SAMPLE_DIFF_DATA
            mock_ai_instance.analyze_commit_diff.return_value = SAMPLE_AI_ANALYSIS
            mock_report_repo_instance.get_daily_reports_by_user_and_date.return_value = self.test_daily_report

            # Create analyzed commit object
            analyzed_commit = Commit(
                id=uuid.uuid4(),
                commit_hash=self.test_commit_payload.commit_hash,
                author_id=self.test_user_id,
                ai_estimated_hours=Decimal(str(SAMPLE_AI_ANALYSIS["estimated_hours"])),
                seniority_score=SAMPLE_AI_ANALYSIS["seniority_score"],
                complexity_score=SAMPLE_AI_ANALYSIS["complexity_score"],
                risk_level=SAMPLE_AI_ANALYSIS["risk_level"],
                key_changes=SAMPLE_AI_ANALYSIS["key_changes"],
                seniority_rationale=SAMPLE_AI_ANALYSIS["seniority_rationale"],
                model_used=SAMPLE_AI_ANALYSIS["model_used"],
                commit_timestamp=self.test_commit_payload.commit_timestamp,
                eod_report_id=self.test_daily_report.id,
                eod_report_summary=self.test_daily_report.clarified_tasks_summary,
                comparison_notes="EOD report found. Alignment between commit and report.",
            )
            mock_commit_repo_instance.save_commit.return_value = analyzed_commit

            # Execute the service with mocked repositories
            service = CommitAnalysisService(mock_supabase)
            # Manually set the mocked repositories since __init__ might create real ones
            service.commit_repository = mock_commit_repo_instance
            service.user_repository = mock_user_repo_instance
            service.github_integration = mock_github_instance
            service.ai_integration = mock_ai_instance
            service.daily_report_service.daily_report_repository = mock_report_repo_instance

            result = await service.process_commit(self.test_commit_payload)

            # Verify the flow
            assert result is not None
            assert result.commit_hash == self.test_commit_payload.commit_hash
            assert result.author_id == self.test_user_id
            assert result.ai_estimated_hours == Decimal("3.5")
            assert result.seniority_score == 7
            assert result.eod_report_id == self.test_daily_report.id

            # Verify calls were made
            mock_user_repo_instance.get_user_by_github_username.assert_called_once_with("testdev")
            mock_github_instance.get_commit_diff.assert_called_once()
            mock_ai_instance.analyze_commit_diff.assert_called_once()
            mock_commit_repo_instance.save_commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_analysis_with_user_creation(self, setup_test_data):
        """Test commit analysis when user doesn't exist and needs to be created"""
        with (
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo,
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo,
            patch("app.integrations.github_integration.GitHubIntegration") as mock_github,
            patch("app.integrations.ai_integration.AIIntegration") as mock_ai,
            patch("supabase.Client") as mock_supabase,
        ):

            # Configure mocks
            mock_user_repo_instance = AsyncMock()
            mock_commit_repo_instance = AsyncMock()
            mock_github_instance = MagicMock()
            mock_ai_instance = AsyncMock()

            mock_user_repo.return_value = mock_user_repo_instance
            mock_commit_repo.return_value = mock_commit_repo_instance
            mock_github.return_value = mock_github_instance
            mock_ai.return_value = mock_ai_instance

            # User not found, will be created
            mock_user_repo_instance.get_user_by_github_username.return_value = None
            mock_user_repo_instance.get_user_by_email.return_value = None

            # Configure user creation
            new_user = User(
                id=uuid.uuid4(),
                name="testdev",
                email="test@example.com",
                github_username="testdev",
                role=UserRole.EMPLOYEE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                is_active=True,
            )
            mock_user_repo_instance.create_user.return_value = new_user

            # Other mocks
            mock_commit_repo_instance.get_commit_by_hash.return_value = None
            mock_github_instance.get_commit_diff.return_value = SAMPLE_DIFF_DATA
            mock_ai_instance.analyze_commit_diff.return_value = SAMPLE_AI_ANALYSIS

            analyzed_commit = Commit(
                id=uuid.uuid4(),
                commit_hash=self.test_commit_payload.commit_hash,
                author_id=new_user.id,
                ai_estimated_hours=Decimal("3.5"),
                seniority_score=7,
                commit_timestamp=self.test_commit_payload.commit_timestamp,
            )
            mock_commit_repo_instance.save_commit.return_value = analyzed_commit

            # Execute
            service = CommitAnalysisService(mock_supabase)
            result = await service.process_commit(self.test_commit_payload)

            # Verify
            assert result is not None
            assert result.author_id == new_user.id
            mock_user_repo_instance.create_user.assert_called_once()

            # Verify the created user has correct attributes
            created_user_arg = mock_user_repo_instance.create_user.call_args[0][0]
            assert created_user_arg.github_username == "testdev"
            assert created_user_arg.email == "test@example.com"
            assert created_user_arg.role == UserRole.EMPLOYEE

    @pytest.mark.asyncio
    async def test_batch_commit_analysis(self, setup_test_data):
        """Test analyzing multiple commits in batch"""
        with (
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo,
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo,
            patch("app.integrations.github_integration.GitHubIntegration") as mock_github,
            patch("app.integrations.ai_integration.AIIntegration") as mock_ai,
            patch("supabase.Client") as mock_supabase,
        ):

            # Configure mocks
            mock_user_repo_instance = AsyncMock()
            mock_commit_repo_instance = AsyncMock()
            mock_github_instance = MagicMock()
            mock_ai_instance = AsyncMock()

            mock_user_repo.return_value = mock_user_repo_instance
            mock_commit_repo.return_value = mock_commit_repo_instance
            mock_github.return_value = mock_github_instance
            mock_ai.return_value = mock_ai_instance

            # Create multiple commits
            commits_payload = [
                {
                    "hash": "commit1",
                    "message": "First commit",
                    "repository": "testorg/testrepo",
                    "author": {"email": "test@example.com", "name": "Test Dev"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "hash": "commit2",
                    "message": "Second commit",
                    "repository": "testorg/testrepo",
                    "author": {"email": "test@example.com", "name": "Test Dev"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "hash": "commit3",
                    "message": "Third commit",
                    "repository": "testorg/testrepo",
                    "author": {"email": "test@example.com", "name": "Test Dev"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            ]

            # Mock responses
            mock_user_repo_instance.get_user_by_email.return_value = self.test_user
            mock_commit_repo_instance.get_commit_by_hash.return_value = None
            mock_github_instance.get_commit_diff.return_value = SAMPLE_DIFF_DATA
            mock_ai_instance.analyze_commit_diff.return_value = SAMPLE_AI_ANALYSIS

            # Mock save_commit to return different commits
            analyzed_commits = []
            for i, commit_data in enumerate(commits_payload):
                commit = Commit(
                    id=uuid.uuid4(),
                    commit_hash=commit_data["hash"],
                    author_id=self.test_user_id,
                    ai_estimated_hours=Decimal("1.5") * (i + 1),
                    seniority_score=5 + i,
                    commit_timestamp=datetime.fromisoformat(commit_data["timestamp"]),
                )
                analyzed_commits.append(commit)

            mock_commit_repo_instance.save_commit.side_effect = analyzed_commits

            # Execute
            service = CommitAnalysisService(mock_supabase)
            results = await service.batch_analyze_commits(commits_payload)

            # Verify
            assert len(results) == 3
            assert all(r is not None for r in results)
            assert results[0].ai_estimated_hours == Decimal("1.5")
            assert results[1].ai_estimated_hours == Decimal("3.0")
            assert results[2].ai_estimated_hours == Decimal("4.5")

            # Verify all commits were processed
            assert mock_ai_instance.analyze_commit_diff.call_count == 3
            assert mock_commit_repo_instance.save_commit.call_count == 3

    @pytest.mark.asyncio
    async def test_daily_commit_analysis_with_report(self, setup_test_data):
        """Test daily commit analysis when user has submitted EOD report"""
        with (
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo,
            patch("app.repositories.daily_commit_analysis_repository.DailyCommitAnalysisRepository") as mock_daily_repo,
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo,
            patch("app.integrations.ai_integration.AIIntegration") as mock_ai,
        ):

            # Configure mocks
            mock_commit_repo_instance = AsyncMock()
            mock_daily_repo_instance = AsyncMock()
            mock_user_repo_instance = AsyncMock()
            mock_ai_instance = AsyncMock()

            mock_commit_repo.return_value = mock_commit_repo_instance
            mock_daily_repo.return_value = mock_daily_repo_instance
            mock_user_repo.return_value = mock_user_repo_instance
            mock_ai.return_value = mock_ai_instance

            # Set up test commits
            test_commits = [
                Commit(
                    id=uuid.uuid4(),
                    commit_hash=f"hash{i}",
                    author_id=self.test_user_id,
                    ai_estimated_hours=Decimal("1.5"),
                    seniority_score=6,
                    commit_timestamp=datetime.now(timezone.utc),
                    repository="testorg/testrepo",
                    commit_message=f"Commit {i}",
                    additions=50,
                    deletions=20,
                )
                for i in range(3)
            ]

            # Mock responses
            mock_daily_repo_instance.get_by_user_and_date.return_value = None  # No existing analysis
            mock_commit_repo_instance.get_commits_by_user_in_range.return_value = test_commits
            mock_user_repo_instance.get_by_id.return_value = self.test_user

            # Mock AI daily analysis
            daily_ai_result = {
                "total_estimated_hours": 4.5,
                "average_complexity_score": 6,
                "average_seniority_score": 6,
                "summary": "Productive day with authentication implementation",
                "key_insights": ["Consistent code quality", "Good test coverage"],
                "recommendations": ["Consider adding integration tests"],
            }
            mock_ai_instance.analyze_daily_work.return_value = daily_ai_result

            # Execute
            service = DailyCommitAnalysisService()
            result = await service.analyze_for_report(
                self.test_user_id, datetime.now(timezone.utc).date(), self.test_daily_report
            )

            # Verify
            assert result is not None
            assert result.total_estimated_hours == Decimal("4.5")
            assert result.commit_count == 3
            assert result.daily_report_id == self.test_daily_report.id
            assert result.analysis_type == "with_report"

            # Verify AI was called with proper context
            mock_ai_instance.analyze_daily_work.assert_called_once()
            ai_context = mock_ai_instance.analyze_daily_work.call_args[0][0]
            assert ai_context["total_commits"] == 3
            assert "daily_report" in ai_context
            assert ai_context["daily_report"]["summary"] == self.test_daily_report.clarified_tasks_summary

    @pytest.mark.asyncio
    async def test_commit_analysis_error_handling(self, setup_test_data):
        """Test error handling in commit analysis"""
        with (
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo,
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo,
            patch("app.integrations.github_integration.GitHubIntegration") as mock_github,
            patch("app.integrations.ai_integration.AIIntegration") as mock_ai,
            patch("supabase.Client") as mock_supabase,
        ):

            # Configure mocks
            mock_user_repo_instance = AsyncMock()
            mock_commit_repo_instance = AsyncMock()
            mock_github_instance = MagicMock()
            mock_ai_instance = AsyncMock()

            mock_user_repo.return_value = mock_user_repo_instance
            mock_commit_repo.return_value = mock_commit_repo_instance
            mock_github.return_value = mock_github_instance
            mock_ai.return_value = mock_ai_instance

            # Test AI service failure
            mock_commit_repo_instance.get_commit_by_hash.return_value = None
            mock_user_repo_instance.get_user_by_github_username.return_value = self.test_user
            mock_github_instance.get_commit_diff.return_value = SAMPLE_DIFF_DATA
            mock_ai_instance.analyze_commit_diff.side_effect = Exception("AI service unavailable")

            # Execute
            service = CommitAnalysisService(mock_supabase)
            result = await service.process_commit(self.test_commit_payload)

            # Verify - should handle error gracefully
            assert result is None

            # Test GitHub API failure
            mock_github_instance.get_commit_diff.side_effect = Exception("GitHub API error")
            mock_ai_instance.analyze_commit_diff.side_effect = None  # Reset

            result = await service.process_commit(self.test_commit_payload)

            # When GitHub fails but diff is in payload, should still work
            # But in this test, we expect it to fail since fetch_diff would be True
            assert result is None

    @pytest.mark.asyncio
    async def test_commit_analysis_with_skip_individual_setting(self, setup_test_data):
        """Test commit analysis when SKIP_INDIVIDUAL_COMMIT_ANALYSIS is enabled"""
        with (
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo,
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo,
            patch("app.integrations.github_integration.GitHubIntegration") as mock_github,
            patch("app.config.settings.settings.SKIP_INDIVIDUAL_COMMIT_ANALYSIS", True),
            patch("supabase.Client") as mock_supabase,
        ):

            # Configure mocks
            mock_user_repo_instance = AsyncMock()
            mock_commit_repo_instance = AsyncMock()
            mock_github_instance = MagicMock()

            mock_user_repo.return_value = mock_user_repo_instance
            mock_commit_repo.return_value = mock_commit_repo_instance
            mock_github.return_value = mock_github_instance

            # Set up mocks
            mock_commit_repo_instance.get_commit_by_hash.return_value = None
            mock_user_repo_instance.get_user_by_github_username.return_value = self.test_user
            mock_github_instance.get_commit_diff.return_value = SAMPLE_DIFF_DATA

            # Create minimal commit (no AI analysis)
            minimal_commit = Commit(
                id=uuid.uuid4(),
                commit_hash=self.test_commit_payload.commit_hash,
                author_id=self.test_user_id,
                ai_estimated_hours=Decimal("0.0"),
                seniority_score=5,
                complexity_score=5,
                risk_level="medium",
                seniority_rationale="Skipped individual analysis - will be analyzed in daily batch",
                model_used="none (batch analysis mode)",
                commit_timestamp=self.test_commit_payload.commit_timestamp,
            )
            mock_commit_repo_instance.save_commit.return_value = minimal_commit

            # Execute
            service = CommitAnalysisService(mock_supabase)

            # Patch AI integration to ensure it's not called
            with patch.object(service.ai_integration, "analyze_commit_diff") as mock_ai_call:
                result = await service.process_commit(self.test_commit_payload)

            # Verify
            assert result is not None
            assert result.model_used == "none (batch analysis mode)"
            assert "batch" in result.seniority_rationale.lower()
            mock_ai_call.assert_not_called()  # AI should not be called in batch mode


class TestCommitAnalysisWebhook:
    """Test the webhook endpoint for commit analysis"""

    @pytest.fixture
    def test_client(self):
        """Create a test client for the FastAPI app"""
        from app.main import app

        return TestClient(app)

    @pytest.fixture
    def valid_commit_payload(self):
        """Valid commit payload for webhook testing"""
        return {
            "commit_hash": "abc123def456",
            "commit_message": "feat: Add new feature",
            "commit_url": "https://github.com/org/repo/commit/abc123",
            "commit_timestamp": datetime.now(timezone.utc).isoformat(),
            "author_github_username": "testdev",
            "author_email": "test@example.com",
            "repository_name": "org/repo",
            "repository_url": "https://github.com/org/repo",
            "branch": "main",
            "diff_url": "https://github.com/org/repo/commit/abc123.diff",
            "files_changed": ["file1.py", "file2.py"],
            "additions": 100,
            "deletions": 50,
        }

    def test_webhook_authentication_required(self, test_client, valid_commit_payload):
        """Test that webhook requires authentication"""
        with patch("app.config.settings.settings.enable_api_auth", True):
            response = test_client.post("/api/v1/integrations/github/commit", json=valid_commit_payload)
            assert response.status_code == 403  # Or whatever error code your auth returns

    def test_webhook_with_valid_auth(self, test_client, valid_commit_payload):
        """Test webhook with valid authentication"""
        with (
            patch("app.config.settings.settings.enable_api_auth", True),
            patch("app.config.settings.settings.make_integration_api_key", "test_key"),
            patch("app.config.settings.settings.api_key_header", "X-API-Key"),
            patch("app.services.commit_analysis_service.CommitAnalysisService.process_commit") as mock_process,
        ):

            # Mock successful processing
            mock_process.return_value = AsyncMock(return_value=MagicMock(commit_hash="abc123def456"))

            response = test_client.post(
                "/api/v1/integrations/github/commit", json=valid_commit_payload, headers={"X-API-Key": "test_key"}
            )

            assert response.status_code == 202
            assert response.json()["commit_hash"] == "abc123def456"

    def test_webhook_invalid_payload(self, test_client):
        """Test webhook with invalid payload"""
        with patch("app.config.settings.settings.enable_api_auth", False):
            # Missing required fields
            invalid_payload = {
                "commit_message": "Test commit"
                # Missing commit_hash and other required fields
            }

            response = test_client.post("/api/v1/integrations/github/commit", json=invalid_payload)

            assert response.status_code == 422  # Validation error

    def test_webhook_processing_error(self, test_client, valid_commit_payload):
        """Test webhook when processing fails"""
        with (
            patch("app.config.settings.settings.enable_api_auth", False),
            patch("app.services.commit_analysis_service.CommitAnalysisService.process_commit") as mock_process,
        ):

            # Mock processing failure
            mock_process.return_value = None

            response = test_client.post("/api/v1/integrations/github/commit", json=valid_commit_payload)

            # Should still return 202 but with error in processing
            assert response.status_code == 500  # Or whatever your error handling returns


# Run specific test scenarios
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
