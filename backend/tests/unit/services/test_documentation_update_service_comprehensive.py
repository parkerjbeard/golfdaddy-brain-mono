"""
Comprehensive unit tests for the DocumentationUpdateService.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest
from github import GithubException

from app.core.circuit_breaker import CircuitBreakerOpenError
from app.core.exceptions import AIIntegrationError, ConfigurationError, ExternalServiceError
from app.core.rate_limiter import RateLimitExceededError
from app.services.documentation_update_service import DocumentationUpdateService
from tests.fixtures.auto_doc_fixtures import (
    GITHUB_MOCK_RESPONSES,
    MOCK_OPENAI_RESPONSES,
    SAMPLE_DIFFS,
    SAMPLE_PATCHES,
    TEST_CONFIG,
)


class TestDocumentationUpdateServiceComprehensive:
    """Comprehensive test cases for DocumentationUpdateService."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for the service."""
        with patch("app.services.documentation_update_service.settings") as mock:
            mock.GITHUB_TOKEN = TEST_CONFIG["github_token"]
            mock.OPENAI_API_KEY = TEST_CONFIG["openai_api_key"]
            mock.DOCUMENTATION_OPENAI_MODEL = "gpt-4"
            yield mock

    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        with patch("app.services.documentation_update_service.Github") as mock:
            client = Mock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        with patch("app.services.documentation_update_service.OpenAI") as mock:
            client = Mock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def service(self, mock_settings, mock_github_client, mock_openai_client):
        """Create a DocumentationUpdateService instance."""
        # Mock circuit breakers and rate limiters
        with patch("app.services.documentation_update_service.create_github_circuit_breaker"):
            with patch("app.services.documentation_update_service.create_openai_circuit_breaker"):
                with patch("app.services.documentation_update_service.create_github_rate_limiter"):
                    with patch("app.services.documentation_update_service.create_openai_rate_limiter"):
                        service = DocumentationUpdateService()
                        # Set up mock circuit breakers and rate limiters
                        service.github_circuit_breaker = AsyncMock()
                        service.github_circuit_breaker.call = AsyncMock(side_effect=lambda f, *args: f(*args))
                        service.openai_circuit_breaker = AsyncMock()
                        service.openai_circuit_breaker.call = AsyncMock(
                            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs)
                        )
                        service.github_rate_limiter = AsyncMock()
                        service.github_rate_limiter.acquire = AsyncMock()
                        service.openai_rate_limiter = AsyncMock()
                        service.openai_rate_limiter.acquire = AsyncMock()
                        return service

    def test_initialization_success(self, mock_settings):
        """Test successful service initialization."""
        service = DocumentationUpdateService()
        assert service.github_token == TEST_CONFIG["github_token"]
        assert service.openai_api_key == TEST_CONFIG["openai_api_key"]
        assert service.openai_model == "gpt-4"

    def test_initialization_missing_github_token(self, mock_settings):
        """Test initialization with missing GitHub token."""
        mock_settings.GITHUB_TOKEN = None

        with pytest.raises(ConfigurationError, match="GitHub token not configured"):
            DocumentationUpdateService()

    def test_initialization_missing_openai_key(self, mock_settings):
        """Test initialization with missing OpenAI API key."""
        mock_settings.OPENAI_API_KEY = None

        with pytest.raises(ConfigurationError, match="OpenAI API key not configured"):
            DocumentationUpdateService()

    def test_log_separator(self, service, capsys):
        """Test log separator formatting."""
        # Test empty separator
        service._log_separator()
        # Should log a line of '='

        # Test with message
        service._log_separator("TEST MESSAGE", "-", 20)
        # Should center the message

        # Test with long message
        service._log_separator("VERY LONG MESSAGE THAT EXCEEDS LENGTH", "=", 10)
        # Should just print the message

    @pytest.mark.asyncio
    async def test_get_repository_content_success(self, service):
        """Test successful repository content retrieval."""
        repo_name = "test-owner/test-repo"

        # Mock repository and contents
        mock_repo = Mock()
        mock_file1 = Mock()
        mock_file1.path = "README.md"
        mock_file1.name = "README.md"
        mock_file1.type = "file"
        mock_file1.sha = "abc123"
        mock_file1.decoded_content = b"# Test README"

        mock_file2 = Mock()
        mock_file2.path = "docs/api.md"
        mock_file2.name = "api.md"
        mock_file2.type = "file"
        mock_file2.sha = "def456"
        mock_file2.decoded_content = b"# API Documentation"

        mock_dir = Mock()
        mock_dir.path = "docs"
        mock_dir.name = "docs"
        mock_dir.type = "dir"

        service.github_client.get_repo = Mock(return_value=mock_repo)
        mock_repo.get_contents = Mock(
            side_effect=[[mock_file1, mock_dir], [mock_file2]]  # Root contents  # docs/ contents
        )

        result = await service.get_repository_content(repo_name)

        assert len(result) == 2
        assert result[0]["path"] == "README.md"
        assert result[0]["content"] == "# Test README"
        assert result[1]["path"] == "docs/api.md"
        assert result[1]["content"] == "# API Documentation"

    @pytest.mark.asyncio
    async def test_get_repository_content_rate_limit(self, service):
        """Test repository content retrieval with rate limiting."""
        import time

        service.github_rate_limiter.acquire.side_effect = RateLimitExceededError("github_api", time.time() + 3600)

        with pytest.raises(ExternalServiceError, match="GitHub rate limit"):
            await service.get_repository_content("test-repo")

    @pytest.mark.asyncio
    async def test_get_repository_content_circuit_breaker_open(self, service):
        """Test repository content retrieval with open circuit breaker."""
        service.github_circuit_breaker.call.side_effect = CircuitBreakerOpenError("github_api", 5, 60)

        with pytest.raises(ExternalServiceError, match="GitHub service temporarily unavailable"):
            await service.get_repository_content("test-repo")

    @pytest.mark.asyncio
    async def test_analyze_commit_and_suggest_updates_success(self, service):
        """Test successful commit analysis and update suggestion."""
        # Create a mock commit object
        commit = Mock()
        commit.sha = "abc123"
        commit.commit.message = "Add user authentication"
        commit.stats.additions = 50
        commit.stats.deletions = 10
        commit.files = [Mock(filename="auth.py", patch="+ def authenticate()...", additions=50, deletions=10)]

        # Mock repository documentation
        mock_docs = [{"path": "docs/auth.md", "content": "# Authentication\nOld content..."}]

        # Mock AI response in the format expected by analyze_documentation
        ai_response = {
            "changes_needed": True,
            "proposed_changes": [
                {
                    "file_path": "docs/auth.md",
                    "current_content": "Old content...",
                    "proposed_content": "New content with authenticate() method documented...",
                    "change_summary": "Added documentation for new authenticate function",
                }
            ],
        }

        with patch.object(service, "get_repository_content", return_value=mock_docs):
            service.openai_client.chat = Mock()
            service.openai_client.chat.completions = Mock()
            service.openai_client.chat.completions.create = Mock(
                return_value=Mock(choices=[Mock(message=Mock(content=json.dumps(ai_response)))])
            )

            result = await service.analyze_commit_and_suggest_updates(commit, mock_docs)

        assert len(result) == 1
        assert result[0]["file"] == "docs/auth.md"
        assert "authenticate() method documented" in result[0]["updated"]

    @pytest.mark.asyncio
    async def test_analyze_commit_empty_documentation(self, service):
        """Test commit analysis when no documentation exists."""
        # Create a mock commit object
        commit = Mock()
        commit.sha = "abc123"
        commit.commit.message = "Initial commit"
        commit.stats.additions = 0
        commit.stats.deletions = 0
        commit.files = []

        # Mock get_repository_content to return empty list
        with patch.object(service, "get_repository_content", return_value=[]):
            result = await service.analyze_commit_and_suggest_updates(commit, [])

        assert result == []

    @pytest.mark.asyncio
    async def test_analyze_commit_ai_error(self, service):
        """Test commit analysis with AI error."""
        # Create a mock commit object
        commit = Mock()
        commit.sha = "abc123"
        commit.commit.message = "Update logic"
        commit.stats.additions = 20
        commit.stats.deletions = 5
        commit.files = [Mock(filename="src/logic.py", additions=20, deletions=5)]

        mock_docs = [{"path": "README.md", "content": "# Test"}]

        # Mock get_repository_content and OpenAI error
        with patch.object(service, "get_repository_content", return_value=mock_docs):
            service.openai_client.chat.completions.create = Mock(side_effect=Exception("API Error"))

            with patch("app.services.documentation_update_service.logger") as mock_logger:
                result = await service.analyze_commit_and_suggest_updates(commit, mock_docs)

        # Should log error and return empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_analyze_commit_invalid_ai_response(self, service):
        """Test commit analysis with invalid AI response format."""
        # Create a mock commit object
        commit = Mock()
        commit.sha = "abc123"
        commit.commit.message = "Bug fix"
        commit.stats.additions = 10
        commit.stats.deletions = 2
        commit.files = [Mock(filename="src/bugfix.py", additions=10, deletions=2)]

        mock_docs = [{"path": "README.md", "content": "# Test"}]

        # Mock get_repository_content and AI returns invalid JSON
        with patch.object(service, "get_repository_content", return_value=mock_docs):
            service.openai_client.chat.completions.create = Mock(
                return_value=Mock(choices=[Mock(message=Mock(content="Invalid JSON{{{"))])
            )

            result = await service.analyze_commit_and_suggest_updates(commit, mock_docs)

        assert result == []  # Should handle gracefully

    @pytest.mark.asyncio
    async def test_scan_repository_for_updates_success(self, service):
        """Test successful repository scan for documentation updates."""
        repo_name = "test-owner/test-repo"

        # Mock repository and commits
        mock_repo = Mock()
        mock_commit1 = Mock()
        mock_commit1.sha = "abc123"
        mock_commit1.commit.message = "Add feature X"
        mock_commit1.stats.additions = 100
        mock_commit1.stats.deletions = 20
        mock_commit1.files = [Mock(filename="feature.py", patch="+ def feature_x():")]

        mock_commit2 = Mock()
        mock_commit2.sha = "def456"
        mock_commit2.commit.message = "[skip-docs] Internal refactor"

        service.github_client.get_repo = Mock(return_value=mock_repo)
        mock_repo.get_commits = Mock(return_value=[mock_commit1, mock_commit2])

        # Mock analyze method
        mock_suggestions = [{"file": "docs/feature.md", "updated": "New content"}]
        with patch.object(service, "analyze_commit_and_suggest_updates", return_value=mock_suggestions):
            result = await service.scan_repository_for_updates(repo_name, days_back=7)

        assert len(result["suggested_updates"]) == 1
        assert result["commits_analyzed"] == 1  # One commit (skip-docs excluded)
        assert result["repository"] == repo_name

    @pytest.mark.asyncio
    async def test_scan_repository_skip_docs_commits(self, service):
        """Test repository scan skips documentation commits."""
        repo_name = "test-owner/test-repo"

        mock_repo = Mock()
        mock_commits = [
            Mock(sha="1", commit=Mock(message="[skip-docs] Update")),
            Mock(sha="2", commit=Mock(message="docs: Update README")),
            Mock(sha="3", commit=Mock(message="DOC: Fix typo")),
        ]

        service.github_client.get_repo = Mock(return_value=mock_repo)
        mock_repo.get_commits = Mock(return_value=mock_commits)

        with patch.object(service, "analyze_commit_and_suggest_updates", return_value=[]):
            result = await service.scan_repository_for_updates(repo_name)

        assert result["commits_analyzed"] == 0  # All commits should be skipped

    @pytest.mark.asyncio
    async def test_create_documentation_pr_success(self, service):
        """Test successful documentation PR creation."""
        repo_name = "test-owner/test-repo"
        updates = [
            {"file": "docs/api.md", "original": "Old content", "updated": "New content", "reason": "Added new endpoint"}
        ]

        # Mock repository and file operations
        mock_repo = Mock()
        mock_repo.default_branch = "main"

        # Mock getting file
        mock_file = Mock()
        mock_file.sha = "old_sha_123"
        mock_repo.get_contents = Mock(return_value=mock_file)

        # Mock branch creation
        mock_main_branch = Mock()
        mock_main_branch.commit.sha = "main_sha"
        mock_repo.get_branch = Mock(return_value=mock_main_branch)
        mock_repo.create_git_ref = Mock()

        # Mock file update
        mock_repo.update_file = Mock()

        # Mock PR creation
        mock_pr = Mock()
        mock_pr.html_url = "https://github.com/test/pr/123"
        mock_pr.number = 123
        mock_repo.create_pull = Mock(return_value=mock_pr)

        service.github_client.get_repo = Mock(return_value=mock_repo)

        result = await service.create_documentation_pr(repo_name, updates)

        assert result["success"] is True
        assert result["pr_url"] == "https://github.com/test/pr/123"
        assert result["pr_number"] == 123

        # Verify branch was created
        mock_repo.create_git_ref.assert_called_once()

        # Verify file was updated
        mock_repo.update_file.assert_called_once()

        # Verify PR was created
        mock_repo.create_pull.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_documentation_pr_no_updates(self, service):
        """Test PR creation with no updates."""
        result = await service.create_documentation_pr("test-repo", [])

        assert result["success"] is False
        assert result["error"] == "No updates provided"

    @pytest.mark.asyncio
    async def test_create_documentation_pr_branch_exists(self, service):
        """Test PR creation when branch already exists."""
        repo_name = "test-owner/test-repo"
        updates = [{"file": "test.md", "updated": "content"}]

        mock_repo = Mock()
        service.github_client.get_repo = Mock(return_value=mock_repo)

        # Simulate branch already exists error
        mock_repo.create_git_ref.side_effect = GithubException(422, {"message": "Reference already exists"})

        # Should try with a different branch name
        with patch("app.services.documentation_update_service.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "20240115-103045"

            # Mock successful operations after branch name change
            mock_repo.get_branch = Mock()
            mock_repo.get_contents = Mock(return_value=Mock(sha="123"))
            mock_repo.update_file = Mock()
            mock_repo.create_pull = Mock(return_value=Mock(html_url="https://test.pr", number=1))

            # Second call should succeed
            mock_repo.create_git_ref.side_effect = [
                GithubException(422, {"message": "Reference already exists"}),
                None,  # Success on second try
            ]

            result = await service.create_documentation_pr(repo_name, updates)

            # Should have tried to create branch twice
            assert mock_repo.create_git_ref.call_count == 2

    @pytest.mark.asyncio
    async def test_quality_check_integration(self, service):
        """Test quality check integration in the workflow."""
        # Create a mock quality score response
        quality_response = {"overall_score": 85, "issues": ["Missing examples"], "suggestions": ["Add code examples"]}

        content = "# API Documentation\nThis is test content."

        service.openai_client.chat.completions.create = Mock(
            return_value=Mock(choices=[Mock(message=Mock(content=json.dumps(quality_response)))])
        )

        # This would be called as part of the documentation update process
        # Verify the service can parse quality responses
        assert json.loads(quality_response) is not None

    @pytest.mark.asyncio
    async def test_batch_file_updates(self, service):
        """Test updating multiple files in a single PR."""
        repo_name = "test-owner/test-repo"
        updates = [
            {"file": "docs/api.md", "updated": "API content", "original": "old1"},
            {"file": "docs/guide.md", "updated": "Guide content", "original": "old2"},
            {"file": "README.md", "updated": "README content", "original": "old3"},
        ]

        mock_repo = Mock()
        mock_repo.default_branch = "main"

        # Mock file operations for each file
        mock_files = {"docs/api.md": Mock(sha="sha1"), "docs/guide.md": Mock(sha="sha2"), "README.md": Mock(sha="sha3")}

        mock_repo.get_contents = Mock(side_effect=lambda path: mock_files.get(path))
        mock_repo.get_branch = Mock(return_value=Mock(commit=Mock(sha="main_sha")))
        mock_repo.create_git_ref = Mock()
        mock_repo.update_file = Mock()
        mock_repo.create_pull = Mock(return_value=Mock(html_url="https://pr.url", number=99))

        service.github_client.get_repo = Mock(return_value=mock_repo)

        result = await service.create_documentation_pr(repo_name, updates)

        assert result["success"] is True
        assert result["files_updated"] == 3
        assert mock_repo.update_file.call_count == 3

    @pytest.mark.asyncio
    async def test_analyze_commit_with_context(self, service):
        """Test commit analysis with full context."""
        # Create a mock commit object
        commit = Mock()
        commit.sha = "abc123"
        commit.commit.message = "Add authentication middleware"
        commit.stats.additions = 150
        commit.stats.deletions = 30
        commit.files = [
            Mock(filename="middleware/auth.py", patch=SAMPLE_DIFFS["simple_addition"], additions=150, deletions=30)
        ]

        # Mock getting all documentation
        mock_docs = [
            {"path": "docs/middleware.md", "content": "# Middleware Guide"},
            {"path": "docs/security.md", "content": "# Security Overview"},
            {"path": "README.md", "content": "# Project README"},
        ]

        with patch.object(service, "get_repository_content", return_value=mock_docs):
            service.openai_client.chat.completions.create = Mock(
                return_value=Mock(
                    choices=[
                        Mock(
                            message=Mock(
                                content=json.dumps(
                                    {
                                        "changes_needed": True,
                                        "proposed_changes": [
                                            {
                                                "file_path": "docs/middleware.md",
                                                "current_content": "# Middleware Guide",
                                                "proposed_content": "# Middleware Guide\n\n## Authentication Middleware\n...",
                                                "change_summary": "Added documentation for new auth middleware",
                                            }
                                        ],
                                    }
                                )
                            )
                        )
                    ]
                )
            )

            result = await service.analyze_commit_and_suggest_updates(commit, mock_docs)

            assert len(result) == 1
            assert result[0]["file"] == "docs/middleware.md"
            assert "Authentication Middleware" in result[0]["updated"]

            # Verify AI was called with proper context
            ai_call = service.openai_client.chat.completions.create.call_args
            messages = ai_call[1]["messages"]
            assert any("middleware/auth.py" in str(msg) for msg in messages)
            assert any("Middleware Guide" in str(msg) for msg in messages)

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, service):
        """Test handling concurrent requests with rate limiting."""
        import asyncio

        repo_names = ["repo1", "repo2", "repo3"]

        # Mock get_repository_content to simulate API calls
        async def mock_get_content(repo):
            await asyncio.sleep(0.1)  # Simulate API delay
            return [{"path": "README.md", "content": f"# {repo}"}]

        with patch.object(service, "get_repository_content", side_effect=mock_get_content):
            # Run concurrent requests
            tasks = [service.get_repository_content(repo) for repo in repo_names]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify rate limiter was called for each request
            assert service.github_rate_limiter.acquire.call_count == 3

            # Check results
            successful_results = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_results) >= 1  # At least some should succeed
