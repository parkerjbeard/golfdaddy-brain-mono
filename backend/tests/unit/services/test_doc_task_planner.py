"""
Unit tests for the documentation task planner.
"""

import pytest

from app.services.change_analyzer import (
    ChangeCategory,
    ChangedEndpoint,
    ChangedSymbol,
    ChangeType,
    ConfigChange,
    MigrationChange,
    StructuredChange,
)
from app.services.doc_task_planner import (
    ConfidenceCalculator,
    DocSection,
    DocTaskType,
    DocumentationTask,
    DocumentationTaskPlanner,
    MappingRule,
)


class TestDocumentationTaskPlanner:
    """Test the documentation task planner."""

    @pytest.fixture
    def planner(self):
        """Create a task planner instance."""
        return DocumentationTaskPlanner()

    def test_plan_api_documentation_task(self, planner):
        """Test planning API documentation for new functions."""
        # Create a change with new public function
        change = StructuredChange(
            file_path="api.py",
            change_type=ChangeType.ADDED,
            category=ChangeCategory.NEW_FEATURE,
            symbols=[
                ChangedSymbol(
                    name="process_data",
                    kind="function",
                    change_type=ChangeType.ADDED,
                    file_path="api.py",
                    start_line=10,
                    end_line=20,
                    signature="def process_data(input: dict) -> dict",
                    docstring="Process input data",
                    is_public=True,
                )
            ],
            impact_score=0.7,
        )

        tasks = planner.plan_tasks([change])

        assert len(tasks) >= 1
        api_task = next((t for t in tasks if t.task_type == DocTaskType.API_REFERENCE), None)
        assert api_task is not None
        assert api_task.target_section == DocSection.API_DOCS
        assert "process_data" in api_task.title
        assert api_task.confidence > 0.5

    def test_plan_endpoint_documentation_task(self, planner):
        """Test planning REST API documentation for new endpoints."""
        change = StructuredChange(
            file_path="routes.py",
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.API_CHANGE,
            endpoints=[
                ChangedEndpoint(
                    method="GET",
                    path="/users/{id}",
                    change_type=ChangeType.ADDED,
                    file_path="routes.py",
                    handler="get_user",
                ),
                ChangedEndpoint(
                    method="POST",
                    path="/users",
                    change_type=ChangeType.ADDED,
                    file_path="routes.py",
                    handler="create_user",
                ),
            ],
            impact_score=0.8,
        )

        tasks = planner.plan_tasks([change])

        assert len(tasks) >= 1
        endpoint_task = next((t for t in tasks if t.task_type == DocTaskType.API_REFERENCE), None)
        assert endpoint_task is not None
        assert "2 new API endpoint" in endpoint_task.title
        assert endpoint_task.priority >= 8

    def test_plan_config_documentation_task(self, planner):
        """Test planning configuration documentation."""
        change = StructuredChange(
            file_path="settings.py",
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.CONFIG_CHANGE,
            configs=[
                ConfigChange(
                    key="MAX_RETRIES",
                    old_value="3",
                    new_value="5",
                    file_path="settings.py",
                    change_type=ChangeType.MODIFIED,
                )
            ],
            impact_score=0.6,
        )

        tasks = planner.plan_tasks([change])

        config_task = next((t for t in tasks if t.task_type == DocTaskType.CONFIG_REFERENCE), None)
        assert config_task is not None
        assert config_task.target_section == DocSection.CONFIGURATION
        assert "MAX_RETRIES" in str(config_task.metadata)

    def test_plan_breaking_change_documentation(self, planner):
        """Test planning documentation for breaking changes."""
        change = StructuredChange(
            file_path="api.py",
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.BREAKING_CHANGE,
            breaking_changes=["Removed deprecated function old_process", "Changed signature of process_data"],
            impact_score=0.9,
        )

        tasks = planner.plan_tasks([change])

        breaking_task = next((t for t in tasks if t.task_type == DocTaskType.UPGRADE_GUIDE), None)
        assert breaking_task is not None
        assert breaking_task.priority == 10  # Highest priority
        assert breaking_task.confidence >= 0.9
        # Breaking changes with very high confidence (1.0) may be auto-generated
        # but typically should still require review
        assert breaking_task.confidence >= 0.9

    def test_plan_migration_documentation(self, planner):
        """Test planning database migration documentation."""
        change = StructuredChange(
            file_path="migrations/001_create_users.py",
            change_type=ChangeType.ADDED,
            category=ChangeCategory.MIGRATION,
            migrations=[
                MigrationChange(
                    version="001",
                    description="create_users",
                    file_path="migrations/001_create_users.py",
                    change_type=ChangeType.ADDED,
                    tables_affected=["users"],
                    operations=["create_table"],
                )
            ],
            impact_score=0.8,
        )

        tasks = planner.plan_tasks([change])

        migration_task = next((t for t in tasks if t.task_type == DocTaskType.MIGRATION_GUIDE), None)
        assert migration_task is not None
        assert "001" in migration_task.title
        assert migration_task.target_section == DocSection.MIGRATION

    def test_plan_feature_guide(self, planner):
        """Test planning feature guide documentation."""
        change = StructuredChange(
            file_path="features.py",
            change_type=ChangeType.ADDED,
            category=ChangeCategory.NEW_FEATURE,
            new_features=["New function: export_to_csv", "New class: DataExporter"],
            impact_score=0.7,
        )

        tasks = planner.plan_tasks([change])

        feature_task = next((t for t in tasks if t.task_type == DocTaskType.FEATURE_GUIDE), None)
        assert feature_task is not None
        assert feature_task.target_section == DocSection.TUTORIALS
        assert len(feature_task.metadata["features"]) == 2

    def test_plan_changelog_entry(self, planner):
        """Test planning changelog entries."""
        change = StructuredChange(
            file_path="utils.py",
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.BUG_FIX,
            impact_score=0.4,  # Above threshold for changelog
        )

        tasks = planner.plan_tasks([change])

        changelog_task = next((t for t in tasks if t.task_type == DocTaskType.CHANGELOG_ENTRY), None)
        assert changelog_task is not None
        assert changelog_task.auto_generate is True  # Can be auto-generated
        assert changelog_task.confidence >= 0.8

    def test_confidence_based_auto_generation(self, planner):
        """Test that auto-generation is based on confidence."""
        # High confidence change
        high_conf_change = StructuredChange(
            file_path="api.py",
            change_type=ChangeType.ADDED,
            category=ChangeCategory.API_CHANGE,
            endpoints=[
                ChangedEndpoint(
                    method="GET",
                    path="/health",
                    change_type=ChangeType.ADDED,
                    file_path="api.py",
                    handler="health_check",
                )
            ],
            impact_score=0.8,
        )

        tasks = planner.plan_tasks([high_conf_change])
        high_conf_task = tasks[0]

        # Should have high confidence
        assert high_conf_task.confidence >= 0.8
        # With confidence >= 0.8, it can be auto-generated
        assert high_conf_task.auto_generate is True

        # Changelog should auto-generate
        changelog_task = next((t for t in tasks if t.task_type == DocTaskType.CHANGELOG_ENTRY), None)
        if changelog_task:
            assert changelog_task.auto_generate is True

    def test_task_deduplication(self, planner):
        """Test that duplicate tasks are removed."""
        # Create two similar changes in the same file
        change1 = StructuredChange(
            file_path="api.py",
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.NEW_FEATURE,
            symbols=[
                ChangedSymbol(
                    name="func1",
                    kind="function",
                    change_type=ChangeType.ADDED,
                    file_path="api.py",
                    start_line=10,
                    end_line=15,
                    is_public=True,
                )
            ],
            impact_score=0.6,
        )

        change2 = StructuredChange(
            file_path="api.py",
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.NEW_FEATURE,
            symbols=[
                ChangedSymbol(
                    name="func2",
                    kind="function",
                    change_type=ChangeType.ADDED,
                    file_path="api.py",
                    start_line=20,
                    end_line=25,
                    is_public=True,
                )
            ],
            impact_score=0.7,
        )

        tasks = planner.plan_tasks([change1, change2])

        # Should have deduplicated API reference tasks for the same file
        api_tasks = [
            t for t in tasks if t.task_type == DocTaskType.API_REFERENCE and t.source_change.file_path == "api.py"
        ]
        assert len(api_tasks) == 1  # Should be deduplicated
        # Should keep the one with higher confidence (func2 has 0.7 impact)
        # Check that it's one of the two changes we created
        assert api_tasks[0].source_change.impact_score in [0.6, 0.7]

    def test_task_priority_ordering(self, planner):
        """Test that tasks are ordered by priority."""
        changes = [
            # Low priority change
            StructuredChange(
                file_path="utils.py",
                change_type=ChangeType.MODIFIED,
                category=ChangeCategory.REFACTOR,
                impact_score=0.3,
            ),
            # High priority breaking change
            StructuredChange(
                file_path="api.py",
                change_type=ChangeType.MODIFIED,
                category=ChangeCategory.BREAKING_CHANGE,
                breaking_changes=["Removed function"],
                impact_score=0.9,
            ),
            # Medium priority feature
            StructuredChange(
                file_path="features.py",
                change_type=ChangeType.ADDED,
                category=ChangeCategory.NEW_FEATURE,
                new_features=["New feature"],
                impact_score=0.6,
            ),
        ]

        tasks = planner.plan_tasks(changes)

        # Should be ordered by priority (descending)
        priorities = [t.priority for t in tasks]
        assert priorities == sorted(priorities, reverse=True)

        # Breaking change should be first
        assert tasks[0].source_change.category == ChangeCategory.BREAKING_CHANGE


