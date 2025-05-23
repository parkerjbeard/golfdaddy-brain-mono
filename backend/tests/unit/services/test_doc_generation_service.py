import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any

from app.services.doc_generation_service import DocGenerationService
from app.core.exceptions import (
    AIIntegrationError,
    DatabaseError,
    ResourceNotFoundError,
    AppExceptionBase
)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock_client = Mock()
    return mock_client


@pytest.fixture
def mock_task_repository():
    """Mock TaskRepository."""
    return Mock()


@pytest.fixture
def mock_ai_integration():
    """Mock AIIntegration."""
    return Mock()


@pytest.fixture
def doc_service(mock_supabase):
    """DocGenerationService instance with mocked dependencies."""
    with patch('app.services.doc_generation_service.TaskRepository') as mock_task_repo, \
         patch('app.services.doc_generation_service.AIIntegration') as mock_ai:
        service = DocGenerationService(mock_supabase)
        service.task_repository = mock_task_repo.return_value
        service.ai_integration = mock_ai.return_value
        return service


class TestDocGenerationService:
    """Test suite for DocGenerationService."""

    def test_get_documentation_by_id_success(self, doc_service, mock_supabase):
        """Test successful document retrieval."""
        doc_id = "test-doc-id"
        expected_doc = {
            "id": doc_id,
            "title": "Test Document",
            "content": "Test content",
            "doc_type": "general"
        }
        
        mock_response = Mock()
        mock_response.data = expected_doc
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response
        
        result = doc_service.get_documentation_by_id(doc_id)
        
        assert result == expected_doc
        mock_supabase.table.assert_called_with("docs")

    def test_get_documentation_by_id_not_found(self, doc_service, mock_supabase):
        """Test document not found scenario."""
        doc_id = "nonexistent-doc-id"
        
        mock_response = Mock()
        mock_response.data = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response
        
        result = doc_service.get_documentation_by_id(doc_id)
        
        assert result is None

    def test_get_documentation_by_id_database_error(self, doc_service, mock_supabase):
        """Test database error during document retrieval."""
        doc_id = "test-doc-id"
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = Exception("Database connection failed")
        
        with pytest.raises(DatabaseError) as exc_info:
            doc_service.get_documentation_by_id(doc_id)
        
        assert "Failed to fetch document" in str(exc_info.value)

    def test_generate_documentation_success(self, doc_service):
        """Test successful documentation generation."""
        context = {
            "description": "Test API documentation",
            "file_references": ["api.py", "models.py"],
            "doc_type": "api"
        }
        related_task_id = "task-123"
        
        # Mock AI integration
        generated_content = "# API Documentation\n\nTest API content"
        doc_service.ai_integration.generate_doc.return_value = generated_content
        
        # Mock Supabase insert
        mock_response = Mock()
        mock_response.data = [{"id": "doc-123"}]
        mock_response.error = None
        doc_service.supabase.table.return_value.insert.return_value.execute.return_value = mock_response
        
        with patch('app.services.doc_generation_service.uuid.uuid4') as mock_uuid, \
             patch('app.services.doc_generation_service.datetime') as mock_datetime:
            
            mock_uuid.return_value = "doc-123"
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T00:00:00"
            
            result = doc_service.generate_documentation(context, related_task_id)
        
        assert result["doc_id"] == "doc-123"
        assert result["title"] == "API Documentation"
        assert result["content"] == generated_content
        assert result["generated_at"] == "2023-01-01T00:00:00"
        
        doc_service.ai_integration.generate_doc.assert_called_once()

    def test_generate_documentation_ai_failure(self, doc_service):
        """Test AI generation failure."""
        context = {"description": "Test documentation"}
        
        doc_service.ai_integration.generate_doc.return_value = None
        
        with pytest.raises(AIIntegrationError) as exc_info:
            doc_service.generate_documentation(context)
        
        assert "AI failed to generate documentation content" in str(exc_info.value)

    def test_generate_documentation_database_save_error(self, doc_service):
        """Test database save error during generation."""
        context = {"description": "Test documentation"}
        
        doc_service.ai_integration.generate_doc.return_value = "Generated content"
        
        # Mock database error
        mock_response = Mock()
        mock_response.error = Mock()
        mock_response.error.message = "Database constraint violation"
        doc_service.supabase.table.return_value.insert.return_value.execute.return_value = mock_response
        
        with pytest.raises(DatabaseError) as exc_info:
            doc_service.generate_documentation(context)
        
        assert "Failed to save documentation" in str(exc_info.value)

    def test_save_doc_reference_success(self, doc_service):
        """Test successful document reference saving."""
        doc_id = "doc-123"
        doc_url = "https://github.com/owner/repo/blob/main/docs/api.md"
        related_task_id = "task-456"
        
        # Mock successful update
        mock_response = Mock()
        mock_response.error = None
        doc_service.supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response
        
        # Mock task repository
        mock_task = Mock()
        doc_service.task_repository.get_task_by_id.return_value = mock_task
        doc_service.task_repository.update_task.return_value = True
        
        with patch('app.services.doc_generation_service.UUID') as mock_uuid:
            mock_uuid.return_value = related_task_id
            
            result = doc_service.save_doc_reference(doc_id, doc_url, related_task_id)
        
        assert result is True
        doc_service.supabase.table.assert_called_with("docs")

    def test_save_doc_reference_task_not_found(self, doc_service):
        """Test saving doc reference when task is not found."""
        doc_id = "doc-123"
        doc_url = "https://github.com/owner/repo/blob/main/docs/api.md"
        related_task_id = "nonexistent-task"
        
        # Mock successful URL update
        mock_response = Mock()
        mock_response.error = None
        doc_service.supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response
        
        # Mock task not found
        doc_service.task_repository.get_task_by_id.return_value = None
        
        with patch('app.services.doc_generation_service.UUID'):
            result = doc_service.save_doc_reference(doc_id, doc_url, related_task_id)
        
        # Should still succeed for doc URL part
        assert result is True

    def test_handle_iteration_success(self, doc_service):
        """Test successful document iteration."""
        doc_id = "doc-123"
        feedback = "Please add more examples"
        
        # Mock original document
        original_doc = {
            "id": doc_id,
            "title": "API Documentation",
            "content": "Original content",
            "feedback_history": []
        }
        doc_service.get_documentation_by_id = Mock(return_value=original_doc)
        
        # Mock AI update
        updated_content = "Updated content with examples"
        doc_service.ai_integration.update_doc.return_value = updated_content
        
        # Mock successful update
        mock_response = Mock()
        mock_response.error = None
        mock_response.data = [{"id": doc_id}]
        doc_service.supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response
        
        with patch('app.services.doc_generation_service.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T01:00:00"
            
            result = doc_service.handle_iteration(doc_id, feedback)
        
        assert result["doc_id"] == doc_id
        assert result["content"] == updated_content
        assert result["updated_at"] == "2023-01-01T01:00:00"
        
        doc_service.ai_integration.update_doc.assert_called_once()

    def test_handle_iteration_document_not_found(self, doc_service):
        """Test iteration when document is not found."""
        doc_id = "nonexistent-doc"
        feedback = "Please add more examples"
        
        doc_service.get_documentation_by_id = Mock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            doc_service.handle_iteration(doc_id, feedback)
        
        assert "Document" in str(exc_info.value)

    def test_handle_iteration_ai_failure(self, doc_service):
        """Test iteration with AI update failure."""
        doc_id = "doc-123"
        feedback = "Please add more examples"
        
        original_doc = {
            "id": doc_id,
            "content": "Original content",
            "feedback_history": []
        }
        doc_service.get_documentation_by_id = Mock(return_value=original_doc)
        doc_service.ai_integration.update_doc.return_value = None
        
        with pytest.raises(AIIntegrationError) as exc_info:
            doc_service.handle_iteration(doc_id, feedback)
        
        assert "AI failed to update documentation content" in str(exc_info.value)

    def test_extract_title_from_markdown(self, doc_service):
        """Test title extraction from markdown content."""
        content_with_title = "# API Documentation\n\nThis is the content."
        title = doc_service._extract_title(content_with_title)
        assert title == "API Documentation"
        
        content_without_title = "This is content without a title."
        title = doc_service._extract_title(content_without_title)
        assert title is None

    def test_append_feedback_history(self, doc_service):
        """Test feedback history management."""
        existing_history = [
            {"timestamp": "2023-01-01T00:00:00", "feedback": "First feedback"}
        ]
        new_feedback = "Second feedback"
        
        with patch('app.services.doc_generation_service.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T01:00:00"
            
            updated_history = doc_service._append_feedback_history(existing_history, new_feedback)
        
        assert len(updated_history) == 2
        assert updated_history[1]["feedback"] == new_feedback
        assert updated_history[1]["timestamp"] == "2023-01-01T01:00:00"

    def test_append_feedback_history_empty(self, doc_service):
        """Test feedback history creation from empty list."""
        new_feedback = "First feedback"
        
        with patch('app.services.doc_generation_service.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T00:00:00"
            
            history = doc_service._append_feedback_history([], new_feedback)
        
        assert len(history) == 1
        assert history[0]["feedback"] == new_feedback