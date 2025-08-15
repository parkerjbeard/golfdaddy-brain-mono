"""
Unit tests for ProposalRepository.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.proposals import Proposal
from app.repositories.proposal_repository import ProposalRepository


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    session.add = Mock()
    session.delete = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def repository(mock_session):
    """Create a ProposalRepository instance with mock session."""
    return ProposalRepository(mock_session)


@pytest.fixture
def sample_proposal_data():
    """Sample proposal data for testing."""
    return {
        "commit": "abc123def456",
        "repo": "test-repo",
        "patch": "--- a/docs/api.md\n+++ b/docs/api.md\n@@ -1,3 +1,4 @@\n+# API Documentation\n",
        "targets": ["docs/api.md"],
        "status": "pending",
        "scores": {"relevance": 0.9, "accuracy": 0.85},
        "cost_cents": 15,
        "metadata": {"generated_by": "gpt-4"},
    }


@pytest.fixture
def sample_proposal():
    """Create a sample Proposal instance."""
    return Proposal(
        id=uuid4(),
        commit="abc123def456",
        repo="test-repo",
        patch="Sample patch content",
        targets=["docs/api.md"],
        status="pending",
        scores={"relevance": 0.9, "accuracy": 0.85},
        cost_cents=15,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


class TestProposalRepository:
    """Test cases for ProposalRepository."""

    @pytest.mark.asyncio
    async def test_create_proposal_success(self, repository, mock_session, sample_proposal_data):
        """Test successful proposal creation."""
        # Arrange
        mock_session.refresh.side_effect = lambda x: setattr(x, "id", uuid4())

        # Act
        result = await repository.create_proposal(sample_proposal_data)

        # Assert
        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_proposal_database_error(self, repository, mock_session, sample_proposal_data):
        """Test proposal creation with database error."""
        # Arrange
        mock_session.commit.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            await repository.create_proposal(sample_proposal_data)

        assert "Failed to create proposal" in str(exc_info.value)
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_proposal_by_id_found(self, repository, mock_session, sample_proposal):
        """Test getting proposal by ID when it exists."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_proposal
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.get_proposal_by_id(sample_proposal.id)

        # Assert
        assert result == sample_proposal
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_proposal_by_id_not_found(self, repository, mock_session):
        """Test getting proposal by ID when it doesn't exist."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        proposal_id = uuid4()

        # Act
        result = await repository.get_proposal_by_id(proposal_id)

        # Assert
        assert result is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_proposal_by_commit(self, repository, mock_session, sample_proposal):
        """Test getting proposal by commit and repo."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_proposal
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.get_proposal_by_commit("abc123def456", "test-repo")

        # Assert
        assert result == sample_proposal
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_proposals_by_status(self, repository, mock_session, sample_proposal):
        """Test getting proposals by status."""
        # Arrange
        proposals = [
            sample_proposal,
            Proposal(id=uuid4(), commit="xyz789", repo="test-repo", patch="Another patch", status="pending"),
        ]
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = proposals
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.get_proposals_by_status("pending", repo="test-repo")

        # Assert
        assert len(result) == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pending_proposals_with_age_filter(self, repository, mock_session):
        """Test getting pending proposals with age filter."""
        # Arrange
        recent_proposal = Proposal(
            id=uuid4(),
            commit="abc123",
            repo="test-repo",
            patch="Patch",
            status="pending",
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [recent_proposal]
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.get_pending_proposals(hours_old=2)

        # Assert
        assert len(result) == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_proposal_status_success(self, repository, mock_session, sample_proposal):
        """Test successful proposal status update."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_proposal
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.update_proposal_status(sample_proposal.id, "approved", {"approver": "user123"})

        # Assert
        assert result == sample_proposal
        assert sample_proposal.status == "approved"
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_proposal_status_not_found(self, repository, mock_session):
        """Test updating status of non-existent proposal."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        proposal_id = uuid4()

        # Act & Assert
        with pytest.raises(ResourceNotFoundError) as exc_info:
            await repository.update_proposal_status(proposal_id, "approved")

        assert "Proposal" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_proposal_scores(self, repository, mock_session, sample_proposal):
        """Test updating proposal scores."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_proposal
        mock_session.execute.return_value = mock_result
        new_scores = {"relevance": 0.95, "accuracy": 0.90, "completeness": 0.85}

        # Act
        result = await repository.update_proposal_scores(sample_proposal.id, new_scores)

        # Assert
        assert result == sample_proposal
        assert sample_proposal.scores == new_scores
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_expire_old_proposals(self, repository, mock_session):
        """Test expiring old proposals."""
        # Arrange
        mock_result = Mock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.expire_old_proposals(days=7)

        # Assert
        assert result == 3
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_proposal_statistics(self, repository, mock_session):
        """Test getting proposal statistics."""
        # Arrange
        # Mock status counts
        status_rows = [
            Mock(status="pending", count=5),
            Mock(status="approved", count=10),
            Mock(status="rejected", count=2),
        ]

        # Mock cost statistics
        cost_row = Mock(avg_cost=25.5, total_cost=433)

        # Mock approved proposals for score calculation
        approved_proposals = [
            Proposal(
                id=uuid4(),
                commit="abc",
                repo="test",
                patch="patch",
                status="approved",
                scores={"relevance": 0.9, "accuracy": 0.8},
            )
        ]

        mock_status_result = Mock()
        mock_status_result.__iter__ = Mock(return_value=iter(status_rows))

        mock_cost_result = Mock()
        mock_cost_result.one.return_value = cost_row

        mock_approved_result = Mock()
        mock_approved_result.scalars.return_value.all.return_value = approved_proposals

        mock_session.execute.side_effect = [mock_status_result, mock_cost_result, mock_approved_result]

        # Act
        result = await repository.get_proposal_statistics(repo="test-repo", days=30)

        # Assert
        assert result["total"] == 17
        assert result["by_status"]["approved"] == 10
        assert result["avg_cost_cents"] == 25.5
        assert result["total_cost_cents"] == 433
        assert result["avg_score"] > 0
        assert mock_session.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_delete_proposal_success(self, repository, mock_session, sample_proposal):
        """Test successful proposal deletion."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_proposal
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.delete_proposal(sample_proposal.id)

        # Assert
        assert result is True
        mock_session.delete.assert_called_once_with(sample_proposal)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_proposal_not_found(self, repository, mock_session):
        """Test deleting non-existent proposal."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        proposal_id = uuid4()

        # Act & Assert
        with pytest.raises(ResourceNotFoundError) as exc_info:
            await repository.delete_proposal(proposal_id)

        assert "Proposal" in str(exc_info.value)
