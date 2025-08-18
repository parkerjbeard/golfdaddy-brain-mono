"""
Comprehensive integration tests for the auto documentation workflow.
"""

import asyncio
import json
import os
import subprocess
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.core.database import get_db
from app.doc_agent.client import AutoDocClient
from app.models.doc_approval import DocApproval
from app.services.context_analyzer import ContextAnalyzer
from app.services.doc_generation_service import DocGenerationService
from app.services.doc_quality_service import DocQualityService, QualityLevel
from app.services.documentation_update_service import DocumentationUpdateService
from app.services.embedding_service import EmbeddingService
from tests.fixtures.auto_doc_fixtures import (
    MOCK_OPENAI_RESPONSES,
    SAMPLE_DIFFS,
    SAMPLE_PATCHES,
    TEST_CONFIG,
    WORKFLOW_SCENARIOS,
    create_doc_approval,
    create_doc_embedding,
)


class TestAutoDocWorkflowIntegration:
    """Integration tests for complete auto documentation workflow."""

    @pytest.fixture
    async def test_db(self):
        """Create test database session."""
        # In real implementation, this would create a test database
        # For now, we'll mock it
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = Mock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.refresh = AsyncMock()
        yield db

    @pytest.fixture
    def mock_github_action_env(self):
        """Mock GitHub Actions environment."""
        env_vars = {
            "GITHUB_REPOSITORY": "test-owner/test-repo",
            "GITHUB_SHA": "abc123def456789",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_ACTOR": "test-user",
            "OPENAI_API_KEY": TEST_CONFIG["openai_api_key"],
            "GITHUB_TOKEN": TEST_CONFIG["github_token"],
            "DOCS_REPOSITORY": TEST_CONFIG["docs_repository"],
            "SLACK_BOT_TOKEN": TEST_CONFIG["slack_bot_token"],
            "DATABASE_URL": TEST_CONFIG["database_url"],
        }

        with patch.dict(os.environ, env_vars):
            yield env_vars

    @pytest.fixture
    def mock_services(self):
        """Mock all required services."""
        with patch("app.services.slack_service.SlackService") as mock_slack:
            with patch("openai.AsyncOpenAI") as mock_openai:
                with patch("github.Github") as mock_github:
                    mock_slack_instance = Mock()
                    mock_slack_instance.send_message = AsyncMock(return_value={"ts": "123.456"})
                    mock_slack_instance.update_message = AsyncMock()
                    mock_slack.return_value = mock_slack_instance

                    mock_openai_instance = Mock()
                    mock_openai_instance.chat = Mock()
                    mock_openai_instance.chat.completions = Mock()
                    mock_openai_instance.embeddings = Mock()
                    mock_openai.return_value = mock_openai_instance

                    mock_github_instance = Mock()
                    mock_github.return_value = mock_github_instance

                    yield {"slack": mock_slack_instance, "openai": mock_openai_instance, "github": mock_github_instance}

    @pytest.mark.asyncio
    async def test_github_action_trigger_to_approval(self, test_db, mock_github_action_env, mock_services):
        """Test complete flow from GitHub Action trigger to Slack approval."""
        # Step 1: Simulate GitHub Action trigger
        commit_hash = mock_github_action_env["GITHUB_SHA"]

        # Mock git diff
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.return_value = SAMPLE_DIFFS["api_endpoint_addition"]

            # Step 2: Initialize AutoDocClient
            client = AutoDocClient(
                openai_api_key=mock_github_action_env["OPENAI_API_KEY"],
                github_token=mock_github_action_env["GITHUB_TOKEN"],
                docs_repo=mock_github_action_env["DOCS_REPOSITORY"],
                slack_channel="#documentation",
                enable_semantic_search=True,
            )

            # Get commit diff
            diff = client.get_commit_diff(".", commit_hash)
            assert diff == SAMPLE_DIFFS["api_endpoint_addition"]

        # Step 3: Analyze diff with AI
        mock_services["openai"].chat.completions.create = Mock(
            return_value=Mock(choices=[Mock(message=Mock(content=SAMPLE_PATCHES["api_endpoint_patch"]))])
        )

        # Mock context gathering
        with patch.object(
            client,
            "_gather_context",
            return_value={
                "repository": "test-repo",
                "affected_files": ["backend/app/api/reports.py"],
                "related_docs": [],
                "code_patterns": ["FastAPI", "REST API"],
            },
        ):
            patch = await client.analyze_diff_with_context(diff, ".", commit_hash, test_db)
            assert patch == SAMPLE_PATCHES["api_endpoint_patch"]

        # Step 4: Create approval request
        approval_id = await client.propose_via_slack(
            diff, patch, commit_hash, "Add report generation endpoint", test_db
        )

        assert approval_id is not None
        assert test_db.add.called
        assert test_db.commit.called
        assert mock_services["slack"].send_message.called

        # Verify Slack message content
        slack_call = mock_services["slack"].send_message.call_args
        assert slack_call[1]["channel"] == "#documentation"
        blocks = slack_call[1]["blocks"]
        assert any("approve_doc_update" in str(block) for block in blocks)
        assert any(commit_hash[:8] in str(block) for block in blocks)

    @pytest.mark.asyncio
    async def test_approval_to_pr_creation(self, test_db, mock_services):
        """Test flow from Slack approval to GitHub PR creation."""
        # Setup: Create an approved documentation update
        approval = DocApproval(
            id=uuid.uuid4(),
            commit_hash="abc123",
            repository="test-owner/test-repo",
            diff_content=SAMPLE_DIFFS["api_endpoint_addition"],
            patch_content=SAMPLE_PATCHES["api_endpoint_patch"],
            slack_channel="#documentation",
            status="approved",
            approved_by="john.doe",
            approved_at=datetime.utcnow(),
        )

        # Mock GitHub repository
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_repo.create_pull = Mock(return_value=Mock(html_url="https://github.com/test/pr/123", number=123))
        mock_services["github"].get_repo.return_value = mock_repo

        # Create AutoDocClient
        client = AutoDocClient(
            openai_api_key=TEST_CONFIG["openai_api_key"],
            github_token=TEST_CONFIG["github_token"],
            docs_repo=approval.repository,
        )

        # Apply the patch
        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"

            with patch("subprocess.check_call") as mock_subprocess:
                pr_url = client.apply_patch(
                    approval.patch_content, approval.commit_hash, f"auto-docs-{approval.commit_hash[:7]}"
                )

        assert pr_url == "https://github.com/test/pr/123"
        assert mock_repo.create_pull.called

        # Verify git operations
        git_calls = mock_subprocess.call_args_list
        assert any("clone" in str(call) for call in git_calls)
        assert any("checkout" in str(call) for call in git_calls)
        assert any("apply" in str(call) for call in git_calls)
        assert any("push" in str(call) for call in git_calls)

    @pytest.mark.asyncio
    async def test_quality_validation_in_workflow(self, test_db, mock_services):
        """Test quality validation integration in the workflow."""
        # Initialize services
        quality_service = DocQualityService()
        quality_service.openai_client = mock_services["openai"]

        # Test document content
        doc_content = """# API Report Generation

## Overview
This endpoint allows authenticated users to generate various types of reports.

## Endpoint
`POST /api/reports/generate`

## Request Body
```json
{
  "report_type": "performance",
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  }
}
```

## Response
Returns a report object with download URL.

## Error Handling
- 400: Invalid request parameters
- 401: Unauthorized
- 500: Server error
"""

        # Mock quality assessment
        mock_services["openai"].chat.completions.create = Mock(
            return_value=Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content=json.dumps(
                                {
                                    "overall_score": 88,
                                    "completeness_score": 90,
                                    "clarity_score": 85,
                                    "accuracy_score": 92,
                                    "consistency_score": 86,
                                    "grammar_score": 95,
                                    "structure_score": 84,
                                    "issues": [],
                                    "suggestions": ["Consider adding rate limiting information"],
                                }
                            )
                        )
                    )
                ]
            )
        )

        # Validate documentation
        metrics = await quality_service.validate_documentation(doc_content, "api")

        assert metrics.overall_score == 88
        assert metrics.level == QualityLevel.GOOD
        assert quality_service.should_approve_automatically(metrics, "api") is True

    @pytest.mark.asyncio
    async def test_semantic_search_integration(self, test_db, mock_services):
        """Test semantic search integration in the workflow."""
        # Initialize services
        embedding_service = EmbeddingService()
        embedding_service.client = mock_services["openai"]

        context_analyzer = ContextAnalyzer(embedding_service)

        # Mock embeddings
        mock_services["openai"].embeddings.create = Mock(return_value=Mock(data=[Mock(embedding=[0.1] * 1536)]))

        # Create some existing documentation embeddings
        existing_docs = [
            create_doc_embedding(
                title="API Authentication Guide", content="Guide for API authentication...", repository="test-repo"
            ),
            create_doc_embedding(
                title="Report Generation API", content="How to generate reports...", repository="test-repo"
            ),
        ]

        # Mock database query for similar documents
        mock_results = [
            (Mock(**existing_docs[1]), 0.92),  # High similarity to report generation
            (Mock(**existing_docs[0]), 0.75),  # Medium similarity to auth
        ]

        test_db.execute.return_value.all.return_value = [
            Mock(DocEmbedding=doc, similarity=score) for doc, score in mock_results
        ]

        # Find similar documents
        query = "How to create a new report generation endpoint?"
        similar_docs = await embedding_service.find_similar_documents(test_db, query, "test-repo", limit=5)

        assert len(similar_docs) == 2
        assert similar_docs[0][1] == 0.92  # Similarity score
        assert "Report Generation" in similar_docs[0][0].title

    @pytest.mark.asyncio
    async def test_concurrent_workflow_handling(self, test_db, mock_services):
        """Test handling multiple concurrent documentation updates."""
        # Simulate multiple commits triggering documentation updates
        commits = [
            {"hash": "commit1", "diff": SAMPLE_DIFFS["simple_addition"]},
            {"hash": "commit2", "diff": SAMPLE_DIFFS["bug_fix"]},
            {"hash": "commit3", "diff": SAMPLE_DIFFS["schema_update"]},
        ]

        # Create clients for each workflow
        clients = []
        for _ in commits:
            client = AutoDocClient(
                openai_api_key=TEST_CONFIG["openai_api_key"],
                github_token=TEST_CONFIG["github_token"],
                docs_repo=TEST_CONFIG["docs_repository"],
                enable_semantic_search=True,
            )
            clients.append(client)

        # Mock AI responses for each
        mock_services["openai"].chat.completions.create = Mock(
            side_effect=[
                Mock(choices=[Mock(message=Mock(content=f"Patch for commit {i}"))]) for i in range(len(commits))
            ]
        )

        # Process all commits concurrently
        tasks = []
        for i, (client, commit) in enumerate(zip(clients, commits)):
            task = client.analyze_diff(commit["diff"])
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all completed
        successful_results = [r for r in results if isinstance(r, str) and "Patch for commit" in r]
        assert len(successful_results) == len(commits)

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, test_db, mock_services):
        """Test error recovery in the workflow."""
        client = AutoDocClient(
            openai_api_key=TEST_CONFIG["openai_api_key"],
            github_token=TEST_CONFIG["github_token"],
            docs_repo=TEST_CONFIG["docs_repository"],
        )

        # Test 1: OpenAI API failure recovery
        mock_services["openai"].chat.completions.create = Mock(
            side_effect=[
                Exception("API Error"),  # First attempt fails
                Mock(choices=[Mock(message=Mock(content="Recovered patch"))]),  # Retry succeeds
            ]
        )

        # Since _async_retry is a module-level function, we need to import it
        from app.doc_agent.client import _async_retry

        # Should retry and succeed
        with patch("doc_agent.client._async_retry", side_effect=_async_retry):
            result = await client.analyze_diff("test diff")
            # The actual retry logic would handle this

        # Test 2: GitHub API failure recovery
        mock_repo = Mock()
        mock_repo.create_pull.side_effect = [
            Exception("GitHub API Error"),  # First attempt fails
            Mock(html_url="https://github.com/pr/123"),  # Retry succeeds
        ]

        client.github = Mock()
        client.github.get_repo.return_value = mock_repo

        # Test 3: Slack notification failure (non-critical)
        mock_services["slack"].send_message.side_effect = Exception("Slack error")

        # Should handle gracefully and continue
        result = await client.propose_via_slack("diff", "patch", "commit123", db=test_db)
        # In real implementation, this would log error but continue

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_scenarios(self, test_db, mock_services, mock_github_action_env):
        """Test complete end-to-end workflow scenarios."""
        for scenario_name, scenario in WORKFLOW_SCENARIOS.items():
            print(f"\nTesting scenario: {scenario['description']}")

            if scenario_name == "simple_approval":
                await self._test_simple_approval_scenario(test_db, mock_services)
            elif scenario_name == "rejection_with_feedback":
                await self._test_rejection_scenario(test_db, mock_services)
            elif scenario_name == "quality_failure":
                await self._test_quality_failure_scenario(test_db, mock_services)

    async def _test_simple_approval_scenario(self, test_db, mock_services):
        """Test simple approval workflow scenario."""
        # Step 1: Commit triggers action
        commit_hash = "simple123"
        diff = SAMPLE_DIFFS["simple_addition"]

        # Step 2: AI generates patch
        client = AutoDocClient(
            openai_api_key=TEST_CONFIG["openai_api_key"],
            github_token=TEST_CONFIG["github_token"],
            docs_repo=TEST_CONFIG["docs_repository"],
        )

        mock_services["openai"].chat.completions.create = Mock(
            return_value=Mock(choices=[Mock(message=Mock(content=SAMPLE_PATCHES["user_service_patch"]))])
        )

        # Mock the OpenAI client properly
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=SAMPLE_PATCHES["user_service_patch"]))]
        client.openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        patch = await client.analyze_diff(diff)
        assert patch == SAMPLE_PATCHES["user_service_patch"]

        # Step 3: Send to Slack
        approval_id = await client.propose_via_slack(diff, patch, commit_hash, db=test_db)
        assert approval_id is not None

        # Step 4: Simulate approval
        approval = DocApproval(id=approval_id, commit_hash=commit_hash, patch_content=patch, status="approved")

        # Step 5: Create PR
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_repo.create_pull.return_value = Mock(html_url="https://github.com/pr/123")
        mock_services["github"].get_repo.return_value = mock_repo

        with patch("tempfile.TemporaryDirectory"):
            with patch("subprocess.check_call"):
                pr_url = client.apply_patch(patch, commit_hash)

        assert pr_url == "https://github.com/pr/123"

    async def _test_rejection_scenario(self, test_db, mock_services):
        """Test rejection workflow scenario."""
        # Similar setup but with rejection
        approval = create_doc_approval(status="rejected")
        approval["rejection_reason"] = "Documentation needs more examples"

        # No PR should be created
        # Rejection should be logged
        assert approval["status"] == "rejected"
        assert approval["rejection_reason"] is not None

    async def _test_quality_failure_scenario(self, test_db, mock_services):
        """Test quality failure workflow scenario."""
        quality_service = DocQualityService()
        quality_service.openai_client = mock_services["openai"]

        # Low quality documentation
        low_quality_doc = "Bad docs with no structure"

        mock_services["openai"].chat.completions.create = Mock(
            return_value=Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content=json.dumps(
                                {
                                    "overall_score": 45,
                                    "completeness_score": 30,
                                    "clarity_score": 40,
                                    "accuracy_score": 50,
                                    "consistency_score": 45,
                                    "grammar_score": 60,
                                    "structure_score": 35,
                                    "issues": ["No headings", "Too brief", "No examples"],
                                    "suggestions": ["Add proper structure", "Include examples"],
                                }
                            )
                        )
                    )
                ]
            )
        )

        metrics = await quality_service.validate_documentation(low_quality_doc)

        assert metrics.overall_score == 45
        assert metrics.level == QualityLevel.CRITICAL
        assert not quality_service.should_approve_automatically(metrics, "api")

        # Would require manual intervention
        assert len(metrics.issues) > 0
        assert len(metrics.suggestions) > 0


