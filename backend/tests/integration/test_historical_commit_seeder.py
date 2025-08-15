import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.commit import Commit
from app.models.user import User, UserRole
from backend.scripts.seed_historical_commits import HistoricalCommitSeeder


@pytest.fixture
def mock_github_commits():
    """Fixture providing sample GitHub commit data."""
    return [
        {
            "sha": "abc123",
            "commit": {
                "message": "Add new feature",
                "author": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "date": datetime.now(timezone.utc).isoformat() + "Z",
                },
            },
        },
        {
            "sha": "def456",
            "commit": {
                "message": "Fix bug in module",
                "author": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "date": datetime.now(timezone.utc).isoformat() + "Z",
                },
            },
        },
        {
            "sha": "ghi789",
            "commit": {
                "message": "Update documentation",
                "author": {
                    "name": "Another User",
                    "email": "another@example.com",
                    "date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat() + "Z",
                },
            },
        },
    ]


@pytest.fixture
def mock_existing_commits():
    """Fixture providing existing commit data in the database."""
    return {
        "abc123": Commit(
            id=uuid4(),
            commit_hash="abc123",
            commit_message="Add new feature",
            repository_name="test/repo",
            author_email="test@example.com",
            author_id=uuid4(),
            lines_added=100,
            lines_deleted=20,
            changed_files=["feature.py"],
            ai_estimated_hours=Decimal("3.5"),
            complexity_score=7,
            risk_level="medium",
            seniority_score=8,
            ai_analysis_notes=json.dumps(
                {
                    "key_changes": ["Added new feature module"],
                    "seniority_rationale": "Complex implementation",
                    "model_used": "gpt-4o-mini",
                    "impact_score": 10.5,
                }
            ),
            commit_timestamp=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
    }


@pytest.mark.asyncio
async def test_seeder_with_existing_commits_check(mock_github_commits, mock_existing_commits):
    """Test that the seeder correctly handles existing commits when check_existing is True."""

    # Create seeder with check_existing enabled
    seeder = HistoricalCommitSeeder(github_token="fake_token", check_existing=True, max_concurrent=2)

    # Mock GitHub API responses
    with patch.object(seeder, "get_branches", return_value=["main"]):
        with patch.object(seeder, "get_commits_for_branch", return_value=mock_github_commits):
            with patch.object(seeder, "get_commit_details") as mock_details:
                mock_details.return_value = {
                    "author": {"login": "testuser"},
                    "files": [{"filename": "test.py", "additions": 50, "deletions": 10}],
                    "html_url": "https://github.com/test/repo/commit/abc123",
                }

                with patch.object(seeder, "get_commit_diff", return_value="diff content"):
                    # Mock commit repository methods
                    with patch.object(seeder.commit_repo, "get_existing_commit_hashes") as mock_check:
                        with patch.object(seeder.commit_repo, "get_commits_with_analysis") as mock_get:
                            # Configure mocks
                            mock_check.return_value = ["abc123"]  # First commit already exists
                            mock_get.return_value = mock_existing_commits

                            # Mock the commit analyzer for new commits
                            with patch.object(
                                seeder.commit_analyzer, "analyze_commit_traditional_only"
                            ) as mock_analyze:
                                mock_analyze.return_value = {
                                    "estimated_hours": 2.0,
                                    "complexity_score": 5,
                                    "risk_level": "low",
                                    "seniority_score": 6,
                                    "key_changes": ["Fixed bug"],
                                    "seniority_rationale": "Standard bug fix",
                                }

                                # Mock user creation/retrieval
                                with patch.object(seeder, "get_or_create_user") as mock_user:
                                    mock_user.return_value = User(
                                        id=uuid4(),
                                        email="test@example.com",
                                        name="Test User",
                                        github_username="testuser",
                                        role=UserRole.EMPLOYEE,
                                    )

                                    # Mock database storage
                                    with patch.object(seeder, "store_daily_analysis") as mock_store:
                                        # Run the seeder
                                        results = await seeder.seed_repository(
                                            repository="test/repo", days=7, single_branch=True, dry_run=False
                                        )

    # Verify statistics
    assert seeder.stats["existing_commits"] == 1
    assert seeder.stats["reused_analyses"] == 1
    assert seeder.stats["fresh_analyses"] >= 1  # At least def456 should be analyzed

    # Verify results structure
    assert results["repository"] == "test/repo"
    assert "analysis_statistics" in results["summary"]
    stats = results["summary"]["analysis_statistics"]
    assert stats["existing_commits_found"] == 1
    assert stats["analyses_reused"] == 1
    assert stats["check_existing_enabled"] is True


@pytest.mark.asyncio
async def test_seeder_without_existing_commits_check():
    """Test that the seeder analyzes all commits when check_existing is False."""

    # Create seeder with check_existing disabled
    seeder = HistoricalCommitSeeder(github_token="fake_token", check_existing=False, max_concurrent=2)

    mock_commits = [
        {
            "sha": "commit1",
            "commit": {
                "message": "Test commit 1",
                "author": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "date": datetime.now(timezone.utc).isoformat() + "Z",
                },
            },
        }
    ]

    # Mock GitHub API responses
    with patch.object(seeder, "get_branches", return_value=["main"]):
        with patch.object(seeder, "get_commits_for_branch", return_value=mock_commits):
            with patch.object(seeder, "analyze_single_commit") as mock_analyze_single:
                mock_analyze_single.return_value = {
                    "commit_hash": "commit1",
                    "estimated_hours": 1.5,
                    "complexity_score": 4,
                }

                # Mock user creation
                with patch.object(seeder, "get_or_create_user") as mock_user:
                    mock_user.return_value = User(
                        id=uuid4(), email="test@example.com", name="Test User", role=UserRole.EMPLOYEE
                    )

                    # Mock database storage
                    with patch.object(seeder, "store_daily_analysis"):
                        # Run the seeder
                        results = await seeder.seed_repository(
                            repository="test/repo", days=1, single_branch=True, dry_run=False
                        )

    # Verify that commit repository methods were NOT called
    assert (
        not hasattr(seeder.commit_repo, "get_existing_commit_hashes")
        or not seeder.commit_repo.get_existing_commit_hashes.called
    )

    # Verify statistics show no existing commits
    assert seeder.stats["existing_commits"] == 0
    assert seeder.stats["reused_analyses"] == 0

    # Verify results
    stats = results["summary"]["analysis_statistics"]
    assert stats["check_existing_enabled"] is False


