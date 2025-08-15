import json
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from app.core.exceptions import AIIntegrationError, AppExceptionBase, ConfigurationError, ExternalServiceError
from app.services.documentation_update_service import DocumentationUpdateService


@pytest.fixture
def mock_settings():
    """Mock settings."""
    with patch("app.services.documentation_update_service.settings") as mock_settings:
        mock_settings.GITHUB_TOKEN = "test-github-token"
        mock_settings.OPENAI_API_KEY = "test-openai-key"
        mock_settings.DOCUMENTATION_OPENAI_MODEL = "gpt-4"
        yield mock_settings


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    return Mock()


@pytest.fixture
def mock_github_client():
    """Mock GitHub client."""
    return Mock()


@pytest.fixture
def doc_update_service(mock_settings):
    """DocumentationUpdateService instance with mocked dependencies."""
    with (
        patch("app.services.documentation_update_service.OpenAI") as mock_openai,
        patch("app.services.documentation_update_service.Github") as mock_github,
    ):

        service = DocumentationUpdateService()
        service.openai_client = mock_openai.return_value
        service.github_client = mock_github.return_value
        return service


class TestDocumentationUpdateService:
    """Test suite for DocumentationUpdateService."""

    def test_init_success(self, mock_settings):
        """Test successful service initialization."""
        with (
            patch("app.services.documentation_update_service.OpenAI") as mock_openai,
            patch("app.services.documentation_update_service.Github") as mock_github,
        ):

            service = DocumentationUpdateService()

            mock_openai.assert_called_once_with(api_key="test-openai-key")
            mock_github.assert_called_once_with("test-github-token")
            assert service.openai_model == "gpt-4"

    def test_init_missing_github_token(self, mock_settings):
        """Test initialization failure when GitHub token is missing."""
        mock_settings.GITHUB_TOKEN = None

        with pytest.raises(ConfigurationError) as exc_info:
            DocumentationUpdateService()

        assert "GitHub token not configured" in str(exc_info.value)

    def test_init_missing_openai_key(self, mock_settings):
        """Test initialization failure when OpenAI key is missing."""
        mock_settings.OPENAI_API_KEY = None

        with pytest.raises(ConfigurationError) as exc_info:
            DocumentationUpdateService()

        assert "OpenAI API key not configured" in str(exc_info.value)

    def test_init_client_initialization_error(self, mock_settings):
        """Test initialization failure when clients fail to initialize."""
        with patch("app.services.documentation_update_service.OpenAI", side_effect=Exception("OpenAI init failed")):
            with pytest.raises(ConfigurationError) as exc_info:
                DocumentationUpdateService()

            assert "Failed to initialize clients" in str(exc_info.value)

    def test_get_repository_content_success(self, doc_update_service):
        """Test successful repository content retrieval."""
        repo_name = "owner/test-repo"

        # Mock repository structure
        mock_repo = Mock()
        mock_file1 = Mock()
        mock_file1.type = "file"
        mock_file1.name = "README.md"
        mock_file1.path = "README.md"
        mock_file1.sha = "sha1"
        mock_file1.decoded_content = b"# README\nTest content"

        mock_file2 = Mock()
        mock_file2.type = "file"
        mock_file2.name = "api.md"
        mock_file2.path = "docs/api.md"
        mock_file2.sha = "sha2"
        mock_file2.decoded_content = b"# API\nAPI documentation"

        mock_dir = Mock()
        mock_dir.type = "dir"
        mock_dir.path = "docs"

        # Setup mock responses
        doc_update_service.github_client.get_repo.return_value = mock_repo
        mock_repo.get_contents.side_effect = [[mock_file1, mock_dir], [mock_file2]]  # Root level  # docs directory

        result = doc_update_service.get_repository_content(repo_name)

        assert len(result) == 2
        assert result[0]["path"] == "README.md"
        assert result[0]["content"] == "# README\nTest content"
        assert result[1]["path"] == "docs/api.md"
        assert result[1]["content"] == "# API\nAPI documentation"

    def test_get_repository_content_github_error(self, doc_update_service):
        """Test GitHub API error during content retrieval."""
        repo_name = "owner/test-repo"

        from github import GithubException

        github_error = GithubException(404, {"message": "Not Found"})
        doc_update_service.github_client.get_repo.side_effect = github_error

        with pytest.raises(ExternalServiceError) as exc_info:
            doc_update_service.get_repository_content(repo_name)

        assert "GitHub" in str(exc_info.value)
        assert "Not Found" in str(exc_info.value)

    def test_get_repository_content_no_markdown_files(self, doc_update_service):
        """Test repository with no markdown files."""
        repo_name = "owner/test-repo"

        mock_repo = Mock()
        mock_file = Mock()
        mock_file.type = "file"
        mock_file.name = "script.py"
        mock_file.path = "script.py"

        doc_update_service.github_client.get_repo.return_value = mock_repo
        mock_repo.get_contents.return_value = [mock_file]

        result = doc_update_service.get_repository_content(repo_name)

        assert len(result) == 0

    def test_analyze_documentation_success(self, doc_update_service):
        """Test successful documentation analysis."""
        docs_repo_name = "owner/docs-repo"
        source_repo_name = "owner/source-repo"
        commit_analysis = {
            "commit_hash": "abc123",
            "message": "Add new feature",
            "key_changes": ["Added new API endpoint"],
            "suggestions": ["Update documentation"],
            "technical_debt": [],
            "files_changed": ["api.py"],
        }

        # Mock documentation files
        docs_files = [{"path": "api.md", "content": "# API\nExisting API docs"}]
        doc_update_service.get_repository_content = Mock(return_value=docs_files)

        # Mock OpenAI response
        analysis_response = {
            "changes_needed": True,
            "analysis_summary": "API documentation needs updates",
            "proposed_changes": [
                {
                    "file_path": "api.md",
                    "change_summary": "Add new endpoint documentation",
                    "change_details": "Document the new /users endpoint",
                    "justification": "New endpoint added in commit",
                    "priority": "high",
                }
            ],
            "recommendations": "Update API docs regularly",
        }

        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = json.dumps(analysis_response)
        doc_update_service.openai_client.chat.completions.create.return_value = mock_completion

        with patch("app.services.documentation_update_service.datetime") as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T00:00:00"

            result = doc_update_service.analyze_documentation(docs_repo_name, commit_analysis, source_repo_name)

        assert result["changes_needed"] is True
        assert len(result["proposed_changes"]) == 1
        assert result["analyzed_at"] == "2023-01-01T00:00:00"
        assert result["docs_repository"] == docs_repo_name
        assert result["source_repository"] == source_repo_name

    def test_analyze_documentation_no_files(self, doc_update_service):
        """Test analysis with no documentation files found."""
        docs_repo_name = "owner/docs-repo"
        source_repo_name = "owner/source-repo"
        commit_analysis = {"commit_hash": "abc123"}

        doc_update_service.get_repository_content = Mock(return_value=[])

        result = doc_update_service.analyze_documentation(docs_repo_name, commit_analysis, source_repo_name)

        assert result["status"] == "no_files_found"
        assert result["changes_needed"] is False

    def test_analyze_documentation_openai_error(self, doc_update_service):
        """Test OpenAI API error during analysis."""
        docs_repo_name = "owner/docs-repo"
        source_repo_name = "owner/source-repo"
        commit_analysis = {"commit_hash": "abc123"}

        docs_files = [{"path": "api.md", "content": "# API docs"}]
        doc_update_service.get_repository_content = Mock(return_value=docs_files)

        from openai import APIError as OpenAIAPIError

        openai_error = OpenAIAPIError("Rate limit exceeded")
        openai_error.status_code = 429
        openai_error.response = {"error": {"message": "Rate limit exceeded"}}
        doc_update_service.openai_client.chat.completions.create.side_effect = openai_error

        with pytest.raises(AIIntegrationError) as exc_info:
            doc_update_service.analyze_documentation(docs_repo_name, commit_analysis, source_repo_name)

        assert "OpenAI service error" in str(exc_info.value)

    def test_create_analysis_prompt(self, doc_update_service):
        """Test analysis prompt creation."""
        docs_content = "# API\nExisting documentation"
        doc_files_list = ["api.md", "guide.md"]
        commit_analysis = {
            "key_changes": ["Added new endpoint"],
            "suggestions": ["Update docs"],
            "technical_debt": [],
            "message": "Add feature",
            "commit_hash": "abc123",
            "files_changed": ["api.py"],
        }
        source_repo = "owner/repo"

        prompt = doc_update_service._create_analysis_prompt(docs_content, doc_files_list, commit_analysis, source_repo)

        assert "owner/repo" in prompt
        assert "abc123" in prompt
        assert "Add feature" in prompt
        assert "Added new endpoint" in prompt
        assert "api.md" in prompt
        assert "# API\nExisting documentation" in prompt

    def test_create_pull_request_success(self, doc_update_service):
        """Test successful pull request creation."""
        docs_repo_name = "owner/docs-repo"
        proposed_changes = [
            {
                "file_path": "api.md",
                "change_summary": "Add new endpoint docs",
                "change_details": "Document the /users endpoint",
                "justification": "New API endpoint added",
            }
        ]
        commit_analysis = {"commit_hash": "abc123def456", "repository": "owner/source-repo"}

        # Mock GitHub operations
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_ref = Mock()
        mock_ref.object.sha = "base-sha"
        mock_repo.get_git_ref.return_value = mock_ref
        mock_repo.create_git_ref = Mock()

        # Mock file operations
        mock_file_content = Mock()
        mock_file_content.decoded_content = b"# API\nExisting content"
        mock_file_content.sha = "file-sha"
        mock_repo.get_contents.return_value = mock_file_content
        mock_repo.update_file = Mock()

        # Mock PR creation
        mock_pr = Mock()
        mock_pr.number = 42
        mock_pr.html_url = "https://github.com/owner/docs-repo/pull/42"
        mock_repo.create_pull.return_value = mock_pr

        doc_update_service.github_client.get_repo.return_value = mock_repo

        # Mock OpenAI for content generation
        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = "# API\nUpdated content with new endpoint"
        doc_update_service.openai_client.chat.completions.create.return_value = mock_completion

        with patch("app.services.documentation_update_service.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20230101120000"

            result = doc_update_service.create_pull_request(docs_repo_name, proposed_changes, commit_analysis)

        assert result["status"] == "success"
        assert result["pull_request_number"] == 42
        assert result["pull_request_url"] == "https://github.com/owner/docs-repo/pull/42"

        # Verify GitHub API calls
        mock_repo.create_git_ref.assert_called_once()
        mock_repo.update_file.assert_called_once()
        mock_repo.create_pull.assert_called_once()

    def test_create_pull_request_no_changes(self, doc_update_service):
        """Test PR creation with no changes."""
        result = doc_update_service.create_pull_request("owner/repo", [], {})

        assert result["status"] == "no_changes"
        assert result["message"] == "No documentation changes needed"

    def test_save_to_git_repository_new_file(self, doc_update_service):
        """Test saving new file to Git repository."""
        repo_name = "owner/docs-repo"
        file_path = "new-doc"
        content = "# New Documentation\nContent here"
        title = "New Documentation"

        # Mock repository
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_repo.get_contents.side_effect = Exception("File not found")  # File doesn't exist

        # Mock file creation
        mock_result = {"commit": Mock()}
        mock_result["commit"].sha = "new-commit-sha"
        mock_repo.create_file.return_value = mock_result

        doc_update_service.github_client.get_repo.return_value = mock_repo

        result = doc_update_service.save_to_git_repository(repo_name, file_path, content, title)

        assert result["status"] == "success"
        assert result["file_path"] == "new-doc.md"
        assert result["commit_sha"] == "new-commit-sha"
        assert "github.com/owner/docs-repo/blob/main/new-doc.md" in result["url"]

        mock_repo.create_file.assert_called_once()

    def test_save_to_git_repository_update_existing(self, doc_update_service):
        """Test updating existing file in Git repository."""
        repo_name = "owner/docs-repo"
        file_path = "existing-doc.md"
        content = "# Updated Documentation\nNew content"
        title = "Updated Documentation"

        # Mock repository
        mock_repo = Mock()
        mock_repo.default_branch = "main"

        # Mock existing file
        mock_file_content = Mock()
        mock_file_content.sha = "existing-sha"
        mock_repo.get_contents.return_value = mock_file_content

        # Mock file update
        mock_result = {"commit": Mock()}
        mock_result["commit"].sha = "updated-commit-sha"
        mock_repo.update_file.return_value = mock_result

        doc_update_service.github_client.get_repo.return_value = mock_repo

        result = doc_update_service.save_to_git_repository(repo_name, file_path, content, title)

        assert result["status"] == "success"
        assert result["file_path"] == "existing-doc.md"
        assert result["commit_sha"] == "updated-commit-sha"

        mock_repo.update_file.assert_called_once()

    def test_save_to_git_repository_github_error(self, doc_update_service):
        """Test GitHub error during file save."""
        repo_name = "owner/docs-repo"
        file_path = "test-doc.md"
        content = "# Test"
        title = "Test"

        from github import GithubException

        github_error = GithubException(403, {"message": "Permission denied"})
        doc_update_service.github_client.get_repo.side_effect = github_error

        with pytest.raises(ExternalServiceError) as exc_info:
            doc_update_service.save_to_git_repository(repo_name, file_path, content, title)

        assert "GitHub" in str(exc_info.value)
        assert "Permission denied" in str(exc_info.value)

    def test_log_separator(self, doc_update_service):
        """Test log separator utility method."""
        with patch("app.services.documentation_update_service.logger") as mock_logger:
            doc_update_service._log_separator("TEST MESSAGE", "*", 20)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "TEST MESSAGE" in call_args
            assert "*" in call_args

    def test_log_separator_no_message(self, doc_update_service):
        """Test log separator without message."""
        with patch("app.services.documentation_update_service.logger") as mock_logger:
            doc_update_service._log_separator()

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert call_args == "=" * 80
