#!/usr/bin/env python3
"""
Analyze the latest commit directly using GitHub PAT (non-interactive)
"""

import os
import sys
import asyncio
from pathlib import Path

# Add backend directory to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.config.database import get_db
from app.services.commit_analysis_service import CommitAnalysisService
from app.integrations.github_integration import GitHubIntegration
from dotenv import load_dotenv

# Load environment variables
env_path = backend_path / ".env"
if env_path.exists():
    load_dotenv(env_path)

async def analyze_latest():
    """Analyze the most recent commit."""
    
    print("🚀 Analyzing latest commit from GolfDaddy...")
    
    # Initialize services
    db = get_db()
    github_integration = GitHubIntegration()
    commit_service = CommitAnalysisService(db)
    
    # Get latest commit
    repository = "parkerjbeard/golfdaddy-brain-mono"
    
    # Fetch commit details from GitHub
    import requests
    headers = {
        "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(
        f"https://api.github.com/repos/{repository}/commits?per_page=1",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch commits: {response.status_code}")
        return
    
    commits = response.json()
    if not commits:
        print("❌ No commits found")
        return
    
    latest_commit = commits[0]
    commit_sha = latest_commit['sha']
    
    print(f"\n📝 Analyzing commit: {commit_sha[:8]}")
    print(f"   Message: {latest_commit['commit']['message'].split('\\n')[0]}")
    print(f"   Author: {latest_commit['commit']['author']['name']}")
    
    # Prepare commit data
    commit_data = {
        "repository": repository,
        "commit_hash": commit_sha,
        "author": {
            "name": latest_commit['commit']['author']['name'],
            "email": latest_commit['commit']['author']['email'],
            "login": latest_commit['author']['login'] if latest_commit.get('author') else None
        },
        "message": latest_commit['commit']['message'],
        "timestamp": latest_commit['commit']['author']['date'],
        "url": latest_commit['html_url']
    }
    
    # Analyze the commit
    print("\n🔍 Running AI analysis...")
    analyzed_commit = await commit_service.analyze_commit(
        commit_hash=commit_sha,
        commit_data=commit_data,
        fetch_diff=True
    )
    
    if analyzed_commit:
        print("\n✅ Analysis Complete!")
        print(f"   Complexity Score: {analyzed_commit.complexity_score}/10")
        print(f"   AI Estimated Hours: {analyzed_commit.ai_estimated_hours:.1f}")
        print(f"   Points Earned: {analyzed_commit.points_earned}")
        print(f"\n📊 Summary: {analyzed_commit.commit_summary}")
        print(f"\n💡 AI Analysis:\n{analyzed_commit.ai_analysis}")
    else:
        print("❌ Analysis failed")

if __name__ == "__main__":
    asyncio.run(analyze_latest())