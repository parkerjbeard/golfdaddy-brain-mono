#!/usr/bin/env python3
"""
Test the historical commit seeding functionality.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
import json

# Add the scripts directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from seed_historical_commits import HistoricalCommitSeeder


async def test_basic_functionality():
    """Test basic functionality of the historical seeder."""
    print("🧪 Testing Historical Commit Seeder")
    print("=" * 60)
    
    # Test with VS Code repository (public, no auth needed)
    github_token = os.getenv("GITHUB_TOKEN")
    seeder = HistoricalCommitSeeder(github_token=github_token)
    
    # Test 1: Get branches
    print("\n📋 Test 1: Fetching branches from microsoft/vscode")
    branches = seeder.get_branches("microsoft/vscode")
    print(f"✅ Found {len(branches)} branches")
    print(f"   Sample branches: {branches[:5]}")
    
    # Test 2: Get commits from main branch for last 2 days
    print("\n📋 Test 2: Fetching commits from main branch (last 2 days)")
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=2)
    
    commits = seeder.get_commits_for_branch("microsoft/vscode", "main", since, until)
    print(f"✅ Found {len(commits)} commits in the last 2 days")
    
    if commits:
        # Test 3: Get commit details
        print("\n📋 Test 3: Fetching details for a sample commit")
        sample_commit = commits[0]
        details = seeder.get_commit_details("microsoft/vscode", sample_commit['sha'])
        
        if details:
            print(f"✅ Commit: {details['sha'][:8]}")
            print(f"   Author: {details['commit']['author']['name']}")
            print(f"   Message: {details['commit']['message'][:80]}...")
            print(f"   Files changed: {len(details.get('files', []))}")
        
        # Test 4: Get commit diff
        print("\n📋 Test 4: Fetching diff for the same commit")
        diff = seeder.get_commit_diff("microsoft/vscode", sample_commit['sha'])
        
        if diff:
            print(f"✅ Got diff ({len(diff)} characters)")
            print(f"   First 200 chars: {diff[:200]}...")


async def test_analysis_integration():
    """Test the integration with commit analysis."""
    print("\n\n🧪 Testing Analysis Integration")
    print("=" * 60)
    
    # Check if OpenAI API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set. Skipping analysis tests.")
        return
    
    github_token = os.getenv("GITHUB_TOKEN")
    seeder = HistoricalCommitSeeder(github_token=github_token)
    
    # Get a recent commit from VS Code
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=1)
    
    commits = seeder.get_commits_for_branch("microsoft/vscode", "main", since, until)
    
    if not commits:
        print("❌ No recent commits found to analyze")
        return
    
    # Analyze commits for a specific author on a specific date
    # Group by author
    by_author = {}
    for commit in commits[:5]:  # Just analyze first 5 commits
        author = commit['commit']['author']['email']
        if author not in by_author:
            by_author[author] = []
        by_author[author].append(commit)
    
    # Analyze commits for the first author
    if by_author:
        author_email = list(by_author.keys())[0]
        author_commits = by_author[author_email]
        
        print(f"\n📋 Analyzing {len(author_commits)} commits for {author_email}")
        
        result = await seeder.analyze_commits_for_day(
            "microsoft/vscode",
            author_email,
            datetime.now(timezone.utc),
            author_commits
        )
        
        print(f"\n✅ Analysis Results:")
        print(f"   Total commits: {result['total_commits']}")
        print(f"   Analyzed commits: {result['analyzed_commits']}")
        print(f"   Total estimated hours: {result['total_hours']}")
        print(f"   Average complexity: {result['average_complexity']}")


async def test_dry_run_seeding():
    """Test a dry run of the full seeding process."""
    print("\n\n🧪 Testing Dry Run Seeding (1 day, main branch only)")
    print("=" * 60)
    
    github_token = os.getenv("GITHUB_TOKEN")
    seeder = HistoricalCommitSeeder(github_token=github_token)
    
    # Run seeding for just 1 day on main branch
    results = await seeder.seed_repository(
        repository="microsoft/vscode",
        days=1,
        branches=["main"],
        dry_run=True
    )
    
    print("\n📊 Dry Run Results:")
    print(f"   Repository: {results['repository']}")
    print(f"   Total commits: {results['summary']['total_commits']}")
    print(f"   Unique authors: {results['summary']['unique_authors']}")
    print(f"   Total estimated hours: {results['summary']['total_hours']}")
    
    # Save test results
    output_file = "test_seeding_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Test results saved to {output_file}")


async def main():
    """Run all tests."""
    try:
        await test_basic_functionality()
        await test_analysis_integration()
        await test_dry_run_seeding()
        
        print("\n\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())