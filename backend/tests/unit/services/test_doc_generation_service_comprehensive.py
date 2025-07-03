"""
Comprehensive unit tests for the DocGenerationService.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import uuid
from datetime import datetime
import json

from app.services.doc_generation_service import DocGenerationService
from app.core.exceptions import (
    AIIntegrationError, DatabaseError, ResourceNotFoundError, AppExceptionBase
)
from tests.fixtures.auto_doc_fixtures import (
    QUALITY_TEST_CASES, TEST_CONFIG
)


class TestDocGenerationServiceComprehensive:
    """Comprehensive test cases for DocGenerationService."""
    
    @pytest.fixture
    def mock_supabase(self):
        """Create a mock Supabase client."""
        mock = Mock()
        mock.table = Mock(return_value=mock)
        mock.select = Mock(return_value=mock)
        mock.eq = Mock(return_value=mock)
        mock.single = Mock(return_value=mock)
        mock.insert = Mock(return_value=mock)
        mock.update = Mock(return_value=mock)
        mock.execute = Mock()
        return mock
    
    @pytest.fixture
    def mock_ai_integration(self):
        """Create a mock AI integration."""
        with patch('app.services.doc_generation_service.AIIntegration') as mock:
            instance = Mock()
            mock.return_value = instance
            yield instance
    
    @pytest.fixture
    def service(self, mock_supabase, mock_ai_integration):
        """Create a DocGenerationService instance."""
        return DocGenerationService(mock_supabase)
    
    def test_get_documentation_by_id_success(self, service, mock_supabase):
        """Test successful document retrieval by ID."""
        doc_id = str(uuid.uuid4())
        expected_doc = {
            "id": doc_id,
            "title": "Test Documentation",
            "content": "Test content",
            "doc_type": "api",
            "created_at": datetime.utcnow().isoformat()
        }
        
        mock_supabase.execute.return_value = Mock(data=expected_doc)
        
        result = service.get_documentation_by_id(doc_id)
        
        assert result == expected_doc
        mock_supabase.table.assert_called_with("docs")
        mock_supabase.eq.assert_called_with("id", doc_id)
    
    def test_get_documentation_by_id_not_found(self, service, mock_supabase):
        """Test document retrieval when document doesn't exist."""
        doc_id = str(uuid.uuid4())
        mock_supabase.execute.return_value = Mock(data=None)
        
        result = service.get_documentation_by_id(doc_id)
        
        assert result is None
    
    def test_get_documentation_by_id_database_error(self, service, mock_supabase):
        """Test document retrieval with database error."""
        doc_id = str(uuid.uuid4())
        mock_supabase.execute.side_effect = Exception("Database connection failed")
        
        with pytest.raises(DatabaseError) as exc_info:
            service.get_documentation_by_id(doc_id)
        
        assert "Failed to fetch document" in str(exc_info.value)
        assert doc_id in str(exc_info.value)
    
    def test_generate_documentation_success(self, service, mock_supabase, mock_ai_integration):
        """Test successful documentation generation."""
        context = {
            "description": "User authentication service implementation",
            "file_references": ["auth_service.py", "user_model.py"],
            "doc_type": "api"
        }
        
        generated_content = """# Authentication Service API

## Overview
This service handles user authentication and authorization.

## Methods
- authenticate(username, password)
- refresh_token(token)
- logout(user_id)"""
        
        mock_ai_integration.generate_doc.return_value = generated_content
        mock_supabase.execute.return_value = Mock(data=[{"id": "123"}], error=None)
        
        with patch('uuid.uuid4', return_value="test-uuid"):
            result = service.generate_documentation(context)
        
        assert result["doc_id"] == "test-uuid"
        assert result["title"] == "Authentication Service API"
        assert result["content"] == generated_content
        assert "generated_at" in result
        
        # Verify AI was called with correct input
        mock_ai_integration.generate_doc.assert_called_once_with({
            "description": context["description"],
            "files": context["file_references"],
            "doc_type": context["doc_type"]
        })
        
        # Verify database insert
        mock_supabase.insert.assert_called_once()
        insert_data = mock_supabase.insert.call_args[0][0]
        assert insert_data["title"] == "Authentication Service API"
        assert insert_data["content"] == generated_content
    
    def test_generate_documentation_ai_failure(self, service, mock_ai_integration):
        """Test documentation generation when AI fails."""
        context = {"description": "Test", "doc_type": "general"}
        
        mock_ai_integration.generate_doc.return_value = None
        
        with pytest.raises(AIIntegrationError) as exc_info:
            service.generate_documentation(context)
        
        assert "AI failed to generate documentation content" in str(exc_info.value)
    
    def test_generate_documentation_database_save_error(self, service, mock_supabase, mock_ai_integration):
        """Test documentation generation with database save error."""
        context = {"description": "Test", "doc_type": "general"}
        
        mock_ai_integration.generate_doc.return_value = "Generated content"
        mock_supabase.execute.return_value = Mock(data=None, error=Mock(message="Insert failed"))
        
        with pytest.raises(DatabaseError) as exc_info:
            service.generate_documentation(context)
        
        assert "Failed to save documentation" in str(exc_info.value)
    
    def test_generate_documentation_unexpected_error(self, service, mock_ai_integration):
        """Test documentation generation with unexpected error."""
        context = {"description": "Test", "doc_type": "general"}
        
        mock_ai_integration.generate_doc.side_effect = RuntimeError("Unexpected error")
        
        with pytest.raises(AppExceptionBase) as exc_info:
            service.generate_documentation(context)
        
        assert "An unexpected error occurred" in str(exc_info.value)
    
    def test_extract_title_from_markdown(self, service):
        """Test title extraction from markdown content."""
        content_with_title = """# API Reference Guide

This is the content..."""
        
        title = service._extract_title(content_with_title)
        assert title == "API Reference Guide"
        
        content_no_title = """This is content without a markdown heading.
        
Just regular text."""
        
        title = service._extract_title(content_no_title)
        assert title is None
        
        # Test with multiple headings
        content_multiple = """Some intro text

# First Heading
## Second Heading
# Third Heading"""
        
        title = service._extract_title(content_multiple)
        assert title == "First Heading"  # Should get the first one
    
    def test_extract_title_edge_cases(self, service):
        """Test title extraction edge cases."""
        # Empty content
        assert service._extract_title("") is None
        
        # Only whitespace
        assert service._extract_title("   \n\n   ") is None
        
        # Heading with extra spaces
        title = service._extract_title("#    Spaced Title   ")
        assert title == "Spaced Title"
        
        # Non-h1 headings
        assert service._extract_title("## H2 Heading") is None
        assert service._extract_title("### H3 Heading") is None
    
    def test_save_doc_reference_success(self, service, mock_supabase):
        """Test successful document reference saving."""
        doc_id = "test-doc-123"
        doc_url = "https://github.com/org/repo/blob/main/docs/api.md"
        
        mock_supabase.execute.return_value = Mock(error=None)
        
        result = service.save_doc_reference(doc_id, doc_url)
        
        assert result is True
        mock_supabase.update.assert_called_once_with({"external_url": doc_url})
        mock_supabase.eq.assert_called_with("id", doc_id)
    
    def test_save_doc_reference_database_error(self, service, mock_supabase):
        """Test document reference saving with database error."""
        doc_id = "test-doc-123"
        doc_url = "https://example.com/doc"
        
        mock_supabase.execute.return_value = Mock(
            error=Mock(message="Update failed")
        )
        
        with pytest.raises(DatabaseError) as exc_info:
            service.save_doc_reference(doc_id, doc_url)
        
        assert f"Failed to save doc reference URL for {doc_id}" in str(exc_info.value)
    
    def test_handle_iteration_success(self, service, mock_supabase, mock_ai_integration):
        """Test successful document iteration based on feedback."""
        doc_id = str(uuid.uuid4())
        feedback = "Please add more examples and clarify the error handling section"
        
        original_doc = {
            "id": doc_id,
            "title": "Original Title",
            "content": "Original content",
            "feedback_history": []
        }
        
        updated_content = """Original content

## Examples
Here are some examples...

## Error Handling
Detailed error handling explanation..."""
        
        # Mock get_documentation_by_id
        with patch.object(service, 'get_documentation_by_id', return_value=original_doc):
            mock_ai_integration.update_doc.return_value = updated_content
            mock_supabase.execute.return_value = Mock(data=[{"id": doc_id}], error=None)
            
            result = service.handle_iteration(doc_id, feedback)
        
        assert result["doc_id"] == doc_id
        assert result["title"] == "Original Title"
        assert result["content"] == updated_content
        assert "updated_at" in result
        
        # Verify AI was called with correct input
        mock_ai_integration.update_doc.assert_called_once_with({
            "original_content": "Original content",
            "feedback": feedback
        })
        
        # Verify database update
        mock_supabase.update.assert_called_once()
        update_data = mock_supabase.update.call_args[0][0]
        assert update_data["content"] == updated_content
        assert len(update_data["feedback_history"]) == 1
        assert update_data["feedback_history"][0]["feedback"] == feedback
    
    def test_handle_iteration_document_not_found(self, service):
        """Test iteration when document doesn't exist."""
        doc_id = str(uuid.uuid4())
        feedback = "Update something"
        
        with patch.object(service, 'get_documentation_by_id', return_value=None):
            with pytest.raises(ResourceNotFoundError) as exc_info:
                service.handle_iteration(doc_id, feedback)
            
            assert "Document" in str(exc_info.value)
            assert doc_id in str(exc_info.value)
    
    def test_handle_iteration_ai_update_failure(self, service, mock_ai_integration):
        """Test iteration when AI fails to update."""
        doc_id = str(uuid.uuid4())
        feedback = "Update something"
        original_doc = {"id": doc_id, "content": "Original"}
        
        with patch.object(service, 'get_documentation_by_id', return_value=original_doc):
            mock_ai_integration.update_doc.return_value = None
            
            with pytest.raises(AIIntegrationError) as exc_info:
                service.handle_iteration(doc_id, feedback)
            
            assert "AI failed to update documentation" in str(exc_info.value)
    
    def test_append_feedback_history(self, service):
        """Test feedback history appending."""
        # New history
        new_history = service._append_feedback_history([], "First feedback")
        assert len(new_history) == 1
        assert new_history[0]["feedback"] == "First feedback"
        assert "timestamp" in new_history[0]
        
        # Append to existing
        existing = [{"timestamp": "2024-01-01T00:00:00", "feedback": "Old feedback"}]
        updated = service._append_feedback_history(existing, "New feedback")
        assert len(updated) == 2
        assert updated[0]["feedback"] == "Old feedback"  # Original preserved
        assert updated[1]["feedback"] == "New feedback"
        
        # Verify original list not modified
        assert len(existing) == 1
    
    def test_generate_documentation_with_custom_title(self, service, mock_supabase, mock_ai_integration):
        """Test documentation generation with custom title fallback."""
        context = {
            "description": "Database migration guide",
            "doc_type": "tutorial"
        }
        
        # Content without markdown title
        generated_content = """This guide explains how to perform database migrations.
        
Step 1: Backup your data...
Step 2: Run migration scripts..."""
        
        mock_ai_integration.generate_doc.return_value = generated_content
        mock_supabase.execute.return_value = Mock(data=[{"id": "123"}], error=None)
        
        result = service.generate_documentation(context)
        
        # Should use doc_type capitalized as title
        assert result["title"] == "Tutorial Documentation"
    
    def test_database_error_handling_patterns(self, service, mock_supabase):
        """Test various database error handling patterns."""
        doc_id = "test-123"
        
        # Test with error object
        mock_supabase.execute.return_value = Mock(
            data=None,
            error=Mock(message="Connection timeout")
        )
        
        with pytest.raises(DatabaseError) as exc_info:
            service.get_documentation_by_id(doc_id)
        
        # Test with exception during execute
        mock_supabase.execute.side_effect = RuntimeError("Network error")
        
        with pytest.raises(DatabaseError) as exc_info:
            service.get_documentation_by_id(doc_id)
        
        assert "Database error" in str(exc_info.value) or "Failed to fetch" in str(exc_info.value)
    
    def test_concurrent_documentation_generation(self, service, mock_supabase, mock_ai_integration):
        """Test behavior under concurrent generation scenarios."""
        contexts = [
            {"description": f"Service {i}", "doc_type": "api"}
            for i in range(3)
        ]
        
        mock_ai_integration.generate_doc.side_effect = [
            f"# Service {i} Documentation" for i in range(3)
        ]
        mock_supabase.execute.return_value = Mock(data=[{"id": "123"}], error=None)
        
        results = []
        for context in contexts:
            with patch('uuid.uuid4', return_value=f"uuid-{len(results)}"):
                result = service.generate_documentation(context)
                results.append(result)
        
        assert len(results) == 3
        assert all(r["doc_id"].startswith("uuid-") for r in results)
        assert results[0]["title"] == "Service 0 Documentation"
        assert results[2]["title"] == "Service 2 Documentation"
    
    def test_handle_iteration_preserves_metadata(self, service, mock_supabase, mock_ai_integration):
        """Test that iteration preserves document metadata."""
        doc_id = str(uuid.uuid4())
        original_doc = {
            "id": doc_id,
            "title": "API Guide",
            "content": "Original content",
            "doc_type": "api",
            "created_at": "2024-01-01T00:00:00",
            "feedback_history": [
                {"timestamp": "2024-01-02T00:00:00", "feedback": "Initial feedback"}
            ],
            "metadata": {"version": "1.0", "author": "system"}
        }
        
        with patch.object(service, 'get_documentation_by_id', return_value=original_doc):
            mock_ai_integration.update_doc.return_value = "Updated content"
            mock_supabase.execute.return_value = Mock(data=[original_doc], error=None)
            
            result = service.handle_iteration(doc_id, "New feedback")
        
        # Verify update preserves existing fields
        update_call = mock_supabase.update.call_args[0][0]
        assert len(update_call["feedback_history"]) == 2
        assert update_call["feedback_history"][0]["feedback"] == "Initial feedback"
        assert update_call["feedback_history"][1]["feedback"] == "New feedback"