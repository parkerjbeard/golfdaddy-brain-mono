"""
Unit tests for house style configuration.
"""

import json
import tempfile
from pathlib import Path

import pytest

from app.services.house_style import DocumentationStructure, HouseStyleConfig, HouseStyleValidator, PromptTone


class TestHouseStyleConfig:
    """Test house style configuration."""

    @pytest.fixture
    def default_config(self):
        """Create a default house style configuration."""
        return HouseStyleConfig()

    @pytest.fixture
    def custom_config(self):
        """Create a custom house style configuration."""
        return HouseStyleConfig(
            tone=PromptTone.FRIENDLY,
            voice="passive",
            person="third",
            terminology={"api": "API", "url": "URL"},
            forbidden_phrases=["obviously", "simply", "just"],
            preferred_phrases={"click": "select", "log in": "sign in"},
        )

    def test_default_configuration(self, default_config):
        """Test default house style configuration."""
        assert default_config.tone == PromptTone.PROFESSIONAL
        assert default_config.voice == "active"
        assert default_config.person == "second"
        assert default_config.american_spelling is True
        assert default_config.oxford_comma is True
        assert default_config.max_line_length == 100

    def test_custom_configuration(self, custom_config):
        """Test custom house style configuration."""
        assert custom_config.tone == PromptTone.FRIENDLY
        assert custom_config.voice == "passive"
        assert custom_config.person == "third"
        assert custom_config.terminology["api"] == "API"
        assert "obviously" in custom_config.forbidden_phrases

    def test_apply_to_text_terminology(self, default_config):
        """Test applying terminology replacements."""
        text = "The api uses json format with a rest interface."
        result = default_config.apply_to_text(text)

        assert "API" in result
        assert "JSON" in result
        assert "REST" in result
        assert "api" not in result

    def test_apply_to_text_forbidden_phrases(self, default_config):
        """Test removing forbidden phrases."""
        text = "This is obviously simple. Just use the API naturally."
        result = default_config.apply_to_text(text)

        assert "obviously" not in result
        assert "Just" not in result.split()  # Check word boundary
        assert "naturally" not in result

    def test_apply_to_text_preferred_phrases(self, default_config):
        """Test applying preferred phrases."""
        text = "Click the button to log in and fill in the form."
        result = default_config.apply_to_text(text)

        assert "select" in result
        assert "sign in" in result
        assert "enter" in result
        assert "click" not in result.lower()

    def test_apply_american_spelling(self, default_config):
        """Test converting British to American spelling."""
        text = "The colour of the centre dialogue in the programme."
        result = default_config.apply_to_text(text)

        assert "color" in result
        assert "center" in result
        assert "dialog" in result
        assert "program" in result
        assert "colour" not in result

    def test_apply_oxford_comma(self, default_config):
        """Test applying Oxford comma."""
        text = "We support Python, JavaScript and TypeScript."
        result = default_config.apply_to_text(text)

        assert "Python, JavaScript, and TypeScript" in result

    def test_to_dict(self, custom_config):
        """Test converting configuration to dictionary."""
        config_dict = custom_config.to_dict()

        assert config_dict["tone"] == "friendly"
        assert config_dict["voice"] == "passive"
        assert config_dict["person"] == "third"
        assert "terminology" in config_dict
        assert "forbidden_phrases" in config_dict
        assert "structure" in config_dict

    def test_save_and_load_json(self, custom_config):
        """Test saving and loading configuration from JSON."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Save configuration
            custom_config.save_to_file(temp_path)

            # Load configuration
            loaded_config = HouseStyleConfig.from_file(temp_path)

            assert loaded_config.tone == custom_config.tone
            assert loaded_config.voice == custom_config.voice
            assert loaded_config.terminology == custom_config.terminology

        finally:
            temp_path.unlink()

    def test_save_and_load_yaml(self, custom_config):
        """Test saving and loading configuration from YAML."""
        pytest.importorskip("yaml")  # Skip if yaml not installed

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Save configuration
            custom_config.save_to_file(temp_path)

            # Load configuration
            loaded_config = HouseStyleConfig.from_file(temp_path)

            assert loaded_config.tone == custom_config.tone
            assert loaded_config.voice == custom_config.voice

        finally:
            temp_path.unlink()

    def test_validate_structure_api(self, default_config):
        """Test validating API documentation structure."""
        # Correct structure
        content = {"title": "API", "description": "API docs", "authentication": "Bearer token", "endpoints": []}

        messages = default_config.validate_structure(content, "api")

        # Should have some messages about missing expected sections
        assert any("Missing" in msg for msg in messages)

    def test_validate_structure_unexpected_sections(self, default_config):
        """Test detecting unexpected sections."""
        content = {
            "title": "API",
            "unexpected_section": "This should not be here",
            "another_unexpected": "Neither should this",
        }

        messages = default_config.validate_structure(content, "api")

        assert any("Unexpected section: unexpected_section" in msg for msg in messages)
        assert any("Unexpected section: another_unexpected" in msg for msg in messages)

    def test_validate_structure_order(self, default_config):
        """Test validating section order."""
        # Wrong order
        content = {"endpoints": [], "description": "API docs", "title": "API"}

        messages = default_config.validate_structure(content, "api")

        assert any("not in preferred order" in msg for msg in messages)

    def test_documentation_structure_defaults(self):
        """Test default documentation structure."""
        structure = DocumentationStructure()

        assert "title" in structure.api_structure
        assert "endpoints" in structure.api_structure
        assert "prerequisites" in structure.tutorial_structure
        assert "added" in structure.changelog_structure


class TestHouseStyleValidator:
    """Test house style validator."""

    @pytest.fixture
    def validator(self):
        """Create a house style validator."""
        config = HouseStyleConfig()
        return HouseStyleValidator(config)

    def test_validate_forbidden_phrases(self, validator):
        """Test detecting forbidden phrases."""
        content = "This is obviously very simple to understand."
        issues = validator.validate(content)

        assert len(issues) > 0
        assert any("forbidden phrase: 'obviously'" in issue for issue in issues)
        assert any("forbidden phrase: 'simply'" in issue for issue in issues)

    def test_validate_line_length(self, validator):
        """Test detecting lines exceeding maximum length."""
        long_line = "x" * 101  # Exceeds default max of 100
        content = f"Short line\n{long_line}\nAnother short line"

        issues = validator.validate(content)

        assert len(issues) > 0
        assert any("Line 2 exceeds maximum length" in issue for issue in issues)

    def test_validate_preferred_phrases(self, validator):
        """Test detecting non-preferred phrases."""
        content = "Click the button to log in to the system."
        issues = validator.validate(content)

        assert any("non-preferred phrase: 'click'" in issue for issue in issues)
        assert any("use 'select' instead" in issue for issue in issues)
        assert any("non-preferred phrase: 'log in'" in issue for issue in issues)
        assert any("use 'sign in' instead" in issue for issue in issues)

    def test_validate_british_spelling(self, validator):
        """Test detecting British spelling."""
        content = "The colour of the centre is important."
        issues = validator.validate(content)

        assert any("British spelling: 'colour'" in issue for issue in issues)
        assert any("British spelling: 'centre'" in issue for issue in issues)

    def test_validate_clean_content(self, validator):
        """Test validating clean content with no issues."""
        content = "This is clean content.\nIt follows all the rules.\nNo issues here."
        issues = validator.validate(content)

        assert len(issues) == 0

    def test_custom_config_validation(self):
        """Test validation with custom configuration."""
        config = HouseStyleConfig(
            forbidden_phrases=["bad_word", "another_bad"],
            max_line_length=50,
            american_spelling=False,  # Don't check spelling
        )
        validator = HouseStyleValidator(config)

        content = "This line contains a bad_word and is also quite long indeed."
        issues = validator.validate(content)

        assert any("forbidden phrase: 'bad_word'" in issue for issue in issues)
        assert any("exceeds maximum length" in issue for issue in issues)
        # Should not check for British spelling
        assert not any("British spelling" in issue for issue in issues)
