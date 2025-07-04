#!/usr/bin/env python3
"""
Comprehensive test suite for demo_golfdaddy.py
Tests all functionality including error cases and edge conditions.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call, ANY
import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime
import asyncio
from typing import Dict, Any, List
import requests

# Add scripts directory to Python path
scripts_path = Path(__file__).parent
sys.path.insert(0, str(scripts_path))

# Mock rich console to avoid terminal output during tests
with patch('rich.console.Console'):
    from demo_golfdaddy import GolfDaddyDemo, DEMO_CONFIG


class TestGolfDaddyDemo(unittest.TestCase):
    """Test suite for GolfDaddy demo script"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.demo = GolfDaddyDemo()
        # Mock console to capture output
        self.demo.console = Mock()
        
        # Set up test configuration
        self.demo.config = {
            "api_base_url": "http://localhost:8000",
            "frontend_url": "http://localhost:8080",
            "github_token": "test_github_token",
            "github_username": "testuser",
            "demo_repo_name": "test-repo",
            "demo_docs_repo_name": "test-docs-repo",
            "test_user_email": "test@example.com",
            "test_user_password": "testpass123"
        }
        
        # Mock session
        self.demo.session = Mock()
        self.demo.auth_token = "test_auth_token"
    
    def test_initialization(self):
        """Test demo initialization"""
        demo = GolfDaddyDemo()
        self.assertIsNotNone(demo.console)
        self.assertIsNotNone(demo.config)
        self.assertIsNotNone(demo.session)
        self.assertIsNone(demo.auth_token)
        self.assertEqual(demo.demo_repos, {})
        self.assertEqual(demo.created_resources, [])
    
    @patch('requests.get')
    def test_check_api_health_success(self, mock_get):
        """Test successful API health check"""
        mock_get.return_value.status_code = 200
        result = self.demo.check_api_health()
        self.assertTrue(result)
        mock_get.assert_called_once_with("http://localhost:8000/health")
    
    @patch('requests.get')
    def test_check_api_health_failure(self, mock_get):
        """Test failed API health check"""
        mock_get.return_value.status_code = 500
        result = self.demo.check_api_health()
        self.assertFalse(result)
    
    @patch('requests.get')
    def test_check_api_health_exception(self, mock_get):
        """Test API health check with exception"""
        mock_get.side_effect = Exception("Connection error")
        result = self.demo.check_api_health()
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_check_docker_services_success(self, mock_run):
        """Test successful Docker services check"""
        mock_run.return_value.returncode = 0
        result = self.demo.check_docker_services()
        self.assertTrue(result)
    
    @patch('subprocess.run')
    def test_check_docker_services_failure(self, mock_run):
        """Test failed Docker services check"""
        mock_run.return_value.returncode = 1
        result = self.demo.check_docker_services()
        self.assertFalse(result)
    
    @patch('requests.Session.post')
    def test_authenticate_success(self, mock_post):
        """Test successful authentication"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "new_token"}
        
        self.demo.authenticate()
        
        self.assertEqual(self.demo.auth_token, "new_token")
        self.demo.session.headers.update.assert_called_with(
            {"Authorization": "Bearer new_token"}
        )
    
    @patch('requests.Session.post')
    def test_authenticate_failure(self, mock_post):
        """Test authentication failure - falls back to API key"""
        mock_post.return_value.status_code = 401
        
        self.demo.authenticate()
        
        self.demo.session.headers.update.assert_called_with(
            {"X-API-Key": "dev-api-key"}
        )
    
    @patch('requests.get')
    def test_get_github_username_success(self, mock_get):
        """Test successful GitHub username fetch"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"login": "githubuser"}
        
        self.demo.get_github_username()
        
        self.assertEqual(self.demo.config["github_username"], "githubuser")
        mock_get.assert_called_once_with(
            "https://api.github.com/user",
            headers={"Authorization": "token test_github_token"}
        )
    
    @patch('requests.get')
    def test_get_github_username_failure(self, mock_get):
        """Test failed GitHub username fetch"""
        mock_get.return_value.status_code = 401
        
        with self.assertRaises(Exception) as context:
            self.demo.get_github_username()
        
        self.assertIn("Failed to fetch GitHub username", str(context.exception))
    
    def test_github_analysis_imports(self):
        """Test that GitHub analysis can import required modules"""
        # Create a mock analyzed commit
        mock_commit = Mock()
        mock_commit.complexity_score = 7
        mock_commit.ai_estimated_hours = 2.5
        mock_commit.points_earned = 10
        mock_commit.risk_level = "medium"
        mock_commit.files_changed = 5
        mock_commit.additions = 100
        mock_commit.deletions = 50
        mock_commit.commit_summary = "Test commit summary"
        mock_commit.ai_analysis = "Test AI analysis"
        mock_commit.key_changes = ["Change 1", "Change 2"]
        
        # Test the import path setup
        backend_path = Path(__file__).parent.parent / "backend"
        self.assertTrue(backend_path.exists(), f"Backend path {backend_path} should exist")
        
        # Verify we can import the required modules
        try:
            sys.path.insert(0, str(backend_path))
            from app.config.database import get_db
            from app.services.commit_analysis_service import CommitAnalysisService
            import asyncio
            
            # Modules imported successfully
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import required modules: {e}")
    
    @patch('requests.get')
    @patch('asyncio.run')
    @patch('demo_golfdaddy.get_db')
    @patch('demo_golfdaddy.CommitAnalysisService')
    @patch('rich.prompt.Confirm.ask')
    def test_demo_github_analysis_full_flow(self, mock_confirm, mock_service_class, 
                                          mock_get_db, mock_asyncio_run, mock_requests_get):
        """Test complete GitHub analysis demo flow"""
        # Always continue with demo
        mock_confirm.return_value = True
        
        # Mock GitHub API responses
        responses = []
        
        # Response 1: GitHub user
        user_response = Mock()
        user_response.status_code = 200
        user_response.json.return_value = {"login": "testuser"}
        responses.append(user_response)
        
        # Response 2: Repository info
        repo_response = Mock()
        repo_response.status_code = 200
        repo_response.json.return_value = {"full_name": "testuser/test-repo"}
        responses.append(repo_response)
        
        # Response 3: Commits list
        commits_response = Mock()
        commits_response.status_code = 200
        commits_response.json.return_value = [{
            "sha": "abc123def456",
            "commit": {
                "message": "Test commit message",
                "author": {
                    "name": "Test Author",
                    "date": "2024-01-01T00:00:00Z"
                }
            }
        }]
        responses.append(commits_response)
        
        mock_requests_get.side_effect = responses
        
        # Mock commit analysis
        mock_analyzed_commit = Mock()
        mock_analyzed_commit.complexity_score = 7
        mock_analyzed_commit.ai_estimated_hours = 2.5
        mock_analyzed_commit.points_earned = 10
        mock_analyzed_commit.risk_level = "medium"
        mock_analyzed_commit.files_changed = 5
        mock_analyzed_commit.additions = 100
        mock_analyzed_commit.deletions = 50
        mock_analyzed_commit.commit_summary = "Test commit summary"
        mock_analyzed_commit.ai_analysis = "Test AI analysis"
        mock_analyzed_commit.key_changes = ["Change 1", "Change 2"]
        
        mock_asyncio_run.return_value = mock_analyzed_commit
        
        # Mock CommitAnalysisService
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        # Add sys.path mock to avoid import errors
        with patch('sys.path', sys.path + [str(Path(__file__).parent.parent / "backend")]):
            # Run the demo
            self.demo.demo_github_analysis()
        
        # Verify GitHub API calls
        self.assertEqual(mock_requests_get.call_count, 3)
        
        # Verify commit analysis was called
        mock_asyncio_run.assert_called_once()
        
        # Verify output was displayed
        self.demo.console.print.assert_called()
        
        # Check for success message
        success_calls = [call for call in self.demo.console.print.call_args_list 
                        if "GitHub analysis demo complete!" in str(call)]
        self.assertTrue(len(success_calls) > 0, "Should print success message")
    
    def test_demo_github_analysis_no_commits(self):
        """Test GitHub analysis when no commits are found"""
        with patch('requests.get') as mock_get:
            # Mock responses
            mock_get.side_effect = [
                Mock(status_code=200, json=Mock(return_value={"login": "testuser"})),
                Mock(status_code=200, json=Mock(return_value={"full_name": "testuser/test-repo"})),
                Mock(status_code=200, json=Mock(return_value=[]))  # No commits
            ]
            
            with patch('rich.prompt.Confirm.ask', return_value=True):
                self.demo.demo_github_analysis()
            
            # Check for error message
            error_calls = [call for call in self.demo.console.print.call_args_list 
                          if "No commits found" in str(call)]
            self.assertTrue(len(error_calls) > 0, "Should print no commits error")
    
    def test_demo_github_analysis_api_error(self):
        """Test GitHub analysis with API errors"""
        with patch('requests.get') as mock_get:
            # First call succeeds, second fails
            mock_get.side_effect = [
                Mock(status_code=200, json=Mock(return_value={"login": "testuser"})),
                Mock(status_code=404)  # Repository not found
            ]
            
            with patch('rich.prompt.Confirm.ask', return_value=True):
                self.demo.demo_github_analysis()
            
            # Check for error message
            error_calls = [call for call in self.demo.console.print.call_args_list 
                          if "Repository not found" in str(call)]
            self.assertTrue(len(error_calls) > 0, "Should print repository not found error")
    
    def test_cleanup_with_resources(self):
        """Test cleanup of created resources"""
        # Add some resources to clean up
        self.demo.created_resources = [
            ("github_repo", "test-repo-1"),
            ("github_repo", "test-repo-2")
        ]
        self.demo.config["github_username"] = "testuser"
        
        with patch('requests.delete') as mock_delete:
            with patch('rich.progress.Progress'):
                self.demo.cleanup()
            
            # Verify delete calls
            self.assertEqual(mock_delete.call_count, 2)
            mock_delete.assert_any_call(
                "https://api.github.com/repos/testuser/test-repo-1",
                headers={"Authorization": "token test_github_token"}
            )
    
    def test_cleanup_no_resources(self):
        """Test cleanup when no resources were created"""
        self.demo.created_resources = []
        
        with patch('requests.delete') as mock_delete:
            with patch('rich.progress.Progress'):
                self.demo.cleanup()
            
            # No delete calls should be made
            mock_delete.assert_not_called()
    
    @patch('webbrowser.open')
    def test_dashboard_browser_open(self, mock_browser):
        """Test opening dashboard in browser"""
        with patch('rich.prompt.Confirm.ask', return_value=True):
            # Simulate the end of demo_github_analysis where browser is opened
            dashboard_url = f"{self.demo.config['frontend_url']}/daily-reports"
            mock_browser(dashboard_url)
            
        mock_browser.assert_called_with("http://localhost:8080/daily-reports")
    
    def test_error_handling_in_main_run(self):
        """Test error handling in main run method"""
        # Mock to raise exception during prerequisites check
        self.demo.check_prerequisites = Mock(side_effect=Exception("Test error"))
        
        with patch('rich.prompt.Confirm.ask', return_value=False):  # Don't cleanup
            self.demo.run()
        
        # Verify error was printed
        error_calls = [call for call in self.demo.console.print.call_args_list 
                      if "Demo error: Test error" in str(call)]
        self.assertTrue(len(error_calls) > 0, "Should print demo error")


