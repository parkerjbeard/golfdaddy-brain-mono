"""
Prompt engineering system with modular templates.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.schemas.doc_output_schemas import DocType
from app.services.context_builder import ChangeContext
from app.services.doc_task_planner import DocumentationTask
from app.services.house_style import HouseStyleConfig, PromptTone

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """Template for generating prompts."""

    system_prompt: str
    instruction_template: str
    context_template: str
    constraint_template: str
    example_template: str
    output_format_instruction: str


class PromptEngine:
    """Engine for generating prompts for documentation generation."""

    def __init__(self, house_style: Optional[HouseStyleConfig] = None):
        """Initialize the prompt engine.

        Args:
            house_style: Optional house style configuration
        """
        self.house_style = house_style or HouseStyleConfig()
        self.templates = self._initialize_templates()

    def build_prompt(
        self,
        doc_type: DocType,
        task: DocumentationTask,
        context: ChangeContext,
        additional_context: Optional[Dict[str, Any]] = None,
        constraints: Optional[List[str]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build a complete prompt for documentation generation.

        Args:
            doc_type: Type of documentation to generate
            task: Documentation task
            context: Change context with code and documentation
            additional_context: Additional context information
            constraints: Specific constraints for generation
            examples: Example outputs for few-shot learning

        Returns:
            Complete prompt string
        """
        # Get the appropriate template
        template = self._get_template(doc_type)

        # Build prompt sections
        sections = []

        # System prompt
        system_prompt = self._build_system_prompt(template, doc_type)
        sections.append(system_prompt)

        # Main instruction
        instruction = self._build_instruction(template, task, doc_type)
        sections.append(instruction)

        # Context injection
        context_section = self._build_context_section(template, context, additional_context)
        sections.append(context_section)

        # Constraints
        if constraints or self.house_style.constraints:
            constraint_section = self._build_constraint_section(template, constraints)
            sections.append(constraint_section)

        # Examples (few-shot learning)
        if examples:
            example_section = self._build_example_section(template, examples)
            sections.append(example_section)

        # Output format instruction
        output_instruction = self._build_output_instruction(template, doc_type)
        sections.append(output_instruction)

        # Join all sections
        return "\n\n".join(filter(None, sections))

    def _initialize_templates(self) -> Dict[DocType, PromptTemplate]:
        """Initialize prompt templates for different documentation types."""
        return {
            DocType.API_REFERENCE: PromptTemplate(
                system_prompt="""You are an expert technical writer specializing in API documentation.
Your goal is to create clear, comprehensive, and accurate API reference documentation.
Focus on completeness, accuracy, and developer experience.""",
                instruction_template="""Generate API reference documentation for the following changes:

Task: {task_title}
Description: {task_description}

The documentation should include:
- Clear endpoint descriptions
- Complete parameter documentation
- Request/response examples
- Authentication requirements
- Error handling information""",
                context_template="""Context from the codebase:

Changed Code:
{code_changes}

Related Documentation:
{related_docs}

Additional Context:
{additional_context}""",
                constraint_template="""Please adhere to the following constraints:
{constraints}

House Style Guidelines:
- Tone: {tone}
- Terminology: Follow the provided terminology map
- Avoid these phrases: {forbidden_phrases}""",
                example_template="""Here are examples of the expected output format:
{examples}""",
                output_format_instruction="""Generate the documentation in JSON format that matches the APIReferenceDoc schema.
Include all required fields and ensure the structure is valid JSON.""",
            ),
            DocType.CONFIG_REFERENCE: PromptTemplate(
                system_prompt="""You are an expert technical writer specializing in configuration documentation.
Your goal is to create clear, comprehensive configuration references that help users understand and use configuration options effectively.""",
                instruction_template="""Generate configuration reference documentation for the following changes:

Task: {task_title}
Description: {task_description}

The documentation should include:
- Clear descriptions of each configuration option
- Type information and valid values
- Default values and examples
- Environment-specific considerations
- Migration notes for changed options""",
                context_template="""Context from the codebase:

Configuration Changes:
{config_changes}

Current Configuration:
{current_config}

Related Documentation:
{related_docs}""",
                constraint_template="""Please adhere to the following constraints:
{constraints}

Ensure all configuration options are documented with:
- Clear, concise descriptions
- Accurate type information
- Practical examples""",
                example_template="""Here are examples of well-documented configuration options:
{examples}""",
                output_format_instruction="""Generate the documentation in JSON format that matches the ConfigReferenceDoc schema.
Group related options into logical sections.""",
            ),
            DocType.TUTORIAL_GUIDE: PromptTemplate(
                system_prompt="""You are an expert technical writer and educator specializing in creating tutorials and guides.
Your goal is to create clear, step-by-step tutorials that help users learn and implement features effectively.""",
                instruction_template="""Create a tutorial guide for the following feature:

Task: {task_title}
Description: {task_description}

The tutorial should include:
- Clear learning objectives
- Prerequisites
- Step-by-step instructions
- Code examples
- Troubleshooting tips
- Next steps""",
                context_template="""Context about the feature:

New Features:
{new_features}

Code Implementation:
{code_implementation}

Related Documentation:
{related_docs}""",
                constraint_template="""Please follow these guidelines:
{constraints}

Educational best practices:
- Start simple and build complexity
- Include practical examples
- Explain the "why" not just the "how"
- Anticipate common questions""",
                example_template="""Here are examples of effective tutorial sections:
{examples}""",
                output_format_instruction="""Generate the tutorial in JSON format that matches the TutorialGuideDoc schema.
Ensure each step is clear and actionable.""",
            ),
            DocType.CHANGELOG_ENTRY: PromptTemplate(
                system_prompt="""You are a technical writer creating changelog entries.
Your goal is to create clear, concise changelog entries that accurately communicate changes to users.""",
                instruction_template="""Create a changelog entry for the following changes:

Task: {task_title}
Version: {version}

Changes to document:
{change_summary}""",
                context_template="""Details of the changes:

Code Changes:
{code_changes}

Breaking Changes:
{breaking_changes}

New Features:
{new_features}""",
                constraint_template="""Follow these changelog conventions:
{constraints}

- Use clear, action-oriented language
- Group changes by type (Added, Changed, Fixed, etc.)
- Highlight breaking changes prominently
- Include issue/PR references where applicable""",
                example_template="""Example changelog entries:
{examples}""",
                output_format_instruction="""Generate the changelog entry in JSON format that matches the ChangelogEntryDoc schema.
Follow semantic versioning conventions.""",
            ),
            DocType.MIGRATION_GUIDE: PromptTemplate(
                system_prompt="""You are a technical writer specializing in migration guides.
Your goal is to create comprehensive migration guides that help users safely upgrade their systems.""",
                instruction_template="""Create a migration guide for the following changes:

Task: {task_title}
From Version: {from_version}
To Version: {to_version}

The guide should address:
{migration_scope}""",
                context_template="""Migration context:

Breaking Changes:
{breaking_changes}

Code Changes Required:
{code_changes}

Configuration Changes:
{config_changes}

Database Migrations:
{db_migrations}""",
                constraint_template="""Ensure the migration guide:
{constraints}

- Lists all breaking changes clearly
- Provides step-by-step migration instructions
- Includes rollback procedures
- Offers testing recommendations""",
                example_template="""Example migration guide sections:
{examples}""",
                output_format_instruction="""Generate the migration guide in JSON format that matches the MigrationGuideDoc schema.
Ensure all breaking changes are addressed with clear migration paths.""",
            ),
        }

    def _get_template(self, doc_type: DocType) -> PromptTemplate:
        """Get the appropriate template for a documentation type."""
        template = self.templates.get(doc_type)
        if not template:
            # Fallback to API reference template
            logger.warning(f"No template found for {doc_type}, using API reference template")
            template = self.templates[DocType.API_REFERENCE]
        return template

    def _build_system_prompt(self, template: PromptTemplate, doc_type: DocType) -> str:
        """Build the system prompt section."""
        system_prompt = template.system_prompt

        # Add house style tone
        tone_instruction = self._get_tone_instruction(self.house_style.tone)
        system_prompt += f"\n\n{tone_instruction}"

        # Add quality requirements
        system_prompt += "\n\nQuality requirements:"
        system_prompt += "\n- Accuracy: All information must be factually correct"
        system_prompt += "\n- Completeness: Include all necessary information"
        system_prompt += "\n- Clarity: Use clear, unambiguous language"
        system_prompt += "\n- Consistency: Follow established patterns and terminology"

        return system_prompt

    def _build_instruction(self, template: PromptTemplate, task: DocumentationTask, doc_type: DocType) -> str:
        """Build the main instruction section."""
        instruction = template.instruction_template.format(
            task_title=task.title,
            task_description=task.description,
            version=getattr(task, "version", "latest"),
            from_version=getattr(task, "from_version", "previous"),
            to_version=getattr(task, "to_version", "current"),
            change_summary=task.content_template[:500] if task.content_template else "",
            migration_scope=getattr(task, "migration_scope", "all breaking changes"),
        )

        # Add specific requirements based on task metadata
        if task.metadata:
            if "functions" in task.metadata:
                instruction += f"\n\nDocument {len(task.metadata['functions'])} function(s)"
            if "endpoints" in task.metadata:
                instruction += f"\n\nDocument {len(task.metadata['endpoints'])} endpoint(s)"
            if "configs" in task.metadata:
                instruction += f"\n\nDocument {len(task.metadata['configs'])} configuration option(s)"

        return instruction

    def _build_context_section(
        self, template: PromptTemplate, context: ChangeContext, additional_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build the context section with relevant code and documentation."""
        context_parts = []

        # Add code changes
        if context.changed_symbols:
            code_changes = "\n".join(
                [
                    f"- {symbol.kind} {symbol.name}: {symbol.signature or 'No signature'}"
                    for symbol in context.changed_symbols[:10]  # Limit to prevent prompt overflow
                ]
            )
        else:
            code_changes = "No specific code symbols changed"

        # Add related documentation
        if context.related_docs:
            related_docs = "\n".join(
                [
                    f"- {doc.get('heading', 'Unknown')}: {doc.get('content', '')[:200]}"
                    for doc in context.related_docs[:5]
                ]
            )
        else:
            related_docs = "No related documentation found"

        # Format with template
        context_section = template.context_template.format(
            code_changes=code_changes,
            related_docs=related_docs,
            additional_context=additional_context or "No additional context provided",
            config_changes=self._format_config_changes(context),
            current_config=self._format_current_config(context),
            new_features=self._format_new_features(context),
            code_implementation=self._format_code_implementation(context),
            breaking_changes=self._format_breaking_changes(context),
            db_migrations=self._format_db_migrations(context),
        )

        return context_section

    def _build_constraint_section(self, template: PromptTemplate, constraints: Optional[List[str]]) -> str:
        """Build the constraints section."""
        all_constraints = []

        # Add user-provided constraints
        if constraints:
            all_constraints.extend(constraints)

        # Add house style constraints
        if self.house_style.constraints:
            all_constraints.extend(self.house_style.constraints)

        # Format with template
        constraint_section = template.constraint_template.format(
            constraints="\n".join(f"- {c}" for c in all_constraints),
            tone=self.house_style.tone.value,
            forbidden_phrases=", ".join(self.house_style.forbidden_phrases),
        )

        return constraint_section

    def _build_example_section(self, template: PromptTemplate, examples: List[Dict[str, Any]]) -> str:
        """Build the examples section for few-shot learning."""
        if not examples:
            return ""

        formatted_examples = []
        for i, example in enumerate(examples[:3], 1):  # Limit to 3 examples
            formatted_examples.append(f"Example {i}:")
            formatted_examples.append(str(example))
            formatted_examples.append("")

        return template.example_template.format(examples="\n".join(formatted_examples))

    def _build_output_instruction(self, template: PromptTemplate, doc_type: DocType) -> str:
        """Build the output format instruction."""
        instruction = template.output_format_instruction

        # Add specific field requirements
        instruction += "\n\nRequired fields:"
        required_fields = self._get_required_fields(doc_type)
        for field in required_fields:
            instruction += f"\n- {field}"

        # Add quality checks
        instruction += "\n\nBefore finalizing, ensure:"
        instruction += "\n- All technical details are accurate"
        instruction += "\n- Examples are functional and tested"
        instruction += "\n- Language follows house style guidelines"
        instruction += "\n- Structure is logical and easy to navigate"

        return instruction

    def _get_tone_instruction(self, tone: PromptTone) -> str:
        """Get tone-specific instructions."""
        tone_instructions = {
            PromptTone.PROFESSIONAL: "Maintain a professional, authoritative tone suitable for technical documentation.",
            PromptTone.FRIENDLY: "Use a friendly, approachable tone while maintaining technical accuracy.",
            PromptTone.TECHNICAL: "Use precise technical language appropriate for experienced developers.",
            PromptTone.EDUCATIONAL: "Use an educational tone that explains concepts clearly for learners.",
            PromptTone.CONCISE: "Be concise and direct, avoiding unnecessary elaboration.",
        }

        return tone_instructions.get(tone, tone_instructions[PromptTone.PROFESSIONAL])

    def _get_required_fields(self, doc_type: DocType) -> List[str]:
        """Get required fields for a documentation type."""
        required_map = {
            DocType.API_REFERENCE: ["title", "description", "endpoints", "version"],
            DocType.CONFIG_REFERENCE: ["title", "description", "sections"],
            DocType.TUTORIAL_GUIDE: ["title", "description", "steps", "prerequisites"],
            DocType.CHANGELOG_ENTRY: ["version", "date", "changes"],
            DocType.MIGRATION_GUIDE: ["title", "from_version", "to_version", "migration_steps", "breaking_changes"],
        }

        return required_map.get(doc_type, ["title", "description"])

    # Helper methods for formatting context

    def _format_config_changes(self, context: ChangeContext) -> str:
        """Format configuration changes from context."""
        # This would extract config changes from context
        return "Configuration changes details"

    def _format_current_config(self, context: ChangeContext) -> str:
        """Format current configuration from context."""
        return "Current configuration state"

    def _format_new_features(self, context: ChangeContext) -> str:
        """Format new features from context."""
        if hasattr(context, "new_features"):
            return "\n".join(f"- {feature}" for feature in context.new_features)
        return "No new features identified"

    def _format_code_implementation(self, context: ChangeContext) -> str:
        """Format code implementation details from context."""
        if context.changed_symbols:
            return f"Changed {len(context.changed_symbols)} code symbols"
        return "No code implementation details"

    def _format_breaking_changes(self, context: ChangeContext) -> str:
        """Format breaking changes from context."""
        if hasattr(context, "breaking_changes"):
            return "\n".join(f"- {change}" for change in context.breaking_changes)
        return "No breaking changes identified"

    def _format_db_migrations(self, context: ChangeContext) -> str:
        """Format database migrations from context."""
        if hasattr(context, "migrations"):
            return f"Includes {len(context.migrations)} database migration(s)"
        return "No database migrations"
