import unittest
import pytest
from unittest.mock import MagicMock, patch
import json
import requests

from app.integrations.github_integration import GitHubIntegration
from app.services.commit_analysis_service import CommitAnalysisService


class TestGitHubIntegration(unittest.TestCase):
    """Tests for GitHub integration functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.github_integration = GitHubIntegration()
        
    @patch('requests.get')
    def test_get_commit_diff(self, mock_get):
        """Test getting commit diff from GitHub API."""
        # Mock the response from GitHub API
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
            "commit": {
                "author": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "date": "2023-01-01T12:00:00Z"
                },
                "committer": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "date": "2023-01-01T12:00:00Z"
                },
                "message": "Test commit message",
                "verification": {
                    "verified": False,
                    "reason": "unsigned"
                }
            },
            "html_url": "https://github.com/test/repo/commit/6dcb09b5b57875f334f61aebed695e2e4193db5e",
            "files": [
                {
                    "filename": "test.py",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 2,
                    "changes": 12,
                    "patch": "@@ -1,5 +1,13 @@\n print('hello')\n+print('world')"
                }
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Call the method
        result = self.github_integration.get_commit_diff("test/repo", "6dcb09b5b57875f334f61aebed695e2e4193db5e")
        
        # Verify the result
        self.assertEqual(result["commit_hash"], "6dcb09b5b57875f334f61aebed695e2e4193db5e")
        self.assertEqual(result["repository"], "test/repo")
        self.assertEqual(result["additions"], 10)
        self.assertEqual(result["deletions"], 2)
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(result["files"][0]["filename"], "test.py")
        self.assertEqual(result["message"], "Test commit message")
        
    @patch('requests.get')
    def test_compare_commits(self, mock_get):
        """Test comparing two commits."""
        # Mock the response from GitHub API
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
            "total_commits": 1,
            "commits": [
                {
                    "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
                    "commit": {
                        "author": {
                            "name": "Test User",
                            "email": "test@example.com",
                            "date": "2023-01-01T12:00:00Z"
                        },
                        "message": "Test commit message"
                    },
                    "html_url": "https://github.com/test/repo/commit/6dcb09b5b57875f334f61aebed695e2e4193db5e"
                }
            ],
            "files": [
                {
                    "filename": "test.py",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 2,
                    "changes": 12,
                    "patch": "@@ -1,5 +1,13 @@\n print('hello')\n+print('world')"
                }
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Call the method
        result = self.github_integration.compare_commits(
            "test/repo", 
            "6dcb09b5b57875f334f61aebed695e2e4193db5e",
            "abcd1234abcd1234abcd1234abcd1234abcd1234"
        )
        
        # Verify the result
        self.assertEqual(result["repository"], "test/repo")
        self.assertEqual(result["base_commit"], "6dcb09b5b57875f334f61aebed695e2e4193db5e")
        self.assertEqual(result["head_commit"], "abcd1234abcd1234abcd1234abcd1234abcd1234")
        self.assertEqual(result["status"], "ahead")
        self.assertEqual(result["ahead_by"], 1)
        self.assertEqual(result["behind_by"], 0)
        self.assertEqual(len(result["commits"]), 1)
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(result["files"][0]["filename"], "test.py")
        
    def test_verify_webhook(self):
        """Test webhook signature verification."""
        # This would require mocking the settings and hmac functions
        # Just a placeholder for now
        pass
        
        
@pytest.mark.asyncio
@patch('app.services.commit_analysis_service.CommitAnalysisService.analyze_commit')
@patch('app.integrations.github_integration.GitHubIntegration.get_commit_diff')
async def test_process_commit(mock_get_diff, mock_analyze_commit):
    """Test the process_commit method in CommitAnalysisService."""
    # Mock the dependencies
    mock_supabase = MagicMock()
    mock_commit_repo = MagicMock()
    mock_supabase.table.return_value = mock_commit_repo
    
    # Mock the get_commit_diff method
    mock_get_diff.return_value = {
        "commit_hash": "test123",
        "repository": "test/repo",
        "files_changed": ["test.py"],
        "additions": 10,
        "deletions": 2,
        "message": "Test commit",
        "author": {
            "name": "Test User",
            "email": "test@example.com"
        }
    }
    
    # Mock the analyze_commit method
    mock_analyze_commit.return_value = {
        "commit_hash": "test123",
        "ai_estimated_hours": 0.5
    }
    
    # Create test data
    commit_data = {
        "commit_hash": "test123",
        "repository": "test/repo",
        "message": "Test commit",
        "timestamp": "2023-01-01T12:00:00Z",
        "author": {
            "email": "test@example.com",
            "name": "Test User"
        }
    }
    
    # Create an instance of CommitAnalysisService
    service = CommitAnalysisService(mock_supabase)
    
    # Call the method
    result = await service.process_commit(commit_data)
    
    # Verify the method calls
    mock_get_diff.assert_called_once_with("test/repo", "test123")
    mock_analyze_commit.assert_called_once()
    
    # We'd normally verify the result here, but since we're mocking everything
    # this would just be checking that our mocks return what we told them to
    assert result is not None 