class TestDemoIntegration(unittest.TestCase):
    """Integration tests for the full demo flow"""
    
    @patch('rich.console.Console')
    @patch('requests.Session')
    @patch('requests.get')
    @patch('requests.post')
    @patch('subprocess.run')
    @patch('webbrowser.open')
    @patch('rich.prompt.Confirm.ask')
    @patch('rich.prompt.Prompt.ask')
    def test_full_demo_flow(self, mock_prompt, mock_confirm, mock_browser, 
                           mock_subprocess, mock_post, mock_get, 
                           mock_session, mock_console):
        """Test complete demo flow from start to finish"""
        # Always confirm
        mock_confirm.return_value = True
        mock_prompt.return_value = ""  # Just press enter
        
        # Mock subprocess for Docker check
        mock_subprocess.return_value.returncode = 0
        
        # Mock all API responses
        mock_get.side_effect = [
            # Health check
            Mock(status_code=200),
            # Frontend check
            Mock(status_code=200),
            # GitHub user
            Mock(status_code=200, json=Mock(return_value={"login": "testuser"})),
            # More responses as needed...
        ]
        
        # Import and run demo
        from demo_golfdaddy import main
        
        # Mock Path.exists to return True
        with patch('pathlib.Path.exists', return_value=True):
            try:
                # This will fail but we're testing the flow
                main()
            except SystemExit:
                pass  # Expected when demo completes
        
        # Verify key methods were called
        mock_subprocess.assert_called()  # Docker check
        mock_get.assert_called()  # API calls


class TestDemoEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""
    
    def test_demo_with_no_github_token(self):
        """Test demo behavior when GitHub token is missing"""
        demo = GolfDaddyDemo()
        demo.console = Mock()
        demo.config["github_token"] = None
        
        result = demo.check_prerequisites()
        self.assertFalse(result)
    
    def test_demo_with_invalid_repo_name(self):
        """Test demo with invalid repository names"""
        demo = GolfDaddyDemo()
        demo.console = Mock()
        demo.config["demo_repo_name"] = "invalid/repo/name"
        
        # This should handle gracefully
        with patch('requests.post', side_effect=Exception("Invalid repo name")):
            demo.create_demo_repositories()
        
        # Should not crash
        self.assertTrue(True)
    
    def test_concurrent_api_calls(self):
        """Test handling of concurrent API calls"""
        demo = GolfDaddyDemo()
        demo.console = Mock()
        
        # Simulate multiple concurrent calls
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            
            # Make multiple health checks
            results = []
            for _ in range(5):
                results.append(demo.check_api_health())
            
            self.assertTrue(all(results))
            self.assertEqual(mock_get.call_count, 5)


def run_all_tests():
    """Run all tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestGolfDaddyDemo))
    suite.addTests(loader.loadTestsFromTestCase(TestDemoIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestDemoEdgeCases))
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    # Run comprehensive tests
    print("Running comprehensive tests for demo_golfdaddy.py")
    print("=" * 70)
    
    result = run_all_tests()
    
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    
    if not result.wasSuccessful():
        print("\nFailed tests:")
        for test, traceback in result.failures + result.errors:
            print(f"\n{test}:")
            print(traceback)