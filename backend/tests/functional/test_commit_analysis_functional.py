"""
Functional tests for commit analysis that verify real behavior.
These tests use minimal mocking to ensure the system works as expected.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.commit import Commit
from app.models.user import User, UserRole
from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService


class TestCommitAnalysisFunctional:
    """Functional tests that verify the commit analysis system works correctly"""

    @pytest.mark.asyncio
    async def test_commit_analysis_basic_flow(self):
        """Test basic commit analysis flow with minimal mocking"""

        # Create test data
        test_user_id = uuid.uuid4()
        test_commit_hash = "abc123def456"

        # Mock only external dependencies (database and external APIs)
        with (
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo_class,
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo_class,
            patch("app.integrations.github_integration.GitHubIntegration") as mock_github_class,
            patch("app.integrations.ai_integration.AIIntegration") as mock_ai_class,
            patch("app.services.daily_report_service.DailyReportService") as mock_report_service_class,
            patch("supabase.Client") as mock_supabase,
        ):

            # Set up repository mocks
            mock_commit_repo = AsyncMock()
            mock_user_repo = AsyncMock()
            mock_github = MagicMock()
            mock_ai = AsyncMock()
            mock_report_service = AsyncMock()

            mock_commit_repo_class.return_value = mock_commit_repo
            mock_user_repo_class.return_value = mock_user_repo
            mock_github_class.return_value = mock_github
            mock_ai_class.return_value = mock_ai
            mock_report_service_class.return_value = mock_report_service

            # Configure mocks for successful flow
            # 1. Commit doesn't exist
            mock_commit_repo.get_commit_by_hash.return_value = None

            # 2. User exists
            test_user = User(
                id=test_user_id,
                name="John Doe",
                email="john@example.com",
                github_username="johndoe",
                role=UserRole.EMPLOYEE,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            mock_user_repo.get_user_by_github_username.return_value = test_user

            # 3. GitHub returns diff
            mock_github.get_commit_diff.return_value = {
                "files": [
                    {
                        "filename": "src/feature.py",
                        "status": "added",
                        "additions": 50,
                        "deletions": 10,
                        "patch": "+def new_feature():\n+    return 'success'",
                    }
                ],
                "additions": 50,
                "deletions": 10,
                "author": {"name": "John Doe", "email": "john@example.com", "login": "johndoe"},
                "message": "feat: Add new feature",
            }

            # 4. AI returns analysis
            mock_ai.analyze_commit_diff.return_value = {
                "complexity_score": 5,
                "estimated_hours": 2.5,
                "risk_level": "low",
                "seniority_score": 6,
                "seniority_rationale": "Standard implementation",
                "key_changes": ["Added new feature function"],
                "model_used": "gpt-4",
            }

            # 5. Code quality analysis
            mock_ai.analyze_commit_code_quality.return_value = {"quality_score": 7, "issues": []}

            # 6. No daily report
            mock_report_service.get_user_report_for_date.return_value = None

            # 7. Save succeeds
            saved_commit = Commit(
                id=uuid.uuid4(),
                commit_hash=test_commit_hash,
                author_id=test_user_id,
                ai_estimated_hours=Decimal("2.5"),
                seniority_score=6,
                complexity_score=5,
                risk_level="low",
                commit_timestamp=datetime.now(timezone.utc),
            )
            mock_commit_repo.save_commit.return_value = saved_commit

            # Create service and process commit
            service = CommitAnalysisService(mock_supabase)

            commit_payload = CommitPayload(
                commit_hash=test_commit_hash,
                commit_message="feat: Add new feature",
                commit_url="https://github.com/org/repo/commit/abc123",
                commit_timestamp=datetime.now(timezone.utc),
                author_github_username="johndoe",
                author_email="john@example.com",
                repository_name="org/repo",
                repository_url="https://github.com/org/repo",
                branch="main",
                diff_url="https://github.com/org/repo/commit/abc123.diff",
            )

            result = await service.process_commit(commit_payload)

            # Verify the result
            assert result is not None
            assert result.commit_hash == test_commit_hash
            assert result.author_id == test_user_id
            assert result.ai_estimated_hours == Decimal("2.5")
            assert result.seniority_score == 6
            assert result.complexity_score == 5
            assert result.risk_level == "low"

            # Verify the flow executed correctly
            mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_hash)
            mock_user_repo.get_user_by_github_username.assert_called_once_with("johndoe")
            mock_github.get_commit_diff.assert_called_once_with("org/repo", test_commit_hash)
            mock_ai.analyze_commit_diff.assert_called_once()
            mock_commit_repo.save_commit.assert_called_once()

            # Verify the commit was properly constructed
            saved_commit_arg = mock_commit_repo.save_commit.call_args[0][0]
            assert saved_commit_arg.commit_hash == test_commit_hash
            assert saved_commit_arg.author_id == test_user_id

    @pytest.mark.asyncio
    async def test_commit_analysis_with_existing_commit(self):
        """Test processing when commit already exists"""

        with (
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo_class,
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo_class,
            patch("app.config.settings.settings") as mock_settings,
            patch("supabase.Client") as mock_supabase,
        ):

            # Configure settings
            mock_settings.reanalyze_existing_commits = False

            # Set up mocks
            mock_commit_repo = AsyncMock()
            mock_user_repo = AsyncMock()

            mock_commit_repo_class.return_value = mock_commit_repo
            mock_user_repo_class.return_value = mock_user_repo

            # Existing commit with analysis
            existing_commit = Commit(
                id=uuid.uuid4(),
                commit_hash="existing123",
                author_id=uuid.uuid4(),
                ai_estimated_hours=Decimal("3.0"),
                seniority_score=7,
                commit_timestamp=datetime.now(timezone.utc),
            )
            mock_commit_repo.get_commit_by_hash.return_value = existing_commit

            # Create service
            service = CommitAnalysisService(mock_supabase)

            # Process existing commit
            commit_payload = CommitPayload(
                commit_hash="existing123",
                commit_message="Existing commit",
                commit_url="https://github.com/org/repo/commit/existing123",
                commit_timestamp=datetime.now(timezone.utc),
                author_github_username="user",
                author_email="user@example.com",
                repository_name="org/repo",
                repository_url="https://github.com/org/repo",
                branch="main",
                diff_url="https://github.com/org/repo/commit/existing123.diff",
            )

            result = await service.process_commit(commit_payload)

            # Should return existing commit without reprocessing
            assert result is not None
            assert result.id == existing_commit.id
            assert result.commit_hash == "existing123"

            # Should not call any other services
            mock_user_repo.get_user_by_github_username.assert_not_called()

    @pytest.mark.asyncio
    async def test_commit_analysis_error_recovery(self):
        """Test that errors are handled gracefully"""

        with (
            patch("app.repositories.commit_repository.CommitRepository") as mock_commit_repo_class,
            patch("app.repositories.user_repository.UserRepository") as mock_user_repo_class,
            patch("app.integrations.github_integration.GitHubIntegration") as mock_github_class,
            patch("app.integrations.ai_integration.AIIntegration") as mock_ai_class,
            patch("supabase.Client") as mock_supabase,
        ):

            # Set up mocks
            mock_commit_repo = AsyncMock()
            mock_user_repo = AsyncMock()
            mock_github = MagicMock()
            mock_ai = AsyncMock()

            mock_commit_repo_class.return_value = mock_commit_repo
            mock_user_repo_class.return_value = mock_user_repo
            mock_github_class.return_value = mock_github
            mock_ai_class.return_value = mock_ai

            # Configure error scenario - AI fails
            mock_commit_repo.get_commit_by_hash.return_value = None
            mock_user_repo.get_user_by_github_username.return_value = User(
                id=uuid.uuid4(),
                github_username="user",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            mock_github.get_commit_diff.return_value = {"files": [], "additions": 10, "deletions": 5}
            mock_ai.analyze_commit_diff.side_effect = Exception("AI service error")

            # Create service
            service = CommitAnalysisService(mock_supabase)

            # Process commit
            commit_payload = CommitPayload(
                commit_hash="error123",
                commit_message="Test commit",
                commit_url="https://github.com/org/repo/commit/error123",
                commit_timestamp=datetime.now(timezone.utc),
                author_github_username="user",
                author_email="user@example.com",
                repository_name="org/repo",
                repository_url="https://github.com/org/repo",
                branch="main",
                diff_url="https://github.com/org/repo/commit/error123.diff",
            )

            result = await service.process_commit(commit_payload)

            # Should handle error gracefully
            assert result is None

            # Should have attempted the analysis
            mock_ai.analyze_commit_diff.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
