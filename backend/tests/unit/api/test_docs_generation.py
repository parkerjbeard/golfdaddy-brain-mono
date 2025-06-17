import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.api.docs_generation import router
from app.core.exceptions import (
    AIIntegrationError,
    ExternalServiceError,
    ResourceNotFoundError,
    DatabaseError
)


@pytest.fixture
def client():
    """Test client for the docs generation API."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    return Mock()


@pytest.fixture
def mock_doc_service():
    """Mock DocGenerationService."""
    return Mock()


@pytest.fixture
def mock_docs_update_service():
    """Mock DocumentationUpdateService."""
    return Mock()


class TestDocsGenerationAPI:
    """Test suite for documentation generation API endpoints."""

    def test_generate_documentation_success_basic(self, client):
        """Test successful documentation generation without Git integration."""
        request_data = {
            "description": "API documentation for user management",
            "file_references": ["user.py", "auth.py"],
            "doc_type": "api",
            "format": "markdown"
        }
        
        mock_generated_doc = {
            "doc_id": "doc-123",
            "title": "User Management API",
            "content": "# User Management API\n\nDetailed documentation...",
            "generated_at": "2023-01-01T00:00:00"
        }
        
        with patch('app.api.docs_generation.get_supabase_client') as mock_get_supabase, \
             patch('app.api.docs_generation.DocGenerationService') as mock_service_class:
            
            mock_service = Mock()
            mock_service.generate_documentation.return_value = mock_generated_doc
            mock_service_class.return_value = mock_service
            
            response = client.post("/docs", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["doc_id"] == "doc-123"
        assert data["title"] == "User Management API"
        assert data["content"] == "# User Management API\n\nDetailed documentation..."
        assert data["generated_at"] == "2023-01-01T00:00:00"
        assert data["git_url"] is None
        
        mock_service.generate_documentation.assert_called_once()

    def test_generate_documentation_success_with_git(self, client):
        """Test successful documentation generation with Git repository integration."""
        request_data = {
            "description": "API documentation for user management",
            "doc_type": "api",
            "format": "markdown",
            "related_task_id": "task-456",
            "git_repo_name": "owner/docs-repo",
            "git_path": "api/users.md"
        }
        
        mock_generated_doc = {
            "doc_id": "doc-123",
            "title": "User Management API",
            "content": "# User Management API\n\nDetailed documentation...",
            "generated_at": "2023-01-01T00:00:00"
        }
        
        mock_git_result = {
            "status": "success",
            "url": "https://github.com/owner/docs-repo/blob/main/api/users.md"
        }
        
        with patch('app.api.docs_generation.get_supabase_client') as mock_get_supabase, \
             patch('app.api.docs_generation.DocGenerationService') as mock_service_class, \
             patch('app.api.docs_generation.DocumentationUpdateService') as mock_docs_service_class:
            
            mock_service = Mock()
            mock_service.generate_documentation.return_value = mock_generated_doc
            mock_service.save_doc_reference.return_value = True
            mock_service_class.return_value = mock_service
            
            mock_docs_service = Mock()
            mock_docs_service.save_to_git_repository.return_value = mock_git_result
            mock_docs_service_class.return_value = mock_docs_service
            
            response = client.post("/docs", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["doc_id"] == "doc-123"
        assert data["git_url"] == "https://github.com/owner/docs-repo/blob/main/api/users.md"
        
        # Verify Git integration was called
        mock_docs_service.save_to_git_repository.assert_called_once_with(
            repo_name="owner/docs-repo",
            file_path="api/users.md",
            content="# User Management API\n\nDetailed documentation...",
            title="User Management API",
            commit_message="Add documentation: User Management API"
        )
        
        # Verify doc reference was saved
        mock_service.save_doc_reference.assert_called_once_with(
            doc_id="doc-123",
            doc_url="https://github.com/owner/docs-repo/blob/main/api/users.md",
            related_task_id="task-456"
        )

    def test_generate_documentation_ai_integration_error(self, client):
        """Test AI integration error during documentation generation."""
        request_data = {
            "description": "Test documentation",
            "doc_type": "api"
        }
        
        mock_error_doc = {
            "error": "AI service is currently unavailable"
        }
        
        with patch('app.api.docs_generation.get_supabase_client') as mock_get_supabase, \
             patch('app.api.docs_generation.DocGenerationService') as mock_service_class:
            
            mock_service = Mock()
            mock_service.generate_documentation.return_value = mock_error_doc
            mock_service_class.return_value = mock_service
            
            response = client.post("/docs", json=request_data)
        
        assert response.status_code == 500  # AIIntegrationError maps to 500
        
    def test_generate_documentation_git_save_error(self, client):
        """Test error during Git repository save (should not fail the entire request)."""
        request_data = {
            "description": "Test documentation",
            "doc_type": "api",
            "git_repo_name": "owner/docs-repo",
            "git_path": "test.md"
        }
        
        mock_generated_doc = {
            "doc_id": "doc-123",
            "title": "Test Documentation",
            "content": "# Test\nContent",
            "generated_at": "2023-01-01T00:00:00"
        }
        
        with patch('app.api.docs_generation.get_supabase_client') as mock_get_supabase, \
             patch('app.api.docs_generation.DocGenerationService') as mock_service_class, \
             patch('app.api.docs_generation.DocumentationUpdateService') as mock_docs_service_class:
            
            mock_service = Mock()
            mock_service.generate_documentation.return_value = mock_generated_doc
            mock_service_class.return_value = mock_service
            
            mock_docs_service = Mock()
            mock_docs_service.save_to_git_repository.side_effect = Exception("Git save failed")
            mock_docs_service_class.return_value = mock_docs_service
            
            response = client.post("/docs", json=request_data)
        
        # Should still succeed despite Git error
        assert response.status_code == 200
        data = response.json()
        assert data["doc_id"] == "doc-123"
        assert data["git_url"] is None  # Git URL should be None due to error

    def test_generate_documentation_database_error(self, client):
        """Test database error during documentation generation."""
        request_data = {
            "description": "Test documentation",
            "doc_type": "api"
        }
        
        with patch('app.api.docs_generation.get_supabase_client') as mock_get_supabase, \
             patch('app.api.docs_generation.DocGenerationService') as mock_service_class:
            
            mock_service = Mock()
            mock_service.generate_documentation.side_effect = DatabaseError("Database connection failed")
            mock_service_class.return_value = mock_service
            
            response = client.post("/docs", json=request_data)
        
        assert response.status_code == 500  # DatabaseError maps to 500

    def test_generate_documentation_invalid_request_data(self, client):
        """Test request with missing required fields."""
        request_data = {
            # Missing required 'description' field
            "doc_type": "api"
        }
        
        response = client.post("/docs", json=request_data)
        
        assert response.status_code == 422  # Validation error

    def test_generate_documentation_empty_description(self, client):
        """Test request with empty description."""
        request_data = {
            "description": "",
            "doc_type": "api"
        }
        
        response = client.post("/docs", json=request_data)
        
        assert response.status_code == 422  # Validation error for empty string

    def test_generate_documentation_with_task_id(self, client):
        """Test documentation generation linked to a task."""
        request_data = {
            "description": "Task-related documentation",
            "doc_type": "feature",
            "related_task_id": "task-789"
        }
        
        mock_generated_doc = {
            "doc_id": "doc-456",
            "title": "Feature Documentation",
            "content": "# Feature\nDocumentation content",
            "generated_at": "2023-01-01T00:00:00"
        }
        
        with patch('app.api.docs_generation.get_supabase_client') as mock_get_supabase, \
             patch('app.api.docs_generation.DocGenerationService') as mock_service_class:
            
            mock_service = Mock()
            mock_service.generate_documentation.return_value = mock_generated_doc
            mock_service_class.return_value = mock_service
            
            response = client.post("/docs", json=request_data)
        
        assert response.status_code == 200
        
        # Verify task ID was passed to service
        mock_service.generate_documentation.assert_called_once()
        call_args = mock_service.generate_documentation.call_args
        assert call_args[1]["related_task_id"] == "task-789"

    def test_generate_documentation_custom_format(self, client):
        """Test documentation generation with custom format."""
        request_data = {
            "description": "HTML documentation",
            "doc_type": "guide",
            "format": "html"
        }
        
        mock_generated_doc = {
            "doc_id": "doc-html",
            "title": "HTML Guide",
            "content": "<h1>HTML Guide</h1><p>Content</p>",
            "generated_at": "2023-01-01T00:00:00"
        }
        
        with patch('app.api.docs_generation.get_supabase_client') as mock_get_supabase, \
             patch('app.api.docs_generation.DocGenerationService') as mock_service_class:
            
            mock_service = Mock()
            mock_service.generate_documentation.return_value = mock_generated_doc
            mock_service_class.return_value = mock_service
            
            response = client.post("/docs", json=request_data)
        
        assert response.status_code == 200
        
        # Verify format was passed to service
        call_args = mock_service.generate_documentation.call_args[0][0]
        assert call_args["format"] == "html"

    def test_generate_documentation_with_file_references(self, client):
        """Test documentation generation with file references."""
        request_data = {
            "description": "Component documentation",
            "doc_type": "component",
            "file_references": [
                "src/components/Button.tsx",
                "src/components/Button.test.tsx",
                "src/styles/button.css"
            ]
        }
        
        mock_generated_doc = {
            "doc_id": "doc-component",
            "title": "Button Component",
            "content": "# Button Component\nDocumentation with references",
            "generated_at": "2023-01-01T00:00:00"
        }
        
        with patch('app.api.docs_generation.get_supabase_client') as mock_get_supabase, \
             patch('app.api.docs_generation.DocGenerationService') as mock_service_class:
            
            mock_service = Mock()
            mock_service.generate_documentation.return_value = mock_generated_doc
            mock_service_class.return_value = mock_service
            
            response = client.post("/docs", json=request_data)
        
        assert response.status_code == 200
        
        # Verify file references were passed to service
        call_args = mock_service.generate_documentation.call_args[0][0]
        assert call_args["file_references"] == [
            "src/components/Button.tsx",
            "src/components/Button.test.tsx",
            "src/styles/button.css"
        ]

    def test_documentation_request_model_validation(self):
        """Test the DocumentationRequest Pydantic model validation."""
        from app.api.docs_generation import DocumentationRequest
        
        # Valid request
        valid_data = {
            "description": "Test documentation",
            "doc_type": "api",
            "format": "markdown"
        }
        request = DocumentationRequest(**valid_data)
        assert request.description == "Test documentation"
        assert request.doc_type == "api"
        assert request.format == "markdown"
        assert request.file_references is None
        assert request.related_task_id is None
        assert request.git_repo_name is None
        assert request.git_path is None
        
        # Test with all fields
        full_data = {
            "description": "Complete documentation",
            "doc_type": "guide",
            "format": "html",
            "file_references": ["file1.py", "file2.py"],
            "related_task_id": "task-123",
            "git_repo_name": "owner/repo",
            "git_path": "docs/guide.md"
        }
        full_request = DocumentationRequest(**full_data)
        assert full_request.file_references == ["file1.py", "file2.py"]
        assert full_request.related_task_id == "task-123"
        assert full_request.git_repo_name == "owner/repo"
        assert full_request.git_path == "docs/guide.md"

    def test_documentation_response_model(self):
        """Test the DocumentationResponse Pydantic model."""
        from app.api.docs_generation import DocumentationResponse
        
        response_data = {
            "doc_id": "doc-123",
            "title": "Test Documentation",
            "content": "# Test\nContent here",
            "generated_at": "2023-01-01T00:00:00",
            "git_url": "https://github.com/owner/repo/blob/main/test.md"
        }
        
        response = DocumentationResponse(**response_data)
        assert response.doc_id == "doc-123"
        assert response.title == "Test Documentation"
        assert response.content == "# Test\nContent here"
        assert response.generated_at == "2023-01-01T00:00:00"
        assert response.git_url == "https://github.com/owner/repo/blob/main/test.md"