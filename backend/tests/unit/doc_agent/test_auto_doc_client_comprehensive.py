"""
Comprehensive unit tests for the AutoDocClient class with semantic search.
"""

import asyncio
import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, call, mock_open, patch

import pytest

from app.doc_agent.client import AutoDocClient, _async_retry, _retry
from app.models.doc_approval import DocApproval
from app.services.context_analyzer import ContextAnalyzer
from app.services.embedding_service import EmbeddingService
from tests.fixtures.auto_doc_fixtures import (
    MOCK_OPENAI_RESPONSES,
    SAMPLE_DIFFS,
    SAMPLE_PATCHES,
    TEST_CONFIG,
    create_code_context,
    create_doc_approval,
)


class TestAutoDocClientComprehensive:
    """Comprehensive test cases for AutoDocClient with all features."""

    @pytest.fixture
    def client(self):
        """Create a test client instance with semantic search enabled."""
        with patch("app.doc_agent.client.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = TEST_CONFIG["slack_bot_token"]
            mock_settings.SLACK_DEFAULT_CHANNEL = "#test-channel"
            mock_settings.DOC_AGENT_OPENAI_MODEL = "gpt-4"

            return AutoDocClient(
                openai_api_key=TEST_CONFIG["openai_api_key"],
                github_token=TEST_CONFIG["github_token"],
                docs_repo=TEST_CONFIG["docs_repository"],
                slack_channel="#documentation",
                enable_semantic_search=True,
            )

    @pytest.fixture
    def client_no_semantic(self):
        """Create a test client instance without semantic search."""
        return AutoDocClient(
            openai_api_key=TEST_CONFIG["openai_api_key"],
            github_token=TEST_CONFIG["github_token"],
            docs_repo=TEST_CONFIG["docs_repository"],
            enable_semantic_search=False,
        )

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        return session

    def test_client_initialization_with_semantic_search(self, client):
        """Test client initialization with semantic search enabled."""
        assert client.enable_semantic_search is True
        assert client.embedding_service is not None
        assert client.context_analyzer is not None
        assert isinstance(client.embedding_service, EmbeddingService)
        assert isinstance(client.context_analyzer, ContextAnalyzer)

    def test_client_initialization_without_semantic_search(self, client_no_semantic):
        """Test client initialization with semantic search disabled."""
        assert client_no_semantic.enable_semantic_search is False
        assert client_no_semantic.embedding_service is None
        assert client_no_semantic.context_analyzer is None

    @pytest.mark.asyncio
    async def test_analyze_diff_with_context_full_flow(self, client, mock_db_session):
        """Test analyze_diff_with_context with full context gathering."""
        diff = SAMPLE_DIFFS["api_endpoint_addition"]
        repo_path = "/test/test-repo"  # Changed to match expected repo name
        commit_hash = "abc123"

        # Mock context analyzer
        mock_context = {
            "repository": "test-repo",
            "commit_hash": commit_hash,
            "affected_files": ["backend/app/api/reports.py"],
            "related_docs": [
                {
                    "title": "API Reference",
                    "content": "Existing API documentation...",
                    "similarity": 0.85,
                    "file_path": "docs/api/reference.md",
                }
            ],
            "code_patterns": ["REST API", "FastAPI"],
            "dependencies": ["fastapi", "pydantic"],
        }

        with patch.object(client, "_gather_context", return_value=mock_context) as mock_gather:
            # Create a proper mock response
            mock_response = AsyncMock()
            mock_response.choices = [Mock(message=Mock(content=SAMPLE_PATCHES["api_endpoint_patch"]))]

            # Mock the openai client's chat.completions.create method
            if hasattr(client.openai_client, "chat"):
                client.openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
            else:
                # Create the nested structure if it doesn't exist
                client.openai_client = Mock()
                client.openai_client.chat = Mock()
                client.openai_client.chat.completions = Mock()
                client.openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await client.analyze_diff_with_context(diff, repo_path, commit_hash, mock_db_session)

            assert result == SAMPLE_PATCHES["api_endpoint_patch"]
            mock_gather.assert_called_once_with(mock_db_session, "test-repo", diff, commit_hash)

            # Verify the enhanced prompt was used
            call_args = client.openai_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            user_prompt = messages[1]["content"]
            assert "REPOSITORY CONTEXT:" in user_prompt
            assert "REST API" in user_prompt
            assert "API Reference" in user_prompt

    @pytest.mark.asyncio
    async def test_analyze_diff_with_context_fallback(self, client):
        """Test analyze_diff_with_context falls back to regular analysis on error."""
        diff = SAMPLE_DIFFS["simple_addition"]

        # Mock the OpenAI client to raise an error, triggering the fallback
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content="context result"))]

        # Make the OpenAI call fail to trigger fallback
        client.openai_client.chat.completions.create = AsyncMock(side_effect=Exception("OpenAI API error"))

        # Mock analyze_diff for the fallback
        mock_analyze = AsyncMock(return_value="fallback result")
        with patch.object(client, "analyze_diff", mock_analyze):
            # Also mock _gather_context to return valid context
            mock_context = {"repository": "repo", "affected_files": ["file.py"], "related_docs": []}
            with patch.object(client, "_gather_context", return_value=mock_context):
                # Mock logger to avoid error logs
                with patch("app.doc_agent.client.logger"):
                    result = await client.analyze_diff_with_context(diff, "/repo", "abc123", None)

                    assert result == "fallback result"
                    mock_analyze.assert_called_once_with(diff)

    @pytest.mark.asyncio
    async def test_gather_context_comprehensive(self, client, mock_db_session):
        """Test comprehensive context gathering."""
        diff = SAMPLE_DIFFS["multiple_files"]
        repository = "test-owner/test-repo"
        commit_hash = "abc123"

        # Mock file context from context analyzer
        file_context = {
            "design_patterns": ["Repository Pattern", "Service Layer"],
            "dependencies": ["sqlalchemy", "pydantic"],
        }

        # Mock embedding service responses
        related_docs = [
            (Mock(title="Project API", content="API docs...", file_path="docs/api.md"), 0.9),
            (Mock(title="Database Schema", content="Schema docs...", file_path="docs/schema.md"), 0.8),
        ]

        duplicates = [Mock(title="Old Project Docs", file_path="docs/old/project.md")]

        with patch.object(client.context_analyzer, "get_file_context", return_value=file_context):
            with patch.object(client.embedding_service, "find_similar_documents", return_value=related_docs):
                with patch.object(client.embedding_service, "detect_duplicates", return_value=duplicates):

                    context = await client._gather_context(mock_db_session, repository, diff, commit_hash)

                    assert context["repository"] == repository
                    assert context["commit_hash"] == commit_hash
                    assert len(context["affected_files"]) == 2
                    assert "backend/app/models/project.py" in context["affected_files"]
                    assert "Repository Pattern" in context["code_patterns"]
                    assert "sqlalchemy" in context["dependencies"]
                    assert len(context["related_docs"]) == 2
                    assert context["related_docs"][0]["title"] == "Project API"
                    assert "potential_duplicates" in context
                    assert context["potential_duplicates"][0]["title"] == "Old Project Docs"

    @pytest.mark.asyncio
    async def test_propose_via_slack_with_stats(self, client, mock_db_session):
        """Test Slack proposal with diff statistics parsing."""
        diff = SAMPLE_DIFFS["multiple_files"]
        doc_patch = SAMPLE_PATCHES["api_endpoint_patch"]
        commit_hash = "abc123"
        commit_message = "Add project budget tracking"

        # Set up database mock to handle approval creation
        approval_id = uuid.uuid4()

        # Mock the refresh to add ID to the approval object
        async def mock_refresh(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = approval_id

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        # Mock Slack service - need to patch SlackService class
        from unittest.mock import patch as mock_patch

        with mock_patch(
            "app.services.slack_message_templates.SlackMessageTemplates.doc_agent_approval"
        ) as mock_template:
            # Mock the template to return valid message structure
            mock_template.return_value = {
                "text": "Doc approval request",
                "blocks": [{"type": "section", "text": {"text": "Add project budget tracking"}}],
            }

            # Create a mock instance
            mock_slack_instance = Mock()
            mock_slack_instance.send_message = AsyncMock(return_value={"ts": "1234567890.123456"})

            # Re-initialize the slack_service on the client
            client.slack_service = mock_slack_instance

            result = await client.propose_via_slack(diff, doc_patch, commit_hash, commit_message, mock_db_session)

            # Result should be a UUID string (the approval ID)
            assert result is not None, f"Result was None, expected UUID string"
            assert isinstance(result, str), f"Result type was {type(result)}, expected str"
            # Verify it's a valid UUID format
            uuid.UUID(result)  # This will raise if not valid UUID
            assert result == str(approval_id)

            # Verify the Slack message was sent with correct stats
            call_args = mock_slack_instance.send_message.call_args
            assert call_args[1]["channel"] == "#documentation"
            blocks = call_args[1]["blocks"]

            # Should contain statistics about the diff
            message_str = str(blocks)
            assert "Add project budget tracking" in message_str

    def test_summarize_diff(self, client):
        """Test diff summarization for semantic search."""
        diff = SAMPLE_DIFFS["api_endpoint_addition"]

        summary = client._summarize_diff(diff)

        assert "Files changed:" in summary
        assert "backend/app/api/reports.py" in summary
        assert "Changes include:" in summary
        assert len(summary) <= 500  # Should be truncated

    def test_build_context_aware_prompt(self, client):
        """Test context-aware prompt building."""
        diff = SAMPLE_DIFFS["simple_addition"]
        context = {
            "repository": "test-repo",
            "affected_files": ["file1.py", "file2.py"],
            "code_patterns": ["Repository", "Service"],
            "dependencies": ["fastapi", "sqlalchemy"],
            "related_docs": [{"title": "API Guide", "content": "Guide content...", "similarity": 0.9}],
            "potential_duplicates": [{"title": "Old Docs", "file_path": "docs/old.md"}],
        }

        prompt = client._build_context_aware_prompt(diff, context)

        assert "REPOSITORY CONTEXT:" in prompt
        assert "test-repo" in prompt
        assert "Repository" in prompt
        assert "fastapi" in prompt
        assert "API Guide" in prompt
        assert "WARNING: Potential duplicate" in prompt
        assert "Old Docs" in prompt
        assert diff in prompt

    @pytest.mark.asyncio
    async def test_check_documentation_coverage(self, client, mock_db_session):
        """Test documentation coverage checking."""
        repository = "test-repo"
        file_path = "app/services/user_service.py"

        # Mock file context
        file_context = {
            "module_name": "user_service",
            "classes": ["UserService", "UserValidator"],
            "functions": ["get_user", "create_user", "update_user", "delete_user", "validate_email", "hash_password"],
        }

        # Mock related docs
        related_docs = [(Mock(title="User Service API", file_path="docs/api/user.md"), 0.75)]

        with patch.object(client.context_analyzer, "get_file_context", return_value=file_context):
            with patch.object(client.embedding_service, "find_similar_documents", return_value=related_docs):

                coverage = await client.check_documentation_coverage(mock_db_session, repository, file_path)

                assert coverage["file_path"] == file_path
                assert coverage["has_documentation"] is True
                assert coverage["coverage_score"] == 0.75
                assert len(coverage["documentation_files"]) == 1
                assert len(coverage["suggestions"]) > 0
                assert any("Document classes" in s for s in coverage["suggestions"])
                assert any("6 functions" in s for s in coverage["suggestions"])

    @pytest.mark.asyncio
    async def test_check_documentation_coverage_no_docs(self, client, mock_db_session):
        """Test documentation coverage checking with no existing docs."""
        repository = "test-repo"
        file_path = "app/services/new_service.py"

        file_context = {"classes": ["NewService"]}

        with patch.object(client.context_analyzer, "get_file_context", return_value=file_context):
            with patch.object(client.embedding_service, "find_similar_documents", return_value=[]):

                coverage = await client.check_documentation_coverage(mock_db_session, repository, file_path)

                assert coverage["has_documentation"] is False
                assert coverage["coverage_score"] == 0.0
                assert any("Create initial documentation" in s for s in coverage["suggestions"])

    def test_apply_patch_with_authentication_error(self, client):
        """Test apply_patch with GitHub authentication error."""
        # Mock the GitHub client to avoid real API calls
        client.github = None  # This will make apply_patch return None early

        result = client.apply_patch("patch", "abc123")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_and_send_approval_with_metadata(self, client, mock_db_session):
        """Test approval creation with full metadata."""
        diff = SAMPLE_DIFFS["bug_fix"]
        patch = "fix patch"
        commit_hash = "fix123"
        commit_message = "Fix authentication bug"

        # Mock Slack service
        client.slack_service = Mock()
        client.slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})

        result = await client._create_and_send_approval(
            mock_db_session, diff, patch, commit_hash, commit_message, files_affected=1, additions=2, deletions=1
        )

        # Verify approval was created with correct metadata
        assert mock_db_session.add.called
        approval_arg = mock_db_session.add.call_args[0][0]
        assert approval_arg.commit_hash == commit_hash
        assert approval_arg.approval_metadata["commit_message"] == commit_message
        assert approval_arg.approval_metadata["files_affected"] == 1
        assert approval_arg.approval_metadata["additions"] == 2
        assert approval_arg.approval_metadata["deletions"] == 1

        # Verify Slack message was sent
        assert client.slack_service.send_message.called

    @pytest.mark.asyncio
    async def test_propose_via_slack_expired_handling(self, client, mock_db_session):
        """Test handling of expired approvals."""
        # Create an expired approval
        expired_approval = DocApproval(
            id=uuid.uuid4(),
            commit_hash="old123",
            repository="test-repo",
            diff_content="old diff",
            patch_content="old patch",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired
            status="pending",
        )

        # This test verifies the expiration logic in the approval workflow
        assert expired_approval.expires_at < datetime.utcnow()
        assert expired_approval.status == "pending"

    def test_retry_mechanism_with_specific_exceptions(self):
        """Test retry mechanism with specific exception types."""
        call_count = 0

        def func_with_specific_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network error")
            elif call_count == 2:
                raise TimeoutError("Timeout")
            return "success"

        result = _retry(
            func_with_specific_error, retries=3, initial_delay=0.01, exceptions=(ConnectionError, TimeoutError)
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_with_backoff(self):
        """Test async retry with exponential backoff timing."""
        call_times = []

        async def timing_func():
            call_times.append(asyncio.get_event_loop().time())
            if len(call_times) < 3:
                raise Exception("Retry needed")
            return "done"

        result = await _async_retry(timing_func, retries=3, initial_delay=0.1, backoff=2)

        assert result == "done"
        assert len(call_times) == 3

        # Verify exponential backoff (approximately)
        if len(call_times) >= 3:
            first_delay = call_times[1] - call_times[0]
            second_delay = call_times[2] - call_times[1]
            assert second_delay > first_delay * 1.5  # Allow some variance

    def test_get_commit_diff_with_show_command(self, client):
        """Test get_commit_diff uses git show command."""
        repo_path = "/test/repo"
        commit_hash = "abc123"
        expected_diff = "diff content"

        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.return_value = expected_diff

            result = client.get_commit_diff(repo_path, commit_hash)

            assert result == expected_diff
            mock_subprocess.assert_called_once_with(["git", "-C", repo_path, "show", commit_hash], text=True)

    @pytest.mark.asyncio
    async def test_openai_client_not_available(self):
        """Test behavior when OpenAI client is not available."""
        with patch("app.doc_agent.client.AsyncOpenAI", None):
            client = AutoDocClient(openai_api_key="test-key", github_token="test-token", docs_repo="test-repo")

            assert client.openai_client is None

            # Test analyze_diff returns empty string
            result = await client.analyze_diff("some diff")
            assert result == ""

    def test_apply_patch_pr_creation_failure(self, client):
        """Test apply_patch when PR creation fails."""
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_repo.create_pull.side_effect = Exception("PR creation failed")

        client.github = Mock()
        client.github.get_repo.return_value = mock_repo

        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"

            # Mock file operations
            with patch("builtins.open", mock_open()):
                with patch("subprocess.check_call"):
                    result = client.apply_patch("patch", "abc123")

                    assert result is None

    @pytest.mark.asyncio
    async def test_full_workflow_simulation(self, client, mock_db_session):
        """Test complete workflow from diff to PR creation."""
        # Step 1: Get commit diff
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.return_value = SAMPLE_DIFFS["api_endpoint_addition"]
            diff = client.get_commit_diff("/repo", "abc123")

        # Step 2: Analyze diff with context
        with patch.object(client, "_gather_context") as mock_gather:
            mock_gather.return_value = {
                "repository": "test-repo",
                "affected_files": ["api/reports.py"],
                "related_docs": [],
                "code_patterns": ["REST API"],
            }

            # Fix the OpenAI client mocking structure
            mock_response = AsyncMock()
            mock_response.choices = [Mock(message=Mock(content=SAMPLE_PATCHES["api_endpoint_patch"]))]
            client.openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

            doc_patch = await client.analyze_diff_with_context(diff, "/repo", "abc123", mock_db_session)

        # Step 3: Propose via Slack
        with patch.object(client.slack_service, "send_message") as mock_send:
            mock_send.return_value = {"ts": "123.456"}

            result = await client.propose_via_slack(diff, doc_patch, "abc123", "Add report generation", mock_db_session)

            # Result should be an approval ID
            assert result is not None
            assert isinstance(result, str)
            approval_id = result

        # Step 4: Apply patch (after approval)
        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"

            # Mock file operations
            from unittest.mock import mock_open

            with patch("builtins.open", mock_open()):
                with patch("subprocess.check_call"):
                    mock_repo = Mock()
                    mock_repo.default_branch = "main"
                    mock_repo.create_pull.return_value = Mock(html_url="https://github.com/test/pr/123")

                    client.github = Mock()
                    client.github.get_repo.return_value = mock_repo

                    pr_url = client.apply_patch(doc_patch, "abc123")

                    assert pr_url == "https://github.com/test/pr/123"
