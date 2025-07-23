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
from decimal import Decimal

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
from app.repositories.daily_work_analysis_repository import DailyWorkAnalysisRepository
from app.models.daily_work_analysis import DailyWorkAnalysis, WorkItem


class HistoricalCommitSeeder:
    """Handles seeding of historical commit data from GitHub."""
    
    def __init__(self, github_token: Optional[str] = None, model: Optional[str] = None, analysis_method: str = "both"):
        self.github_token = github_token
        self.commit_analyzer = CommitAnalyzer()
        self.analysis_method = analysis_method  # NEW: Store analysis method
        self.enable_daily_analysis = False  # NEW: Flag for daily analysis mode
        if model:
            self.commit_analyzer.commit_analysis_model = model
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = None
        self.user_cache = {}  # Cache to avoid repeated lookups
        # Initialize Supabase client
        self.supabase_client = get_supabase_client_safe()
        
        # Initialize repositories
        self.daily_work_repo = DailyWorkAnalysisRepository()
    
    def set_daily_analysis_mode(self, enabled: bool):
        """Enable or disable daily analysis mode."""
        self.enable_daily_analysis = enabled
        
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
        if self.enable_daily_analysis:
            return await self.analyze_daily_batch(repository, author_email, date, commits)
        else:
            return await self.analyze_individual_commits(repository, author_email, date, commits)
    
    async def analyze_individual_commits(self, repository: str, author_email: str, date: datetime, commits: List[dict]) -> Dict:
        """Analyze commits individually using the traditional method."""
        total_hours = 0.0
        total_complexity = 0.0
        total_impact_score = 0.0  # NEW: Track impact scores
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
                    total_impact_score += float(analysis.get('impact_score', 0))  # NEW: Add impact score
                    
                    # Enhanced logging for both methods
                    hours = analysis.get('estimated_hours', 0)
                    impact = analysis.get('impact_score', 0)
                    print(f"    ✅ Traditional: {hours}h, Impact: {impact} points")
                    
                    # NEW: Log impact scoring breakdown
                    if analysis.get('impact_business_value'):
                        bv = analysis.get('impact_business_value', 0)
                        tc = analysis.get('impact_technical_complexity', 0)
                        cq = analysis.get('impact_code_quality_points', 0)
                        risk = analysis.get('impact_risk_penalty', 0)
                        print(f"    📊 Impact breakdown: BV={bv}, TC={tc}, CQ={cq}, Risk={risk}")
                else:
                    print(f"    ❌ Analysis failed")
                    
            except Exception as e:
                print(f"    ❌ Error analyzing commit: {e}")
                continue
        
        # Calculate averages
        avg_complexity = total_complexity / len(analyses) if analyses else 0
        avg_impact = total_impact_score / len(analyses) if analyses else 0  # NEW: Average impact
        
        return {
            "date": date.strftime('%Y-%m-%d'),
            "author_email": author_email,
            "github_username": github_username,
            "author_name": author_name,
            "total_commits": len(commits),
            "analyzed_commits": len(analyses),
            "total_hours": round(total_hours, 1),
            "average_complexity": round(avg_complexity, 1),
            "total_impact_score": round(total_impact_score, 1),  # NEW: Total impact
            "average_impact": round(avg_impact, 1),  # NEW: Average impact
            "analyses": analyses
        }
    
    async def analyze_daily_batch(self, repository: str, author_email: str, date: datetime, commits: List[dict]) -> Dict:
        """Analyze commits using daily batch analysis instead of individual analysis."""
        print(f"\n📅 Daily batch analysis for {author_email} on {date.strftime('%Y-%m-%d')}")
        
        # Prepare context for daily analysis
        commit_summaries = []
        github_username = None
        author_name = None
        
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
            
            commit_summaries.append({
                "hash": sha[:8],
                "message": commit['commit']['message'],
                "timestamp": commit['commit']['author']['date'],
                "repository": repository,
                "files_changed": files_changed,
                "additions": additions,
                "deletions": deletions
            })
        
        # Prepare context for AI daily analysis
        context = {
            "analysis_date": date.strftime('%Y-%m-%d'),
            "user_name": author_name or author_email,
            "commits": commit_summaries,
            "total_commits": len(commits),
            "repositories": [repository],
            "total_lines_changed": sum(c.get('additions', 0) + c.get('deletions', 0) for c in commit_summaries),
        }
        
        # Use AI integration for daily analysis
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from app.integrations.ai_integration import AIIntegration
            ai_integration = AIIntegration()
            daily_result = await ai_integration.analyze_daily_work(context)
            
            print(f"    ✅ Daily analysis: {daily_result.get('total_estimated_hours', 0)}h estimated")
            print(f"    📊 Summary: {daily_result.get('work_summary', 'No summary')}")
            
        except Exception as e:
            print(f"    ❌ Daily analysis failed: {e}")
            daily_result = {
                "total_estimated_hours": 0,
                "average_complexity_score": 0,
                "work_summary": "Daily analysis failed",
                "key_achievements": [],
                "recommendations": []
            }
        
        return {
            "date": date.strftime('%Y-%m-%d'),
            "author_email": author_email,
            "github_username": github_username,
            "author_name": author_name,
            "total_commits": len(commits),
            "analyzed_commits": len(commits),
            "total_hours": round(daily_result.get('total_estimated_hours', 0), 1),
            "average_complexity": round(daily_result.get('average_complexity_score', 0), 1),
            "total_impact_score": 0,  # Daily analysis doesn't provide impact scores yet
            "average_impact": 0,
            "analyses": [],  # No individual analyses in daily mode
            "daily_analysis": daily_result,
            "commit_summaries": commit_summaries  # Include commit summaries for storage
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
                "total_impact_score": 0.0,  # NEW: Track total impact score
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
                results["summary"]["total_impact_score"] += day_analysis.get("total_impact_score", 0)  # NEW: Add impact score
                
                # Store in database if not dry run
                if not dry_run and day_analysis["analyzed_commits"] > 0:
                    await self.store_daily_analysis(repository, day_analysis)
        
        # Sort daily summaries by date
        results["summary"]["daily_summaries"].sort(key=lambda x: x["date"])
        results["summary"]["total_hours"] = round(results["summary"]["total_hours"], 1)
        results["summary"]["total_impact_score"] = round(results["summary"]["total_impact_score"], 1)  # NEW: Round impact score
        
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
            
            if not user:
                print(f"  ⚠️  Could not create/find user for {author_email}, skipping storage")
                return
            
            # Parse analysis date
            analysis_date = datetime.strptime(day_analysis["date"], '%Y-%m-%d').date()
            
            if self.enable_daily_analysis:
                # Store as daily batch analysis
                await self._store_daily_batch_analysis(repository, day_analysis, user, analysis_date)
            else:
                # Store individual commit analyses (traditional method)
                await self._store_individual_commit_analyses(repository, day_analysis, user)
                
        except Exception as e:
            print(f"  ❌ Error storing data: {e}")
            import traceback
            traceback.print_exc()
    
    async def _store_daily_batch_analysis(self, repository: str, day_analysis: Dict, user, analysis_date):
        """Store daily batch analysis in the daily_work_analyses table."""
        
        # Get daily analysis data
        daily_result = day_analysis.get("daily_analysis", {})
        author_email = day_analysis["author_email"]
        
        # Prepare work items for each commit
        work_items = []
        total_loc_added = 0
        total_loc_removed = 0
        total_files_changed = 0
        
        # Get commit summaries from daily analysis context
        commit_summaries = day_analysis.get("commit_summaries", [])
        for commit_summary in commit_summaries:
            # Parse timestamp
            timestamp_str = commit_summary.get("timestamp", "")
            try:
                parsed_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')) if timestamp_str else datetime.now(timezone.utc)
            except:
                parsed_timestamp = datetime.now(timezone.utc)
            
            work_item_dict = {
                'item_type': "commit",
                'source': "github",
                'source_id': commit_summary.get("hash", ""),
                'title': commit_summary.get("message", "")[:255],  # Truncate if too long
                'description': commit_summary.get("message", ""),
                'url': f"https://github.com/{repository}/commit/{commit_summary.get('hash', '')}",
                'created_at': parsed_timestamp,
                'completed_at': parsed_timestamp,
                'loc_added': commit_summary.get("additions", 0),
                'loc_removed': commit_summary.get("deletions", 0),
                'files_changed': len(commit_summary.get("files_changed", [])),
                'estimated_hours': 0.0,  # Individual hours not available in daily batch
                'item_metadata': {
                    "repository": repository,
                    "files_changed": commit_summary.get("files_changed", []),
                    "analysis_method": "daily_batch"
                }
            }
            work_items.append(work_item_dict)
            
            # Accumulate totals
            total_loc_added += commit_summary.get("additions", 0)
            total_loc_removed += commit_summary.get("deletions", 0)
            total_files_changed += len(commit_summary.get("files_changed", []))
        
        # Store the daily analysis with work items included
        daily_analysis_dict = {
            'user_id': str(user.id),
            'analysis_date': analysis_date,
            'total_work_items': len(work_items),
            'total_commits': len(work_items),
            'total_tickets': 0,
            'total_prs': 0,
            'total_loc_added': total_loc_added,
            'total_loc_removed': total_loc_removed,
            'total_files_changed': total_files_changed,
            'total_estimated_hours': day_analysis.get("total_hours", 0.0),
            'daily_summary': daily_result.get("work_summary", ""),
            'key_achievements': daily_result.get("key_achievements", []),
            'technical_highlights': daily_result.get("technical_highlights", []),
            'data_sources': ["github"],
            'processing_status': "completed",
            'work_items': work_items  # Include work items in creation
        }
        
        stored_daily_analysis = await self.daily_work_repo.create(daily_analysis_dict)
        
        print(f"  💾 Stored daily batch analysis for {author_email} on {day_analysis['date']}")
        print(f"    📊 {len(work_items)} work items, {total_loc_added}+ / {total_loc_removed}- lines, {day_analysis.get('total_hours', 0)}h estimated")
    
    async def _store_individual_commit_analyses(self, repository: str, day_analysis: Dict, user):
        """Store individual commit analyses in the commits table (traditional method)."""
        
        author_email = day_analysis["author_email"]
        github_username = day_analysis.get("github_username")
        
        # Create commit repository instance
        commit_repo = CommitRepository(self.supabase_client)
        
        # Store each individual commit analysis
        for analysis in day_analysis["analyses"]:
            # ENHANCED: Store comprehensive analysis metadata
            analysis_metadata = {
                # Traditional scoring
                "key_changes": analysis.get("key_changes", []),
                "seniority_rationale": analysis.get("seniority_rationale", ""),
                "model_used": analysis.get("model_used", "gpt-4o-mini"),
                "analyzed_at": analysis.get("analyzed_at"),
                
                # NEW: Structured anchor data
                "total_lines": analysis.get("total_lines"),
                "total_files": analysis.get("total_files"),
                "initial_anchor": analysis.get("initial_anchor"),
                "final_anchor": analysis.get("final_anchor"),
                "base_hours": analysis.get("base_hours"),
                "multipliers_applied": analysis.get("multipliers_applied"),
                
                # NEW: Impact scoring data
                "impact_business_value": analysis.get("impact_business_value"),
                "impact_technical_complexity": analysis.get("impact_technical_complexity"),
                "impact_code_quality_points": analysis.get("impact_code_quality_points"),
                "impact_risk_penalty": analysis.get("impact_risk_penalty"),
                "impact_business_value_reasoning": analysis.get("impact_business_value_reasoning"),
                "impact_technical_complexity_reasoning": analysis.get("impact_technical_complexity_reasoning"),
                "impact_code_quality_reasoning": analysis.get("impact_code_quality_reasoning"),
                "impact_risk_reasoning": analysis.get("impact_risk_reasoning"),
                "impact_classification": analysis.get("impact_classification"),
                "impact_calculation_breakdown": analysis.get("impact_calculation_breakdown"),
                
                # Metadata
                "analysis_version": "2.0",
                "scoring_methods": analysis.get("scoring_methods", ["hours_estimation", "impact_points"])
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
                author_id=user.id,
                complexity_score=int(float(analysis["complexity_score"])),  # Convert to int
                ai_estimated_hours=Decimal(str(analysis["estimated_hours"])),  # Convert to Decimal
                risk_level=analysis["risk_level"],
                seniority_score=int(float(analysis["seniority_score"])),  # Convert to int
                ai_analysis_notes=json.dumps(analysis_metadata),  # Store all metadata as JSON
                code_quality_analysis=analysis_metadata,
                lines_added=analysis.get("additions", 0),
                lines_deleted=analysis.get("deletions", 0),
                changed_files=analysis.get("files_changed", []),
                commit_timestamp=commit_timestamp,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            await commit_repo.save_commit(commit_data)
        
        print(f"  💾 Stored {len(day_analysis['analyses'])} individual commit analyses for {author_email} on {day_analysis['date']}")


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
    
    # Enable daily batch analysis (analyzing commits per day instead of individually)
    seeder.set_daily_analysis_mode(True)
    
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
        print(f"Total Impact Score: {results['summary']['total_impact_score']}")  # NEW: Show impact score
        
        # Print top contributors by both methods
        author_hours = defaultdict(float)
        author_impact = defaultdict(float)  # NEW: Track impact scores
        for day_summary in results['summary']['daily_summaries']:
            author_hours[day_summary['author_email']] += day_summary['total_hours']
            author_impact[day_summary['author_email']] += day_summary.get('total_impact_score', 0)  # NEW: Add impact score
        
        print("\n🏆 Top Contributors by Estimated Hours:")
        for author, hours in sorted(author_hours.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {author}: {hours:.1f} hours")

        print("\n🏆 Top Contributors by Impact Score:")  # NEW: Impact score ranking
        for author, impact in sorted(author_impact.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {author}: {impact:.1f} points")
        
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