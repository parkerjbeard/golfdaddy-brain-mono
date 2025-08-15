"""
Unit tests for the EmbeddingService class.
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from app.models.doc_embeddings import DocEmbedding
from app.services.embedding_service import EmbeddingService


class TestEmbeddingService:
    """Test cases for EmbeddingService."""

    @pytest.fixture
    def service(self):
        """Create a test service instance."""
        with patch("app.services.embedding_service.AsyncOpenAI") as mock_openai:
            service = EmbeddingService()
            service.openai = mock_openai()
            return service

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        # Mock query results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)
        return db

    @pytest.fixture
    def sample_embedding(self):
        """Create a sample embedding vector."""
        return np.random.rand(1536).tolist()

    @pytest.fixture
    def sample_doc_embedding(self, sample_embedding):
        """Create a sample DocEmbedding instance."""
        return DocEmbedding(
            id=uuid.uuid4(),
            content="Sample documentation content",
            embedding=sample_embedding,
            title="Sample Document",
            file_path="/docs/sample.md",
            repository="test-repo",
            doc_metadata={"type": "documentation", "version": "1.0"},
            created_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, service, sample_embedding):
        """Test successful embedding generation."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=sample_embedding)]
        service.openai.embeddings.create = AsyncMock(return_value=mock_response)

        result = await service.generate_embedding("Test content")

        assert result == sample_embedding
        service.openai.embeddings.create.assert_called_once_with(
            model="text-embedding-ada-002", input="Test content", encoding_format="float"
        )

    @pytest.mark.asyncio
    async def test_generate_embedding_handles_error(self, service):
        """Test embedding generation error handling."""
        service.openai.embeddings.create = AsyncMock(side_effect=Exception("API Error"))

        result = await service.generate_embedding("Test content")
        assert result is None

    @pytest.mark.asyncio
    async def test_embed_document_new_doc(self, service, mock_db, sample_embedding):
        """Test embedding a new document."""
        # Mock embedding generation
        service.openai.embeddings.create = AsyncMock(return_value=Mock(data=[Mock(embedding=sample_embedding)]))

        # Mock database query - no existing embedding
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock the insert result
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_primary_key = [uuid.uuid4()]
        mock_db.execute = AsyncMock(return_value=mock_insert_result)

        # Mock db.get to return a new embedding
        mock_embedding = Mock(spec=DocEmbedding)
        mock_db.get = AsyncMock(return_value=mock_embedding)

        result = await service.embed_document(
            db=mock_db,
            title="New Document",
            content="New document content",
            doc_type="documentation",
            repository="test-repo",
            file_path="/docs/new.md",
            doc_metadata={"version": "1.0"},
        )

        assert result is not None
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_document_update_existing(self, service, mock_db, sample_embedding, sample_doc_embedding):
        """Test updating an existing document embedding."""
        # Mock embedding generation
        service.openai.embeddings.create = AsyncMock(return_value=Mock(data=[Mock(embedding=sample_embedding)]))

        # Mock database execute for the insert/update
        mock_result = MagicMock()
        mock_result.inserted_primary_key = [sample_doc_embedding.id]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock the get() call that retrieves the updated record
        updated_doc = sample_doc_embedding
        updated_doc.embedding = sample_embedding
        updated_doc.content = "Updated content"
        mock_db.get = AsyncMock(return_value=updated_doc)

        result = await service.embed_document(
            db=mock_db,
            title=sample_doc_embedding.title,
            content="Updated content",
            doc_type="documentation",
            repository=sample_doc_embedding.repository,
            file_path=sample_doc_embedding.file_path,
            doc_metadata={"version": "2.0"},
        )

        assert result == sample_doc_embedding
        assert result.embedding == sample_embedding
        assert result.content == "Updated content"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_similar_documents_success(self, service, mock_db, sample_doc_embedding, sample_embedding):
        """Test finding similar documents."""
        # Mock embedding generation for query
        service.openai.embeddings.create = AsyncMock(return_value=Mock(data=[Mock(embedding=sample_embedding)]))

        # Mock database query - returns rows with id and similarity
        mock_row1 = Mock(id=sample_doc_embedding.id, similarity=0.95)
        mock_row2 = Mock(id=uuid.uuid4(), similarity=0.85)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row1, mock_row2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock db.get() to return the actual DocEmbedding objects
        mock_db.get = AsyncMock(side_effect=[sample_doc_embedding, sample_doc_embedding])

        results = await service.find_similar_documents(
            db=mock_db, query="Find similar content", repository="test-repo", limit=5, threshold=0.8
        )

        assert len(results) == 2
        assert all(score >= 0.8 for _, score in results)
        assert results[0][1] == 0.95  # Check similarity scores
        assert results[1][1] == 0.85
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_similar_documents_no_results(self, service, mock_db, sample_embedding):
        """Test finding similar documents with no results."""
        # Mock embedding generation
        service.openai.embeddings.create = AsyncMock(return_value=Mock(data=[Mock(embedding=sample_embedding)]))

        # Mock database query - no results
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await service.find_similar_documents(db=mock_db, query="No matching content", threshold=0.9)

        assert results == []

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(self, service):
        """Test batch embedding generation."""
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = [np.random.rand(1536).tolist() for _ in texts]

        # Mock OpenAI response with all embeddings
        mock_response = Mock()
        mock_response.data = [Mock(embedding=emb) for emb in embeddings]

        service.openai.embeddings.create = AsyncMock(return_value=mock_response)

        results = await service.generate_embeddings_batch(texts)

        assert len(results) == len(texts)
        assert service.openai.embeddings.create.call_count == 1  # Single batch call

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_failure(self, service):
        """Test batch embedding generation with failure."""
        texts = ["Text 1", "Text 2", "Text 3"]

        # Mock API error
        service.openai.embeddings.create = AsyncMock(side_effect=Exception("API Error"))

        results = await service.generate_embeddings_batch(texts)

        assert len(results) == 3  # Returns None for all on error
        assert all(r is None for r in results)
        assert service.openai.embeddings.create.call_count == 1

    @pytest.mark.asyncio
    async def test_detect_duplicates_found(self, service, mock_db, sample_embedding, sample_doc_embedding):
        """Test duplicate detection when duplicates exist."""
        # Mock similar documents with high similarity
        similar_doc = DocEmbedding(
            id=uuid.uuid4(),
            content="Very similar content",
            embedding=sample_embedding,
            title="Similar Document",
            file_path="/docs/similar.md",
            repository="test-repo",
        )

        # Mock find_similar_documents to return documents with high similarity
        service.find_similar_documents = AsyncMock(
            return_value=[
                (similar_doc, 0.98),  # Very high similarity - above threshold
                (sample_doc_embedding, 0.85),  # Below threshold
            ]
        )

        duplicates = await service.detect_duplicates(
            db=mock_db, title="New Document", content="Very similar content", repository="test-repo", threshold=0.9
        )

        assert len(duplicates) == 1
        assert duplicates[0].title == "Similar Document"

    @pytest.mark.asyncio
    async def test_detect_duplicates_none_found(self, service, mock_db, sample_embedding):
        """Test duplicate detection when no duplicates exist."""
        # Mock find_similar_documents to return documents below threshold
        service.find_similar_documents = AsyncMock(
            return_value=[(Mock(title="Doc1"), 0.7), (Mock(title="Doc2"), 0.6)]  # Below threshold  # Below threshold
        )

        duplicates = await service.detect_duplicates(
            db=mock_db,
            title="Unique Document",
            content="Completely unique content",
            repository="test-repo",
            threshold=0.9,
        )

        assert duplicates == []

    # @pytest.mark.asyncio
    # async def test_delete_embedding_success(self, service, mock_db, sample_doc_embedding):
    #     """Test successful embedding deletion."""
    #     # Mock database query
    #     mock_result = MagicMock()
    #     mock_result.scalar_one_or_none.return_value = sample_doc_embedding
    #     mock_db.execute = AsyncMock(return_value=mock_result)

    #     result = await service.delete_embedding(
    #         db=mock_db,
    #         repository="test-repo",
    #         file_path="/docs/sample.md"
    #     )

    #     assert result is True
    #     mock_db.delete.assert_called_once_with(sample_doc_embedding)
    #     mock_db.commit.assert_called_once()

    # @pytest.mark.asyncio
    # async def test_delete_embedding_not_found(self, service, mock_db):
    #     """Test deletion when embedding doesn't exist."""
    #     # Mock database query - not found
    #     mock_result = MagicMock()
    #     mock_result.scalar_one_or_none.return_value = None
    #     mock_db.execute = AsyncMock(return_value=mock_result)

    #     result = await service.delete_embedding(
    #         db=mock_db,
    #         repository="test-repo",
    #         file_path="/docs/nonexistent.md"
    #     )

    #     assert result is False
    #     mock_db.delete.assert_not_called()

    def test_embedding_caching(self, service):
        """Test embedding cache functionality."""
        # Store in cache
        embedding = np.random.rand(1536).tolist()
        content = "Cached content"
        cache_key = hashlib.md5(content.encode()).hexdigest()

        service._cache[cache_key] = embedding

        # Verify cache retrieval
        assert cache_key in service._cache
        assert service._cache[cache_key] == embedding

    @pytest.mark.asyncio
    async def test_rate_limiting(self, service):
        """Test rate limiting functionality."""
        # Set a low rate limit for testing
        service.rate_limiter.max_calls = 2
        service.rate_limiter.time_window = 1  # 1 second

        # Mock OpenAI responses
        service.openai.embeddings.create = AsyncMock(
            return_value=Mock(data=[Mock(embedding=np.random.rand(1536).tolist())])
        )

        # Make rapid requests
        results = []
        for i in range(3):
            result = await service.generate_embedding(f"Text {i}")
            results.append(result)

        # Should have rate limited after 2 requests - returns None on rate limit
        assert results[0] is not None
        assert results[1] is not None
        assert results[2] is None  # Rate limited, returns None

    @pytest.mark.asyncio
    async def test_update_embeddings_for_repository(self, service, mock_db):
        """Test updating all embeddings for a repository."""
        # Mock database query for existing embeddings
        existing_embeddings = [
            Mock(id=uuid.uuid4(), content="Doc 1", file_path="/doc1.md"),
            Mock(id=uuid.uuid4(), content="Doc 2", file_path="/doc2.md"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = existing_embeddings
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock embedding generation
        service.openai.embeddings.create = AsyncMock(
            return_value=Mock(data=[Mock(embedding=np.random.rand(1536).tolist())])
        )

        updated_count = await service.update_embeddings_for_repository(db=mock_db, repository="test-repo")

        assert updated_count == len(existing_embeddings)
        assert service.openai.embeddings.create.call_count == len(existing_embeddings)
        mock_db.commit.assert_called()
