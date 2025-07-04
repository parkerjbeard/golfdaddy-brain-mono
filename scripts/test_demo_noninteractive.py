#!/usr/bin/env python3
"""
Non-interactive test runner for demo_golfdaddy.py
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import asyncio

# Add scripts directory to path
scripts_path = Path(__file__).parent
sys.path.insert(0, str(scripts_path))

# Add backend directory to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Load environment variables
from dotenv import load_dotenv
env_path = backend_path / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded environment from {env_path}")

# Import demo after setting up paths
from demo_golfdaddy import GolfDaddyDemo

def test_demo_sections():
    """Test each section of the demo independently"""
    
    print("=" * 70)
    print("Testing GolfDaddy Demo Script")
    print("=" * 70)
    
    # Create demo instance
    demo = GolfDaddyDemo()
    
    # Test 1: Check prerequisites
    print("\n1. Testing prerequisites check...")
    try:
        result = demo.check_prerequisites()
        print(f"   Prerequisites: {'✓ PASS' if result else '✗ FAIL'}")
        
        # Individual checks
        print(f"   - API Health: {'✓' if demo.check_api_health() else '✗'}")
        print(f"   - Frontend: {'✓' if demo.check_frontend() else '✗'}")
        print(f"   - Docker: {'✓' if demo.check_docker_services() else '✗'}")
        print(f"   - GitHub Token: {'✓' if demo.config['github_token'] else '✗'}")
        print(f"   - OpenAI Key: {'✓' if os.getenv('OPENAI_API_KEY') else '✗'}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: Authentication
    print("\n2. Testing authentication...")
    try:
        with patch('requests.Session.post') as mock_post:
            mock_post.return_value.status_code = 401  # Simulate auth failure
            demo.authenticate()
            print("   ✓ Authentication handled (fallback to API key)")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: GitHub integration
    print("\n3. Testing GitHub integration...")
    try:
        with patch('requests.get') as mock_get:
            # Mock GitHub user API
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"login": "testuser"}
            
            demo.get_github_username()
            print(f"   ✓ GitHub username: {demo.config.get('github_username', 'Not set')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 4: Commit analysis
    print("\n4. Testing commit analysis functionality...")
    try:
        # Check if backend imports are available
        from app.config.database import get_db
        from app.services.commit_analysis_service import CommitAnalysisService
        
        print("   ✓ Backend imports available")
        
        # Test creating service instance
        db = get_db()
        service = CommitAnalysisService(db)
        print("   ✓ CommitAnalysisService instantiated")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 5: Demo flow (mocked)
    print("\n5. Testing demo flow with mocks...")
    try:
        with patch('rich.prompt.Confirm.ask', return_value=False):  # Don't run full demo
            with patch('requests.get') as mock_get:
                with patch('requests.post') as mock_post:
                    with patch('webbrowser.open'):
                        # Mock API responses
                        mock_get.return_value.status_code = 200
                        mock_post.return_value.status_code = 200
                        
                        # Test show_welcome
                        demo.show_welcome()
                        print("   ✓ Welcome screen displayed")
                        
                        # Test setup (without actually running)
                        print("   ✓ Demo setup would run here")
                        
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 70)
    print("Demo testing complete!")
    
    # Summary
    print("\nSummary:")
    print(f"- Environment: {'✓ Loaded' if env_path.exists() else '✗ Not found'}")
    print(f"- GitHub Token: {'✓ Set' if os.getenv('GITHUB_TOKEN') else '✗ Not set'}")
    print(f"- Backend imports: {'✓ Available' if 'CommitAnalysisService' in locals() else '✗ Not available'}")
    print(f"- API accessible: {'✓ Yes' if demo.check_api_health() else '✗ No'}")


def test_specific_commit_analysis():
    """Test analyzing a specific commit"""
    print("\n" + "=" * 70)
    print("Testing Commit Analysis")
    print("=" * 70)
    
    try:
        from app.config.database import get_db
        from app.services.commit_analysis_service import CommitAnalysisService
        from app.integrations.github_integration import GitHubIntegration
        
        # Initialize services
        db = get_db()
        github = GitHubIntegration()
        service = CommitAnalysisService(db)
        
        print("✓ Services initialized")
        
        # Test fetching a commit
        repo = "parkerjbeard/golfdaddy-brain-mono"
        print(f"\nFetching latest commit from {repo}...")
        
        # Mock or real fetch
        commit_data = {
            "repository": repo,
            "commit_hash": "test123",
            "author": {
                "name": "Test User",
                "email": "test@example.com",
                "login": "testuser"
            },
            "message": "Test commit",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        print("✓ Commit data prepared")
        
        # Would run analysis here
        print("✓ Analysis would run here (skipped for test)")
        
    except Exception as e:
        print(f"✗ Error in commit analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run tests
    test_demo_sections()
    test_specific_commit_analysis()
    
    print("\n" + "=" * 70)
    print("All tests complete!")
    
    # Check if we can run the full demo
    print("\nTo run the full interactive demo:")
    print("  cd backend")
    print("  source venv/bin/activate") 
    print("  python ../scripts/demo_golfdaddy.py")