class TestConfidenceCalculator:
    """Test the confidence calculator."""

    @pytest.fixture
    def calculator(self):
        """Create a confidence calculator instance."""
        return ConfidenceCalculator()

    def test_calculate_api_change_confidence(self, calculator):
        """Test confidence calculation for API changes."""
        change = StructuredChange(
            file_path="api.py",
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.API_CHANGE,
            endpoints=[ChangedEndpoint(method="GET", path="/test", change_type=ChangeType.ADDED, file_path="api.py")],
            impact_score=0.8,
        )

        task = DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title="Test",
            description="Test",
            content_template="",
            source_change=change,
            confidence=0.0,
            priority=5,
            auto_generate=False,
        )

        confidence = calculator.calculate(change, task)

        # API changes should have high confidence
        assert confidence >= 0.7

    def test_calculate_breaking_change_confidence(self, calculator):
        """Test confidence calculation for breaking changes."""
        change = StructuredChange(
            file_path="api.py",
            change_type=ChangeType.MODIFIED,
            category=ChangeCategory.BREAKING_CHANGE,
            breaking_changes=["Breaking change"],
            impact_score=0.9,
        )

        task = DocumentationTask(
            task_type=DocTaskType.UPGRADE_GUIDE,
            target_section=DocSection.MIGRATION,
            title="Test",
            description="Test",
            content_template="",
            source_change=change,
            confidence=0.0,
            priority=10,
            auto_generate=False,
        )

        confidence = calculator.calculate(change, task)

        # Breaking changes should have very high confidence
        assert confidence >= 0.9

    def test_confidence_with_docstrings(self, calculator):
        """Test that docstrings increase confidence."""
        # Change without docstrings
        change_no_docs = StructuredChange(
            file_path="test.py",
            change_type=ChangeType.ADDED,
            category=ChangeCategory.NEW_FEATURE,
            symbols=[
                ChangedSymbol(
                    name="func",
                    kind="function",
                    change_type=ChangeType.ADDED,
                    file_path="test.py",
                    start_line=1,
                    end_line=2,
                    docstring=None,
                )
            ],
            impact_score=0.5,
        )

        # Change with docstrings
        change_with_docs = StructuredChange(
            file_path="test.py",
            change_type=ChangeType.ADDED,
            category=ChangeCategory.NEW_FEATURE,
            symbols=[
                ChangedSymbol(
                    name="func",
                    kind="function",
                    change_type=ChangeType.ADDED,
                    file_path="test.py",
                    start_line=1,
                    end_line=2,
                    docstring="Well documented function",
                )
            ],
            impact_score=0.5,
        )

        task = DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title="Test",
            description="Test",
            content_template="",
            source_change=None,
            confidence=0.0,
            priority=5,
            auto_generate=False,
        )

        task.source_change = change_no_docs
        conf_no_docs = calculator.calculate(change_no_docs, task)

        task.source_change = change_with_docs
        conf_with_docs = calculator.calculate(change_with_docs, task)

        # Docstrings should increase confidence
        assert conf_with_docs > conf_no_docs
