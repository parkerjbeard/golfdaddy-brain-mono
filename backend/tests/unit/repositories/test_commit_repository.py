import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import DatabaseError
from app.models.commit import Commit
from app.repositories.commit_repository import CommitRepository


@pytest.fixture
def mock_supabase_client():
    """Fixture to provide a mocked Supabase client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def sample_commit():
    """Fixture to provide a sample commit object."""
    return Commit(
        id=uuid4(),
        commit_hash="abc123def456",
        author_id=uuid4(),
        repository_name="test/repo",
        repository_url="https://github.com/test/repo",
        commit_message="Test commit message",
        commit_url="https://github.com/test/repo/commit/abc123def456",
        author_github_username="testuser",
        author_email="test@example.com",
        lines_added=100,
        lines_deleted=50,
        changed_files=["file1.py", "file2.py"],
        complexity_score=5,
        risk_level="medium",
        ai_estimated_hours=Decimal("2.5"),
        seniority_score=7,
        commit_timestamp=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_get_existing_commit_hashes_empty_list(mock_supabase_client):
    """Test checking for existing commits with empty input list."""
    repo = CommitRepository(client=mock_supabase_client)

    # Act
    result = await repo.get_existing_commit_hashes([])

    # Assert
    assert result == []
    mock_supabase_client.table.assert_not_called()


@pytest.mark.asyncio
async def test_get_existing_commit_hashes_single_batch(mock_supabase_client):
    """Test checking for existing commits with a small list (single batch)."""
    repo = CommitRepository(client=mock_supabase_client)

    commit_hashes = ["hash1", "hash2", "hash3"]

    # Configure mock response
    mock_response = MagicMock()
    mock_response.data = [{"commit_hash": "hash1"}, {"commit_hash": "hash3"}]

    mock_supabase_client.table.return_value.select.return_value.in_.return_value.execute = MagicMock(
        return_value=mock_response
    )

    # Act
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = mock_response
        result = await repo.get_existing_commit_hashes(commit_hashes)

    # Assert
    assert set(result) == {"hash1", "hash3"}
    mock_supabase_client.table.assert_called_once_with("commits")
    mock_supabase_client.table.return_value.select.assert_called_once_with("commit_hash")


@pytest.mark.asyncio
async def test_get_existing_commit_hashes_multiple_batches(mock_supabase_client):
    """Test checking for existing commits with a large list (multiple batches)."""
    repo = CommitRepository(client=mock_supabase_client)

    # Create a list of 250 commit hashes (should result in 3 batches of 100 each)
    commit_hashes = [f"hash{i}" for i in range(250)]

    # Configure mock responses for each batch
    batch1_response = MagicMock()
    batch1_response.data = [{"commit_hash": f"hash{i}"} for i in range(0, 50, 2)]  # Even numbers 0-98

    batch2_response = MagicMock()
    batch2_response.data = [{"commit_hash": f"hash{i}"} for i in range(100, 150, 3)]  # Every 3rd from 100-149

    batch3_response = MagicMock()
    batch3_response.data = [{"commit_hash": f"hash{i}"} for i in range(200, 210)]  # 200-209

    # Set up mock to return different responses for each call
    responses = [batch1_response, batch2_response, batch3_response]

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = responses
        result = await repo.get_existing_commit_hashes(commit_hashes)

    # Assert
    expected_hashes = (
        [f"hash{i}" for i in range(0, 50, 2)]
        + [f"hash{i}" for i in range(100, 150, 3)]
        + [f"hash{i}" for i in range(200, 210)]
    )
    assert len(result) == len(expected_hashes)
    assert set(result) == set(expected_hashes)


@pytest.mark.asyncio
async def test_get_commits_with_analysis_empty_list(mock_supabase_client):
    """Test fetching commits with analysis for empty input list."""
    repo = CommitRepository(client=mock_supabase_client)

    # Act
    result = await repo.get_commits_with_analysis([])

    # Assert
    assert result == {}
    mock_supabase_client.table.assert_not_called()


@pytest.mark.asyncio
async def test_get_commits_with_analysis_success(mock_supabase_client, sample_commit):
    """Test successfully fetching commits with their analysis data."""
    repo = CommitRepository(client=mock_supabase_client)

    commit_hashes = ["abc123def456", "xyz789ghi012"]

    # Configure mock response
    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": str(sample_commit.id),
            "commit_hash": "abc123def456",
            "author_id": str(sample_commit.author_id),
            "repository_name": sample_commit.repository_name,
            "commit_message": sample_commit.commit_message,
            "lines_added": sample_commit.lines_added,
            "lines_deleted": sample_commit.lines_deleted,
            "changed_files": sample_commit.changed_files,
            "complexity_score": sample_commit.complexity_score,
            "risk_level": sample_commit.risk_level,
            "ai_estimated_hours": "2.5",
            "seniority_score": sample_commit.seniority_score,
            "commit_timestamp": sample_commit.commit_timestamp.isoformat(),
            "created_at": sample_commit.created_at.isoformat(),
            "updated_at": sample_commit.updated_at.isoformat(),
            "ai_analysis_notes": json.dumps(
                {
                    "key_changes": ["Added feature X", "Fixed bug Y"],
                    "seniority_rationale": "Complex architectural changes",
                    "impact_score": 8.5,
                    "impact_classification": "feature",
                }
            ),
        }
    ]

    mock_supabase_client.table.return_value.select.return_value.in_.return_value.execute = MagicMock(
        return_value=mock_response
    )

    # Act
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = mock_response
        result = await repo.get_commits_with_analysis(commit_hashes)

    # Assert
    assert len(result) == 1
    assert "abc123def456" in result
    commit = result["abc123def456"]
    assert commit.commit_hash == "abc123def456"
    assert commit.ai_estimated_hours == Decimal("2.5")
    assert commit.seniority_score == sample_commit.seniority_score


@pytest.mark.asyncio
async def test_get_commits_with_analysis_with_decimal_conversion(mock_supabase_client):
    """Test fetching commits with decimal conversion for ai_estimated_hours."""
    repo = CommitRepository(client=mock_supabase_client)

    commit_hashes = ["test_hash"]

    # Configure mock response with string value for ai_estimated_hours
    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": str(uuid4()),
            "commit_hash": "test_hash",
            "author_id": str(uuid4()),
            "repository_name": "test/repo",
            "commit_message": "Test",
            "ai_estimated_hours": "3.14159",  # Will be rounded to 3.1
            "commit_timestamp": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    mock_supabase_client.table.return_value.select.return_value.in_.return_value.execute = MagicMock(
        return_value=mock_response
    )

    # Act
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = mock_response
        result = await repo.get_commits_with_analysis(commit_hashes)

    # Assert
    assert len(result) == 1
    assert "test_hash" in result
    commit = result["test_hash"]
    assert commit.ai_estimated_hours == Decimal("3.1")  # Should be rounded


@pytest.mark.asyncio
async def test_get_existing_commit_hashes_database_error(mock_supabase_client):
    """Test handling database error when checking for existing commits."""
    repo = CommitRepository(client=mock_supabase_client)

    commit_hashes = ["hash1", "hash2"]

    # Configure mock to raise an exception
    mock_supabase_client.table.return_value.select.return_value.in_.return_value.execute.side_effect = Exception(
        "Database connection failed"
    )

    # Act & Assert
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = Exception("Database connection failed")
        with pytest.raises(DatabaseError) as exc_info:
            await repo.get_existing_commit_hashes(commit_hashes)

        assert "Unexpected error checking commit existence" in str(exc_info.value)


@pytest.mark.asyncio
async def test_convert_commit_to_analysis_from_seeder():
    """Test the _convert_commit_to_analysis method from the seeder script."""
    from backend.scripts.seed_historical_commits import HistoricalCommitSeeder

    seeder = HistoricalCommitSeeder(check_existing=True)

    # Create a sample commit with AI analysis notes
    commit = Commit(
        id=uuid4(),
        commit_hash="test123",
        commit_message="Test commit",
        commit_url="https://github.com/test/repo/commit/test123",
        commit_timestamp=datetime.now(timezone.utc),
        lines_added=50,
        lines_deleted=20,
        changed_files=["file1.py", "file2.py"],
        ai_estimated_hours=Decimal("3.5"),
        complexity_score=7,
        risk_level="high",
        seniority_score=8,
        ai_analysis_notes=json.dumps(
            {
                "key_changes": ["Added new feature", "Refactored module"],
                "seniority_rationale": "Complex refactoring requiring deep knowledge",
                "model_used": "gpt-4o-mini",
                "impact_score": 12.5,
                "impact_classification": "enhancement",
                "impact_business_value": 4,
                "impact_technical_complexity": 5,
            }
        ),
        created_at=datetime.now(timezone.utc),
    )

    # Act
    analysis = seeder._convert_commit_to_analysis(commit)

    # Assert
    assert analysis["commit_hash"] == "test123"
    assert analysis["estimated_hours"] == 3.5
    assert analysis["complexity_score"] == 7
    assert analysis["seniority_score"] == 8
    assert analysis["from_existing"] is True
    assert analysis["key_changes"] == ["Added new feature", "Refactored module"]
    assert analysis["impact_score"] == 12.5
    assert analysis["impact_classification"] == "enhancement"
    assert analysis["impact_business_value"] == 4
    assert analysis["impact_technical_complexity"] == 5


@pytest.mark.asyncio
async def test_convert_commit_to_analysis_malformed_json():
    """Test the _convert_commit_to_analysis method with malformed JSON in ai_analysis_notes."""
    from backend.scripts.seed_historical_commits import HistoricalCommitSeeder

    seeder = HistoricalCommitSeeder(check_existing=True)

    # Create a commit with malformed JSON in ai_analysis_notes
    commit = Commit(
        id=uuid4(),
        commit_hash="test456",
        commit_message="Test commit",
        commit_timestamp=datetime.now(timezone.utc),
        ai_estimated_hours=Decimal("2.0"),
        complexity_score=5,
        ai_analysis_notes="This is not valid JSON",  # Malformed JSON
        created_at=datetime.now(timezone.utc),
    )

    # Act
    analysis = seeder._convert_commit_to_analysis(commit)

    # Assert
    assert analysis["commit_hash"] == "test456"
    assert analysis["estimated_hours"] == 2.0
    assert analysis["from_existing"] is True
    # Should handle malformed JSON gracefully
    assert "key_changes" in analysis
    assert isinstance(analysis["key_changes"], list)
