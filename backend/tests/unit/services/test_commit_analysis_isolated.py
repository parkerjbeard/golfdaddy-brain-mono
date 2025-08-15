"""
Isolated unit tests for commit analysis service with complete mocking.
These tests verify the core functionality without external dependencies.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
import pytest_asyncio

from app.models.commit import Commit
from app.models.daily_report import AiAnalysis, DailyReport
from app.models.user import User, UserRole
from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService


class TestCommitAnalysisServiceIsolated:
    """Isolated tests for commit analysis service"""

    @pytest.fixture
    def mock_dependencies(self):
        """Create all mock dependencies"""
        mocks = {
            "supabase": MagicMock(),
            "commit_repo": AsyncMock(),
            "user_repo": AsyncMock(),
            "ai_integration": AsyncMock(),
            "github_integration": MagicMock(),
            "daily_report_service": AsyncMock(),
        }
        return mocks

    @pytest.fixture
    def service_with_mocks(self, mock_dependencies):
        """Create service with all dependencies mocked"""
        with (
            patch("app.services.commit_analysis_service.CommitRepository") as mock_commit_repo_class,
            patch("app.services.commit_analysis_service.UserRepository") as mock_user_repo_class,
            patch("app.services.commit_analysis_service.AIIntegration") as mock_ai_class,
            patch("app.services.commit_analysis_service.GitHubIntegration") as mock_github_class,
            patch("app.services.commit_analysis_service.DailyReportService") as mock_report_service_class,
        ):

            # Configure class mocks to return instance mocks
            mock_commit_repo_class.return_value = mock_dependencies["commit_repo"]
            mock_user_repo_class.return_value = mock_dependencies["user_repo"]
            mock_ai_class.return_value = mock_dependencies["ai_integration"]
            mock_github_class.return_value = mock_dependencies["github_integration"]
            mock_report_service_class.return_value = mock_dependencies["daily_report_service"]

            service = CommitAnalysisService(mock_dependencies["supabase"])
            return service, mock_dependencies

    @pytest.fixture
    def test_data(self):
        """Common test data"""
        user_id = uuid.uuid4()
        return {
            "user": User(
                id=user_id,
                name="Test Developer",
                email="test@example.com",
                github_username="testdev",
                role=UserRole.EMPLOYEE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                is_active=True,
            ),
            "commit_payload": CommitPayload(
                commit_hash="abc123def456",
                commit_message="feat: Add authentication system",
                commit_url="https://github.com/org/repo/commit/abc123",
                commit_timestamp=datetime.now(timezone.utc),
                author_github_username="testdev",
                author_email="test@example.com",
                repository_name="org/repo",
                repository_url="https://github.com/org/repo",
                branch="main",
                diff_url="https://github.com/org/repo/commit/abc123.diff",
                files_changed=["auth.py", "test_auth.py"],
                additions=150,
                deletions=50,
            ),
            "diff_data": {
                "files": [
                    {
                        "filename": "auth.py",
                        "status": "added",
                        "additions": 100,
                        "deletions": 30,
                        "patch": "+def authenticate(user):\n+    return True",
                    }
                ],
                "additions": 150,
                "deletions": 50,
                "author": {"name": "Test Developer", "email": "test@example.com", "login": "testdev"},
                "message": "feat: Add authentication system",
            },
            "ai_analysis": {
                "complexity_score": 6,
                "estimated_hours": 3.5,
                "risk_level": "medium",
                "seniority_score": 7,
                "seniority_rationale": "Good implementation",
                "key_changes": ["Added authentication"],
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "model_used": "gpt-4",
            },
            "daily_report": DailyReport(
                id=uuid.uuid4(),
                user_id=user_id,
                report_date=datetime.now(timezone.utc),
                raw_text_input="- Implemented authentication\n- Added tests",
                clarified_tasks_summary="Implemented authentication system",
                additional_hours=Decimal("2.0"),
                ai_analysis=AiAnalysis(
                    summary="Authentication work", estimated_hours=3.0, key_achievements=["Authentication implemented"]
                ),
            ),
        }

    @pytest.mark.asyncio
    async def test_analyze_commit_success(self, service_with_mocks, test_data):
        """Test successful commit analysis"""
        service, mocks = service_with_mocks

        # Configure mocks
        mocks["github_integration"].get_commit_diff.return_value = test_data["diff_data"]
        mocks["ai_integration"].analyze_commit_diff.return_value = test_data["ai_analysis"]
        mocks["user_repo"].get_user_by_email.return_value = test_data["user"]
        mocks["daily_report_service"].get_user_report_for_date.return_value = test_data["daily_report"]

        # Mock code quality analysis
        mocks["ai_integration"].analyze_commit_code_quality.return_value = {"quality_score": 8, "issues": []}

        # Create expected commit object
        expected_commit = Commit(
            commit_hash="abc123def456",
            author_id=test_data["user"].id,
            ai_estimated_hours=Decimal("3.5"),
            seniority_score=7,
            complexity_score=6,
            risk_level="medium",
            commit_timestamp=test_data["commit_payload"].commit_timestamp,
            eod_report_id=test_data["daily_report"].id,
        )
        mocks["commit_repo"].save_commit.return_value = expected_commit

        # Execute
        commit_data = {
            "commit_hash": "abc123def456",
            "repository": "org/repo",
            "author": {"email": "test@example.com"},
            "timestamp": test_data["commit_payload"].commit_timestamp,
        }

        result = await service.analyze_commit("abc123def456", commit_data, fetch_diff=True)

        # Verify
        assert result is not None
        assert result.commit_hash == "abc123def456"
        assert result.ai_estimated_hours == Decimal("3.5")
        assert result.seniority_score == 7

        # Verify calls
        mocks["github_integration"].get_commit_diff.assert_called_once_with("org/repo", "abc123def456")
        mocks["ai_integration"].analyze_commit_diff.assert_called_once()
        mocks["commit_repo"].save_commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_commit_new_user(self, service_with_mocks, test_data):
        """Test processing commit when user doesn't exist"""
        service, mocks = service_with_mocks

        # User not found - will be created
        mocks["commit_repo"].get_commit_by_hash.return_value = None
        mocks["user_repo"].get_user_by_github_username.return_value = None
        mocks["user_repo"].get_user_by_email.return_value = None

        # Configure user creation
        new_user = test_data["user"]
        mocks["user_repo"].create_user.return_value = new_user

        # Configure other mocks
        mocks["github_integration"].get_commit_diff.return_value = test_data["diff_data"]
        mocks["ai_integration"].analyze_commit_diff.return_value = test_data["ai_analysis"]
        mocks["daily_report_service"].get_user_report_for_date.return_value = None
        mocks["ai_integration"].analyze_commit_code_quality.return_value = {"quality_score": 7}

        saved_commit = Commit(
            commit_hash=test_data["commit_payload"].commit_hash,
            author_id=new_user.id,
            ai_estimated_hours=Decimal("3.5"),
            commit_timestamp=test_data["commit_payload"].commit_timestamp,
        )
        mocks["commit_repo"].save_commit.return_value = saved_commit

        # Execute
        result = await service.process_commit(test_data["commit_payload"])

        # Verify
        assert result is not None
        assert result.author_id == new_user.id

        # Verify user creation
        mocks["user_repo"].create_user.assert_called_once()
        created_user = mocks["user_repo"].create_user.call_args[0][0]
        assert created_user.github_username == "testdev"
        assert created_user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_analyze_commit_no_diff(self, service_with_mocks, test_data):
        """Test handling when no diff is available"""
        service, mocks = service_with_mocks

        # No diff available
        commit_data = {
            "commit_hash": "abc123",
            "repository": "org/repo",
            "files_changed": ["file1.py"],
            "additions": 10,
            "deletions": 5,
        }

        # Execute
        result = await service.analyze_commit("abc123", commit_data, fetch_diff=False)

        # Should return None when no diff content
        assert result is None

    @pytest.mark.asyncio
    async def test_batch_analyze_commits(self, service_with_mocks, test_data):
        """Test batch commit analysis"""
        service, mocks = service_with_mocks

        # Create multiple commits
        commits = [
            {"hash": "commit1", "repository": "org/repo", "diff": "diff1"},
            {"hash": "commit2", "repository": "org/repo", "diff": "diff2"},
            {"hash": "commit3", "repository": "org/repo", "diff": "diff3"},
        ]

        # Configure mocks
        mocks["user_repo"].get_user_by_email.return_value = test_data["user"]
        mocks["ai_integration"].analyze_commit_diff.return_value = test_data["ai_analysis"]
        mocks["daily_report_service"].get_user_report_for_date.return_value = None
        mocks["ai_integration"].analyze_commit_code_quality.return_value = {"quality_score": 7}

        # Mock different commits for save
        saved_commits = []
        for i, commit in enumerate(commits):
            saved_commit = Commit(
                commit_hash=commit["hash"],
                author_id=test_data["user"].id,
                ai_estimated_hours=Decimal(str(1.5 * (i + 1))),
                commit_timestamp=datetime.now(timezone.utc),
            )
            saved_commits.append(saved_commit)

        mocks["commit_repo"].save_commit.side_effect = saved_commits

        # Execute
        results = await service.batch_analyze_commits(commits)

        # Verify
        assert len(results) == 3
        assert all(r is not None for r in results)
        assert results[0].ai_estimated_hours == Decimal("1.5")
        assert results[1].ai_estimated_hours == Decimal("3.0")
        assert results[2].ai_estimated_hours == Decimal("4.5")

    @pytest.mark.asyncio
    async def test_skip_individual_analysis_mode(self, service_with_mocks, test_data):
        """Test when SKIP_INDIVIDUAL_COMMIT_ANALYSIS is enabled"""
        service, mocks = service_with_mocks

        with patch("app.config.settings.settings.SKIP_INDIVIDUAL_COMMIT_ANALYSIS", True):
            # Configure basic mocks
            mocks["user_repo"].get_user_by_email.return_value = test_data["user"]
            mocks["daily_report_service"].get_user_report_for_date.return_value = None

            # Create minimal commit (no AI analysis)
            minimal_commit = Commit(
                commit_hash="abc123",
                author_id=test_data["user"].id,
                ai_estimated_hours=Decimal("0.0"),
                seniority_score=5,
                complexity_score=5,
                model_used="none (batch analysis mode)",
                commit_timestamp=datetime.now(timezone.utc),
            )
            mocks["commit_repo"].save_commit.return_value = minimal_commit

            # Execute
            commit_data = {
                "commit_hash": "abc123",
                "repository": "org/repo",
                "diff": "some diff content",
                "author": {"email": "test@example.com"},
                "timestamp": datetime.now(timezone.utc),
            }

            result = await service.analyze_commit("abc123", commit_data, fetch_diff=False)

            # Verify
            assert result is not None
            assert result.model_used == "none (batch analysis mode)"
            assert result.ai_estimated_hours == Decimal("0.0")

            # AI should not be called
            mocks["ai_integration"].analyze_commit_diff.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_handling_ai_failure(self, service_with_mocks, test_data):
        """Test handling of AI service failure"""
        service, mocks = service_with_mocks

        # Configure mocks
        mocks["github_integration"].get_commit_diff.return_value = test_data["diff_data"]
        mocks["ai_integration"].analyze_commit_diff.side_effect = Exception("AI service error")
        mocks["user_repo"].get_user_by_email.return_value = test_data["user"]

        # Execute
        commit_data = {
            "commit_hash": "abc123",
            "repository": "org/repo",
            "author": {"email": "test@example.com"},
            "timestamp": datetime.now(timezone.utc),
        }

        result = await service.analyze_commit("abc123", commit_data, fetch_diff=True)

        # Should handle error gracefully
        assert result is None

    @pytest.mark.asyncio
    async def test_eod_report_integration(self, service_with_mocks, test_data):
        """Test EOD report integration in commit analysis"""
        service, mocks = service_with_mocks

        # Configure mocks
        mocks["github_integration"].get_commit_diff.return_value = test_data["diff_data"]
        mocks["ai_integration"].analyze_commit_diff.return_value = test_data["ai_analysis"]
        mocks["user_repo"].get_user_by_email.return_value = test_data["user"]
        mocks["daily_report_service"].get_user_report_for_date.return_value = test_data["daily_report"]
        mocks["ai_integration"].analyze_commit_code_quality.return_value = {"quality_score": 8}

        # Create commit with EOD integration
        commit_with_eod = Commit(
            commit_hash="abc123",
            author_id=test_data["user"].id,
            ai_estimated_hours=Decimal("3.5"),
            eod_report_id=test_data["daily_report"].id,
            eod_report_summary=test_data["daily_report"].clarified_tasks_summary,
            comparison_notes="EOD report UUID(",
            commit_timestamp=datetime.now(timezone.utc),
        )
        mocks["commit_repo"].save_commit.return_value = commit_with_eod

        # Execute
        commit_data = {
            "commit_hash": "abc123",
            "repository": "org/repo",
            "author": {"email": "test@example.com"},
            "author_id": test_data["user"].id,
            "timestamp": datetime.now(timezone.utc),
        }

        result = await service.analyze_commit("abc123", commit_data, fetch_diff=True)

        # Verify
        assert result is not None
        assert result.eod_report_id == test_data["daily_report"].id
        assert result.eod_report_summary == test_data["daily_report"].clarified_tasks_summary
        assert "EOD report" in result.comparison_notes


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
