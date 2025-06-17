import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from doc_agent.client import AutoDocClient
from app.services.doc_generation_service import DocGenerationService
from app.services.documentation_update_service import DocumentationUpdateService


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for integration tests."""
    client = Mock()
    # Mock async completion
    mock_completion = Mock()
    mock_completion.choices = [Mock()]
    mock_completion.choices[0].message.content = "Generated documentation content"
    client.chat.completions.create.return_value = mock_completion
    return client


@pytest.fixture
def mock_github_client():
    """Mock GitHub client for integration tests."""
    client = Mock()
    mock_repo = Mock()
    mock_repo.default_branch = "main"
    client.get_repo.return_value = mock_repo
    return client


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for integration tests."""
    client = Mock()
    mock_response = Mock()
    mock_response.data = [{"id": "doc-123"}]
    mock_response.error = None
    client.table.return_value.insert.return_value.execute.return_value = mock_response
    client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response
    return client


class TestDocumentationAutomationIntegration:
    """Integration tests for the complete documentation automation flow."""

    @pytest.mark.asyncio
    async def test_auto_doc_client_full_workflow(self, mock_openai_client, mock_github_client):
        """Test AutoDocClient end-to-end workflow."""
        # Setup
        client = AutoDocClient(
            openai_api_key="test-key",
            github_token="test-token",
            docs_repo="owner/docs-repo"
        )
        client.openai_client = mock_openai_client
        client.github = mock_github_client
        
        # Mock diff generation
        sample_diff = """diff --git a/api.py b/api.py
index 1111111..2222222 100644
--- a/api.py
+++ b/api.py
@@ -10,4 +10,7 @@ def get_users():
     return users
 
+def create_user(data):
+    # New endpoint for user creation
+    return user_service.create(data)
+"""
        
        # Mock OpenAI response for diff analysis
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = """--- a/docs/api.md
+++ b/docs/api.md
@@ -15,3 +15,10 @@ GET /users
 Returns a list of all users.
 
+## POST /users
+
+Creates a new user.
+
+**Request Body:** User data object
+**Response:** Created user object
+"""
        
        # Mock GitHub PR creation
        mock_pr = Mock()
        mock_pr.html_url = "https://github.com/owner/docs-repo/pull/42"
        mock_github_client.get_repo.return_value.create_pull.return_value = mock_pr
        
        # Execute workflow
        analyzed_diff = await client.analyze_diff(sample_diff)
        assert "POST /users" in analyzed_diff
        
        approved = client.propose_via_slack(analyzed_diff)
        assert approved is True
        
        pr_url = client.apply_patch(analyzed_diff, "abc123")
        assert pr_url == "https://github.com/owner/docs-repo/pull/42"

    def test_doc_generation_service_integration(self, mock_supabase_client):
        """Test DocGenerationService with realistic workflow."""
        service = DocGenerationService(mock_supabase_client)
        
        # Mock AI integration
        mock_ai = Mock()
        mock_ai.generate_doc.return_value = "# User API\n\nComprehensive user management API documentation."
        service.ai_integration = mock_ai
        
        # Mock task repository
        mock_task_repo = Mock()
        mock_task = Mock()
        mock_task_repo.get_task_by_id.return_value = mock_task
        mock_task_repo.update_task.return_value = True
        service.task_repository = mock_task_repo
        
        # Test documentation generation
        context = {
            "description": "Document the user management API endpoints",
            "file_references": ["user_controller.py", "user_model.py"],
            "doc_type": "api"
        }
        
        with patch('app.services.doc_generation_service.uuid.uuid4') as mock_uuid, \
             patch('app.services.doc_generation_service.datetime') as mock_datetime:
            
            mock_uuid.return_value = "doc-integration-test"
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"
            
            result = service.generate_documentation(context, "task-456")
        
        # Verify result
        assert result["doc_id"] == "doc-integration-test"
        assert result["title"] == "User API"
        assert "user management API documentation" in result["content"]
        assert result["generated_at"] == "2023-01-01T12:00:00"
        
        # Verify AI was called with correct parameters
        mock_ai.generate_doc.assert_called_once()
        ai_call_args = mock_ai.generate_doc.call_args[0][0]
        assert ai_call_args["description"] == "Document the user management API endpoints"
        assert ai_call_args["files"] == ["user_controller.py", "user_model.py"]
        assert ai_call_args["doc_type"] == "api"

    def test_documentation_update_service_integration(self):
        """Test DocumentationUpdateService with realistic scenario."""
        with patch('app.services.documentation_update_service.settings') as mock_settings:
            mock_settings.GITHUB_TOKEN = "test-token"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.DOCUMENTATION_OPENAI_MODEL = "gpt-4"
            
            with patch('app.services.documentation_update_service.OpenAI') as mock_openai_class, \
                 patch('app.services.documentation_update_service.Github') as mock_github_class:
                
                # Setup service
                service = DocumentationUpdateService()
                
                # Mock repository content
                mock_docs = [
                    {
                        "path": "api.md",
                        "content": "# API Documentation\n\n## GET /users\nReturns users",
                        "sha": "doc-sha-1"
                    },
                    {
                        "path": "setup.md", 
                        "content": "# Setup Guide\n\nHow to setup the application",
                        "sha": "doc-sha-2"
                    }
                ]
                service.get_repository_content = Mock(return_value=mock_docs)
                
                # Mock OpenAI analysis
                analysis_result = {
                    "changes_needed": True,
                    "analysis_summary": "New API endpoint requires documentation",
                    "proposed_changes": [
                        {
                            "file_path": "api.md",
                            "change_summary": "Add POST /users endpoint documentation",
                            "change_details": "Document the new user creation endpoint with request/response examples",
                            "justification": "New endpoint added in recent commit",
                            "priority": "high"
                        }
                    ],
                    "recommendations": "Keep API documentation up to date with code changes"
                }
                
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[0].message.content = str(analysis_result).replace("'", '"')
                service.openai_client.chat.completions.create.return_value = mock_completion
                
                # Test commit analysis
                commit_analysis = {
                    "commit_hash": "abc123def456",
                    "message": "Add user creation endpoint",
                    "key_changes": ["Added POST /users endpoint"],
                    "suggestions": ["Update API documentation"],
                    "technical_debt": [],
                    "files_changed": ["user_controller.py"]
                }
                
                with patch('app.services.documentation_update_service.json.loads') as mock_json:
                    mock_json.return_value = analysis_result
                    
                    result = service.analyze_documentation(
                        "owner/docs-repo",
                        commit_analysis,
                        "owner/source-repo"
                    )
                
                # Verify analysis result
                assert result["changes_needed"] is True
                assert len(result["proposed_changes"]) == 1
                assert result["proposed_changes"][0]["file_path"] == "api.md"
                assert "POST /users" in result["proposed_changes"][0]["change_summary"]
                assert result["docs_repository"] == "owner/docs-repo"
                assert result["source_repository"] == "owner/source-repo"

    def test_end_to_end_documentation_workflow(self, mock_supabase_client):
        """Test complete documentation workflow from generation to Git storage."""
        # Step 1: Generate documentation
        doc_service = DocGenerationService(mock_supabase_client)
        mock_ai = Mock()
        mock_ai.generate_doc.return_value = "# Payment API\n\nPayment processing documentation"
        doc_service.ai_integration = mock_ai
        
        with patch('app.services.doc_generation_service.uuid.uuid4') as mock_uuid, \
             patch('app.services.doc_generation_service.datetime') as mock_datetime:
            
            mock_uuid.return_value = "doc-e2e-test"
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T15:00:00"
            
            doc_result = doc_service.generate_documentation({
                "description": "Payment processing API documentation",
                "doc_type": "api"
            })
        
        # Step 2: Save to Git repository
        with patch('app.services.documentation_update_service.settings') as mock_settings:
            mock_settings.GITHUB_TOKEN = "test-token"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.DOCUMENTATION_OPENAI_MODEL = "gpt-4"
            
            with patch('app.services.documentation_update_service.OpenAI'), \
                 patch('app.services.documentation_update_service.Github') as mock_github_class:
                
                docs_service = DocumentationUpdateService()
                
                # Mock GitHub operations
                mock_repo = Mock()
                mock_repo.default_branch = "main"
                mock_repo.get_contents.side_effect = Exception("File not found")  # New file
                mock_result = {"commit": Mock()}
                mock_result["commit"].sha = "new-commit-sha"
                mock_repo.create_file.return_value = mock_result
                docs_service.github_client.get_repo.return_value = mock_repo
                
                git_result = docs_service.save_to_git_repository(
                    repo_name="owner/docs-repo",
                    file_path="api/payments",
                    content=doc_result["content"],
                    title=doc_result["title"]
                )
        
        # Step 3: Save reference back to document
        doc_service.save_doc_reference(
            doc_id=doc_result["doc_id"],
            doc_url=git_result["url"]
        )
        
        # Verify end-to-end workflow
        assert doc_result["doc_id"] == "doc-e2e-test"
        assert doc_result["title"] == "Payment API"
        assert git_result["status"] == "success"
        assert "api/payments.md" in git_result["file_path"]
        assert git_result["commit_sha"] == "new-commit-sha"

    def test_error_handling_integration(self, mock_supabase_client):
        """Test error handling across integrated services."""
        # Test cascade failure scenario
        doc_service = DocGenerationService(mock_supabase_client)
        
        # Mock AI failure
        mock_ai = Mock()
        mock_ai.generate_doc.return_value = None  # AI fails
        doc_service.ai_integration = mock_ai
        
        # Should raise AIIntegrationError
        with pytest.raises(Exception) as exc_info:
            doc_service.generate_documentation({
                "description": "Test documentation"
            })
        
        # Verify error propagation
        assert "AI failed to generate documentation content" in str(exc_info.value)

    def test_partial_failure_recovery(self, mock_supabase_client):
        """Test recovery from partial failures in the workflow."""
        doc_service = DocGenerationService(mock_supabase_client)
        
        # Mock successful AI generation
        mock_ai = Mock()
        mock_ai.generate_doc.return_value = "# Test Documentation\nContent"
        doc_service.ai_integration = mock_ai
        
        # Mock successful doc generation but failed reference save
        mock_task_repo = Mock()
        mock_task_repo.get_task_by_id.return_value = None  # Task not found
        doc_service.task_repository = mock_task_repo
        
        # Mock database operations
        mock_doc_response = Mock()
        mock_doc_response.data = [{"id": "doc-123"}]
        mock_doc_response.error = None
        
        mock_ref_response = Mock()
        mock_ref_response.error = None
        
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = mock_doc_response
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_ref_response
        
        with patch('app.services.doc_generation_service.uuid.uuid4') as mock_uuid, \
             patch('app.services.doc_generation_service.datetime') as mock_datetime:
            
            mock_uuid.return_value = "doc-partial-test"
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T16:00:00"
            
            # Document generation should succeed
            doc_result = doc_service.generate_documentation({
                "description": "Test documentation"
            })
            
            # Reference save should succeed despite missing task
            ref_result = doc_service.save_doc_reference(
                doc_id="doc-partial-test",
                doc_url="https://github.com/owner/repo/blob/main/test.md",
                related_task_id="nonexistent-task"
            )
        
        # Verify partial success
        assert doc_result["doc_id"] == "doc-partial-test"
        assert ref_result is True  # Should succeed despite task not found