#!/usr/bin/env python3
# python backend/scripts/seed_historical_commits.py --repo owner/repo
# --days 30
"""
Seed historical commit data from GitHub repositories.
Analyzes commits from the past month and estimates hours worked per user per day.
"""

import sys
import os
import asyncio
import argparse
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Optional
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Set minimal required environment variables
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_SERVICE_KEY", "dummy_key_for_testing"))
os.environ.setdefault("SUPABASE_URL", os.getenv("SUPABASE_URL", "https://dummy.supabase.co"))

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.integrations.commit_analysis import CommitAnalyzer
from app.config.supabase_client import get_supabase_client_safe
from app.repositories.commit_repository import CommitRepository
from app.models.commit import Commit
from app.repositories.user_repository import UserRepository
from app.models.user import User, UserRole


class HistoricalCommitSeeder:
    """Handles seeding of historical commit data from GitHub."""
    
    def __init__(self, github_token: Optional[str] = None, model: Optional[str] = None):
        self.github_token = github_token
        self.commit_analyzer = CommitAnalyzer()
        if model:
            self.commit_analyzer.commit_analysis_model = model
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = None
        self.user_cache = {}  # Cache to avoid repeated lookups
        # Initialize Supabase client
        self.supabase_client = get_supabase_client_safe()
        
    def _make_github_request(self, url: str, accept_header: str = "application/vnd.github.v3+json") -> requests.Response:
        """Make a GitHub API request with proper headers and rate limit handling."""
        headers = {"Accept": accept_header}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
            
        response = requests.get(url, headers=headers)
        
        # Update rate limit info
        if 'X-RateLimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
            self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))
            
        # Handle rate limiting
        if response.status_code == 403 and self.rate_limit_remaining == 0:
            reset_time = datetime.fromtimestamp(self.rate_limit_reset)
            wait_time = (reset_time - datetime.now()).total_seconds() + 60
            print(f"⏰ Rate limit exceeded. Waiting {wait_time:.0f} seconds until {reset_time}...")
            import time
            time.sleep(wait_time)
            return self._make_github_request(url, accept_header)
            
        return response
    
    def get_branches(self, repository: str) -> List[str]:
        """Get all branches for a repository."""
        owner, repo = repository.split("/")
        branches = []
        page = 1
        
        while True:
            url = f"https://api.github.com/repos/{owner}/{repo}/branches?per_page=100&page={page}"
            response = self._make_github_request(url)
            
            if response.status_code != 200:
                print(f"⚠️  Failed to fetch branches: {response.status_code}")
                break
                
            page_branches = response.json()
            if not page_branches:
                break
                
            branches.extend([branch['name'] for branch in page_branches])
            page += 1
            
        return branches
    
    def get_commits_for_branch(self, repository: str, branch: str, since: datetime, until: datetime) -> List[dict]:
        """Get all commits for a specific branch within the date range."""
        owner, repo = repository.split("/")
        commits = []
        page = 1
        
        # Format dates for GitHub API
        since_str = since.isoformat() + 'Z'
        until_str = until.isoformat() + 'Z'
        
        while True:
            url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            url += f"?sha={branch}&since={since_str}&until={until_str}&per_page=100&page={page}"
            
            response = self._make_github_request(url)
            
            if response.status_code != 200:
                print(f"⚠️  Failed to fetch commits for branch {branch}: {response.status_code}")
                break
                
            page_commits = response.json()
            if not page_commits:
                break
                
            commits.extend(page_commits)
            page += 1
            
            print(f"  📦 Fetched {len(page_commits)} commits from page {page} of branch {branch}")
            
        return commits
    
    async def get_or_create_user(self, github_username: str, author_email: str, author_name: str) -> Optional[User]:
        """Get existing user by GitHub username or create a new one."""
        # Check cache first
        if github_username in self.user_cache:
            return self.user_cache[github_username]
        
        user_repo = UserRepository(self.supabase_client)
        
        # Try to find user by GitHub username first
        user = await user_repo.get_user_by_github_username(github_username)
        
        # If not found, try by email
        if not user:
            user = await user_repo.get_user_by_email(author_email)
        
        # Create new user if not found
        if not user:
            print(f"  👤 Creating new user for GitHub username: {github_username}")
            try:
                user_data = User(
                    email=author_email,
                    name=author_name or github_username,  # Use GitHub username as name if no name provided
                    github_username=github_username,
                    role=UserRole.DEVELOPER,
                    is_active=True,
                    metadata={
                        "source": "historical_commit_seeder",
                        "created_from": "github_commits"
                    }
                )
                user = await user_repo.create_user(user_data)
                print(f"    ✅ Created user: {user.name} ({user.email})")
            except Exception as e:
                print(f"    ❌ Failed to create user: {e}")
                return None
        
        # Cache the user
        self.user_cache[github_username] = user
        return user
    
    def get_commit_diff(self, repository: str, commit_sha: str) -> Optional[str]:
        """Get the diff for a specific commit."""
        owner, repo = repository.split("/")
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}"
        
        response = self._make_github_request(url, accept_header="application/vnd.github.v3.diff")
        
        if response.status_code == 200:
            return response.text
        else:
            print(f"⚠️  Failed to fetch diff for commit {commit_sha}: {response.status_code}")
            return None
    
    def get_commit_details(self, repository: str, commit_sha: str) -> Optional[dict]:
        """Get detailed information about a commit."""
        owner, repo = repository.split("/")
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}"
        
        response = self._make_github_request(url)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️  Failed to fetch details for commit {commit_sha}: {response.status_code}")
            return None
    
    async def analyze_commits_for_day(self, repository: str, author_email: str, date: datetime, commits: List[dict]) -> Dict:
        """Analyze all commits for a specific author on a specific day."""
        total_hours = 0.0
        total_complexity = 0.0
        analyses = []
        github_username = None
        author_name = None
        
        print(f"\n📅 Analyzing {len(commits)} commits for {author_email} on {date.strftime('%Y-%m-%d')}")
        
        for commit in commits:
            sha = commit['sha']
            
            # Get commit details and diff
            details = self.get_commit_details(repository, sha)
            if not details:
                continue
                
            diff = self.get_commit_diff(repository, sha)
            if not diff:
                continue
            
            # Extract GitHub username from author data
            if not github_username and details.get('author'):
                github_username = details['author'].get('login')
            
            # Keep author name for user creation
            if not author_name:
                author_name = commit['commit']['author']['name']
            
            # Extract file information
            files_changed = []
            additions = 0
            deletions = 0
            
            for file in details.get('files', []):
                files_changed.append(file.get('filename'))
                additions += file.get('additions', 0)
                deletions += file.get('deletions', 0)
            
            # Prepare data for analysis
            commit_data = {
                "commit_hash": sha,
                "repository": repository,
                "diff": diff,
                "message": commit['commit']['message'],
                "author_name": commit['commit']['author']['name'],
                "author_email": commit['commit']['author']['email'],
                "files_changed": files_changed,
                "additions": additions,
                "deletions": deletions,
                "timestamp": commit['commit']['author']['date'],
                "commit_url": details.get('html_url', '')
            }
            
            try:
                # Analyze the commit
                print(f"  🔍 Analyzing commit {sha[:8]}: {commit['commit']['message'][:50]}...")
                analysis = await self.commit_analyzer.analyze_commit_diff(commit_data)
                
                if analysis and not analysis.get('error'):
                    # Merge original commit data with analysis results
                    analysis.update({
                        "commit_hash": sha,
                        "message": commit_data["message"],
                        "commit_url": commit_data["commit_url"],
                        "timestamp": commit_data["timestamp"],
                        "additions": commit_data["additions"],
                        "deletions": commit_data["deletions"],
                        "files_changed": commit_data["files_changed"]
                    })
                    analyses.append(analysis)
                    total_hours += float(analysis.get('estimated_hours', 0))
                    total_complexity += float(analysis.get('complexity_score', 0))
                    print(f"    ✅ Estimated hours: {analysis.get('estimated_hours')}")
                else:
                    print(f"    ❌ Analysis failed")
                    
            except Exception as e:
                print(f"    ❌ Error analyzing commit: {e}")
                continue
        
        # Calculate averages
        avg_complexity = total_complexity / len(analyses) if analyses else 0
        
        return {
            "date": date.strftime('%Y-%m-%d'),
            "author_email": author_email,
            "github_username": github_username,
            "author_name": author_name,
            "total_commits": len(commits),
            "analyzed_commits": len(analyses),
            "total_hours": round(total_hours, 1),
            "average_complexity": round(avg_complexity, 1),
            "analyses": analyses
        }
    
    async def seed_repository(self, repository: str, days: int = 30, branches: Optional[List[str]] = None, 
                            dry_run: bool = False, single_branch: bool = False) -> Dict:
        """Seed historical data for a repository."""
        # Calculate date range
        until = datetime.now(timezone.utc)
        since = until - timedelta(days=days)
        
        print(f"\n🚀 Seeding historical data for {repository}")
        print(f"📅 Date range: {since.strftime('%Y-%m-%d')} to {until.strftime('%Y-%m-%d')}")
        
        # Get branches to analyze
        if branches:
            branches_to_analyze = branches
        elif single_branch:
            # Just use the default branch (usually main or master)
            branches_to_analyze = ['main']  # Will fallback to master if main doesn't exist
        else:
            print("🌿 Fetching all branches...")
            branches_to_analyze = self.get_branches(repository)
            print(f"  Found {len(branches_to_analyze)} branches")
        
        # Collect all commits from all branches
        all_commits = []
        seen_shas = set()
        
        for branch in branches_to_analyze:
            print(f"\n🔍 Fetching commits from branch: {branch}")
            commits = self.get_commits_for_branch(repository, branch, since, until)
            
            # Deduplicate commits (same commit can appear in multiple branches)
            for commit in commits:
                sha = commit['sha']
                if sha not in seen_shas:
                    seen_shas.add(sha)
                    all_commits.append(commit)
            
            print(f"  📊 Found {len(commits)} commits ({len(all_commits)} unique total)")
        
        # Group commits by author and date
        commits_by_author_date = defaultdict(lambda: defaultdict(list))
        
        for commit in all_commits:
            author_email = commit['commit']['author']['email']
            commit_date = datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
            date_key = commit_date.date()
            
            commits_by_author_date[author_email][date_key].append(commit)
        
        print(f"\n📊 Found {len(commits_by_author_date)} unique authors")
        print(f"📊 Total unique commits: {len(all_commits)}")
        
        # Analyze commits grouped by author and date
        results = {
            "repository": repository,
            "date_range": {
                "since": since.isoformat(),
                "until": until.isoformat()
            },
            "summary": {
                "total_commits": len(all_commits),
                "unique_authors": len(commits_by_author_date),
                "total_hours": 0.0,
                "daily_summaries": []
            }
        }
        
        # Process each author's commits by date
        for author_email, dates in commits_by_author_date.items():
            print(f"\n👤 Processing commits for {author_email}")
            
            for date, commits in sorted(dates.items()):
                day_datetime = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)
                day_analysis = await self.analyze_commits_for_day(
                    repository, author_email, day_datetime, commits
                )
                
                results["summary"]["daily_summaries"].append(day_analysis)
                results["summary"]["total_hours"] += day_analysis["total_hours"]
                
                # Store in database if not dry run
                if not dry_run and day_analysis["analyzed_commits"] > 0:
                    await self.store_daily_analysis(repository, day_analysis)
        
        # Sort daily summaries by date
        results["summary"]["daily_summaries"].sort(key=lambda x: x["date"])
        results["summary"]["total_hours"] = round(results["summary"]["total_hours"], 1)
        
        return results
    
    async def store_daily_analysis(self, repository: str, day_analysis: Dict):
        """Store the daily analysis results in the database."""
        try:
            # Get or create user first
            github_username = day_analysis.get("github_username")
            author_email = day_analysis["author_email"]
            author_name = day_analysis.get("author_name", github_username)
            
            user = None
            if github_username:
                user = await self.get_or_create_user(github_username, author_email, author_name)
            
            # Create commit repository instance
            commit_repo = CommitRepository(self.supabase_client)
            
            # Store each individual commit analysis
            for analysis in day_analysis["analyses"]:
                # Store analysis metadata in code_quality_analysis JSON field
                analysis_metadata = {
                    "key_changes": analysis.get("key_changes", []),
                    "seniority_rationale": analysis.get("seniority_rationale", ""),
                    "model_used": analysis.get("model_used", "gpt-4o-mini"),
                    "analyzed_at": analysis.get("analyzed_at")
                }
                
                # Parse commit timestamp
                commit_timestamp = datetime.now(timezone.utc)
                if analysis.get("timestamp"):
                    try:
                        commit_timestamp = datetime.fromisoformat(analysis["timestamp"].replace('Z', '+00:00'))
                    except:
                        pass
                
                commit_data = Commit(
                    commit_hash=analysis["commit_hash"],
                    commit_message=analysis.get("message", ""),
                    commit_url=analysis.get("commit_url", ""),
                    repository_name=repository,
                    repository_url=f"https://github.com/{repository}",
                    author_email=author_email,
                    author_github_username=github_username,
                    author_id=user.id if user else None,
                    complexity_score=analysis["complexity_score"],
                    ai_estimated_hours=analysis["estimated_hours"],
                    risk_level=analysis["risk_level"],
                    seniority_score=analysis["seniority_score"],
                    ai_analysis_notes=analysis.get("seniority_rationale", ""),
                    code_quality_analysis=analysis_metadata,
                    lines_added=analysis.get("additions", 0),
                    lines_deleted=analysis.get("deletions", 0),
                    changed_files=analysis.get("files_changed", []),
                    commit_timestamp=commit_timestamp,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                
                await commit_repo.save_commit(commit_data)
            
            print(f"  💾 Stored {len(day_analysis['analyses'])} analyses for {author_email} on {day_analysis['date']}")
            
        except Exception as e:
            print(f"  ❌ Error storing data: {e}")


async def main():
    """Main entry point for the historical seeding script."""
    parser = argparse.ArgumentParser(
        description="Seed historical commit data from GitHub repositories"
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="microsoft/vscode",
        help="Repository to analyze (format: owner/repo)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)"
    )
    parser.add_argument(
        "--branches",
        type=str,
        nargs="+",
        help="Specific branches to analyze (default: all branches)"
    )
    parser.add_argument(
        "--single-branch",
        action="store_true",
        help="Only analyze the main branch (faster for testing)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis without storing results in database"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="OpenAI model to use for analysis (e.g., gpt-4o-mini, o1-mini)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (JSON format)"
    )
    
    args = parser.parse_args()
    
    # Check for required environment variables
    github_token = os.getenv("GITHUB_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not github_token:
        print("⚠️  GITHUB_TOKEN not found. Will try to access public repositories without authentication.")
        print("   For private repos or higher rate limits, set GITHUB_TOKEN environment variable.")
    
    if not openai_key:
        print("❌ Error: OPENAI_API_KEY must be set in your environment or .env file.")
        sys.exit(1)
    
    # Create seeder instance
    seeder = HistoricalCommitSeeder(github_token=github_token, model=args.model)
    
    try:
        # Run the seeding process
        results = await seeder.seed_repository(
            repository=args.repo,
            days=args.days,
            branches=args.branches,
            dry_run=args.dry_run,
            single_branch=args.single_branch
        )
        
        # Print summary
        print("\n" + "="*60)
        print("📊 SEEDING COMPLETE")
        print("="*60)
        print(f"Repository: {results['repository']}")
        print(f"Date Range: {args.days} days")
        print(f"Total Commits Analyzed: {results['summary']['total_commits']}")
        print(f"Unique Authors: {results['summary']['unique_authors']}")
        print(f"Total Estimated Hours: {results['summary']['total_hours']}")
        
        # Print top contributors
        author_hours = defaultdict(float)
        for day_summary in results['summary']['daily_summaries']:
            author_hours[day_summary['author_email']] += day_summary['total_hours']
        
        print("\n🏆 Top Contributors by Estimated Hours:")
        for author, hours in sorted(author_hours.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {author}: {hours:.1f} hours")
        
        # Save results to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n💾 Results saved to {args.output}")
    
    except KeyboardInterrupt:
        print("\n⚠️  Seeding interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())