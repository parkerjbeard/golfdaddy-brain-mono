"""
House style configuration for documentation generation.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PromptTone(Enum):
    """Tone options for documentation."""

    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    TECHNICAL = "technical"
    EDUCATIONAL = "educational"
    CONCISE = "concise"


@dataclass
class DocumentationStructure:
    """Preferred documentation structure."""

    api_structure: List[str] = field(
        default_factory=lambda: [
            "title",
            "description",
            "authentication",
            "base_url",
            "endpoints",
            "models",
            "examples",
            "errors",
        ]
    )

    config_structure: List[str] = field(
        default_factory=lambda: ["title", "overview", "sections", "environment_variables", "examples", "defaults"]
    )

    tutorial_structure: List[str] = field(
        default_factory=lambda: [
            "title",
            "introduction",
            "prerequisites",
            "objectives",
            "steps",
            "summary",
            "next_steps",
            "troubleshooting",
        ]
    )

    changelog_structure: List[str] = field(
        default_factory=lambda: [
            "version",
            "date",
            "summary",
            "added",
            "changed",
            "deprecated",
            "removed",
            "fixed",
            "security",
        ]
    )


@dataclass
class HouseStyleConfig:
    """Configuration for house style in documentation."""

    # Tone and voice
    tone: PromptTone = PromptTone.PROFESSIONAL
    voice: str = "active"  # active or passive
    person: str = "second"  # first, second, or third person

    # Terminology mapping
    terminology: Dict[str, str] = field(
        default_factory=lambda: {
            "API": "API",  # Ensure consistent capitalization
            "URL": "URL",
            "JSON": "JSON",
            "REST": "REST",
            "HTTP": "HTTP",
            "CRUD": "CRUD",
            "SDK": "SDK",
            "OAuth": "OAuth",
            "JWT": "JWT",
        }
    )

    # Forbidden phrases to avoid
    forbidden_phrases: List[str] = field(
        default_factory=lambda: [
            "obviously",
            "simply",
            "just",
            "easy",
            "trivial",
            "should be obvious",
            "as you know",
            "of course",
            "naturally",
        ]
    )

    # Preferred phrases
    preferred_phrases: Dict[str, str] = field(
        default_factory=lambda: {
            "click": "select",
            "hit": "press",
            "do": "perform",
            "see": "refer to",
            "check": "verify",
            "make sure": "ensure",
            "fill in": "enter",
            "log in": "sign in",
            "log out": "sign out",
        }
    )

    # Documentation structure preferences
    structure: DocumentationStructure = field(default_factory=DocumentationStructure)

    # Formatting preferences
    code_block_style: str = "fenced"  # fenced or indented
    list_style: str = "bullet"  # bullet, numbered, or mixed
    heading_style: str = "atx"  # atx (#) or setext (underline)
    max_line_length: int = 100
    indent_size: int = 2

    # Content preferences
    include_examples: bool = True
    include_prerequisites: bool = True
    include_troubleshooting: bool = True
    include_see_also: bool = True
    include_timestamps: bool = False
    include_author: bool = False

    # Code example preferences
    example_language_priority: List[str] = field(
        default_factory=lambda: ["python", "javascript", "typescript", "bash", "curl"]
    )

    # Constraints for generation
    constraints: List[str] = field(
        default_factory=lambda: [
            "Use present tense for descriptions",
            "Use imperative mood for instructions",
            "Include at least one example per endpoint",
            "Document all error responses",
            "Include authentication requirements",
            "Specify rate limiting if applicable",
        ]
    )

    # Version and changelog preferences
    version_format: str = "semver"  # semver, date, or custom
    changelog_format: str = "keepachangelog"  # keepachangelog or conventional

    # Language preferences
    american_spelling: bool = True
    oxford_comma: bool = True

    # Technical preferences
    parameter_naming: str = "snake_case"  # snake_case, camelCase, PascalCase
    null_representation: str = "null"  # null, nil, None
    boolean_representation: Dict[bool, str] = field(default_factory=lambda: {True: "true", False: "false"})

    @classmethod
    def from_file(cls, file_path: Path) -> "HouseStyleConfig":
        """Load house style configuration from a file.

        Args:
            file_path: Path to configuration file (JSON or YAML)

        Returns:
            HouseStyleConfig instance
        """
        try:
            with open(file_path, "r") as f:
                if file_path.suffix == ".json":
                    data = json.load(f)
                elif file_path.suffix in [".yaml", ".yml"]:
                    import yaml

                    data = yaml.safe_load(f)
                else:
                    raise ValueError(f"Unsupported file format: {file_path.suffix}")

            # Convert tone string to enum if necessary
            if "tone" in data and isinstance(data["tone"], str):
                data["tone"] = PromptTone[data["tone"].upper()]

            # Create structure if provided
            if "structure" in data:
                data["structure"] = DocumentationStructure(**data["structure"])

            return cls(**data)

        except Exception as e:
            logger.error(f"Error loading house style from {file_path}: {e}")
            return cls()  # Return default configuration

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "tone": self.tone.value,
            "voice": self.voice,
            "person": self.person,
            "terminology": self.terminology,
            "forbidden_phrases": self.forbidden_phrases,
            "preferred_phrases": self.preferred_phrases,
            "structure": {
                "api_structure": self.structure.api_structure,
                "config_structure": self.structure.config_structure,
                "tutorial_structure": self.structure.tutorial_structure,
                "changelog_structure": self.structure.changelog_structure,
            },
            "code_block_style": self.code_block_style,
            "list_style": self.list_style,
            "heading_style": self.heading_style,
            "max_line_length": self.max_line_length,
            "indent_size": self.indent_size,
            "include_examples": self.include_examples,
            "include_prerequisites": self.include_prerequisites,
            "include_troubleshooting": self.include_troubleshooting,
            "include_see_also": self.include_see_also,
            "include_timestamps": self.include_timestamps,
            "include_author": self.include_author,
            "example_language_priority": self.example_language_priority,
            "constraints": self.constraints,
            "version_format": self.version_format,
            "changelog_format": self.changelog_format,
            "american_spelling": self.american_spelling,
            "oxford_comma": self.oxford_comma,
            "parameter_naming": self.parameter_naming,
            "null_representation": self.null_representation,
            "boolean_representation": self.boolean_representation,
        }

    def save_to_file(self, file_path: Path):
        """Save configuration to a file.

        Args:
            file_path: Path to save configuration
        """
        try:
            data = self.to_dict()

            with open(file_path, "w") as f:
                if file_path.suffix == ".json":
                    json.dump(data, f, indent=2)
                elif file_path.suffix in [".yaml", ".yml"]:
                    import yaml

                    yaml.dump(data, f, default_flow_style=False)
                else:
                    raise ValueError(f"Unsupported file format: {file_path.suffix}")

            logger.info(f"Saved house style configuration to {file_path}")

        except Exception as e:
            logger.error(f"Error saving house style to {file_path}: {e}")
            raise

    def apply_to_text(self, text: str) -> str:
        """Apply house style rules to text.

        Args:
            text: Text to apply style to

        Returns:
            Text with house style applied
        """
        result = text

        # Apply terminology replacements
        for old_term, new_term in self.terminology.items():
            # Case-insensitive replacement while preserving the preferred case
            import re

            pattern = re.compile(re.escape(old_term), re.IGNORECASE)
            result = pattern.sub(new_term, result)

        # Remove forbidden phrases (with word boundaries)
        for phrase in self.forbidden_phrases:
            # Use word boundaries for better matching
            pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
            result = pattern.sub("", result)

        # Apply preferred phrases
        for old_phrase, new_phrase in self.preferred_phrases.items():
            # Case-insensitive replacement while preserving case
            pattern = re.compile(r"\b" + re.escape(old_phrase) + r"\b", re.IGNORECASE)

            def replace_with_case(match):
                original = match.group(0)
                if original[0].isupper():
                    return new_phrase.capitalize()
                return new_phrase

            result = pattern.sub(replace_with_case, result)

        # Apply spelling preferences
        if self.american_spelling:
            result = self._apply_american_spelling(result)

        # Apply comma preferences
        if self.oxford_comma:
            result = self._apply_oxford_comma(result)

        # Clean up any double spaces or empty lines created
        result = re.sub(r"\s+", " ", result)
        result = re.sub(r"\n\s*\n\s*\n", "\n\n", result)

        return result.strip()

    def _apply_american_spelling(self, text: str) -> str:
        """Convert British spelling to American spelling.

        Args:
            text: Text to convert

        Returns:
            Text with American spelling
        """
        british_to_american = {
            "colour": "color",
            "flavour": "flavor",
            "honour": "honor",
            "labour": "labor",
            "neighbour": "neighbor",
            "centre": "center",
            "metre": "meter",
            "theatre": "theater",
            "defence": "defense",
            "licence": "license",
            "offence": "offense",
            "pretence": "pretense",
            "organise": "organize",
            "recognise": "recognize",
            "analyse": "analyze",
            "paralyse": "paralyze",
            "catalogue": "catalog",
            "dialogue": "dialog",
            "programme": "program",
        }

        result = text
        for british, american in british_to_american.items():
            result = result.replace(british, american)
            result = result.replace(british.capitalize(), american.capitalize())

        return result

    def _apply_oxford_comma(self, text: str) -> str:
        """Ensure Oxford comma is used in lists.

        Args:
            text: Text to process

        Returns:
            Text with Oxford comma applied
        """
        # Simple implementation - find patterns like "A, B and C" and convert to "A, B, and C"
        import re

        pattern = r"(\w+),\s+(\w+)\s+and\s+(\w+)"
        replacement = r"\1, \2, and \3"
        return re.sub(pattern, replacement, text)

    def validate_structure(self, content: Dict[str, Any], doc_type: str) -> List[str]:
        """Validate that content follows preferred structure.

        Args:
            content: Content to validate
            doc_type: Type of documentation

        Returns:
            List of validation messages
        """
        messages = []

        # Get expected structure
        expected_structure = []
        if doc_type == "api":
            expected_structure = self.structure.api_structure
        elif doc_type == "config":
            expected_structure = self.structure.config_structure
        elif doc_type == "tutorial":
            expected_structure = self.structure.tutorial_structure
        elif doc_type == "changelog":
            expected_structure = self.structure.changelog_structure

        # Check for missing sections
        for section in expected_structure:
            if section not in content:
                messages.append(f"Missing expected section: {section}")

        # Check for unexpected sections
        for section in content:
            if section not in expected_structure:
                messages.append(f"Unexpected section: {section}")

        # Check section order
        content_sections = list(content.keys())
        expected_order = [s for s in expected_structure if s in content_sections]
        actual_order = [s for s in content_sections if s in expected_structure]

        if expected_order != actual_order:
            messages.append(f"Sections not in preferred order. Expected: {expected_order}, Got: {actual_order}")

        return messages


class HouseStyleValidator:
    """Validator for checking content against house style."""

    def __init__(self, config: HouseStyleConfig):
        """Initialize validator with house style configuration.

        Args:
            config: House style configuration
        """
        self.config = config

    def validate(self, content: str) -> List[str]:
        """Validate content against house style rules.

        Args:
            content: Content to validate

        Returns:
            List of validation issues
        """
        import re

        issues = []

        # Check for forbidden phrases (case-insensitive with word boundaries)
        for phrase in self.config.forbidden_phrases:
            pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
            if pattern.search(content):
                issues.append(f"Found forbidden phrase: '{phrase}'")

        # Check line length
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if len(line) > self.config.max_line_length:
                issues.append(f"Line {i} exceeds maximum length ({len(line)} > {self.config.max_line_length})")

        # Check for non-preferred phrases (case-insensitive with word boundaries)
        for old_phrase, new_phrase in self.config.preferred_phrases.items():
            pattern = re.compile(r"\b" + re.escape(old_phrase) + r"\b", re.IGNORECASE)
            if pattern.search(content):
                issues.append(f"Found non-preferred phrase: '{old_phrase}' (use '{new_phrase}' instead)")

        # Check spelling (case-insensitive with word boundaries)
        if self.config.american_spelling:
            british_words = ["colour", "flavour", "centre", "organise", "analyse"]
            for word in british_words:
                pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
                if pattern.search(content):
                    issues.append(f"Found British spelling: '{word}'")

        return issues
