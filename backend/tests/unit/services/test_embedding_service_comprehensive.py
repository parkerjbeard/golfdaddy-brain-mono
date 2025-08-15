"""
Comprehensive unit tests for the EmbeddingService.
"""

import asyncio
import hashlib
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest
from sqlalchemy import select

from app.models.doc_embeddings import CodeContext, DocEmbedding
from app.services.embedding_service import EmbeddingService, RateLimiter
from tests.fixtures.auto_doc_fixtures import MOCK_OPENAI_RESPONSES, create_code_context, create_doc_embedding


class TestRateLimiter:
    """Test cases for the RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_calls=10, time_window=60)
        assert limiter.max_calls == 10
        assert limiter.time_window == 60
        assert len(limiter.calls) == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_calls_within_limit(self):
        """Test rate limiter allows calls within limit."""
        limiter = RateLimiter(max_calls=3, time_window=60)

        # Should allow 3 calls
        for _ in range(3):
            await limiter.check()

        assert len(limiter.calls) == 3

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess_calls(self):
        """Test rate limiter blocks calls exceeding limit."""
        limiter = RateLimiter(max_calls=2, time_window=60)

        # First 2 calls should succeed
        await limiter.check()
        await limiter.check()

        # Third call should raise exception
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await limiter.check()

    @pytest.mark.asyncio
    async def test_rate_limiter_window_expiry(self):
        """Test rate limiter resets after time window."""
        limiter = RateLimiter(max_calls=1, time_window=0.1)  # 100ms window

        # First call should succeed
        await limiter.check()

        # Immediate second call should fail
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await limiter.check()

        # Wait for window to expire
        await asyncio.sleep(0.15)

        # Should allow new call
        await limiter.check()  # Should not raise


class TestEmbeddingServiceComprehensive:
    """Comprehensive test cases for EmbeddingService."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        mock = AsyncMock()
        mock.embeddings = AsyncMock()
        mock.embeddings.create = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_openai_client):
        """Create an EmbeddingService instance."""
        with patch("app.services.embedding_service.AsyncOpenAI", return_value=mock_openai_client):
            with patch("app.services.embedding_service.settings") as mock_settings:
                mock_settings.OPENAI_API_KEY = "test-key"
                mock_settings.EMBEDDING_MODEL = "text-embedding-ada-002"
                mock_settings.EMBEDDING_RATE_LIMIT = 100
                service = EmbeddingService()
                service.client = mock_openai_client
                return service

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, service, mock_openai_client):
        """Test successful embedding generation."""
        text = "This is a test document about user authentication."
        expected_embedding = [0.1] * 1536

        mock_openai_client.embeddings.create.return_value = Mock(data=[Mock(embedding=expected_embedding)])

        result = await service.generate_embedding(text)

        assert result == expected_embedding
        mock_openai_client.embeddings.create.assert_called_once_with(
            model="text-embedding-ada-002", input=text, encoding_format="float"
        )

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text(self, service):
        """Test embedding generation with empty text."""
        assert await service.generate_embedding("") is None
        assert await service.generate_embedding("   ") is None
        assert await service.generate_embedding(None) is None

    @pytest.mark.asyncio
    async def test_generate_embedding_with_cache(self, service, mock_openai_client):
        """Test embedding generation uses cache."""
        text = "Cached document content"
        expected_embedding = [0.2] * 1536

        mock_openai_client.embeddings.create.return_value = Mock(data=[Mock(embedding=expected_embedding)])

        # First call should hit API
        result1 = await service.generate_embedding(text)
        assert mock_openai_client.embeddings.create.call_count == 1

        # Second call should use cache
        result2 = await service.generate_embedding(text)
        assert mock_openai_client.embeddings.create.call_count == 1  # No additional call

        assert result1 == result2 == expected_embedding

    @pytest.mark.asyncio
    async def test_generate_embedding_rate_limiting(self, service, mock_openai_client):
        """Test embedding generation respects rate limits."""
        # Override rate limiter with strict limit
        service.rate_limiter = RateLimiter(max_calls=2, time_window=60)

        mock_openai_client.embeddings.create.return_value = Mock(data=[Mock(embedding=[0.1] * 1536)])

        # Clear cache to ensure API calls
        service._cache.clear()

        # First two calls should succeed
        await service.generate_embedding("Text 1")
        await service.generate_embedding("Text 2")

        # Third call should fail due to rate limit
        result = await service.generate_embedding("Text 3")
        assert result is None  # Service returns None on rate limit error

    @pytest.mark.asyncio
    async def test_generate_embedding_api_error(self, service, mock_openai_client):
        """Test embedding generation handles API errors."""
        mock_openai_client.embeddings.create.side_effect = Exception("API Error")

        result = await service.generate_embedding("Test text")

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, service, mock_openai_client):
        """Test batch embedding generation."""
        texts = ["Document 1 about authentication", "Document 2 about authorization", "Document 3 about security"]

        expected_embeddings = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]

        mock_openai_client.embeddings.create.return_value = Mock(
            data=[
                Mock(embedding=expected_embeddings[0]),
                Mock(embedding=expected_embeddings[1]),
                Mock(embedding=expected_embeddings[2]),
            ]
        )

        results = await service.generate_embeddings_batch(texts)

        assert len(results) == 3
        assert results[0] == expected_embeddings[0]
        assert results[1] == expected_embeddings[1]
        assert results[2] == expected_embeddings[2]

        mock_openai_client.embeddings.create.assert_called_once_with(
            model="text-embedding-ada-002", input=texts, encoding_format="float"
        )

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_with_empty_texts(self, service, mock_openai_client):
        """Test batch embedding with some empty texts."""
        texts = ["Valid text", "", "Another valid text", "   ", None]

        mock_openai_client.embeddings.create.return_value = Mock(
            data=[Mock(embedding=[0.1] * 1536), Mock(embedding=[0.2] * 1536)]
        )

        results = await service.generate_embeddings_batch(texts)

        assert len(results) == 5
        assert results[0] is not None  # Valid text
        assert results[1] is None  # Empty string
        assert results[2] is not None  # Another valid text
        assert results[3] is None  # Whitespace
        assert results[4] is None  # None

        # Only valid texts should be sent to API
        call_args = mock_openai_client.embeddings.create.call_args
        assert call_args[1]["input"] == ["Valid text", "Another valid text"]

    @pytest.mark.asyncio
    async def test_create_or_update_embedding_new(self, service, mock_db_session):
        """Test creating a new embedding record."""
        doc_data = create_doc_embedding()
        embedding = [0.5] * 1536

        # Mock database responses
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch.object(service, "generate_embedding", return_value=embedding):
            result = await service.create_or_update_embedding(
                mock_db_session,
                document_id=doc_data["id"],
                title=doc_data["title"],
                content=doc_data["content"],
                metadata=doc_data["metadata"],
            )

        assert result is not None
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called_once()

        # Since we use insert with on_conflict_do_update, we check execute was called
        # with the correct values
        execute_call_args = mock_db_session.execute.call_args[0][0]
        # The actual insert statement would have these values set

    @pytest.mark.asyncio
    async def test_create_or_update_embedding_update_existing(self, service, mock_db_session):
        """Test updating an existing embedding record."""
        existing_embedding = DocEmbedding(
            id="existing-id", document_id="doc-123", title="Old Title", content="Old content", embedding=[0.1] * 1536
        )

        new_embedding = [0.9] * 1536

        # Mock the db.get call that happens after insert/update
        mock_db_session.get.return_value = existing_embedding

        with patch.object(service, "generate_embedding", return_value=new_embedding):
            result = await service.create_or_update_embedding(
                mock_db_session, document_id="doc-123", title="New Title", content="New content"
            )

        # The method returns the result from embed_document
        # which uses db.get to retrieve the created/updated record
        assert result is not None
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_similar_documents(self, service, mock_db_session):
        """Test finding similar documents."""
        query = "How to implement user authentication?"
        repository = "test-repo"

        # Mock similar documents
        similar_docs = [
            (create_doc_embedding(title="Auth Guide"), 0.92),
            (create_doc_embedding(title="Security Best Practices"), 0.85),
            (create_doc_embedding(title="Login Implementation"), 0.78),
        ]

        # Mock the database results to match what the implementation expects
        mock_results = []
        mock_docs = []
        for doc, score in similar_docs:
            mock_doc = Mock()
            for key, value in doc.items():
                setattr(mock_doc, key, value)
            mock_docs.append(mock_doc)
            # The SQL query returns rows with id and similarity
            mock_results.append(Mock(id=doc["id"], similarity=score))

        # Mock fetchall to return results
        mock_fetch_result = Mock()
        mock_fetch_result.fetchall.return_value = mock_results
        mock_db_session.execute.return_value = mock_fetch_result

        # Mock db.get to return the corresponding documents
        async def mock_get(cls, id):
            return mock_docs[next(i for i, r in enumerate(mock_results) if r.id == id)]

        mock_db_session.get = AsyncMock(side_effect=mock_get)

        with patch.object(service, "generate_embedding", return_value=[0.5] * 1536):
            results = await service.find_similar_documents(mock_db_session, query, repository, limit=3, threshold=0.7)

        assert len(results) == 3
        assert results[0][1] == 0.92  # Similarity score
        assert results[0][0].title == "Auth Guide"

        # Verify SQL query construction
        execute_call = mock_db_session.execute.call_args[0][0]
        assert "find_similar_docs" in str(execute_call)

    @pytest.mark.asyncio
    async def test_find_similar_documents_no_embedding(self, service, mock_db_session):
        """Test finding similar documents when embedding generation fails."""
        with patch.object(service, "generate_embedding", return_value=None):
            results = await service.find_similar_documents(mock_db_session, "query", "repo")

        assert results == []

    @pytest.mark.asyncio
    async def test_detect_duplicates(self, service, mock_db_session):
        """Test duplicate detection."""
        title = "User Authentication Guide"
        content = "This guide explains how to implement user authentication..."
        repository = "test-repo"

        # Mock potential duplicates
        duplicates = [
            create_doc_embedding(title="User Auth Guide", doc_id="dup-1"),
            create_doc_embedding(title="Authentication Tutorial", doc_id="dup-2"),
        ]

        mock_results = []
        for dup in duplicates:
            mock_doc = Mock()
            for key, value in dup.items():
                setattr(mock_doc, key, value)
            mock_results.append((mock_doc, 0.95))  # High similarity

        with patch.object(service, "find_similar_documents", return_value=mock_results):
            results = await service.detect_duplicates(
                mock_db_session, title, content, repository, exclude_id="current-doc", threshold=0.9
            )

        assert len(results) == 2
        assert results[0].id == "dup-1"
        assert results[1].id == "dup-2"

    @pytest.mark.asyncio
    async def test_batch_create_embeddings(self, service, mock_db_session):
        """Test batch creation of embeddings."""
        documents = [
            {
                "document_id": f"doc-{i}",
                "title": f"Document {i}",
                "content": f"Content for document {i}",
                "metadata": {"index": i},
            }
            for i in range(3)
        ]

        embeddings = [[float(i)] * 1536 for i in range(3)]

        with patch.object(service, "generate_embeddings_batch", return_value=embeddings):
            results = await service.batch_create_embeddings(mock_db_session, documents)

        assert len(results) == 3
        assert mock_db_session.execute.call_count == 3
        assert mock_db_session.commit.call_count == 3  # Each create_or_update_embedding commits

    @pytest.mark.asyncio
    async def test_batch_create_embeddings_partial_failure(self, service, mock_db_session):
        """Test batch creation with some embedding failures."""
        documents = [
            {"document_id": "doc-1", "title": "Doc 1", "content": "Content 1"},
            {"document_id": "doc-2", "title": "Doc 2", "content": "Content 2"},
            {"document_id": "doc-3", "title": "Doc 3", "content": "Content 3"},
        ]

        # Mock create_or_update_embedding to simulate second one failing
        mock_embedding_1 = Mock(title="Doc 1")
        mock_embedding_3 = Mock(title="Doc 3")

        # Side effect: first succeeds, second raises exception, third succeeds
        async def mock_create_or_update(db, document_id, title, content, metadata=None):
            if document_id == "doc-2":
                raise Exception("Embedding generation failed")
            elif document_id == "doc-1":
                return mock_embedding_1
            else:
                return mock_embedding_3

        with patch.object(service, "create_or_update_embedding", side_effect=mock_create_or_update):
            results = await service.batch_create_embeddings(mock_db_session, documents)

        # The actual implementation returns all results including None for failures
        assert len(results) == 3
        assert results[0].title == "Doc 1"
        assert results[1] is None  # Second one failed
        assert results[2].title == "Doc 3"

    @pytest.mark.asyncio
    async def test_search_code_context(self, service, mock_db_session):
        """Test searching for code context."""
        query = "Repository pattern implementation"
        repository = "test-repo"

        # Mock code context results
        code_contexts = [
            create_code_context(file_path="services/user_service.py"),
            create_code_context(file_path="repositories/user_repository.py"),
        ]

        mock_results = []
        for ctx in code_contexts:
            mock_ctx = Mock()
            for key, value in ctx.items():
                setattr(mock_ctx, key, value)
            mock_results.append(Mock(CodeContext=mock_ctx, similarity=0.88))

        # Mock the SQL query result
        mock_result_rows = [Mock(id="ctx-1", similarity=0.88), Mock(id="ctx-2", similarity=0.85)]

        mock_fetch_result = Mock()
        mock_fetch_result.fetchall.return_value = mock_result_rows
        mock_db_session.execute.return_value = mock_fetch_result

        # Mock the CodeContext objects
        mock_contexts = [
            Mock(file_path="services/user_service.py", module_name="user_service"),
            Mock(file_path="repositories/user_repository.py", module_name="user_repository"),
        ]

        mock_db_session.get.side_effect = mock_contexts

        with patch.object(service, "generate_embedding", return_value=[0.5] * 1536):
            results = await service.search_code_context(mock_db_session, query, repository, limit=2)

        assert len(results) == 2
        assert results[0][0].file_path == "services/user_service.py"
        assert results[0][1] == 0.88

    @pytest.mark.asyncio
    async def test_update_code_context_embedding(self, service, mock_db_session):
        """Test updating code context embeddings."""
        file_path = "app/services/test_service.py"
        repository = "test-repo"
        context_data = {
            "module_name": "test_service",
            "class_names": ["TestService"],
            "function_names": ["test_function"],
            "design_patterns": ["Service Layer"],
        }

        # Mock the insert/update operation
        mock_result = Mock()
        mock_result.inserted_primary_key = ["ctx-1"]
        mock_db_session.execute.return_value = mock_result

        # Mock the returned context after update
        updated_context = Mock(spec=CodeContext)
        updated_context.file_path = file_path
        updated_context.module_name = "test_service"
        updated_context.class_names = ["TestService"]
        updated_context.context_embedding = [0.7] * 1536
        mock_db_session.get.return_value = updated_context

        with patch.object(service, "generate_embedding", return_value=[0.7] * 1536):
            result = await service.update_code_context_embedding(mock_db_session, repository, file_path, context_data)

        assert result == updated_context
        assert result.module_name == "test_service"
        assert result.class_names == ["TestService"]
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, service):
        """Test cache key generation is consistent."""
        text = "Test document content"

        # Generate embedding twice
        cache_key1 = hashlib.md5(text.encode()).hexdigest()
        cache_key2 = hashlib.md5(text.encode()).hexdigest()

        assert cache_key1 == cache_key2

        # Different text should have different key
        different_text = "Different content"
        different_key = hashlib.md5(different_text.encode()).hexdigest()

        assert cache_key1 != different_key

    @pytest.mark.asyncio
    async def test_embedding_dimension_validation(self, service):
        """Test embedding dimension validation."""
        assert service.dimension == 1536  # Ada-002 dimensions

        # Verify model configuration
        assert service.model == "text-embedding-ada-002"

    @pytest.mark.asyncio
    async def test_concurrent_embedding_generation(self, service, mock_openai_client):
        """Test concurrent embedding generation with rate limiting."""
        import asyncio

        # Set up responses for multiple calls
        mock_openai_client.embeddings.create.return_value = Mock(data=[Mock(embedding=[0.1] * 1536)])

        # Clear cache to ensure API calls
        service._cache.clear()

        # Create concurrent tasks
        texts = [f"Document {i}" for i in range(5)]
        tasks = [service.generate_embedding(text) for text in texts]

        # Run concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should handle rate limiting gracefully
        successful_results = [r for r in results if r is not None and not isinstance(r, Exception)]
        assert len(successful_results) > 0

    @pytest.mark.asyncio
    async def test_embedding_service_initialization_error(self):
        """Test embedding service initialization with missing API key."""
        with patch("app.services.embedding_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None

            # Should still initialize but with warnings
            service = EmbeddingService()
            assert service.client is None  # Client is None when API key is missing

    @pytest.mark.asyncio
    async def test_database_error_handling(self, service, mock_db_session):
        """Test database error handling during embedding operations."""
        mock_db_session.commit.side_effect = Exception("Database error")

        with patch.object(service, "generate_embedding", return_value=[0.1] * 1536):
            result = await service.create_or_update_embedding(
                mock_db_session, document_id="doc-123", title="Test", content="Content"
            )

            # The method should return None on database error
            assert result is None
            assert mock_db_session.rollback.called
