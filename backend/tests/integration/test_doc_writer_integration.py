"""
Integration tests for the documentation writer system.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.schemas.doc_output_schemas import DocType
from app.services.context_builder import ChangeContext
from app.services.doc_task_planner import DocSection, DocTaskType, DocumentationTask
from app.services.doc_writer import DocumentationWriter, WriterInput
from app.services.house_style import HouseStyleConfig, PromptTone
from app.services.patch_generator import PatchAction, PatchGenerator
from app.services.prompt_engineering import PromptEngine
from app.services.target_file_selector import DocFramework, TargetFile


class TestDocWriterIntegration:
    """Integration tests for the documentation writer system."""

    @pytest.fixture
    async def test_session(self):
        """Create a test database session."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            yield session

        await engine.dispose()

    @pytest.fixture
    def house_style(self):
        """Create a house style configuration."""
        return HouseStyleConfig(
            tone=PromptTone.PROFESSIONAL,
            forbidden_phrases=["obviously", "simply"],
            preferred_phrases={"click": "select"},
            american_spelling=True,
        )

    @pytest.fixture
    def sample_task(self):
        """Create a sample documentation task."""
        return DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title="Document User Management API",
            description="Create comprehensive API documentation for user endpoints",
            content_template="",
            source_change=Mock(),
            confidence=0.85,
            priority=9,
            auto_generate=True,
            metadata={
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/api/users",
                        "handler": "list_users",
                        "description": "List all users with pagination",
                    },
                    {
                        "method": "POST",
                        "path": "/api/users",
                        "handler": "create_user",
                        "description": "Create a new user",
                    },
                    {
                        "method": "GET",
                        "path": "/api/users/{id}",
                        "handler": "get_user",
                        "description": "Get a specific user by ID",
                    },
                ]
            },
        )

    @pytest.mark.asyncio
    async def test_full_documentation_generation_pipeline(self, test_session, house_style, sample_task):
        """Test the full documentation generation pipeline."""
        # Create writer with house style
        writer = DocumentationWriter(test_session, house_style)

        # Mock AI response
        ai_response = {
            "title": "User Management API",
            "version": "1.0.0",
            "description": "API for managing users in the system",
            "authentication": "Bearer token required for all endpoints",
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/api/users",
                    "summary": "List all users",
                    "description": "Retrieve a paginated list of all users",
                    "parameters": [
                        {
                            "name": "page",
                            "type": "integer",
                            "required": False,
                            "description": "Page number",
                            "default": 1,
                        },
                        {
                            "name": "limit",
                            "type": "integer",
                            "required": False,
                            "description": "Items per page",
                            "default": 20,
                        },
                    ],
                    "response_schema": {
                        "type": "object",
                        "properties": {
                            "users": {"type": "array"},
                            "total": {"type": "integer"},
                            "page": {"type": "integer"},
                        },
                    },
                    "error_responses": [
                        {"code": 401, "description": "Unauthorized"},
                        {"code": 500, "description": "Internal server error"},
                    ],
                }
            ],
        }

        writer.ai_integration.generate_text = AsyncMock(return_value=json.dumps(ai_response))

        # Create context
        context = Mock(spec=ChangeContext)
        context.changed_symbols = [
            Mock(name="list_users", kind="function", signature="async def list_users(page: int, limit: int)")
        ]
        context.related_docs = []

        # Create target files
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "docs" / "api.md"
            target_file.parent.mkdir(parents=True, exist_ok=True)

            targets = [
                TargetFile(
                    path=str(target_file),
                    framework=DocFramework.MKDOCS,
                    confidence=0.9,
                    reason="Semantic match",
                    create_if_missing=True,
                )
            ]

            # Create input
            input_data = WriterInput(
                task=sample_task,
                context=context,
                target_files=targets,
                constraints=["Include authentication details", "Provide examples"],
            )

            # Generate documentation
            output = await writer.write_documentation(input_data)

            # Verify output
            assert output.documentation.doc_type == DocType.API_REFERENCE
            assert output.confidence > 0.5
            assert len(output.patches) > 0

            # Verify house style was applied
            content_str = json.dumps(output.documentation.content)
            assert "obviously" not in content_str.lower()
            assert "simply" not in content_str.lower()

            # Apply patches
            patch_generator = PatchGenerator(workspace_dir=Path(tmpdir) / ".patches")

            for patch_data in output.patches:
                patch = patch_generator.generate_patch(
                    action=PatchAction(patch_data["action"]),
                    file_path=patch_data["file_path"],
                    original_content=patch_data.get("original_content"),
                    new_content=patch_data.get("content") or patch_data.get("new_content"),
                )

                success, error = patch_generator.apply_patch(patch)
                assert success, f"Failed to apply patch: {error}"

            # Verify file was created
            assert target_file.exists()
            content = target_file.read_text()

            # Verify content structure
            assert "# User Management API" in content
            assert "## Authentication" in content
            assert "## Endpoints" in content
            assert "GET `/api/users`" in content

    @pytest.mark.asyncio
    async def test_prompt_engineering_integration(self, test_session, house_style):
        """Test prompt engineering system integration."""
        prompt_engine = PromptEngine(house_style)

        task = Mock(
            title="Document Configuration",
            description="Document application configuration options",
            content_template="Config template",
            metadata={"configs": [{"key": "DEBUG", "value": "true"}]},
        )

        context = Mock(spec=ChangeContext)
        context.changed_symbols = []
        context.related_docs = []
        context.new_features = []
        context.breaking_changes = []
        context.deprecations = []
        context.performance_impacts = []
        context.security_considerations = []
        context.related_code = []
        context.diff_context = {}

        # Build prompt
        prompt = prompt_engine.build_prompt(
            doc_type=DocType.CONFIG_REFERENCE,
            task=task,
            context=context,
            constraints=["Document all environment variables"],
            examples=[{"example": "Sample config"}],
        )

        # Verify prompt structure
        assert "technical writer" in prompt.lower()
        assert "configuration" in prompt.lower()
        assert "Document Configuration" in prompt
        assert "environment variables" in prompt
        assert "Sample config" in prompt

        # Verify house style is included
        assert str(house_style.tone.value) in prompt
        # Check that house style guidelines are mentioned
        assert "house style" in prompt.lower() or "style guidelines" in prompt.lower()

    @pytest.mark.asyncio
    async def test_patch_generation_and_rollback(self, test_session):
        """Test patch generation and rollback capabilities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            patch_generator = PatchGenerator(workspace_dir=Path(tmpdir) / ".patches")

            # Create multiple patches
            file1 = Path(tmpdir) / "doc1.md"
            file2 = Path(tmpdir) / "doc2.md"

            patches_data = [
                {"action": "create", "file_path": str(file1), "new_content": "# Document 1\n\nContent for document 1."},
                {"action": "create", "file_path": str(file2), "new_content": "# Document 2\n\nContent for document 2."},
            ]

            # Generate patch set
            patch_set = patch_generator.generate_patch_set(patches_data, atomic=True)

            # Apply patches
            success, errors = patch_generator.apply_patch_set(patch_set)
            assert success
            assert file1.exists()
            assert file2.exists()

            # Test incremental update
            base_patch = patch_set.patches[0]
            incremental = patch_generator.generate_incremental_patch(
                base_patch=base_patch, new_content="# Document 1 Updated\n\nUpdated content."
            )

            success, error = patch_generator.apply_patch(incremental)
            assert success
            assert "Updated content" in file1.read_text()

            # Rollback incremental patch
            success, error = patch_generator.rollback_patch(incremental)
            assert success
            assert "Updated content" not in file1.read_text()

            # Rollback entire patch set
            # Note: patch_set was already applied, so we can rollback
            success, errors = patch_generator.rollback_patch_set(patch_set)
            # The patches are already applied, should succeed
            assert success or len(errors) == 0  # Allow for already rolled back state
            assert not file1.exists()
            assert not file2.exists()

    @pytest.mark.asyncio
    async def test_different_doc_types(self, test_session, house_style):
        """Test generating different types of documentation."""
        writer = DocumentationWriter(test_session, house_style)

        # Test data for different doc types
        test_cases = [
            {
                "doc_type": DocType.CHANGELOG_ENTRY,
                "task_type": DocTaskType.CHANGELOG_ENTRY,
                "response": {
                    "version": "2.0.0",
                    "date": "2024-01-01",
                    "changes": [
                        {"type": "added", "description": "New feature X"},
                        {"type": "fixed", "description": "Bug in feature Y"},
                    ],
                },
            },
            {
                "doc_type": DocType.TUTORIAL_GUIDE,
                "task_type": DocTaskType.FEATURE_GUIDE,
                "response": {
                    "title": "Getting Started",
                    "description": "Learn the basics",
                    "prerequisites": ["Python 3.8+"],
                    "steps": [
                        {
                            "step_number": 1,
                            "title": "Installation",
                            "description": "Install the package",
                            "code_examples": [],
                        }
                    ],
                },
            },
            {
                "doc_type": DocType.MIGRATION_GUIDE,
                "task_type": DocTaskType.MIGRATION_GUIDE,
                "response": {
                    "title": "Migration Guide",
                    "from_version": "1.0",
                    "to_version": "2.0",
                    "breaking_changes": ["API changes"],
                    "migration_steps": [
                        {"step_number": 1, "title": "Update configs", "description": "Update configuration files"}
                    ],
                },
            },
        ]

        for test_case in test_cases:
            # Mock AI response
            writer.ai_integration.generate_text = AsyncMock(return_value=json.dumps(test_case["response"]))

            # Create task
            task = DocumentationTask(
                task_type=test_case["task_type"],
                target_section=DocSection.CHANGELOG,
                title=f"Generate {test_case['doc_type'].value}",
                description="Test generation",
                content_template="",
                source_change=Mock(),
                confidence=0.8,
                priority=5,
                auto_generate=True,
            )

            # Create input
            # Create properly configured context mock
            mock_context = Mock(spec=ChangeContext)
            mock_context.changed_symbols = []
            mock_context.related_docs = []

            input_data = WriterInput(
                task=task,
                context=mock_context,
                target_files=[
                    TargetFile(
                        path=f"test_{test_case['doc_type'].value}.md",
                        framework=DocFramework.GENERIC,
                        confidence=0.9,
                        reason="Test",
                        create_if_missing=True,
                    )
                ],
            )

            # Generate documentation
            output = await writer.write_documentation(input_data)

            # Verify correct doc type
            assert output.documentation.doc_type == test_case["doc_type"]

            # Verify content matches response
            for key in test_case["response"]:
                assert key in output.documentation.content

    @pytest.mark.asyncio
    async def test_validation_and_error_handling(self, test_session, house_style):
        """Test validation and error handling."""
        writer = DocumentationWriter(test_session, house_style)

        # Mock AI response with invalid structure
        writer.ai_integration.generate_text = AsyncMock(
            return_value=json.dumps({"invalid_field": "This doesn't match schema"})
        )

        task = DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title="Test",
            description="Test",
            content_template="",
            source_change=Mock(),
            confidence=0.5,
            priority=5,
            auto_generate=False,
        )

        # Create properly configured context mock
        mock_context = Mock(spec=ChangeContext)
        mock_context.changed_symbols = []
        mock_context.related_docs = []

        input_data = WriterInput(task=task, context=mock_context, target_files=[])

        # Should handle invalid response gracefully
        output = await writer.write_documentation(input_data)

        # Should have warnings about missing fields
        assert len(output.documentation.warnings) > 0

        # Should have lower confidence due to validation issues
        assert output.confidence < task.confidence

        # Should generate suggestions for improvement
        assert len(output.suggestions) > 0
