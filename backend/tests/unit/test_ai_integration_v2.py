"""Unit tests for standardized AI integration."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.integrations.ai_integration_v2 import AIIntegrationV2


class TestAIIntegrationV2:
    """Test cases for standardized AI integration."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch("app.integrations.ai_integration_v2.settings") as mock:
            mock.OPENAI_API_KEY = "test_api_key"
            mock.OPENAI_MODEL = "gpt-4-turbo-preview"
            mock.CODE_QUALITY_MODEL = "gpt-4-turbo-preview"
            yield mock

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        with patch("app.integrations.ai_integration_v2.AsyncOpenAI") as mock_constructor:
            client = AsyncMock()
            mock_constructor.return_value = client
            # Return a tuple with both the constructor and client instance
            yield (mock_constructor, client)

    @pytest.fixture
    def ai_integration(self, mock_settings, mock_openai_client):
        """Create AIIntegrationV2 instance for testing."""
        return AIIntegrationV2()

    def test_init_with_api_key(self, mock_settings, mock_openai_client):
        """Test initialization with API key."""
        mock_constructor, client = mock_openai_client
        ai = AIIntegrationV2()

        assert ai.api_key == "test_api_key"
        assert ai.client is not None
        assert ai.model == "gpt-4-turbo-preview"
        mock_constructor.assert_called_once()

    def test_init_without_api_key(self, mock_openai_client):
        """Test initialization without API key."""
        mock_constructor, client = mock_openai_client
        with patch("app.integrations.ai_integration_v2.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.OPENAI_MODEL = "gpt-4"
            mock_settings.CODE_QUALITY_MODEL = "gpt-4"

            ai = AIIntegrationV2()

            assert ai.client is None
            mock_constructor.assert_not_called()

    @pytest.mark.asyncio
    async def test_make_completion_request(self, ai_integration, mock_openai_client):
        """Test making a standardized completion request."""
        mock_constructor, client = mock_openai_client
        # Mock response
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        client.chat.completions.create.return_value = mock_response

        messages = [{"role": "system", "content": "You are a helpful assistant"}, {"role": "user", "content": "Hello"}]

        result = await ai_integration._make_completion_request(messages)

        assert result == "Test response"
        client.chat.completions.create.assert_called_once()

        # Verify call parameters
        call_args = client.chat.completions.create.call_args
        assert call_args[1]["model"] == "gpt-4-turbo-preview"
        assert call_args[1]["messages"] == messages
        assert call_args[1]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_make_completion_request_with_json(self, ai_integration, mock_openai_client):
        """Test completion request with JSON response format."""
        mock_constructor, client = mock_openai_client
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content='{"key": "value"}'))]
        client.chat.completions.create.return_value = mock_response

        result = await ai_integration._make_completion_request(
            messages=[{"role": "user", "content": "Test"}], response_format={"type": "json_object"}
        )

        assert result == '{"key": "value"}'

        # Verify response format was passed
        call_args = client.chat.completions.create.call_args
        assert call_args[1]["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_make_completion_request_no_client(self, ai_integration):
        """Test completion request without client."""
        ai_integration.client = None

        result = await ai_integration._make_completion_request(messages=[{"role": "user", "content": "Test"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_commit_diff(self, ai_integration, mock_openai_client):
        """Test analyzing commit diff."""
        mock_constructor, client = mock_openai_client
        commit_data = {"diff": "diff --git a/test.py\n+new code", "message": "Add new feature"}

        mock_response = AsyncMock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "estimated_hours": 2.5,
                            "complexity_score": 6,
                            "seniority_score": 7,
                            "key_changes": ["Added new feature"],
                            "potential_issues": [],
                            "suggestions": ["Add tests"],
                        }
                    )
                )
            )
        ]
        client.chat.completions.create.return_value = mock_response

        result = await ai_integration.analyze_commit_diff(commit_data)

        assert result["estimated_hours"] == 2.5
        assert result["complexity_score"] == 6
        assert result["key_changes"] == ["Added new feature"]
        assert "analyzed_at" in result
        assert result["model_used"] == "gpt-4-turbo-preview"

    @pytest.mark.asyncio
    async def test_analyze_commit_diff_no_diff(self, ai_integration):
        """Test analyzing commit without diff."""
        result = await ai_integration.analyze_commit_diff({})

        assert result == {"error": "No diff provided"}

    @pytest.mark.asyncio
    async def test_generate_documentation(self, ai_integration, mock_openai_client):
        """Test generating documentation."""
        mock_constructor, client = mock_openai_client
        context = {"doc_type": "API", "text": "Function documentation needed"}

        mock_response = AsyncMock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "content": "# API Documentation\n\nThis is the documentation.",
                            "sections": [{"title": "Overview", "content": "API overview"}],
                            "metadata": {"doc_type": "API", "format": "markdown"},
                            "summary": "API documentation for the function",
                        }
                    )
                )
            )
        ]
        client.chat.completions.create.return_value = mock_response

        result = await ai_integration.generate_documentation(context)

        assert result["content"] == "# API Documentation\n\nThis is the documentation."
        assert len(result["sections"]) == 1
        assert result["summary"] == "API documentation for the function"
        assert "generated_at" in result

    @pytest.mark.asyncio
    async def test_analyze_eod_report(self, ai_integration, mock_openai_client):
        """Test analyzing EOD report."""
        mock_constructor, client = mock_openai_client
        report_text = """
        - Completed feature implementation
        - Fixed bug in authentication
        - Started working on tests
        """

        mock_response = AsyncMock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "key_achievements": ["Completed feature implementation", "Fixed authentication bug"],
                            "estimated_hours": 6.5,
                            "estimated_difficulty": "Medium",
                            "sentiment": "Positive",
                            "potential_blockers": [],
                            "summary": "Productive day with feature completion and bug fixes.",
                            "clarification_requests": [],
                        }
                    )
                )
            )
        ]
        client.chat.completions.create.return_value = mock_response

        result = await ai_integration.analyze_eod_report(report_text)

        assert len(result["key_achievements"]) == 2
        assert result["estimated_hours"] == 6.5
        assert result["estimated_difficulty"] == "Medium"
        assert result["sentiment"] == "Positive"
        assert "analyzed_at" in result

    @pytest.mark.asyncio
    async def test_analyze_code_quality(self, ai_integration, mock_openai_client):
        """Test analyzing code quality."""
        mock_constructor, client = mock_openai_client
        diff = "diff --git a/test.py\n+def new_function():\n+    return 42"
        message = "Add utility function"

        mock_response = AsyncMock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "readability_score": 0.8,
                            "complexity_score": 0.2,
                            "maintainability_score": 0.9,
                            "test_coverage_estimation": 0.0,
                            "security_concerns": [],
                            "performance_issues": [],
                            "best_practices_adherence": ["Simple function", "Clear naming"],
                            "suggestions_for_improvement": ["Add docstring", "Add tests"],
                            "positive_feedback": ["Clean implementation"],
                            "estimated_seniority_level": "Mid-Level",
                            "overall_assessment_summary": "Simple, clean function that needs documentation.",
                        }
                    )
                )
            )
        ]
        client.chat.completions.create.return_value = mock_response

        result = await ai_integration.analyze_code_quality(diff, message)

        assert result["readability_score"] == 0.8
        assert result["complexity_score"] == 0.2
        assert len(result["suggestions_for_improvement"]) == 2
        assert result["estimated_seniority_level"] == "Mid-Level"

    @pytest.mark.asyncio
    async def test_analyze_semantic_similarity(self, ai_integration, mock_openai_client):
        """Test analyzing semantic similarity."""
        mock_constructor, client = mock_openai_client
        text1 = "Implemented user authentication"
        text2 = "Added login functionality"

        mock_response = AsyncMock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "similarity_score": 0.75,
                            "is_duplicate": True,
                            "reasoning": "Both describe authentication implementation",
                            "overlapping_aspects": ["authentication", "user access"],
                            "unique_to_text1": ["implementation details"],
                            "unique_to_text2": ["login specific"],
                        }
                    )
                )
            )
        ]
        client.chat.completions.create.return_value = mock_response

        result = await ai_integration.analyze_semantic_similarity(text1, text2)

        assert result["similarity_score"] == 0.75
        assert result["is_duplicate"] is True
        assert "authentication" in result["overlapping_aspects"]

    @pytest.mark.asyncio
    async def test_analyze_daily_work(self, ai_integration, mock_openai_client):
        """Test analyzing daily work."""
        mock_constructor, client = mock_openai_client
        context = {
            "user_name": "John Doe",
            "analysis_date": "2024-01-15",
            "total_commits": 10,
            "repositories": ["repo1", "repo2"],
            "total_lines_changed": 500,
            "commits": [
                {"timestamp": "10:00", "repository": "repo1", "message": "Fix bug", "additions": 50, "deletions": 10}
            ],
        }

        mock_response = AsyncMock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "total_estimated_hours": 7.5,
                            "average_complexity_score": 6,
                            "average_seniority_score": 7,
                            "work_summary": "Productive day with bug fixes and features",
                            "key_achievements": ["Fixed critical bug", "Implemented new feature"],
                            "hour_estimation_reasoning": "Based on commit volume and complexity",
                            "consistency_with_report": True,
                            "recommendations": ["Consider code review", "Add more tests"],
                        }
                    )
                )
            )
        ]
        client.chat.completions.create.return_value = mock_response

        result = await ai_integration.analyze_daily_work(context)

        assert result["total_estimated_hours"] == 7.5
        assert result["average_complexity_score"] == 6
        assert len(result["key_achievements"]) == 2
        assert len(result["recommendations"]) == 2
        assert "analyzed_at" in result

    @pytest.mark.asyncio
    async def test_error_handling_json_decode(self, ai_integration, mock_openai_client):
        """Test error handling for JSON decode errors."""
        mock_constructor, client = mock_openai_client
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content="Not valid JSON"))]
        client.chat.completions.create.return_value = mock_response

        result = await ai_integration.analyze_commit_diff({"diff": "test diff", "message": "test"})

        assert result["error"] == "Invalid response format"

    @pytest.mark.asyncio
    async def test_error_handling_api_error(self, ai_integration, mock_openai_client):
        """Test error handling for API errors."""
        mock_constructor, client = mock_openai_client
        client.chat.completions.create.side_effect = Exception("API Error")

        result = await ai_integration.analyze_commit_diff({"diff": "test diff", "message": "test"})

        assert result["error"] == "Failed to analyze commit"
