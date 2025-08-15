"""
Unit tests for DocChunkRepository.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import numpy as np
import pytest

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.doc_chunks import DocChunk
from app.repositories.doc_chunk_repository import DocChunkRepository


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    session.add = Mock()
    session.add_all = Mock()
    session.delete = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def repository(mock_session):
    """Create a DocChunkRepository instance with mock session."""
    return DocChunkRepository(mock_session)


@pytest.fixture
def sample_chunk_data():
    """Sample chunk data for testing."""
    return {
        "repo": "test-repo",
        "path": "docs/api.md",
        "heading": "API Documentation",
        "order_key": 1,
        "content": "This is the API documentation content.",
        "embedding": [0.1] * 3072,  # Mock embedding
    }


@pytest.fixture
def sample_chunk():
    """Create a sample DocChunk instance."""
    return DocChunk(
        id=uuid4(),
        repo="test-repo",
        path="docs/api.md",
        heading="API Documentation",
        order_key=1,
        content="This is the API documentation content.",
        embedding=[0.1] * 3072,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


class TestDocChunkRepository:
    """Test cases for DocChunkRepository."""

    @pytest.mark.asyncio
    async def test_create_chunk_success(self, repository, mock_session, sample_chunk_data):
        """Test successful chunk creation."""
        # Arrange
        mock_chunk = DocChunk(**sample_chunk_data)
        mock_session.refresh.side_effect = lambda x: setattr(x, "id", uuid4())

        # Act
        result = await repository.create_chunk(sample_chunk_data)

        # Assert
        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_chunk_database_error(self, repository, mock_session, sample_chunk_data):
        """Test chunk creation with database error."""
        # Arrange
        mock_session.commit.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(DatabaseError) as exc_info:
            await repository.create_chunk(sample_chunk_data)

        assert "Failed to create doc chunk" in str(exc_info.value)
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_create_chunks_success(self, repository, mock_session, sample_chunk_data):
        """Test successful bulk chunk creation."""
        # Arrange
        chunks_data = [sample_chunk_data, {**sample_chunk_data, "order_key": 2}]

        # Act
        result = await repository.bulk_create_chunks(chunks_data)

        # Assert
        assert len(result) == 2
        mock_session.add_all.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_create_chunks_empty_list(self, repository, mock_session):
        """Test bulk creation with empty list."""
        # Act
        result = await repository.bulk_create_chunks([])

        # Assert
        assert result == []
        mock_session.add_all.assert_not_called()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_chunk_by_id_found(self, repository, mock_session, sample_chunk):
        """Test getting chunk by ID when it exists."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_chunk
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.get_chunk_by_id(sample_chunk.id)

        # Assert
        assert result == sample_chunk
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_chunk_by_id_not_found(self, repository, mock_session):
        """Test getting chunk by ID when it doesn't exist."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        chunk_id = uuid4()

        # Act
        result = await repository.get_chunk_by_id(chunk_id)

        # Assert
        assert result is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_chunks_by_document(self, repository, mock_session, sample_chunk):
        """Test getting chunks by document."""
        # Arrange
        chunks = [sample_chunk, DocChunk(**{**sample_chunk.__dict__, "id": uuid4(), "order_key": 2})]
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = chunks
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.get_chunks_by_document("test-repo", "docs/api.md")

        # Assert
        assert len(result) == 2
        assert result[0] == chunks[0]
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_similar_chunks(self, repository, mock_session):
        """Test searching for similar chunks."""
        # Arrange
        embedding = [0.2] * 3072
        mock_rows = [
            Mock(id=uuid4(), repo="test-repo", path="docs/api.md", heading="API", content="Content", similarity=0.85)
        ]
        mock_session.execute.return_value = mock_rows

        # Act
        result = await repository.search_similar_chunks(embedding=embedding, repo="test-repo", limit=5, threshold=0.7)

        # Assert
        assert len(result) == 1
        assert result[0]["similarity"] == 0.85
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_chunk_success(self, repository, mock_session, sample_chunk):
        """Test successful chunk update."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_chunk
        mock_session.execute.return_value = mock_result
        update_data = {"content": "Updated content"}

        # Act
        result = await repository.update_chunk(sample_chunk.id, update_data)

        # Assert
        assert result == sample_chunk
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_chunk_not_found(self, repository, mock_session):
        """Test updating non-existent chunk."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        chunk_id = uuid4()

        # Act & Assert
        with pytest.raises(ResourceNotFoundError) as exc_info:
            await repository.update_chunk(chunk_id, {"content": "Updated"})

        assert "DocChunk" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_chunk_success(self, repository, mock_session, sample_chunk):
        """Test successful chunk deletion."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_chunk
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.delete_chunk(sample_chunk.id)

        # Assert
        assert result is True
        mock_session.delete.assert_called_once_with(sample_chunk)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document_chunks(self, repository, mock_session):
        """Test deleting all chunks for a document."""
        # Arrange
        mock_result = Mock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.delete_document_chunks("test-repo", "docs/api.md")

        # Assert
        assert result == 5
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_chunks_success(self, repository, mock_session, sample_chunk_data):
        """Test upserting chunks."""
        # Arrange
        chunks_data = [sample_chunk_data, {**sample_chunk_data, "order_key": 2}]

        # Mock the fetch after upsert
        mock_chunks = [DocChunk(**data) for data in chunks_data]
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_chunks
        mock_session.execute.side_effect = [None, mock_result]  # First for upsert, second for fetch

        # Act
        result = await repository.upsert_chunks(chunks_data)

        # Assert
        assert len(result) == 2
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_chunks_by_repo(self, repository, mock_session, sample_chunk):
        """Test getting chunks by repository."""
        # Arrange
        chunks = [sample_chunk]
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = chunks
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.get_chunks_by_repo("test-repo", limit=10)

        # Assert
        assert len(result) == 1
        assert result[0] == sample_chunk
        mock_session.execute.assert_called_once()
