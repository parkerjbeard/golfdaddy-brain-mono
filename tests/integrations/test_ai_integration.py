import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json
from typing import Dict, Any

from app.integrations.ai_integration import AIIntegration
from app.config.settings import settings

@pytest.fixture
def mock_openai_response():
    """Fixture for mock OpenAI API response."""
    return MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "complexity_score": 7,
                        "estimated_hours": 4.5,
                        "risk_level": "medium",
                        "key_changes": ["Added new feature", "Updated dependencies"],
                        "technical_debt": ["Missing tests", "Complex logic"],
                        "suggestions": ["Add unit tests", "Consider refactoring"]
                    })
                )
            )
        ]
    )

@pytest.fixture
def mock_doc_response():
    """Fixture for mock documentation response."""
    return MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "content": "# Test Documentation",
                        "format": "markdown",
                        "sections": [
                            {
                                "title": "Overview",
                                "content": "Test content"
                            }
                        ],
                        "metadata": {
                            "generated_at": datetime.now().isoformat(),
                            "doc_type": "test",
                            "format": "markdown"
                        }
                    })
                )
            )
        ]
    )

@pytest.fixture
def sample_commit_data():
    """Fixture for sample commit data."""
    return {
        "commit_hash": "abc123",
        "repository": "test/repo",
        "message": "Test commit message",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "files_changed": ["file1.py", "file2.py"],
        "additions": 100,
        "deletions": 50,
        "diff": "diff --git a/file1.py b/file1.py\nindex 1234567..abcdef0 100644\n--- a/file1.py\n+++ b/file1.py\n@@ -1,5 +1,5 @@\n Line 1\n-Line 2\n+Updated Line 2\n Line 3"
    }

@pytest.fixture
def sample_doc_context():
    """Fixture for sample documentation context."""
    return {
        "text": "Test documentation context",
        "doc_type": "test",
        "format": "markdown",
        "file_references": ["file1.py", "file2.py"],
        "commit_data": {
            "repository": "test/repo",
            "author_name": "Test Author",
            "message": "Test commit message",
            "files_changed": ["file1.py", "file2.py"]
        }
    }

class TestAIIntegration:
    """Test suite for AIIntegration class."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        # Mock settings
        settings.openai_api_key = "test-api-key"
        settings.openai_model = "test-model"
        
        # Create instance
        self.ai = AIIntegration()
    
    def test_init_without_api_key(self):
        """Test initialization without API key."""
        with patch('app.config.settings.settings.openai_api_key', None):
            with pytest.raises(ValueError, match="OpenAI API key not configured in settings"):
                AIIntegration()
    
    def test_analyze_commit_diff(self, mock_openai_response, sample_commit_data):
        """Test commit diff analysis."""
        with patch.object(self.ai.client.chat.completions, 'create', return_value=mock_openai_response):
            result = self.ai.analyze_commit_diff(sample_commit_data)
            
            # Verify API call
            self.ai.client.chat.completions.create.assert_called_once()
            
            # Verify response structure
            assert isinstance(result, dict)
            assert "complexity_score" in result
            assert "estimated_hours" in result
            assert "risk_level" in result
            assert "key_changes" in result
            assert "technical_debt" in result
            assert "suggestions" in result
            assert "analyzed_at" in result
            assert "commit_hash" in result
            assert "repository" in result
            
            # Verify values
            assert result["complexity_score"] == 7
            assert result["estimated_hours"] == 4.5
            assert result["risk_level"] == "medium"
            assert len(result["key_changes"]) == 2
            assert len(result["technical_debt"]) == 2
            assert len(result["suggestions"]) == 2
    
    def test_analyze_commit_diff_error(self, sample_commit_data):
        """Test error handling in commit diff analysis."""
        with patch.object(self.ai.client.chat.completions, 'create', side_effect=Exception("API Error")):
            result = self.ai.analyze_commit_diff(sample_commit_data)
            
            assert isinstance(result, dict)
            assert result["error"] is True
            assert "message" in result
            assert "timestamp" in result
    
    def test_generate_doc(self, mock_doc_response, sample_doc_context):
        """Test documentation generation."""
        with patch.object(self.ai.client.chat.completions, 'create', return_value=mock_doc_response):
            result = self.ai.generate_doc(sample_doc_context)
            
            # Verify API call
            self.ai.client.chat.completions.create.assert_called_once()
            
            # Verify response structure
            assert isinstance(result, dict)
            assert "content" in result
            assert "format" in result
            assert "sections" in result
            assert "metadata" in result
            assert "generated_at" in result
            
            # Verify values
            assert result["format"] == "markdown"
            assert len(result["sections"]) == 1
            assert result["sections"][0]["title"] == "Overview"
    
    def test_generate_doc_error(self, sample_doc_context):
        """Test error handling in documentation generation."""
        with patch.object(self.ai.client.chat.completions, 'create', side_effect=Exception("API Error")):
            result = self.ai.generate_doc(sample_doc_context)
            
            assert isinstance(result, dict)
            assert result["error"] is True
            assert "message" in result
            assert "timestamp" in result
    
    def test_generate_doc_without_commit_data(self, mock_doc_response):
        """Test documentation generation without commit data."""
        context = {
            "text": "Test documentation context",
            "doc_type": "test",
            "format": "markdown"
        }
        
        with patch.object(self.ai.client.chat.completions, 'create', return_value=mock_doc_response):
            result = self.ai.generate_doc(context)
            
            assert isinstance(result, dict)
            assert "content" in result
            assert "format" in result
            assert "sections" in result
            assert "metadata" in result
    
    def test_error_handling(self):
        """Test error handling method."""
        error = Exception("Test error")
        result = self.ai.error_handling(error)
        
        assert isinstance(result, dict)
        assert result["error"] is True
        assert result["message"] == "Test error"
        assert "timestamp" in result 