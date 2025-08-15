"""
JSON schemas for structured documentation output.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DocType(Enum):
    """Types of documentation outputs."""

    API_REFERENCE = "api_reference"
    CONFIG_REFERENCE = "config_reference"
    TUTORIAL_GUIDE = "tutorial_guide"
    CHANGELOG_ENTRY = "changelog_entry"
    MIGRATION_GUIDE = "migration_guide"
    ARCHITECTURE_DOC = "architecture_doc"
    TROUBLESHOOTING = "troubleshooting"


class CodeExample(BaseModel):
    """Schema for code examples in documentation."""

    language: str = Field(..., description="Programming language for syntax highlighting")
    code: str = Field(..., description="The actual code example")
    title: Optional[str] = Field(None, description="Title or description of the example")
    line_numbers: bool = Field(False, description="Whether to show line numbers")


class Parameter(BaseModel):
    """Schema for API parameter documentation."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type")
    required: bool = Field(True, description="Whether the parameter is required")
    default: Optional[Any] = Field(None, description="Default value if any")
    description: str = Field(..., description="Parameter description")
    example: Optional[Any] = Field(None, description="Example value")


class EndpointDoc(BaseModel):
    """Schema for API endpoint documentation."""

    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    path: str = Field(..., description="Endpoint path")
    summary: str = Field(..., description="Brief endpoint summary")
    description: str = Field(..., description="Detailed endpoint description")
    parameters: List[Parameter] = Field(default_factory=list, description="Request parameters")
    request_body: Optional[Dict[str, Any]] = Field(None, description="Request body schema")
    response_schema: Dict[str, Any] = Field(..., description="Response schema")
    response_examples: List[CodeExample] = Field(default_factory=list, description="Response examples")
    error_responses: List[Dict[str, Any]] = Field(
        default_factory=list, description="Error response codes and descriptions"
    )
    authentication: Optional[str] = Field(None, description="Authentication requirements")
    rate_limiting: Optional[str] = Field(None, description="Rate limiting information")
    deprecated: bool = Field(False, description="Whether the endpoint is deprecated")
    since_version: Optional[str] = Field(None, description="Version when added")


class FunctionDoc(BaseModel):
    """Schema for function/method documentation."""

    name: str = Field(..., description="Function name")
    signature: str = Field(..., description="Function signature")
    description: str = Field(..., description="Function description")
    parameters: List[Parameter] = Field(default_factory=list, description="Function parameters")
    returns: Optional[Dict[str, Any]] = Field(None, description="Return value documentation")
    raises: List[Dict[str, str]] = Field(default_factory=list, description="Exceptions that can be raised")
    examples: List[CodeExample] = Field(default_factory=list, description="Usage examples")
    see_also: List[str] = Field(default_factory=list, description="Related functions or documentation")
    since_version: Optional[str] = Field(None, description="Version when added")
    deprecated: bool = Field(False, description="Whether the function is deprecated")


class ConfigOption(BaseModel):
    """Schema for configuration option documentation."""

    key: str = Field(..., description="Configuration key")
    type: str = Field(..., description="Value type")
    default: Optional[Any] = Field(None, description="Default value")
    required: bool = Field(False, description="Whether the option is required")
    description: str = Field(..., description="Option description")
    valid_values: Optional[List[Any]] = Field(None, description="List of valid values if constrained")
    example: Optional[Any] = Field(None, description="Example value")
    environment_variable: Optional[str] = Field(None, description="Corresponding environment variable")
    deprecated: bool = Field(False, description="Whether the option is deprecated")
    since_version: Optional[str] = Field(None, description="Version when added")


class TutorialStep(BaseModel):
    """Schema for tutorial step."""

    step_number: int = Field(..., description="Step number in sequence")
    title: str = Field(..., description="Step title")
    description: str = Field(..., description="Step description")
    code_examples: List[CodeExample] = Field(default_factory=list, description="Code examples for this step")
    expected_output: Optional[str] = Field(None, description="Expected output or result")
    troubleshooting: List[str] = Field(default_factory=list, description="Common issues and solutions")
    tips: List[str] = Field(default_factory=list, description="Tips and best practices")


class ChangelogEntryType(str, Enum):
    """Types of changelog entries."""

    ADDED = "added"
    CHANGED = "changed"
    DEPRECATED = "deprecated"
    REMOVED = "removed"
    FIXED = "fixed"
    SECURITY = "security"