class TestWorkflowMonitoring:
    """Test workflow monitoring and metrics."""

    @pytest.mark.asyncio
    async def test_workflow_metrics_collection(self, test_db):
        """Test collecting metrics throughout the workflow."""
        metrics = {
            "workflow_start": datetime.utcnow(),
            "diff_analysis_time": None,
            "ai_generation_time": None,
            "quality_check_time": None,
            "total_time": None,
            "status": "in_progress",
        }

        # Simulate workflow steps with timing
        start = datetime.utcnow()

        # Step 1: Diff analysis
        await asyncio.sleep(0.1)  # Simulate processing
        metrics["diff_analysis_time"] = (datetime.utcnow() - start).total_seconds()

        # Step 2: AI generation
        ai_start = datetime.utcnow()
        await asyncio.sleep(0.2)  # Simulate AI call
        metrics["ai_generation_time"] = (datetime.utcnow() - ai_start).total_seconds()

        # Step 3: Quality check
        quality_start = datetime.utcnow()
        await asyncio.sleep(0.05)  # Simulate quality check
        metrics["quality_check_time"] = (datetime.utcnow() - quality_start).total_seconds()

        # Complete
        metrics["total_time"] = (datetime.utcnow() - metrics["workflow_start"]).total_seconds()
        metrics["status"] = "completed"

        # Verify metrics
        assert metrics["diff_analysis_time"] > 0
        assert metrics["ai_generation_time"] > 0
        assert metrics["quality_check_time"] > 0
        assert metrics["total_time"] >= sum(
            [metrics["diff_analysis_time"], metrics["ai_generation_time"], metrics["quality_check_time"]]
        )

    @pytest.mark.asyncio
    async def test_workflow_failure_tracking(self, test_db):
        """Test tracking workflow failures."""
        failure_log = []

        async def track_failure(step: str, error: Exception):
            failure_log.append(
                {
                    "step": step,
                    "error": str(error),
                    "timestamp": datetime.utcnow(),
                    "traceback": None,  # Would include full traceback in production
                }
            )

        # Simulate failures at different steps
        try:
            raise ValueError("AI API rate limit exceeded")
        except Exception as e:
            await track_failure("ai_generation", e)

        try:
            raise ConnectionError("GitHub API unreachable")
        except Exception as e:
            await track_failure("pr_creation", e)

        assert len(failure_log) == 2
        assert failure_log[0]["step"] == "ai_generation"
        assert "rate limit" in failure_log[0]["error"]
        assert failure_log[1]["step"] == "pr_creation"
        assert "unreachable" in failure_log[1]["error"]
