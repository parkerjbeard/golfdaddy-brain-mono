"""
Comprehensive tests for Deduplication Service
"""
import pytest
from datetime import datetime, timezone, timedelta, date
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal

from app.services.deduplication_service import (
    DeduplicationService,
    DeduplicationRule,
    DeduplicationResult,
    WorkType
)
from app.models.commit import Commit
from app.models.daily_report import DailyReport
from app.models.user import User, UserRole


@pytest.fixture
def mock_commit_repo():
    return Mock()


@pytest.fixture
def mock_daily_report_repo():
    return Mock()


@pytest.fixture
def mock_ai_integration():
    return Mock()


@pytest.fixture
def deduplication_service(mock_commit_repo, mock_daily_report_repo, mock_ai_integration):
    service = DeduplicationService()
    service.commit_repo = mock_commit_repo
    service.daily_report_repo = mock_daily_report_repo
    service.ai_integration = mock_ai_integration
    return service


@pytest.fixture
def sample_user():
    return User(
        id=uuid4(),
        email="developer@test.com",
        name="Test Developer",
        role=UserRole.DEVELOPER,
        is_active=True
    )


@pytest.fixture
def sample_commits():
    """Create sample commits with various scenarios"""
    base_time = datetime.now(timezone.utc)
    user_id = uuid4()
    
    return [
        Commit(
            id=uuid4(),
            repository="test/repo",
            commit_hash="abc123",
            message="feat: implement user authentication",
            author_email="dev@test.com",
            commit_date=base_time - timedelta(hours=6),
            estimated_hours=3.0,
            estimated_points=5,
            user_id=user_id,
            files_changed=["auth.py", "login.py"],
            analysis={
                "complexity": "medium",
                "impact_areas": ["authentication", "security"]
            }
        ),
        Commit(
            id=uuid4(),
            repository="test/repo",
            commit_hash="def456",
            message="fix: resolve login bug",
            author_email="dev@test.com",
            commit_date=base_time - timedelta(hours=4),
            estimated_hours=1.5,
            estimated_points=2,
            user_id=user_id,
            files_changed=["login.py"],
            analysis={
                "complexity": "low",
                "impact_areas": ["authentication"]
            }
        ),
        Commit(
            id=uuid4(),
            repository="test/repo",
            commit_hash="ghi789",
            message="docs: update README",
            author_email="dev@test.com",
            commit_date=base_time - timedelta(hours=2),
            estimated_hours=0.5,
            estimated_points=1,
            user_id=user_id,
            files_changed=["README.md"],
            analysis={
                "complexity": "trivial",
                "impact_areas": ["documentation"]
            }
        )
    ]