@pytest.mark.asyncio
async def test_seeder_statistics_tracking():
    """Test that the seeder correctly tracks various statistics."""

    seeder = HistoricalCommitSeeder(github_token="fake_token", check_existing=True, max_concurrent=1)

    # Create a mix of commits
    mock_commits = [
        {
            "sha": f"commit{i}",
            "commit": {
                "message": f"Commit {i}",
                "author": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "date": datetime.now(timezone.utc).isoformat() + "Z",
                },
            },
        }
        for i in range(5)
    ]

    with patch.object(seeder, "get_branches", return_value=["main"]):
        with patch.object(seeder, "get_commits_for_branch", return_value=mock_commits):
            # Mock that commits 0 and 1 already exist
            with patch.object(seeder.commit_repo, "get_existing_commit_hashes") as mock_check:
                mock_check.return_value = ["commit0", "commit1"]

                with patch.object(seeder.commit_repo, "get_commits_with_analysis") as mock_get:
                    # Return existing commits
                    mock_get.return_value = {"commit0": MagicMock(spec=Commit), "commit1": MagicMock(spec=Commit)}

                    # Mock successful analysis for new commits
                    with patch.object(seeder, "analyze_single_commit") as mock_analyze:
                        mock_analyze.side_effect = [
                            {"commit_hash": "commit2", "estimated_hours": 1.0},
                            {"commit_hash": "commit3", "estimated_hours": 2.0},
                            None,  # commit4 fails
                        ]

                        with patch.object(seeder, "get_or_create_user"):
                            with patch.object(seeder, "store_daily_analysis"):
                                results = await seeder.seed_repository(
                                    repository="test/repo", days=1, single_branch=True, dry_run=False
                                )

    # Verify final statistics
    stats = results["summary"]["analysis_statistics"]
    assert stats["total_commits_processed"] == 5
    assert stats["existing_commits_found"] == 2
    assert stats["new_commits_found"] == 3
    assert stats["analyses_reused"] == 2
    assert stats["fresh_analyses_performed"] == 2  # commit2 and commit3
    # Note: failed_analyses might not increment if analyze_single_commit returns None


@pytest.mark.asyncio
async def test_convert_commit_to_analysis_integration():
    """Integration test for converting database commits to analysis format."""

    seeder = HistoricalCommitSeeder(check_existing=True)

    # Create a commit with comprehensive data
    commit = Commit(
        id=uuid4(),
        commit_hash="integration_test",
        commit_message="Integration test commit",
        commit_url="https://github.com/test/repo/commit/integration_test",
        repository_name="test/repo",
        author_email="test@example.com",
        author_id=uuid4(),
        lines_added=150,
        lines_deleted=75,
        changed_files=["file1.py", "file2.py", "file3.py"],
        ai_estimated_hours=Decimal("5.5"),
        complexity_score=8,
        risk_level="high",
        seniority_score=9,
        key_changes=["Major refactoring", "API redesign"],
        seniority_rationale="Requires deep architectural knowledge",
        model_used="gpt-4",
        analyzed_at=datetime.now(timezone.utc),
        ai_analysis_notes=json.dumps(
            {
                "key_changes": ["Major refactoring", "API redesign", "Performance optimization"],
                "seniority_rationale": "Requires deep architectural knowledge and system design skills",
                "model_used": "gpt-4",
                "impact_score": 15.5,
                "impact_classification": "major_feature",
                "impact_business_value": 5,
                "impact_technical_complexity": 5,
                "impact_code_quality_points": 3,
                "impact_risk_penalty": -2.5,
                "additional_metadata": {"review_required": True, "estimated_review_time": 2.0},
            }
        ),
        commit_timestamp=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )

    # Convert to analysis format
    analysis = seeder._convert_commit_to_analysis(commit)

    # Comprehensive assertions
    assert analysis["commit_hash"] == "integration_test"
    assert analysis["estimated_hours"] == 5.5
    assert analysis["complexity_score"] == 8
    assert analysis["risk_level"] == "high"
    assert analysis["seniority_score"] == 9
    assert analysis["from_existing"] is True

    # Check that data from ai_analysis_notes overrides direct fields
    assert len(analysis["key_changes"]) == 3  # From JSON, not from direct field
    assert "Performance optimization" in analysis["key_changes"]

    # Check impact data
    assert analysis["impact_score"] == 15.5
    assert analysis["impact_classification"] == "major_feature"
    assert analysis["impact_business_value"] == 5
    assert analysis["impact_technical_complexity"] == 5

    # Check metadata preservation
    assert "seniority_rationale" in analysis
    assert "system design skills" in analysis["seniority_rationale"]