class ChangelogItem(BaseModel):
    """Schema for individual changelog item."""

    type: ChangelogEntryType = Field(..., description="Type of change")
    description: str = Field(..., description="Change description")
    issue_reference: Optional[str] = Field(None, description="Issue or PR reference")
    breaking: bool = Field(False, description="Whether this is a breaking change")


class APIReferenceDoc(BaseModel):
    """Schema for API reference documentation."""

    title: str = Field(..., description="API reference title")
    version: str = Field(..., description="API version")
    description: str = Field(..., description="API description")
    base_url: Optional[str] = Field(None, description="Base URL for the API")
    authentication: Optional[str] = Field(None, description="Authentication overview")
    endpoints: List[EndpointDoc] = Field(default_factory=list, description="API endpoints")
    functions: List[FunctionDoc] = Field(default_factory=list, description="Functions/methods")
    models: List[Dict[str, Any]] = Field(default_factory=list, description="Data models")
    examples: List[CodeExample] = Field(default_factory=list, description="General examples")


class ConfigReferenceDoc(BaseModel):
    """Schema for configuration reference documentation."""

    title: str = Field(..., description="Configuration reference title")
    description: str = Field(..., description="Configuration overview")
    sections: Dict[str, List[ConfigOption]] = Field(default_factory=dict, description="Configuration sections")
    examples: List[CodeExample] = Field(default_factory=list, description="Configuration examples")
    environment_specific: Dict[str, Any] = Field(
        default_factory=dict, description="Environment-specific configurations"
    )


class TutorialGuideDoc(BaseModel):
    """Schema for tutorial/guide documentation."""

    title: str = Field(..., description="Tutorial title")
    description: str = Field(..., description="Tutorial description")
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisites")
    learning_objectives: List[str] = Field(default_factory=list, description="What users will learn")
    estimated_time: Optional[str] = Field(None, description="Estimated completion time")
    difficulty_level: Optional[str] = Field(None, description="Difficulty level")
    steps: List[TutorialStep] = Field(..., description="Tutorial steps")
    summary: Optional[str] = Field(None, description="Tutorial summary")
    next_steps: List[str] = Field(default_factory=list, description="Suggested next steps")
    additional_resources: List[Dict[str, str]] = Field(default_factory=list, description="Additional resources")


class ChangelogEntryDoc(BaseModel):
    """Schema for changelog entry documentation."""

    version: str = Field(..., description="Version number")
    date: str = Field(..., description="Release date")
    summary: Optional[str] = Field(None, description="Version summary")
    changes: List[ChangelogItem] = Field(..., description="List of changes")
    breaking_changes: List[str] = Field(default_factory=list, description="Breaking changes summary")
    migration_notes: Optional[str] = Field(None, description="Migration notes")
    contributors: List[str] = Field(default_factory=list, description="Contributors")


class MigrationGuideDoc(BaseModel):
    """Schema for migration guide documentation."""

    title: str = Field(..., description="Migration guide title")
    from_version: str = Field(..., description="Version migrating from")
    to_version: str = Field(..., description="Version migrating to")
    summary: str = Field(..., description="Migration summary")
    breaking_changes: List[Dict[str, Any]] = Field(..., description="Breaking changes")
    migration_steps: List[TutorialStep] = Field(..., description="Step-by-step migration")
    code_changes: List[Dict[str, Any]] = Field(default_factory=list, description="Required code changes")
    configuration_changes: List[Dict[str, Any]] = Field(default_factory=list, description="Configuration changes")
    database_migrations: List[Dict[str, Any]] = Field(default_factory=list, description="Database migrations")
    rollback_procedure: Optional[str] = Field(None, description="Rollback procedure")
    testing_checklist: List[str] = Field(default_factory=list, description="Testing checklist")


class DocumentationOutput(BaseModel):
    """Unified documentation output schema."""

    doc_type: DocType = Field(..., description="Type of documentation")
    content: Dict[str, Any] = Field(..., description="Structured documentation content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors if any")
    warnings: List[str] = Field(default_factory=list, description="Warnings about the documentation")

    def get_typed_content(self) -> BaseModel:
        """Get the content as the appropriate typed model."""
        schema_map = {
            DocType.API_REFERENCE: APIReferenceDoc,
            DocType.CONFIG_REFERENCE: ConfigReferenceDoc,
            DocType.TUTORIAL_GUIDE: TutorialGuideDoc,
            DocType.CHANGELOG_ENTRY: ChangelogEntryDoc,
            DocType.MIGRATION_GUIDE: MigrationGuideDoc,
        }

        schema_class = schema_map.get(self.doc_type)
        if schema_class:
            return schema_class(**self.content)
        return self.content
