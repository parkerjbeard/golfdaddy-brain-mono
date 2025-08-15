"""
Documentation task planner with rule-based mapping and confidence scoring.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.services.change_analyzer import (
    ChangeCategory,
    ChangedEndpoint,
    ChangedSymbol,
    ConfigChange,
    MigrationChange,
    StructuredChange,
)

logger = logging.getLogger(__name__)


class DocTaskType(Enum):
    """Types of documentation tasks."""

    API_REFERENCE = "api_reference"
    CONFIG_REFERENCE = "config_reference"
    UPGRADE_GUIDE = "upgrade_guide"
    MIGRATION_GUIDE = "migration_guide"
    FEATURE_GUIDE = "feature_guide"
    CHANGELOG_ENTRY = "changelog_entry"
    CODE_EXAMPLE = "code_example"
    ARCHITECTURE_UPDATE = "architecture_update"
    TROUBLESHOOTING = "troubleshooting"
    RELEASE_NOTES = "release_notes"


class DocSection(Enum):
    """Common documentation sections."""

    API_DOCS = "api_documentation"
    CONFIGURATION = "configuration"
    MIGRATION = "migration_guides"
    TUTORIALS = "tutorials"
    REFERENCE = "reference"
    CHANGELOG = "changelog"
    EXAMPLES = "examples"
    ARCHITECTURE = "architecture"
    TROUBLESHOOTING = "troubleshooting"
    RELEASE_NOTES = "release_notes"


@dataclass
class DocumentationTask:
    """Represents a documentation task to be performed."""

    task_type: DocTaskType
    target_section: DocSection
    title: str
    description: str
    content_template: str
    source_change: StructuredChange
    confidence: float  # 0-1 confidence score
    priority: int  # 1-10 priority score
    auto_generate: bool  # Whether to auto-generate or require review
    metadata: Dict[str, Any] = field(default_factory=dict)
    suggested_files: List[str] = field(default_factory=list)


@dataclass
class MappingRule:
    """Rule for mapping changes to documentation tasks."""

    name: str
    condition: callable  # Function that takes StructuredChange and returns bool
    task_factory: callable  # Function that creates DocumentationTask
    confidence_modifier: float = 0.0  # Adjustment to base confidence
    priority: int = 5  # Default priority


class DocumentationTaskPlanner:
    """Plans documentation tasks based on code changes."""

    def __init__(self):
        """Initialize the task planner with mapping rules."""
        self.rules = self._initialize_rules()
        self.confidence_calculator = ConfidenceCalculator()

    def plan_tasks(self, changes: List[StructuredChange]) -> List[DocumentationTask]:
        """
        Plan documentation tasks for a list of code changes.

        Args:
            changes: List of structured code changes

        Returns:
            List of documentation tasks to perform
        """
        tasks = []

        for change in changes:
            # Apply each rule to the change
            for rule in self.rules:
                if rule.condition(change):
                    try:
                        task = rule.task_factory(change)

                        # Calculate and adjust confidence
                        base_confidence = self.confidence_calculator.calculate(change, task)
                        task.confidence = min(1.0, base_confidence + rule.confidence_modifier)

                        # Set auto-generation based on confidence
                        task.auto_generate = task.confidence >= 0.8

                        # Adjust priority based on change impact
                        task.priority = min(10, rule.priority + int(change.impact_score * 3))

                        tasks.append(task)
                        logger.info(f"Created {task.task_type.value} task with confidence {task.confidence:.2f}")

                    except Exception as e:
                        logger.error(f"Error applying rule {rule.name}: {e}")

        # Deduplicate and prioritize tasks
        tasks = self._deduplicate_tasks(tasks)
        tasks = sorted(tasks, key=lambda t: (-t.priority, -t.confidence))

        return tasks

    def _initialize_rules(self) -> List[MappingRule]:
        """Initialize the mapping rules engine."""
        rules = [
            # New public function → API documentation
            MappingRule(
                name="new_public_function",
                condition=lambda c: any(s.is_public and s.kind in ["function", "async_function"] for s in c.symbols),
                task_factory=self._create_api_doc_task,
                confidence_modifier=0.1,
                priority=7,
            ),
            # New endpoint → REST API documentation
            MappingRule(
                name="new_endpoint",
                condition=lambda c: bool(c.endpoints),
                task_factory=self._create_endpoint_doc_task,
                confidence_modifier=0.2,
                priority=9,
            ),
            # Config change → Configuration reference update
            MappingRule(
                name="config_change",
                condition=lambda c: bool(c.configs),
                task_factory=self._create_config_doc_task,
                confidence_modifier=0.15,
                priority=6,
            ),
            # Breaking change → Upgrade notes + migration guide
            MappingRule(
                name="breaking_change",
                condition=lambda c: bool(c.breaking_changes),
                task_factory=self._create_breaking_change_docs,
                confidence_modifier=0.25,
                priority=10,
            ),
            # Database migration → Migration documentation
            MappingRule(
                name="database_migration",
                condition=lambda c: bool(c.migrations),
                task_factory=self._create_migration_docs,
                confidence_modifier=0.2,
                priority=8,
            ),
            # New feature → Feature guide
            MappingRule(
                name="new_feature",
                condition=lambda c: bool(c.new_features) and not c.breaking_changes,
                task_factory=self._create_feature_guide,
                confidence_modifier=0.1,
                priority=7,
            ),
            # New class → Architecture/design documentation
            MappingRule(
                name="new_class",
                condition=lambda c: any(s.kind == "class" and s.is_public for s in c.symbols),
                task_factory=self._create_architecture_docs,
                confidence_modifier=0.05,
                priority=5,
            ),
            # Any significant change → Changelog entry
            MappingRule(
                name="changelog_entry",
                condition=lambda c: c.impact_score > 0.3,
                task_factory=self._create_changelog_entry,
                confidence_modifier=0.3,
                priority=4,
            ),
        ]

        return rules

    def _create_api_doc_task(self, change: StructuredChange) -> DocumentationTask:
        """Create API documentation task for new functions."""
        public_functions = [s for s in change.symbols if s.is_public and "function" in s.kind]

        if not public_functions:
            raise ValueError("No public functions found")

        func_names = [f.name for f in public_functions]

        return DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title=f"Document new functions: {', '.join(func_names)}",
            description=f"Add API documentation for {len(public_functions)} new function(s)",
            content_template=self._generate_function_template(public_functions),
            source_change=change,
            confidence=0.7,  # Base confidence
            priority=7,
            auto_generate=False,
            metadata={"functions": [f.__dict__ for f in public_functions]},
            suggested_files=[f"docs/api/{change.file_path.replace('.py', '.md')}"],
        )

    def _create_endpoint_doc_task(self, change: StructuredChange) -> DocumentationTask:
        """Create REST API documentation task."""
        endpoints = change.endpoints

        if not endpoints:
            raise ValueError("No endpoints found")

        return DocumentationTask(
            task_type=DocTaskType.API_REFERENCE,
            target_section=DocSection.API_DOCS,
            title=f"Document {len(endpoints)} new API endpoint(s)",
            description="Add REST API documentation with request/response examples",
            content_template=self._generate_endpoint_template(endpoints),
            source_change=change,
            confidence=0.8,
            priority=9,
            auto_generate=False,
            metadata={"endpoints": [e.__dict__ for e in endpoints]},
            suggested_files=["docs/api/endpoints.md", "docs/api/reference.md"],
        )

    def _create_config_doc_task(self, change: StructuredChange) -> DocumentationTask:
        """Create configuration documentation task."""
        configs = change.configs

        return DocumentationTask(
            task_type=DocTaskType.CONFIG_REFERENCE,
            target_section=DocSection.CONFIGURATION,
            title=f"Update configuration docs for {len(configs)} setting(s)",
            description="Document new or changed configuration options",
            content_template=self._generate_config_template(configs),
            source_change=change,
            confidence=0.75,
            priority=6,
            auto_generate=False,
            metadata={"configs": [c.__dict__ for c in configs]},
            suggested_files=["docs/configuration.md", "docs/settings.md"],
        )

    def _create_breaking_change_docs(self, change: StructuredChange) -> DocumentationTask:
        """Create breaking change documentation tasks."""
        return DocumentationTask(
            task_type=DocTaskType.UPGRADE_GUIDE,
            target_section=DocSection.MIGRATION,
            title="Document breaking changes",
            description="Create upgrade guide and migration instructions",
            content_template=self._generate_breaking_change_template(change),
            source_change=change,
            confidence=0.9,
            priority=10,
            auto_generate=False,
            metadata={"breaking_changes": change.breaking_changes},
            suggested_files=["docs/upgrade-guide.md", "docs/migration/latest.md"],
        )

    def _create_migration_docs(self, change: StructuredChange) -> DocumentationTask:
        """Create database migration documentation."""
        migrations = change.migrations

        return DocumentationTask(
            task_type=DocTaskType.MIGRATION_GUIDE,
            target_section=DocSection.MIGRATION,
            title=f"Document database migration: {migrations[0].version if migrations else 'unknown'}",
            description="Document database schema changes and migration steps",
            content_template=self._generate_migration_template(migrations),
            source_change=change,
            confidence=0.8,
            priority=8,
            auto_generate=False,
            metadata={"migrations": [m.__dict__ for m in migrations]},
            suggested_files=["docs/database/migrations.md", "docs/schema-changes.md"],
        )

    def _create_feature_guide(self, change: StructuredChange) -> DocumentationTask:
        """Create feature guide documentation."""
        return DocumentationTask(
            task_type=DocTaskType.FEATURE_GUIDE,
            target_section=DocSection.TUTORIALS,
            title=f"Document new features in {change.file_path}",
            description="Create user guide for new functionality",
            content_template=self._generate_feature_template(change),
            source_change=change,
            confidence=0.65,
            priority=7,
            auto_generate=False,
            metadata={"features": change.new_features},
            suggested_files=["docs/features/latest.md", "docs/user-guide.md"],
        )

    def _create_architecture_docs(self, change: StructuredChange) -> DocumentationTask:
        """Create architecture documentation for new classes."""
        classes = [s for s in change.symbols if s.kind == "class" and s.is_public]

        return DocumentationTask(
            task_type=DocTaskType.ARCHITECTURE_UPDATE,
            target_section=DocSection.ARCHITECTURE,
            title=f"Document new classes: {', '.join(c.name for c in classes)}",
            description="Update architecture documentation with new components",
            content_template=self._generate_class_template(classes),
            source_change=change,
            confidence=0.6,
            priority=5,
            auto_generate=False,
            metadata={"classes": [c.__dict__ for c in classes]},
            suggested_files=["docs/architecture.md", "docs/design/components.md"],
        )

    def _create_changelog_entry(self, change: StructuredChange) -> DocumentationTask:
        """Create changelog entry for any significant change."""
        return DocumentationTask(
            task_type=DocTaskType.CHANGELOG_ENTRY,
            target_section=DocSection.CHANGELOG,
            title="Add changelog entry",
            description=f"Document {change.category.value} in changelog",
            content_template=self._generate_changelog_template(change),
            source_change=change,
            confidence=0.85,
            priority=4,
            auto_generate=True,  # Changelog entries can be auto-generated
            metadata={"category": change.category.value},
            suggested_files=["CHANGELOG.md", "docs/changelog.md"],
        )

    def _generate_function_template(self, functions: List[ChangedSymbol]) -> str:
        """Generate template for function documentation."""
        template = "## API Reference\n\n"

        for func in functions:
            template += f"### `{func.name}`\n\n"
            template += f"**Signature:** `{func.signature or func.name}`\n\n"
            if func.docstring:
                template += f"**Description:** {func.docstring}\n\n"
            template += "**Parameters:**\n- TODO: Document parameters\n\n"
            template += "**Returns:**\n- TODO: Document return value\n\n"
            template += "**Example:**\n```python\n# TODO: Add usage example\n```\n\n"

        return template

    def _generate_endpoint_template(self, endpoints: List[ChangedEndpoint]) -> str:
        """Generate template for endpoint documentation."""
        template = "## API Endpoints\n\n"

        for endpoint in endpoints:
            template += f"### {endpoint.method} `{endpoint.path}`\n\n"
            template += f"**Handler:** `{endpoint.handler or 'Unknown'}`\n\n"
            template += "**Request:**\n```json\n{\n  // TODO: Add request schema\n}\n```\n\n"
            template += "**Response:**\n```json\n{\n  // TODO: Add response schema\n}\n```\n\n"
            template += "**Authentication:** " + ("Required" if endpoint.auth_required else "Not required") + "\n\n"

        return template

    def _generate_config_template(self, configs: List[ConfigChange]) -> str:
        """Generate template for configuration documentation."""
        template = "## Configuration Reference\n\n"

        for config in configs:
            template += f"### `{config.key}`\n\n"
            template += f"**Type:** TODO: Specify type\n\n"
            if config.old_value:
                template += f"**Previous Default:** `{config.old_value}`\n"
            template += f"**New Default:** `{config.new_value}`\n\n"
            template += "**Description:** TODO: Describe this configuration option\n\n"
            template += "**Example:**\n```\n" + f"{config.key}={config.new_value}\n```\n\n"

        return template

    def _generate_breaking_change_template(self, change: StructuredChange) -> str:
        """Generate template for breaking change documentation."""
        template = "## Breaking Changes\n\n"
        template += "### Summary\n\n"

        for breaking in change.breaking_changes:
            template += f"- {breaking}\n"

        template += "\n### Migration Steps\n\n"
        template += "1. TODO: Add step-by-step migration instructions\n"
        template += "2. Update configuration files\n"
        template += "3. Modify affected code\n"
        template += "4. Test thoroughly\n\n"

        template += "### Before/After Examples\n\n"
        template += "**Before:**\n```python\n# Old implementation\n```\n\n"
        template += "**After:**\n```python\n# New implementation\n```\n"

        return template

    def _generate_migration_template(self, migrations: List[MigrationChange]) -> str:
        """Generate template for migration documentation."""
        template = "## Database Migration\n\n"

        for migration in migrations:
            template += f"### Version {migration.version}: {migration.description}\n\n"
            template += f"**Tables Affected:** {', '.join(migration.tables_affected)}\n\n"
            template += f"**Operations:** {', '.join(migration.operations)}\n\n"
            template += "**Migration Command:**\n```bash\n# TODO: Add migration command\n```\n\n"
            template += "**Rollback Command:**\n```bash\n# TODO: Add rollback command\n```\n"

        return template

    def _generate_feature_template(self, change: StructuredChange) -> str:
        """Generate template for feature documentation."""
        template = "## New Features\n\n"

        for feature in change.new_features:
            template += f"### {feature}\n\n"
            template += "**Description:** TODO: Describe the feature\n\n"
            template += "**Usage:**\n```python\n# TODO: Add usage example\n```\n\n"
            template += "**Configuration:** TODO: Document any configuration options\n\n"

        return template

    def _generate_class_template(self, classes: List[ChangedSymbol]) -> str:
        """Generate template for class documentation."""
        template = "## Architecture Components\n\n"

        for cls in classes:
            template += f"### `{cls.name}`\n\n"
            if cls.docstring:
                template += f"**Purpose:** {cls.docstring}\n\n"
            template += "**Responsibilities:**\n- TODO: List responsibilities\n\n"
            template += "**Dependencies:**\n- TODO: List dependencies\n\n"
            template += "**Usage Example:**\n```python\n# TODO: Add usage example\n```\n"

        return template

    def _generate_changelog_template(self, change: StructuredChange) -> str:
        """Generate template for changelog entry."""
        template = f"### {change.category.value.replace('_', ' ').title()}\n\n"

        if change.new_features:
            template += "**Added:**\n"
            for feature in change.new_features:
                template += f"- {feature}\n"
            template += "\n"

        if change.behavior_changes:
            template += "**Changed:**\n"
            for behavior in change.behavior_changes:
                template += f"- {behavior}\n"
            template += "\n"

        if change.breaking_changes:
            template += "**Breaking:**\n"
            for breaking in change.breaking_changes:
                template += f"- {breaking}\n"
            template += "\n"

        template += f"**File:** `{change.file_path}`\n"

        return template

    def _deduplicate_tasks(self, tasks: List[DocumentationTask]) -> List[DocumentationTask]:
        """Remove duplicate documentation tasks."""
        seen = set()
        unique_tasks = []

        for task in tasks:
            # Create a unique key for the task
            key = (task.task_type, task.target_section, task.source_change.file_path)

            if key not in seen:
                seen.add(key)
                unique_tasks.append(task)
            else:
                # If duplicate, keep the one with higher confidence
                existing_idx = next(
                    i
                    for i, t in enumerate(unique_tasks)
                    if (t.task_type, t.target_section, t.source_change.file_path) == key
                )
                if task.confidence > unique_tasks[existing_idx].confidence:
                    unique_tasks[existing_idx] = task

        return unique_tasks


class ConfidenceCalculator:
    """Calculates confidence scores for documentation tasks."""

    def calculate(self, change: StructuredChange, task: DocumentationTask) -> float:
        """
        Calculate confidence score for a documentation task.

        Args:
            change: The source code change
            task: The documentation task

        Returns:
            Confidence score between 0 and 1
        """
        score = 0.5  # Base confidence

        # Adjust based on change category
        category_confidence = {
            ChangeCategory.API_CHANGE: 0.8,
            ChangeCategory.BREAKING_CHANGE: 0.9,
            ChangeCategory.CONFIG_CHANGE: 0.75,
            ChangeCategory.MIGRATION: 0.85,
            ChangeCategory.NEW_FEATURE: 0.7,
            ChangeCategory.DOCUMENTATION: 0.6,
            ChangeCategory.BUG_FIX: 0.4,
            ChangeCategory.REFACTOR: 0.3,
            ChangeCategory.TEST: 0.2,
            ChangeCategory.OTHER: 0.1,
        }
        score = category_confidence.get(change.category, 0.5)

        # Adjust based on task type
        task_confidence = {
            DocTaskType.API_REFERENCE: 0.05,
            DocTaskType.UPGRADE_GUIDE: 0.1,
            DocTaskType.MIGRATION_GUIDE: 0.1,
            DocTaskType.CHANGELOG_ENTRY: 0.15,
            DocTaskType.CONFIG_REFERENCE: 0.05,
            DocTaskType.FEATURE_GUIDE: 0.0,
            DocTaskType.CODE_EXAMPLE: -0.05,
            DocTaskType.ARCHITECTURE_UPDATE: -0.1,
            DocTaskType.TROUBLESHOOTING: -0.15,
            DocTaskType.RELEASE_NOTES: 0.1,
        }
        score += task_confidence.get(task.task_type, 0.0)

        # Adjust based on change characteristics
        if change.symbols:
            # More symbols = more complex = lower confidence
            score -= min(0.1, len(change.symbols) * 0.02)

        if change.endpoints:
            # Endpoints are well-structured = higher confidence
            score += 0.1

        if change.configs:
            # Config changes are straightforward
            score += 0.05

        # Presence of docstrings increases confidence
        documented_symbols = [s for s in change.symbols if s.docstring]
        if documented_symbols:
            score += min(0.1, len(documented_symbols) * 0.03)

        # Clamp to valid range
        return max(0.0, min(1.0, score))
