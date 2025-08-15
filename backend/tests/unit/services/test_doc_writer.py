"""
Unit tests for the documentation writer service.
"""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.schemas.doc_output_schemas import APIReferenceDoc, DocType, DocumentationOutput
from app.services.context_builder import ChangeContext
from app.services.doc_task_planner import DocSection, DocTaskType, DocumentationTask
from app.services.doc_writer import DocumentationWriter, WriterInput, WriterOutput
from app.services.house_style import HouseStyleConfig
from app.services.target_file_selector import DocFramework, TargetFile


class TestDocumentationWriter:
    """Test the documentation writer."""

    @pytest.fixture
    def writer(self):
        """Create a documentation writer instance."""
        mock_session = Mock()
        house_style = HouseStyleConfig()
        writer = DocumentationWriter(mock_session, house_style)
        # Mock AI integration
        writer.ai_integration = AsyncMock()
        return writer

    @pytest.fixture
    def sample_task(self):
        """Create a sample documentation task."""
        return DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title="Document User API",
            description="Add documentation for user management endpoints",
            content_template="## API Reference\n\n### GET /users",
            source_change=Mock(),
            confidence=0.8,
            priority=8,
            auto_generate=True,
            metadata={"endpoints": [{"method": "GET", "path": "/users", "handler": "get_users"}]},
        )

    @pytest.fixture
    def sample_context(self):
        """Create a sample change context."""
        context = Mock(spec=ChangeContext)
        context.changed_symbols = [Mock(name="get_users", kind="function", signature="def get_users()")]
        context.related_docs = []
        context.related_code = []
        context.diff_context = {}
        return context

    @pytest.fixture
    def sample_targets(self):
        """Create sample target files."""
        return [
            TargetFile(
                path="docs/api/users.md",
                framework=DocFramework.MKDOCS,
                confidence=0.9,
                reason="Semantic match",
                create_if_missing=False,
            )
        ]

    @pytest.mark.asyncio
    async def test_write_documentation_basic(self, writer, sample_task, sample_context, sample_targets):
        """Test basic documentation writing."""
        # Mock AI response
        ai_response = json.dumps(
            {
                "title": "User Management API",
                "version": "1.0.0",
                "description": "API for managing users",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/users",
                        "summary": "List all users",
                        "description": "Retrieve a list of all users",
                        "parameters": [],
                        "response_schema": {"type": "array"},
                        "response_examples": [],
                        "error_responses": [],
                    }
                ],
            }
        )
        writer.ai_integration.generate_text.return_value = ai_response

        # Create input
        input_data = WriterInput(task=sample_task, context=sample_context, target_files=sample_targets)

        # Write documentation
        output = await writer.write_documentation(input_data)

        # Verify output
        assert isinstance(output, WriterOutput)
        assert isinstance(output.documentation, DocumentationOutput)
        assert output.documentation.doc_type == DocType.API_REFERENCE
        assert len(output.patches) > 0
        assert output.confidence > 0

    @pytest.mark.asyncio
    async def test_structure_output_validation(self, writer):
        """Test output structuring and validation."""
        content = {"title": "Test API", "version": "1.0.0", "description": "Test description", "endpoints": []}

        output = writer._structure_output(content, DocType.API_REFERENCE)

        assert output.doc_type == DocType.API_REFERENCE
        assert output.content == content
        assert len(output.validation_errors) == 0

    @pytest.mark.asyncio
    async def test_structure_output_with_errors(self, writer):
        """Test output structuring with validation errors."""
        # Missing required fields
        content = {"description": "Test description"}

        output = writer._structure_output(content, DocType.API_REFERENCE)

        assert output.doc_type == DocType.API_REFERENCE
        assert len(output.warnings) > 0  # Should have warnings about missing fields

    def test_apply_house_style(self, writer):
        """Test applying house style to documentation."""
        output = DocumentationOutput(
            doc_type=DocType.API_REFERENCE,
            content={"title": "API Reference", "description": "Simply use this API obviously", "endpoints": []},
        )

        styled_output = writer._apply_house_style(output)

        # Forbidden phrases should be removed
        assert "obviously" not in json.dumps(styled_output.content)
        assert "Simply" not in json.dumps(styled_output.content)

    def test_render_to_markdown_api(self, writer):
        """Test rendering API documentation to markdown."""
        documentation = DocumentationOutput(
            doc_type=DocType.API_REFERENCE,
            content={
                "title": "User API",
                "description": "User management API",
                "authentication": "Bearer token required",
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/users",
                        "summary": "List users",
                        "description": "Get all users",
                        "parameters": [
                            {
                                "name": "limit",
                                "type": "integer",
                                "required": False,
                                "description": "Maximum number of results",
                            }
                        ],
                        "response_schema": {"type": "array"},
                    }
                ],
            },
        )

        markdown = writer._render_to_markdown(documentation)

        assert "# User API" in markdown
        assert "## Authentication" in markdown
        assert "## Endpoints" in markdown
        assert "### GET `/users`" in markdown
        assert "| limit | integer | No |" in markdown

    def test_render_to_markdown_config(self, writer):
        """Test rendering configuration documentation to markdown."""
        documentation = DocumentationOutput(
            doc_type=DocType.CONFIG_REFERENCE,
            content={
                "title": "Configuration",
                "description": "Application configuration",
                "sections": {
                    "Database": [
                        {"key": "DB_HOST", "type": "string", "default": "localhost", "description": "Database host"}
                    ]
                },
            },
        )

        markdown = writer._render_to_markdown(documentation)

        assert "# Configuration" in markdown
        assert "## Database" in markdown
        assert "### `DB_HOST`" in markdown
        assert "**Type:** `string`" in markdown
        assert "**Default:** `localhost`" in markdown

    def test_render_to_markdown_tutorial(self, writer):
        """Test rendering tutorial documentation to markdown."""
        documentation = DocumentationOutput(
            doc_type=DocType.TUTORIAL_GUIDE,
            content={
                "title": "Getting Started",
                "description": "Learn how to use the API",
                "prerequisites": ["API key", "Python 3.8+"],
                "steps": [
                    {
                        "step_number": 1,
                        "title": "Install SDK",
                        "description": "Install the Python SDK",
                        "code_examples": [{"language": "bash", "code": "pip install api-sdk"}],
                    }
                ],
            },
        )

        markdown = writer._render_to_markdown(documentation)

        assert "# Getting Started" in markdown
        assert "## Prerequisites" in markdown
        assert "- API key" in markdown
        assert "## Step 1: Install SDK" in markdown
        assert "```bash" in markdown
        assert "pip install api-sdk" in markdown

    def test_render_to_markdown_changelog(self, writer):
        """Test rendering changelog documentation to markdown."""
        documentation = DocumentationOutput(
            doc_type=DocType.CHANGELOG_ENTRY,
            content={
                "version": "2.0.0",
                "date": "2024-01-01",
                "summary": "Major release",
                "changes": [
                    {"type": "added", "description": "New user API", "breaking": False},
                    {"type": "removed", "description": "Legacy endpoints", "breaking": True},
                ],
            },
        )

        markdown = writer._render_to_markdown(documentation)

        assert "## [2.0.0] - 2024-01-01" in markdown
        assert "### Added" in markdown
        assert "- New user API" in markdown
        assert "### Removed" in markdown
        assert "- **BREAKING:** Legacy endpoints" in markdown

    def test_create_file_patch(self, writer):
        """Test creating a patch for a new file."""
        target = TargetFile(
            path="docs/api.md", framework=DocFramework.MKDOCS, confidence=0.9, reason="New file", create_if_missing=True
        )

        documentation = DocumentationOutput(
            doc_type=DocType.API_REFERENCE, content={"title": "API", "description": "API docs", "endpoints": []}
        )

        task = Mock()
        task.task_type = DocTaskType.API_REFERENCE

        patch = writer._create_file_patch(target, documentation, task)

        assert patch["action"] == "create"
        assert patch["file_path"] == "docs/api.md"
        assert "# API" in patch["content"]

    @pytest.mark.asyncio
    async def test_create_update_patch(self, writer):
        """Test creating a patch for updating an existing file."""
        target = TargetFile(
            path="docs/existing.md", framework=DocFramework.MKDOCS, confidence=0.9, reason="Update", section="API"
        )

        documentation = DocumentationOutput(
            doc_type=DocType.API_REFERENCE, content={"title": "Updated API", "description": "Updated", "endpoints": []}
        )

        task = Mock()
        task.task_type = DocTaskType.API_REFERENCE

        # Mock file reading
        with patch(
            "builtins.open",
            Mock(
                return_value=Mock(
                    __enter__=Mock(
                        return_value=Mock(read=Mock(return_value="# Old Content\n\n## API\n\nOld API content"))
                    )
                )
            ),
        ):
            patch_obj = await writer._create_update_patch(target, documentation, task)

        assert patch_obj is not None
        assert patch_obj["action"] == "update"
        assert patch_obj["file_path"] == "docs/existing.md"

    def test_calculate_confidence(self, writer):
        """Test confidence calculation."""
        documentation = DocumentationOutput(
            doc_type=DocType.API_REFERENCE,
            content={},
            validation_errors=["Error 1"],
            warnings=["Warning 1", "Warning 2"],
        )

        task = Mock(confidence=0.7)
        patches = [{"action": "update"}]

        confidence = writer._calculate_confidence(documentation, task, patches)

        # Should be reduced due to errors and warnings
        assert confidence < 0.7
        assert confidence > 0

    def test_generate_explanations(self, writer):
        """Test generating explanations."""
        documentation = DocumentationOutput(doc_type=DocType.API_REFERENCE, content={}, validation_errors=["Error 1"])

        patches = [
            {"action": "create", "file_path": "docs/api.md"},
            {"action": "update", "file_path": "docs/config.md"},
        ]

        explanations = writer._generate_explanations(documentation, patches)

        assert len(explanations) > 0
        assert any("api_reference" in e for e in explanations)
        assert any("create docs/api.md" in e for e in explanations)
        assert any("update docs/config.md" in e for e in explanations)
        assert any("validation issue" in e for e in explanations)

    def test_generate_suggestions(self, writer):
        """Test generating suggestions."""
        # API documentation without examples
        documentation = DocumentationOutput(
            doc_type=DocType.API_REFERENCE, content={"title": "API", "description": "API docs", "endpoints": []}
        )

        task = Mock(confidence=0.6, task_type=DocTaskType.API_REFERENCE)

        suggestions = writer._generate_suggestions(documentation, task)

        assert len(suggestions) > 0
        assert any("examples" in s for s in suggestions)
        assert any("Manual review" in s for s in suggestions)  # Low confidence

    def test_map_task_to_doc_type(self, writer):
        """Test mapping documentation tasks to document types."""
        from app.services.doc_task_planner import DocTaskType

        # Test various mappings
        task = Mock(task_type=DocTaskType.API_REFERENCE)
        assert writer._map_task_to_doc_type(task) == DocType.API_REFERENCE

        task.task_type = DocTaskType.CONFIG_REFERENCE
        assert writer._map_task_to_doc_type(task) == DocType.CONFIG_REFERENCE

        task.task_type = DocTaskType.FEATURE_GUIDE
        assert writer._map_task_to_doc_type(task) == DocType.TUTORIAL_GUIDE

        task.task_type = DocTaskType.CHANGELOG_ENTRY
        assert writer._map_task_to_doc_type(task) == DocType.CHANGELOG_ENTRY

        task.task_type = DocTaskType.MIGRATION_GUIDE
        assert writer._map_task_to_doc_type(task) == DocType.MIGRATION_GUIDE
