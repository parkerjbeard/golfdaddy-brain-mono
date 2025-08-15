"""
AI-powered documentation writer with structured output generation.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import AsyncSession
from app.integrations.ai_integration_v2 import AIIntegrationV2
from app.schemas.doc_output_schemas import (
    APIReferenceDoc,
    ChangelogEntryDoc,
    ConfigReferenceDoc,
    DocType,
    DocumentationOutput,
    MigrationGuideDoc,
    TutorialGuideDoc,
)
from app.services.context_builder import ChangeContext
from app.services.doc_task_planner import DocumentationTask
from app.services.house_style import HouseStyleConfig
from app.services.prompt_engineering import PromptEngine
from app.services.target_file_selector import TargetFile

logger = logging.getLogger(__name__)


@dataclass
class WriterInput:
    """Input for the documentation writer."""

    task: DocumentationTask
    context: ChangeContext
    target_files: List[TargetFile]
    additional_context: Optional[Dict[str, Any]] = None
    constraints: Optional[List[str]] = None
    examples: Optional[List[Dict[str, Any]]] = None


@dataclass
class WriterOutput:
    """Output from the documentation writer."""

    documentation: DocumentationOutput
    patches: List[Dict[str, Any]]  # List of patch objects
    confidence: float
    explanations: List[str]
    suggestions: List[str]


class DocumentationWriter:
    """Unified interface for AI-powered documentation generation."""

    def __init__(self, session: AsyncSession, house_style: Optional[HouseStyleConfig] = None):
        """Initialize the documentation writer.

        Args:
            session: Database session
            house_style: Optional house style configuration
        """
        self.session = session
        self.ai_integration = AIIntegrationV2()
        self.prompt_engine = PromptEngine(house_style or HouseStyleConfig())
        self.house_style = house_style or HouseStyleConfig()

        # Schema validators for different doc types
        self.schema_map = {
            DocType.API_REFERENCE: APIReferenceDoc,
            DocType.CONFIG_REFERENCE: ConfigReferenceDoc,
            DocType.TUTORIAL_GUIDE: TutorialGuideDoc,
            DocType.CHANGELOG_ENTRY: ChangelogEntryDoc,
            DocType.MIGRATION_GUIDE: MigrationGuideDoc,
        }

    async def write_documentation(self, input_data: WriterInput) -> WriterOutput:
        """Generate documentation based on input.

        Args:
            input_data: Input containing task, context, and targets

        Returns:
            Generated documentation with patches and metadata
        """
        try:
            # Determine documentation type
            doc_type = self._map_task_to_doc_type(input_data.task)

            # Build the prompt
            prompt = self.prompt_engine.build_prompt(
                doc_type=doc_type,
                task=input_data.task,
                context=input_data.context,
                additional_context=input_data.additional_context,
                constraints=input_data.constraints,
                examples=input_data.examples,
            )

            # Generate documentation with AI
            generated_content = await self._generate_with_ai(prompt, doc_type)

            # Validate and structure the output
            structured_output = self._structure_output(generated_content, doc_type)

            # Apply house style
            styled_output = self._apply_house_style(structured_output)

            # Generate patches for target files
            patches = await self._generate_patches(styled_output, input_data.target_files, input_data.task)

            # Calculate confidence and generate metadata
            confidence = self._calculate_confidence(styled_output, input_data.task, patches)

            # Generate explanations and suggestions
            explanations = self._generate_explanations(styled_output, patches)
            suggestions = self._generate_suggestions(styled_output, input_data.task)

            return WriterOutput(
                documentation=styled_output,
                patches=patches,
                confidence=confidence,
                explanations=explanations,
                suggestions=suggestions,
            )

        except Exception as e:
            logger.error(f"Error writing documentation: {e}")
            raise

    async def _generate_with_ai(self, prompt: str, doc_type: DocType) -> Dict[str, Any]:
        """Generate documentation content using AI.

        Args:
            prompt: The constructed prompt
            doc_type: Type of documentation to generate

        Returns:
            Generated content as dictionary
        """
        # Add JSON schema instruction
        schema_class = self.schema_map.get(doc_type)
        if schema_class:
            # Use model_json_schema for Pydantic v2
            schema_dict = schema_class.model_json_schema()
            schema_json = json.dumps(schema_dict, indent=2)
            prompt += f"\n\nPlease structure your response according to this JSON schema:\n{schema_json}"
            prompt += "\n\nProvide the response as valid JSON that matches the schema."

        # Call AI service
        # Try different methods depending on what's available
        if hasattr(self.ai_integration, 'generate_text'):
            response = await self.ai_integration.generate_text(
                prompt=prompt,
                max_tokens=4000,
                temperature=0.7,
                response_format={"type": "json_object"},  # Request JSON response
            )
        elif hasattr(self.ai_integration, 'generate'):
            response = await self.ai_integration.generate(
                prompt=prompt,
                max_tokens=4000,
                temperature=0.7
            )
        else:
            # Fallback
            response = await self.ai_integration(prompt)

        # Parse JSON response
        try:
            content = json.loads(response)
        except json.JSONDecodeError:
            # Fallback to text parsing if JSON fails
            content = self._parse_text_response(response, doc_type)

        return content

    def _structure_output(self, content: Dict[str, Any], doc_type: DocType) -> DocumentationOutput:
        """Structure and validate the generated content.

        Args:
            content: Generated content dictionary
            doc_type: Type of documentation

        Returns:
            Structured documentation output
        """
        validation_errors = []
        warnings = []

        # Validate against schema
        schema_class = self.schema_map.get(doc_type)
        if schema_class:
            try:
                # Validate by creating the model
                validated = schema_class(**content)
                content = validated.dict()
            except Exception as e:
                validation_errors.append(f"Schema validation error: {str(e)}")
                warnings.append("Content may not fully conform to expected structure")

        # Check for required fields based on doc type
        required_fields = self._get_required_fields(doc_type)
        for field in required_fields:
            if field not in content or not content[field]:
                warnings.append(f"Missing or empty required field: {field}")

        # Create structured output
        return DocumentationOutput(
            doc_type=doc_type,
            content=content,
            metadata={
                "generated_at": "2024-01-01T00:00:00Z",  # Would use actual timestamp
                "ai_model": "gpt-4",
                "confidence_score": 0.0,  # Will be calculated later
            },
            validation_errors=validation_errors,
            warnings=warnings,
        )

    def _apply_house_style(self, output: DocumentationOutput) -> DocumentationOutput:
        """Apply house style rules to the documentation.

        Args:
            output: Structured documentation output

        Returns:
            Documentation with house style applied
        """
        content = output.content

        # Apply terminology replacements
        content_str = json.dumps(content)
        for old_term, new_term in self.house_style.terminology.items():
            content_str = content_str.replace(old_term, new_term)

        # Remove forbidden phrases
        for phrase in self.house_style.forbidden_phrases:
            content_str = content_str.replace(phrase, "")

        # Parse back to dictionary
        content = json.loads(content_str)

        # Apply structural preferences
        if output.doc_type == DocType.API_REFERENCE and "endpoints" in content:
            # Ensure endpoints follow preferred structure
            for endpoint in content.get("endpoints", []):
                if "summary" in endpoint and len(endpoint["summary"]) > 100:
                    output.warnings.append(f"Endpoint summary too long: {endpoint.get('path', '')}")

        output.content = content
        return output

    async def _generate_patches(
        self, documentation: DocumentationOutput, target_files: List[TargetFile], task: DocumentationTask
    ) -> List[Dict[str, Any]]:
        """Generate patches for target documentation files.

        Args:
            documentation: Generated documentation
            target_files: Target files to update
            task: Original documentation task

        Returns:
            List of patch objects
        """
        patches = []

        for target in target_files:
            if target.create_if_missing:
                # Generate creation patch
                patch = self._create_file_patch(target, documentation, task)
            else:
                # Generate update patch
                patch = await self._create_update_patch(target, documentation, task)

            if patch:
                patches.append(patch)

        return patches

    def _create_file_patch(
        self, target: TargetFile, documentation: DocumentationOutput, task: DocumentationTask
    ) -> Dict[str, Any]:
        """Create a patch for a new file.

        Args:
            target: Target file information
            documentation: Generated documentation
            task: Documentation task

        Returns:
            Patch object for file creation
        """
        # Convert structured content to markdown
        content = self._render_to_markdown(documentation)

        return {
            "action": "create",
            "file_path": target.path,
            "content": content,
            "metadata": {
                "doc_type": documentation.doc_type.value,
                "task_type": task.task_type.value,
                "framework": target.framework.value,
            },
        }

    async def _create_update_patch(
        self, target: TargetFile, documentation: DocumentationOutput, task: DocumentationTask
    ) -> Optional[Dict[str, Any]]:
        """Create a patch for updating an existing file.

        Args:
            target: Target file information
            documentation: Generated documentation
            task: Documentation task

        Returns:
            Patch object for file update, or None if no update needed
        """
        # Read existing file content
        try:
            with open(target.path, "r") as f:
                existing_content = f.read()
        except FileNotFoundError:
            # File doesn't exist, create it instead
            return self._create_file_patch(target, documentation, task)

        # Generate new content
        new_content = self._render_to_markdown(documentation)

        # If targeting a specific section, merge with existing
        if target.section:
            merged_content = self._merge_sections(existing_content, new_content, target.section)
        else:
            merged_content = new_content

        # Generate diff if content changed
        if merged_content != existing_content:
            return {
                "action": "update",
                "file_path": target.path,
                "original_content": existing_content,
                "new_content": merged_content,
                "diff": self._generate_diff(existing_content, merged_content),
                "metadata": {
                    "doc_type": documentation.doc_type.value,
                    "task_type": task.task_type.value,
                    "section": target.section,
                },
            }

        return None

    def _render_to_markdown(self, documentation: DocumentationOutput) -> str:
        """Render structured documentation to markdown format.

        Args:
            documentation: Structured documentation

        Returns:
            Markdown formatted string
        """
        renderer_map = {
            DocType.API_REFERENCE: self._render_api_reference,
            DocType.CONFIG_REFERENCE: self._render_config_reference,
            DocType.TUTORIAL_GUIDE: self._render_tutorial,
            DocType.CHANGELOG_ENTRY: self._render_changelog,
            DocType.MIGRATION_GUIDE: self._render_migration_guide,
        }

        renderer = renderer_map.get(documentation.doc_type, self._render_generic)
        return renderer(documentation.content)

    def _render_api_reference(self, content: Dict[str, Any]) -> str:
        """Render API reference documentation to markdown."""
        lines = []

        # Title and description
        lines.append(f"# {content.get('title', 'API Reference')}")
        lines.append("")
        lines.append(content.get("description", ""))
        lines.append("")

        # Authentication
        if content.get("authentication"):
            lines.append("## Authentication")
            lines.append("")
            lines.append(content["authentication"])
            lines.append("")

        # Endpoints
        if content.get("endpoints"):
            lines.append("## Endpoints")
            lines.append("")

            for endpoint in content["endpoints"]:
                lines.append(f"### {endpoint['method']} `{endpoint['path']}`")
                lines.append("")
                lines.append(endpoint.get("summary", ""))
                lines.append("")

                if endpoint.get("description"):
                    lines.append(endpoint["description"])
                    lines.append("")

                # Parameters
                if endpoint.get("parameters"):
                    lines.append("**Parameters:**")
                    lines.append("")
                    lines.append("| Name | Type | Required | Description |")
                    lines.append("|------|------|----------|-------------|")

                    for param in endpoint["parameters"]:
                        required = "Yes" if param.get("required", True) else "No"
                        lines.append(
                            f"| {param['name']} | {param['type']} | {required} | {param.get('description', '')} |"
                        )
                    lines.append("")

                # Response
                if endpoint.get("response_schema"):
                    lines.append("**Response:**")
                    lines.append("```json")
                    lines.append(json.dumps(endpoint["response_schema"], indent=2))
                    lines.append("```")
                    lines.append("")

        return "\n".join(lines)

    def _render_config_reference(self, content: Dict[str, Any]) -> str:
        """Render configuration reference to markdown."""
        lines = []

        lines.append(f"# {content.get('title', 'Configuration Reference')}")
        lines.append("")
        lines.append(content.get("description", ""))
        lines.append("")

        # Configuration sections
        for section_name, options in content.get("sections", {}).items():
            lines.append(f"## {section_name}")
            lines.append("")

            for option in options:
                lines.append(f"### `{option['key']}`")
                lines.append("")
                lines.append(f"**Type:** `{option['type']}`")
                lines.append("")
                lines.append(f"**Default:** `{option.get('default', 'None')}`")
                lines.append("")
                lines.append(option.get("description", ""))
                lines.append("")

                if option.get("example"):
                    lines.append("**Example:**")
                    lines.append("```")
                    lines.append(str(option["example"]))
                    lines.append("```")
                    lines.append("")

        return "\n".join(lines)

    def _render_tutorial(self, content: Dict[str, Any]) -> str:
        """Render tutorial guide to markdown."""
        lines = []

        lines.append(f"# {content.get('title', 'Tutorial')}")
        lines.append("")
        lines.append(content.get("description", ""))
        lines.append("")

        # Prerequisites
        if content.get("prerequisites"):
            lines.append("## Prerequisites")
            lines.append("")
            for prereq in content["prerequisites"]:
                lines.append(f"- {prereq}")
            lines.append("")

        # Steps
        if content.get("steps"):
            for step in content["steps"]:
                lines.append(f"## Step {step['step_number']}: {step['title']}")
                lines.append("")
                lines.append(step["description"])
                lines.append("")

                # Code examples
                for example in step.get("code_examples", []):
                    if example.get("title"):
                        lines.append(f"**{example['title']}**")
                        lines.append("")
                    lines.append(f"```{example['language']}")
                    lines.append(example["code"])
                    lines.append("```")
                    lines.append("")

        return "\n".join(lines)

    def _render_changelog(self, content: Dict[str, Any]) -> str:
        """Render changelog entry to markdown."""
        lines = []

        lines.append(f"## [{content.get('version', 'Unreleased')}] - {content.get('date', 'TBD')}")
        lines.append("")

        if content.get("summary"):
            lines.append(content["summary"])
            lines.append("")

        # Group changes by type
        changes_by_type = {}
        for change in content.get("changes", []):
            change_type = change.get("type", "changed")
            if change_type not in changes_by_type:
                changes_by_type[change_type] = []
            changes_by_type[change_type].append(change)

        # Render each type
        type_titles = {
            "added": "### Added",
            "changed": "### Changed",
            "deprecated": "### Deprecated",
            "removed": "### Removed",
            "fixed": "### Fixed",
            "security": "### Security",
        }

        for change_type, title in type_titles.items():
            if change_type in changes_by_type:
                lines.append(title)
                lines.append("")
                for change in changes_by_type[change_type]:
                    prefix = "- **BREAKING:** " if change.get("breaking") else "- "
                    lines.append(f"{prefix}{change['description']}")
                    if change.get("issue_reference"):
                        lines.append(f"  ({change['issue_reference']})")
                lines.append("")

        return "\n".join(lines)

    def _render_migration_guide(self, content: Dict[str, Any]) -> str:
        """Render migration guide to markdown."""
        lines = []

        lines.append(f"# {content.get('title', 'Migration Guide')}")
        lines.append("")
        lines.append(f"**From:** {content.get('from_version', 'Unknown')}")
        lines.append(f"**To:** {content.get('to_version', 'Unknown')}")
        lines.append("")
        lines.append(content.get("summary", ""))
        lines.append("")

        # Breaking changes
        if content.get("breaking_changes"):
            lines.append("## Breaking Changes")
            lines.append("")
            for change in content["breaking_changes"]:
                lines.append(f"- {change}")
            lines.append("")

        # Migration steps
        if content.get("migration_steps"):
            lines.append("## Migration Steps")
            lines.append("")
            for step in content["migration_steps"]:
                lines.append(f"### {step['step_number']}. {step['title']}")
                lines.append("")
                lines.append(step["description"])
                lines.append("")

        return "\n".join(lines)

    def _render_generic(self, content: Dict[str, Any]) -> str:
        """Generic markdown renderer for unknown types."""
        return json.dumps(content, indent=2)

    def _merge_sections(self, existing: str, new: str, section: str) -> str:
        """Merge new content into a specific section of existing document."""
        # Simple implementation - in reality would parse markdown structure
        lines = existing.split("\n")
        new_lines = []
        in_section = False
        section_level = 0

        for line in lines:
            if line.startswith("#"):
                # Check if this is our target section
                if section in line:
                    in_section = True
                    section_level = line.count("#")
                    new_lines.append(line)
                    new_lines.append("")
                    # Insert new content
                    new_lines.extend(new.split("\n"))
                    new_lines.append("")
                elif in_section and line.count("#") <= section_level:
                    # End of our section
                    in_section = False
                    new_lines.append(line)
                elif not in_section:
                    new_lines.append(line)
            elif not in_section:
                new_lines.append(line)

        return "\n".join(new_lines)

    def _generate_diff(self, original: str, new: str) -> str:
        """Generate a unified diff between original and new content."""
        import difflib

        original_lines = original.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff = difflib.unified_diff(original_lines, new_lines, fromfile="original", tofile="new", lineterm="")

        return "".join(diff)

    def _calculate_confidence(
        self, documentation: DocumentationOutput, task: DocumentationTask, patches: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for generated documentation."""
        confidence = 0.8  # Base confidence

        # Adjust based on validation errors
        if documentation.validation_errors:
            confidence -= 0.1 * len(documentation.validation_errors)

        # Adjust based on warnings
        if documentation.warnings:
            confidence -= 0.05 * len(documentation.warnings)

        # Adjust based on task confidence
        confidence = (confidence + task.confidence) / 2

        # Adjust based on patch count
        if not patches:
            confidence -= 0.2  # No patches generated

        return max(0.0, min(1.0, confidence))

    def _generate_explanations(self, documentation: DocumentationOutput, patches: List[Dict[str, Any]]) -> List[str]:
        """Generate explanations for the documentation and patches."""
        explanations = []

        explanations.append(f"Generated {documentation.doc_type.value} documentation")

        if patches:
            explanations.append(f"Created {len(patches)} patch(es) for documentation files")

            for patch in patches:
                action = patch.get("action", "update")
                file_path = patch.get("file_path", "unknown")
                explanations.append(f"Will {action} {file_path}")

        if documentation.validation_errors:
            explanations.append(f"Note: {len(documentation.validation_errors)} validation issue(s) found")

        return explanations

    def _generate_suggestions(self, documentation: DocumentationOutput, task: DocumentationTask) -> List[str]:
        """Generate suggestions for improving the documentation."""
        suggestions = []

        # Check for missing examples
        if documentation.doc_type == DocType.API_REFERENCE:
            if not documentation.content.get("examples"):
                suggestions.append("Consider adding code examples for API usage")

        # Check for missing prerequisites
        if documentation.doc_type == DocType.TUTORIAL_GUIDE:
            if not documentation.content.get("prerequisites"):
                suggestions.append("Consider adding prerequisites section")

        # Check for version information
        if documentation.doc_type == DocType.CHANGELOG_ENTRY:
            if not documentation.content.get("version"):
                suggestions.append("Add version number for this changelog entry")

        # General suggestions based on confidence
        if task.confidence < 0.7:
            suggestions.append("Manual review recommended due to lower confidence")

        return suggestions

    def _map_task_to_doc_type(self, task: DocumentationTask) -> DocType:
        """Map a documentation task to a documentation type."""
        from app.services.doc_task_planner import DocTaskType

        mapping = {
            DocTaskType.API_REFERENCE: DocType.API_REFERENCE,
            DocTaskType.CONFIG_REFERENCE: DocType.CONFIG_REFERENCE,
            DocTaskType.FEATURE_GUIDE: DocType.TUTORIAL_GUIDE,
            DocTaskType.CHANGELOG_ENTRY: DocType.CHANGELOG_ENTRY,
            DocTaskType.MIGRATION_GUIDE: DocType.MIGRATION_GUIDE,
            DocTaskType.UPGRADE_GUIDE: DocType.MIGRATION_GUIDE,
            DocTaskType.ARCHITECTURE_UPDATE: DocType.API_REFERENCE,  # Fallback
            DocTaskType.TROUBLESHOOTING: DocType.TUTORIAL_GUIDE,  # Fallback
        }

        return mapping.get(task.task_type, DocType.API_REFERENCE)

    def _get_required_fields(self, doc_type: DocType) -> List[str]:
        """Get required fields for a documentation type."""
        required_map = {
            DocType.API_REFERENCE: ["title", "description", "endpoints"],
            DocType.CONFIG_REFERENCE: ["title", "sections"],
            DocType.TUTORIAL_GUIDE: ["title", "steps"],
            DocType.CHANGELOG_ENTRY: ["version", "changes"],
            DocType.MIGRATION_GUIDE: ["title", "from_version", "to_version", "migration_steps"],
        }

        return required_map.get(doc_type, [])

    def _parse_text_response(self, response: str, doc_type: DocType) -> Dict[str, Any]:
        """Parse text response when JSON parsing fails."""
        # Fallback parser - extract basic structure from text
        content = {}

        # Try to extract title
        import re

        title_match = re.search(r"#\s+(.+)", response)
        if title_match:
            content["title"] = title_match.group(1)

        # Extract sections
        sections = re.findall(r"##\s+(.+)", response)
        if sections:
            content["sections"] = sections

        # For now, return basic structure
        return content