@pytest.fixture
def sample_daily_report():
    return DailyReport(
        id=uuid4(),
        user_id=uuid4(),
        date=date.today(),
        content="Worked on user authentication feature and fixed login bugs. Also updated documentation.",
        hours_worked=8.0,
        key_achievements=["Implemented authentication", "Fixed login bug", "Updated docs"],
        blockers=[],
        sentiment_score=0.8,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


class TestDeduplicationService:
    """Test cases for DeduplicationService"""

    @pytest.mark.asyncio
    async def test_find_duplicates_high_confidence(self, deduplication_service, mock_ai_integration, sample_commits, sample_daily_report):
        """Test finding duplicates with high confidence matches"""
        # Arrange
        mock_ai_integration.calculate_semantic_similarity = AsyncMock(side_effect=[
            0.95,  # High similarity for auth commit
            0.85,  # High similarity for bug fix
            0.3    # Low similarity for docs
        ])
        
        # Act
        result = await deduplication_service.find_duplicates(
            commits=sample_commits,
            daily_report=sample_daily_report
        )
        
        # Assert
        assert len(result.duplicates) == 2  # Two high-confidence matches
        assert result.total_commit_hours == 5.0  # 3.0 + 1.5 + 0.5
        assert result.deduplicated_hours == 4.5  # 3.0 + 1.5 (high confidence)
        assert result.additional_hours == 3.5  # 8.0 - 4.5
        assert result.confidence_score >= 0.8  # High overall confidence

    @pytest.mark.asyncio
    async def test_find_duplicates_no_matches(self, deduplication_service, mock_ai_integration, sample_commits):
        """Test when no duplicates are found"""
        # Arrange
        report = DailyReport(
            id=uuid4(),
            user_id=uuid4(),
            date=date.today(),
            content="Worked on completely different tasks - data migration and database optimization",
            hours_worked=6.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        mock_ai_integration.calculate_semantic_similarity = AsyncMock(return_value=0.2)  # Low similarity
        
        # Act
        result = await deduplication_service.find_duplicates(
            commits=sample_commits,
            daily_report=report
        )
        
        # Assert
        assert len(result.duplicates) == 0
        assert result.deduplicated_hours == 0.0
        assert result.additional_hours == 6.0  # All hours are additional
        assert result.confidence_score == 1.0  # High confidence in no duplicates

    @pytest.mark.asyncio
    async def test_apply_deduplication_rules(self, deduplication_service):
        """Test application of various deduplication rules"""
        # Test exact match rule
        rule = DeduplicationRule(
            pattern="implement user authentication",
            work_type=WorkType.FEATURE,
            confidence_boost=0.2
        )
        
        # Test with matching content
        confidence = deduplication_service._apply_rules(
            commit_message="feat: implement user authentication",
            report_content="Worked on implementing user authentication",
            base_confidence=0.7
        )
        assert confidence > 0.7  # Should be boosted
        
        # Test with non-matching content
        confidence = deduplication_service._apply_rules(
            commit_message="fix: resolve bug",
            report_content="Updated documentation",
            base_confidence=0.3
        )
        assert confidence == 0.3  # No boost

    @pytest.mark.asyncio
    async def test_deduplication_with_time_correlation(self, deduplication_service, mock_ai_integration):
        """Test that time correlation affects confidence"""
        # Arrange
        now = datetime.now(timezone.utc)
        user_id = uuid4()
        
        # Commit from today
        recent_commit = Commit(
            id=uuid4(),
            commit_hash="recent",
            message="feat: add feature",
            commit_date=now - timedelta(hours=2),
            estimated_hours=2.0,
            user_id=user_id
        )
        
        # Commit from yesterday
        old_commit = Commit(
            id=uuid4(),
            commit_hash="old",
            message="feat: add feature",
            commit_date=now - timedelta(days=1, hours=2),
            estimated_hours=2.0,
            user_id=user_id
        )
        
        report = DailyReport(
            id=uuid4(),
            user_id=user_id,
            date=date.today(),
            content="Added new feature",
            hours_worked=2.0,
            created_at=now,
            updated_at=now
        )
        
        mock_ai_integration.calculate_semantic_similarity = AsyncMock(return_value=0.8)
        
        # Act
        result_recent = await deduplication_service.find_duplicates([recent_commit], report)
        result_old = await deduplication_service.find_duplicates([old_commit], report)
        
        # Assert
        # Recent commit should have higher confidence due to time proximity
        assert len(result_recent.duplicates) == 1
        assert len(result_old.duplicates) == 0  # Old commit filtered out due to date mismatch

    @pytest.mark.asyncio
    async def test_weekly_aggregation(self, deduplication_service, mock_commit_repo, mock_daily_report_repo, sample_user):
        """Test weekly hours aggregation with deduplication"""
        # Arrange
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        
        # Mock commits for the week
        commits = [
            Commit(
                id=uuid4(),
                commit_hash=f"commit{i}",
                message=f"feat: feature {i}",
                commit_date=datetime.now(timezone.utc) - timedelta(days=i),
                estimated_hours=2.0,
                user_id=sample_user.id
            )
            for i in range(5)
        ]
        
        # Mock daily reports for the week
        reports = [
            DailyReport(
                id=uuid4(),
                user_id=sample_user.id,
                date=start_date + timedelta(days=i),
                content=f"Worked on feature {i} and other tasks",
                hours_worked=8.0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            for i in range(5)
        ]
        
        mock_commit_repo.get_commits_by_user_date_range.return_value = commits
        mock_daily_report_repo.get_by_user_date_range.return_value = reports
        
        # Mock deduplication results
        with patch.object(deduplication_service, 'find_duplicates', new_callable=AsyncMock) as mock_find_duplicates:
            mock_find_duplicates.return_value = DeduplicationResult(
                duplicates=[{
                    "commit_id": str(commits[0].id),
                    "confidence": 0.9,
                    "hours_duplicated": 2.0
                }],
                total_commit_hours=2.0,
                deduplicated_hours=2.0,
                additional_hours=6.0,
                confidence_score=0.9
            )
            
            # Act
            result = await deduplication_service.get_weekly_aggregated_hours(
                user_id=sample_user.id,
                start_date=start_date,
                end_date=end_date
            )
        
        # Assert
        assert result["total_commit_hours"] == 10.0  # 5 commits * 2 hours
        assert result["total_report_hours"] == 40.0  # 5 reports * 8 hours
        assert result["deduplicated_hours"] == 10.0  # 5 * 2.0 dedup hours
        assert result["total_unique_hours"] == 40.0  # 10 + (40 - 10)
        assert len(result["daily_breakdown"]) == 5

    @pytest.mark.asyncio
    async def test_deduplication_result_persistence(self, deduplication_service, mock_daily_report_repo):
        """Test that deduplication results are saved"""
        # Arrange
        report_id = uuid4()
        result = DeduplicationResult(
            duplicates=[{
                "commit_id": str(uuid4()),
                "confidence": 0.85,
                "hours_duplicated": 3.0
            }],
            total_commit_hours=5.0,
            deduplicated_hours=3.0,
            additional_hours=5.0,
            confidence_score=0.85
        )
        
        mock_daily_report_repo.save_deduplication_result = AsyncMock()
        
        # Act
        await deduplication_service.save_deduplication_result(report_id, result)
        
        # Assert
        mock_daily_report_repo.save_deduplication_result.assert_called_once_with(
            report_id=report_id,
            result=result
        )

    @pytest.mark.asyncio
    async def test_handle_empty_inputs(self, deduplication_service):
        """Test handling of empty commits or reports"""
        # Test with empty commits list
        report = DailyReport(
            id=uuid4(),
            user_id=uuid4(),
            date=date.today(),
            content="Did some work",
            hours_worked=8.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        result = await deduplication_service.find_duplicates([], report)
        assert result.total_commit_hours == 0.0
        assert result.additional_hours == 8.0
        assert len(result.duplicates) == 0

    @pytest.mark.asyncio
    async def test_ai_similarity_error_handling(self, deduplication_service, mock_ai_integration, sample_commits, sample_daily_report):
        """Test handling of AI service errors"""
        # Arrange
        mock_ai_integration.calculate_semantic_similarity = AsyncMock(
            side_effect=Exception("AI service unavailable")
        )
        
        # Act
        result = await deduplication_service.find_duplicates(
            commits=sample_commits,
            daily_report=sample_daily_report
        )
        
        # Assert - Should fall back to rule-based matching
        assert result is not None
        assert result.confidence_score < 1.0  # Lower confidence due to AI failure

    @pytest.mark.asyncio
    async def test_complex_deduplication_scenario(self, deduplication_service, mock_ai_integration):
        """Test complex scenario with multiple work types"""
        # Arrange
        commits = [
            Commit(
                id=uuid4(),
                commit_hash="feat1",
                message="feat: implement dashboard",
                commit_date=datetime.now(timezone.utc) - timedelta(hours=5),
                estimated_hours=4.0,
                user_id=uuid4()
            ),
            Commit(
                id=uuid4(),
                commit_hash="fix1",
                message="fix: resolve dashboard rendering issue",
                commit_date=datetime.now(timezone.utc) - timedelta(hours=3),
                estimated_hours=1.0,
                user_id=uuid4()
            ),
            Commit(
                id=uuid4(),
                commit_hash="test1",
                message="test: add dashboard tests",
                commit_date=datetime.now(timezone.utc) - timedelta(hours=1),
                estimated_hours=2.0,
                user_id=uuid4()
            )
        ]
        
        report = DailyReport(
            id=uuid4(),
            user_id=uuid4(),
            date=date.today(),
            content="""
            Completed dashboard implementation including:
            - Built main dashboard component
            - Fixed rendering issues that were blocking users
            - Added comprehensive test coverage
            - Reviewed PRs and helped team members
            """,
            hours_worked=9.0,  # More than commit hours
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Mock varying similarities
        mock_ai_integration.calculate_semantic_similarity = AsyncMock(side_effect=[
            0.9,   # High match for dashboard feature
            0.85,  # High match for bug fix
            0.8    # Good match for tests
        ])
        
        # Act
        result = await deduplication_service.find_duplicates(commits, report)
        
        # Assert
        assert len(result.duplicates) == 3  # All commits matched
        assert result.total_commit_hours == 7.0  # 4 + 1 + 2
        assert result.deduplicated_hours == 7.0  # All matched
        assert result.additional_hours == 2.0  # 9 - 7 (PR reviews, helping team)
        assert result.confidence_score > 0.8  # High confidence overall