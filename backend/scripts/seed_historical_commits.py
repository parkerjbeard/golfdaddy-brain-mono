#!/usr/bin/env python3
# python backend/scripts/seed_historical_commits.py --repo GolfDaddy-game/unity-game
# --days 30
"""
Seed historical commit data from GitHub repositories.

This script analyzes commits from GitHub repositories and estimates hours worked per user per day.
It includes intelligent deduplication to avoid re-analyzing commits that have already been processed.

Key Features:
- Checks for existing commits in the database and reuses their analysis
- Only analyzes new/unprocessed commits
- Tracks statistics on reused vs fresh analyses
- Supports parallel processing for efficiency
- Exports results to JSON for audit trail

Usage:
    # Basic usage - analyzes last 30 days, checks for existing commits
    python backend/scripts/seed_historical_commits.py --repo GolfDaddy-game/unity-game
    
    # Re-analyze everything (skip existing check)
    python backend/scripts/seed_historical_commits.py --repo GolfDaddy-game/unity-game --no-check-existing
    
    # Export results to file
    python backend/scripts/seed_historical_commits.py --repo GolfDaddy-game/unity-game --output results.json
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
import time
from requests.exceptions import SSLError, ConnectionError, Timeout, RequestException

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Set minimal required environment variables
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_SERVICE_KEY", "dummy_key_for_testing"))
os.environ.setdefault("SUPABASE_URL", os.getenv("SUPABASE_URL", "https://dummy.supabase.co"))

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.integrations.commit_analysis import CommitAnalyzer
from app.services.batch_service import OpenAIBatchService
from app.config.supabase_client import get_supabase_client_safe
from app.config.settings import settings
from app.repositories.commit_repository import CommitRepository
from app.models.commit import Commit
from app.repositories.user_repository import UserRepository
from app.models.user import User, UserRole
from app.repositories.daily_work_analysis_repository import DailyWorkAnalysisRepository
from app.models.daily_work_analysis import DailyWorkAnalysis, WorkItem


class HistoricalCommitSeeder:
    """Handles seeding of historical commit data from GitHub."""

    def __init__(
        self,
        github_token: Optional[str] = None,
        model: Optional[str] = None,
        analysis_method: str = "both",
        max_concurrent: int = 5,
        check_existing: bool = True,
        use_openai_batch: bool = False,
    ):
        self.github_token = github_token
        self.commit_analyzer = CommitAnalyzer()
        self.analysis_method = analysis_method  # NEW: Store analysis method
        self.enable_daily_analysis = False  # NEW: Flag for daily analysis mode
        self.max_concurrent = max_concurrent  # NEW: Concurrency limit for API calls
        self.check_existing = check_existing  # NEW: Flag to check for existing commits
        self.use_openai_batch = use_openai_batch  # NEW: Use OpenAI Batch API for cheaper backfill
        if model:
            self.commit_analyzer.commit_analysis_model = model
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = None
        self.user_cache = {}  # Cache to avoid repeated lookups
        # Initialize Supabase client
        self.supabase_client = get_supabase_client_safe()

        # Initialize repositories
        self.daily_work_repo = DailyWorkAnalysisRepository()
        self.commit_repo = CommitRepository(self.supabase_client)

        # Semaphore for controlling concurrent API calls
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Track statistics for existing vs new commits
        self.stats = {
            "total_commits": 0,
            "existing_commits": 0,
            "new_commits": 0,
            "reused_analyses": 0,
            "fresh_analyses": 0,
            "failed_analyses": 0,
        }

    def _is_reasoning_or_gpt5(self, model_name: str) -> bool:
        """Determine if model should use Responses API reasoning features."""
        if not model_name:
            return False
        prefixes = ["gpt-5", "o3-mini-", "o4-mini-", "o3-"]
        return any(model_name.startswith(p) for p in prefixes)

    def _build_traditional_hours_prompt(self, commit_data: Dict) -> str:
        """Construct the traditional hours-only prompt for batch requests."""
        # This mirrors the traditional hours prompt used in CommitAnalyzer for consistency
        prompt = f"""You are a senior software engineer with expertise in code analysis. Analyze the following commit and provide ONLY hours-based estimation.

## Scoring Guidelines

### 1. HOURS-BASED TRADITIONAL SCORING

Estimate engineering effort considering:
- Actual development time (not AI-assisted time)
- Code review and refinement cycles
- Mental effort and architecture decisions

#### Reference Anchors - STRUCTURED SELECTION

**STEP 1: Initial Classification**
Based on total lines (additions + deletions):
- Under 50 lines → Start with Anchor A
- 50-199 lines → Start with Anchor B  
- 200-499 lines → Start with Anchor C
- 500-1499 lines → Start with Anchor D
- 1500+ lines → Consider Anchor D or E (see Step 2)

**STEP 2: Refinement Checks**
Apply these checks IN ORDER:

1. **Major Change Detection** (can upgrade D→E):
   □ Commit message says "new system", "new service", "new framework", or "breaking change"?
   □ Creates 5+ new files in a new top-level directory?
   □ Changes 20+ files across 3+ different top-level directories?
   □ Adds new technology/dependency to the project (new language, database, framework)?
   If 2+ checked → Upgrade to Anchor E

2. **File Count Override** (supersedes Step 1):
   □ Changes 25+ files regardless of content?
   If checked → Set to Anchor E

3. **Simplicity Reduction** (can downgrade by one level):
   □ >70% of changes are tests, docs, or comments?
   □ Commit message contains "refactor", "rename", "move", "cleanup"?
   □ Only changes configs, constants, or data files?
   If any checked → Downgrade one anchor level (but never below A)

**ANCHOR VALUES:**
- A: Minimal (0.5h) - Typos, configs, small fixes
- B: Simple (2.5h) - Single-purpose changes, basic features
- C: Standard (6.0h) - Multi-file features, moderate complexity
- D: Complex (12.0h) - Cross-component changes, significant logic
- E: Major (20.0h) - Architectural changes, new subsystems

#### Universal Multipliers:
• Involves concurrent/parallel code: +40%
• Modifies critical path (commit message indicates): +30%
• Includes comprehensive tests (>50% of changes): +20%
• Performance-critical changes: +20%
• Security-sensitive code: +30%
• Documentation only: -50%
• Formatting/refactoring only: -30%

#### Final Calculation:
1. Select anchor from table (no averaging needed)
2. Multiply by applicable multipliers
3. Round to nearest 0.5 hour

### 2. COMPLEXITY SCORING (1-10)

Count these objective factors:
□ Changes core functionality (+3)
□ Modifies multiple components (+2)
□ Adds new abstractions/patterns (+2)
□ Requires algorithmic thinking (+2)
□ Handles error cases (+1)
Total: Min 1, Max 10

### 3. SENIORITY SCORING (1-10)

Score implementation quality:
□ Comprehensive error handling (+2)
□ Well-structured tests (+2)
□ Follows established patterns (+2)
□ Good abstractions (+2)
□ Forward-thinking design (+2)
Total: Min 1, Max 10

For trivial changes (<20 lines AND complexity ≤ 2 AND no tests):
Set seniority = 10 with rationale "Trivial change"

### 4. RISK LEVEL

Assess deployment risk:
• low: Unlikely to cause issues (tests, docs, isolated changes)
• medium: Some risk (core features, integrations)
• high: Significant risk (critical path, data changes, security)

## Output Format

Provide a JSON response with this exact structure:
{{
  "total_lines": <int>,
  "total_files": <int>,
  "initial_anchor": "<A/B/C/D/E>",
  "major_change_checks": ["<specific checks that were true>"],
  "major_change_count": <int>,
  "file_count_override": <boolean>,
  "simplicity_reduction_checks": ["<specific checks that were true>"],
  "final_anchor": "<A/B/C/D/E>",
  "base_hours": <float>,
  "multipliers_applied": ["<multiplier1>", "<multiplier2>"],
  "complexity_score": <int 1-10>,
  "complexity_cap_applied": "<none|tooling|test|doc>",
  "estimated_hours": <float>,
  "risk_level": "<low|medium|high>",
  "seniority_score": <int 1-10>,
  "seniority_rationale": "<explanation>",
  "key_changes": ["<change1>", "<change2>", ...]
}}

## Commit to Analyze

Repository: {commit_data.get('repository', '')}
Author: {commit_data.get('author_name', '')} <{commit_data.get('author_email', '')}>
Message: {commit_data.get('message', '')}
Files Changed: {', '.join(commit_data.get('files_changed', []))}
Additions: {commit_data.get('additions', 0)}
Deletions: {commit_data.get('deletions', 0)}

Diff:
{commit_data.get('diff', '')}"""
        return prompt

    async def analyze_individual_commits_batch(
        self, repository: str, author_email: str, date: datetime, commits: List[dict]
    ) -> Dict:
        """Analyze commits using OpenAI Batch API for cost efficiency."""
        print(
            f"\n📅 Analyzing {len(commits)} commits for {author_email} on {date.strftime('%Y-%m-%d')} (OpenAI Batch)"
        )
        github_username = None
        author_name = None

        # Check existing analyses
        commit_hashes = [c["sha"] for c in commits]
        existing_commits_data = {}
        existing_hashes = set()
        if self.check_existing:
            print(f"  🔍 Checking for existing analyzed commits...")
            existing_hashes = set(await self.commit_repo.get_existing_commit_hashes(commit_hashes))
            if existing_hashes:
                print(f"  📦 Found {len(existing_hashes)} existing commits, fetching their analysis data...")
                existing_commits_data = await self.commit_repo.get_commits_with_analysis(list(existing_hashes))
                self.stats["existing_commits"] += len(existing_hashes)
                self.stats["reused_analyses"] += len(existing_commits_data)
                print(f"  ♻️  Reusing {len(existing_commits_data)} existing analyses")

        # Build batch requests for new commits
        to_analyze = [c for c in commits if c["sha"] not in existing_commits_data]
        if not to_analyze:
            # No new analyses
            return await self.analyze_individual_commits(repository, author_email, date, commits)

        # Prepare commit_data and request bodies
        sha_to_commitdata: Dict[str, Dict] = {}
        requests_jsonl: List[Dict] = []
        model = self.commit_analyzer.commit_analysis_model
        reasoning = {"effort": settings.openai_reasoning_effort} if self._is_reasoning_or_gpt5(model) else None

        for i, commit in enumerate(to_analyze, 1):
            sha = commit["sha"]
            details = self.get_commit_details(repository, sha)
            if not details:
                continue
            diff = self.get_commit_diff(repository, sha)
            if not diff:
                continue

            if not github_username and details.get("author"):
                github_username = details["author"].get("login")
            if not author_name:
                author_name = commit["commit"]["author"]["name"]

            files_changed = []
            additions = 0
            deletions = 0
            for file in details.get("files", []):
                files_changed.append(file.get("filename"))
                additions += file.get("additions", 0)
                deletions += file.get("deletions", 0)

            commit_data = {
                "commit_hash": sha,
                "repository": repository,
                "diff": diff,
                "message": commit["commit"]["message"],
                "author_name": commit["commit"]["author"]["name"],
                "author_email": commit["commit"]["author"]["email"],
                "files_changed": files_changed,
                "additions": additions,
                "deletions": deletions,
                "timestamp": commit["commit"]["author"]["date"],
                "commit_url": details.get("html_url", ""),
            }
            sha_to_commitdata[sha] = commit_data

            prompt = self._build_traditional_hours_prompt(commit_data)
            input_messages = [
                {"role": "system", "content": "You are a senior software engineer with deep expertise in effort estimation and code quality assessment. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ]
            custom_id = f"hours-{sha}"
            req = OpenAIBatchService.build_responses_request(
                custom_id=custom_id,
                model=model,
                input_messages=input_messages,
                response_format={"type": "json_object"},
                reasoning=reasoning,
            )
            requests_jsonl.append(req)
            self.stats["new_commits"] += 1

        # Enqueue batch and poll until complete
        batch_client = OpenAIBatchService()
        batch = batch_client.enqueue_batch(requests_jsonl, completion_window="24h")
        print(f"  📤 Enqueued batch {batch.get('id', 'unknown')} with {len(requests_jsonl)} requests")
        batch = batch_client.poll_until_complete(batch.get("id"))
        print(f"  📥 Batch completed with status: {batch.get('status') or batch.get('state')}")
        results = batch_client.download_results(batch)

        # Parse results and build analyses
        analyses: List[Dict] = []
        for line in results:
            try:
                # Each line typically includes response with body
                custom_id = line.get("custom_id") or line.get("id")
                if not custom_id or not custom_id.startswith("hours-"):
                    continue
                sha = custom_id.split("hours-")[-1]
                body = None
                if isinstance(line.get("response"), dict):
                    body = line["response"].get("body")
                if not body:
                    body = line.get("body")
                content_text = None
                if isinstance(body, dict):
                    content_text = body.get("output_text")
                    if not content_text and body.get("choices"):
                        choices = body["choices"]
                        if choices and isinstance(choices, list):
                            content_text = choices[0].get("message", {}).get("content")
                if not content_text and isinstance(line.get("output"), dict):
                    content_text = line["output"].get("text")
                if not content_text or sha not in sha_to_commitdata:
                    continue
                hours_result = json.loads(content_text)
                cd = sha_to_commitdata[sha]
                analysis = {
                    "total_lines": hours_result.get("total_lines"),
                    "total_files": hours_result.get("total_files"),
                    "initial_anchor": hours_result.get("initial_anchor"),
                    "major_change_checks": hours_result.get("major_change_checks", []),
                    "simplicity_reduction_checks": hours_result.get("simplicity_reduction_checks", []),
                    "final_anchor": hours_result.get("final_anchor"),
                    "base_hours": hours_result.get("base_hours"),
                    "multipliers_applied": hours_result.get("multipliers_applied"),
                    "complexity_score": hours_result.get("complexity_score"),
                    "estimated_hours": hours_result.get("estimated_hours"),
                    "risk_level": hours_result.get("risk_level"),
                    "seniority_score": hours_result.get("seniority_score"),
                    "seniority_rationale": hours_result.get("seniority_rationale"),
                    "key_changes": hours_result.get("key_changes"),
                    # Metadata merge
                    "analyzed_at": datetime.now().isoformat(),
                    "commit_hash": cd.get("commit_hash"),
                    "repository": cd.get("repository"),
                    "model_used": model,
                    "scoring_methods": ["hours_estimation"],
                    # Merge original commit data
                    "message": cd.get("message"),
                    "commit_url": cd.get("commit_url"),
                    "timestamp": cd.get("timestamp"),
                    "additions": cd.get("additions"),
                    "deletions": cd.get("deletions"),
                    "files_changed": cd.get("files_changed"),
                }
                analyses.append(analysis)
                self.stats["fresh_analyses"] += 1
            except Exception as e:
                print(f"    ❌ Failed to parse batch result line: {e}")
                self.stats["failed_analyses"] += 1

        # Combine reused and new analyses
        for sha, commit in existing_commits_data.items():
            analyses.append(self._convert_commit_to_analysis(commit))

        # Compute summary
        total_hours = sum(float(a.get("estimated_hours", 0)) for a in analyses)
        total_complexity = sum(float(a.get("complexity_score", 0)) for a in analyses)
        total_impact_score = sum(float(a.get("impact_score", 0)) for a in analyses)

        github_username = github_username
        author_name = author_name or author_email

        return {
            "date": date.strftime("%Y-%m-%d"),
            "author_email": author_email,
            "github_username": github_username,
            "author_name": author_name,
            "total_commits": len(commits),
            "analyzed_commits": len(analyses),
            "existing_commits_reused": len(existing_hashes),
            "new_commits_analyzed": len([a for a in analyses if not a.get("from_existing")]),
            "total_hours": round(total_hours, 1),
            "average_complexity": round((total_complexity / len(analyses)) if analyses else 0, 1),
            "total_impact_score": round(total_impact_score, 1),
            "average_impact": 0.0,
            "analyses": analyses,
            "commit_details": [
                {
                    "sha": c["sha"],
                    "short_sha": c["sha"][:8],
                    "message": c["commit"]["message"],
                    "timestamp": c["commit"]["author"]["date"],
                    "url": f"https://github.com/{repository}/commit/{c['sha']}",
                    "author": {
                        "name": c["commit"]["author"]["name"],
                        "email": c["commit"]["author"]["email"],
                    },
                }
                for c in commits
            ],
        }

    def set_daily_analysis_mode(self, enabled: bool):
        """Enable or disable daily analysis mode."""
        self.enable_daily_analysis = enabled

    def _convert_commit_to_analysis(self, commit: Commit) -> Dict:
        """Convert an existing Commit object to analysis format.
        
        This method transforms a database Commit object into the same format
        that would be returned by fresh AI analysis, allowing us to seamlessly
        reuse existing analyses without re-calling the AI API.
        
        Args:
            commit: A Commit object retrieved from the database
            
        Returns:
            Dict with analysis results in the expected format
        """
        # Parse AI analysis notes if they exist
        analysis_metadata = {}
        if commit.ai_analysis_notes:
            try:
                analysis_metadata = json.loads(commit.ai_analysis_notes)
            except json.JSONDecodeError:
                analysis_metadata = {"raw_notes": commit.ai_analysis_notes}

        # Build the analysis dictionary
        analysis = {
            "commit_hash": commit.commit_hash,
            "message": commit.commit_message or "",
            "commit_url": commit.commit_url or "",
            "timestamp": commit.commit_timestamp.isoformat() if commit.commit_timestamp else None,
            "additions": commit.lines_added or 0,
            "deletions": commit.lines_deleted or 0,
            "files_changed": commit.changed_files or [],
            "estimated_hours": float(commit.ai_estimated_hours) if commit.ai_estimated_hours else 0.0,
            "complexity_score": commit.complexity_score or 0,
            "risk_level": commit.risk_level or "unknown",
            "seniority_score": commit.seniority_score or 0,
            "key_changes": analysis_metadata.get("key_changes", commit.key_changes or []),
            "seniority_rationale": analysis_metadata.get("seniority_rationale", commit.seniority_rationale or ""),
            "model_used": analysis_metadata.get("model_used", commit.model_used or "unknown"),
            "analyzed_at": (
                commit.analyzed_at.isoformat()
                if commit.analyzed_at
                else commit.created_at.isoformat() if commit.created_at else None
            ),
            "from_existing": True,  # Mark that this came from existing data
        }

        # Add impact scoring data if available
        if "impact_score" in analysis_metadata:
            analysis["impact_score"] = analysis_metadata["impact_score"]
        if "impact_classification" in analysis_metadata:
            analysis["impact_classification"] = analysis_metadata["impact_classification"]
        if "impact_business_value" in analysis_metadata:
            analysis["impact_business_value"] = analysis_metadata["impact_business_value"]
        if "impact_technical_complexity" in analysis_metadata:
            analysis["impact_technical_complexity"] = analysis_metadata["impact_technical_complexity"]

        return analysis

    async def analyze_single_commit(self, commit, repository: str) -> Optional[Dict]:
        """Analyze a single commit with concurrency control."""
        async with self.semaphore:  # Limit concurrent API calls
            sha = commit["sha"]

            # Get commit details and diff
            details = self.get_commit_details(repository, sha)
            if not details:
                return None

            diff = self.get_commit_diff(repository, sha)
            if not diff:
                return None

            # Extract file information
            files_changed = []
            additions = 0
            deletions = 0

            for file in details.get("files", []):
                files_changed.append(file.get("filename"))
                additions += file.get("additions", 0)
                deletions += file.get("deletions", 0)

            # Prepare data for analysis
            commit_data = {
                "commit_hash": sha,
                "repository": repository,
                "diff": diff,
                "message": commit["commit"]["message"],
                "author_name": commit["commit"]["author"]["name"],
                "author_email": commit["commit"]["author"]["email"],
                "files_changed": files_changed,
                "additions": additions,
                "deletions": deletions,
                "timestamp": commit["commit"]["author"]["date"],
                "commit_url": details.get("html_url", ""),
            }

            try:
                # Check diff size before analysis
                diff_size = len(commit_data.get("diff", ""))
                if diff_size > 100000:  # ~100KB limit for safety
                    print(f"    ⚠️  {sha[:8]}: Diff too large ({diff_size:,} chars), filtering large files...")
                    # Try to analyze without the largest files
                    filtered_commit_data = await self._filter_large_files_from_commit(commit_data, repository, sha)
                    if filtered_commit_data:
                        analysis = await self._analyze_filtered_commit(filtered_commit_data, sha)
                    else:
                        print(f"    ⚠️  {sha[:8]}: All files too large, using heuristic estimation")
                        analysis = self._create_fallback_analysis(commit_data)
                else:
                    # Choose analysis method based on configuration
                    if self.analysis_method == "hours":
                        analysis = await self._safe_analyze_commit(
                            lambda: self.commit_analyzer.analyze_commit_traditional_only(commit_data),
                            commit_data,
                            sha,
                            "hours",
                        )
                    elif self.analysis_method == "impact":
                        analysis = await self._safe_analyze_commit(
                            lambda: self.commit_analyzer.analyze_commit_impact(commit_data), commit_data, sha, "impact"
                        )
                    else:  # both - run separate API calls for better accuracy
                        # Run both analyses concurrently with error handling
                        hours_task = self._safe_analyze_commit(
                            lambda: self.commit_analyzer.analyze_commit_traditional_only(commit_data),
                            commit_data,
                            sha,
                            "hours",
                        )
                        impact_task = self._safe_analyze_commit(
                            lambda: self.commit_analyzer.analyze_commit_impact(commit_data), commit_data, sha, "impact"
                        )

                        hours_analysis, impact_analysis = await asyncio.gather(
                            hours_task, impact_task, return_exceptions=True
                        )

                        # Handle potential exceptions
                        if isinstance(hours_analysis, Exception):
                            print(f"    ❌ Hours analysis failed for {sha[:8]}: {hours_analysis}")
                            hours_analysis = None
                        if isinstance(impact_analysis, Exception):
                            print(f"    ❌ Impact analysis failed for {sha[:8]}: {impact_analysis}")
                            impact_analysis = None

                        # Merge the results from separate API calls
                        if hours_analysis and not hours_analysis.get("error"):
                            analysis = {**hours_analysis}  # Start with hours analysis
                            if impact_analysis and not impact_analysis.get("error"):
                                # Add impact data
                                for key, value in impact_analysis.items():
                                    if key.startswith("impact_") or key in ["impact_score", "impact_classification"]:
                                        analysis[key] = value

                            print(
                                f"    ✅ {sha[:8]}: {analysis.get('estimated_hours', 0)}h, {analysis.get('impact_score', 0)} pts (parallel)"
                            )
                        else:
                            # Both failed, use fallback
                            analysis = self._create_fallback_analysis(commit_data)
                            print(f"    🔄 {sha[:8]}: Used fallback analysis (API errors)")

                if analysis and not analysis.get("error"):
                    # Merge original commit data with analysis results
                    analysis.update(
                        {
                            "commit_hash": sha,
                            "message": commit_data["message"],
                            "commit_url": commit_data["commit_url"],
                            "timestamp": commit_data["timestamp"],
                            "additions": commit_data["additions"],
                            "deletions": commit_data["deletions"],
                            "files_changed": commit_data["files_changed"],
                        }
                    )
                    return analysis

            except Exception as e:
                print(f"    ❌ Error analyzing commit {sha[:8]}: {e}")
                return None

            return None

    async def _safe_analyze_commit(
        self, analysis_func, commit_data: Dict, sha: str, analysis_type: str
    ) -> Optional[Dict]:
        """Safely execute commit analysis with error handling for context length and other API errors."""
        try:
            return await analysis_func()
        except Exception as e:
            error_msg = str(e)

            # Handle specific OpenAI API errors
            if "context_length_exceeded" in error_msg or "exceeds the context window" in error_msg:
                print(f"    ⚠️  {sha[:8]}: Context too long for {analysis_type}, using fallback estimation")
                return self._create_fallback_analysis(commit_data)
            elif "rate_limit_exceeded" in error_msg:
                print(f"    ⏰ {sha[:8]}: Rate limit hit for {analysis_type}, waiting 60s...")
                await asyncio.sleep(60)
                try:
                    return await analysis_func()  # Retry once
                except Exception as retry_e:
                    print(f"    ❌ {sha[:8]}: {analysis_type} failed after retry: {retry_e}")
                    return self._create_fallback_analysis(commit_data)
            elif "invalid_api_key" in error_msg or "insufficient_quota" in error_msg:
                print(f"    ❌ {sha[:8]}: API key issue for {analysis_type}: {error_msg}")
                return self._create_fallback_analysis(commit_data)
            else:
                print(f"    ❌ {sha[:8]}: {analysis_type} analysis failed: {error_msg}")
                return self._create_fallback_analysis(commit_data)

    async def _filter_large_files_from_commit(self, commit_data: Dict, repository: str, sha: str) -> Optional[Dict]:
        """Filter out large files from commit to fit within OpenAI context window."""
        try:
            # Get individual file diffs to analyze size by file
            owner, repo = repository.split("/")
            url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"

            response = self._make_github_request(url)
            if response.status_code != 200:
                print(f"    ❌ Could not fetch commit details for filtering: {response.status_code}")
                return None

            commit_details = response.json()
            files = commit_details.get("files", [])

            if not files:
                return None

            # Calculate size of each file's diff content
            file_sizes = []
            for file in files:
                # Estimate diff size based on additions + deletions + context
                file_diff_size = (file.get("additions", 0) + file.get("deletions", 0)) * 50  # Rough estimate per line
                if "patch" in file:
                    file_diff_size = len(file["patch"])

                file_sizes.append(
                    {
                        "filename": file.get("filename", ""),
                        "size": file_diff_size,
                        "additions": file.get("additions", 0),
                        "deletions": file.get("deletions", 0),
                        "changes": file.get("changes", 0),
                        "patch": file.get("patch", ""),
                    }
                )

            # Sort by size descending to identify largest files
            file_sizes.sort(key=lambda x: x["size"], reverse=True)

            # Keep removing largest files until we fit in context window
            filtered_diff_parts = []
            total_filtered_size = 0
            files_included = []
            files_excluded = []
            target_size = 80000  # Conservative limit (~80KB)

            for file_info in reversed(file_sizes):  # Start with smallest files first
                if total_filtered_size + file_info["size"] > target_size and len(files_included) > 0:
                    files_excluded.append(file_info["filename"])
                    continue

                if file_info["patch"]:
                    filtered_diff_parts.append(f"diff --git a/{file_info['filename']} b/{file_info['filename']}")
                    filtered_diff_parts.append(file_info["patch"])
                    files_included.append(file_info["filename"])
                    total_filtered_size += file_info["size"]

            if not files_included:
                print(f"    ⚠️  {sha[:8]}: No files small enough to analyze after filtering")
                return None

            # Create filtered commit data
            filtered_commit_data = commit_data.copy()
            filtered_commit_data["diff"] = "\n".join(filtered_diff_parts)
            filtered_commit_data["files_changed"] = files_included

            # Recalculate totals for included files only
            filtered_additions = sum(f["additions"] for f in file_sizes if f["filename"] in files_included)
            filtered_deletions = sum(f["deletions"] for f in file_sizes if f["filename"] in files_included)

            filtered_commit_data["additions"] = filtered_additions
            filtered_commit_data["deletions"] = filtered_deletions
            filtered_commit_data["files_excluded"] = files_excluded
            filtered_commit_data["filtering_applied"] = True

            print(
                f"    🔍 {sha[:8]}: Filtered to {len(files_included)}/{len(files)} files ({total_filtered_size:,} chars)"
            )
            if files_excluded:
                print(
                    f"    📄 Excluded large files: {', '.join(files_excluded[:3])}{'...' if len(files_excluded) > 3 else ''}"
                )

            return filtered_commit_data

        except Exception as e:
            print(f"    ❌ Error filtering files for {sha[:8]}: {e}")
            return None

    async def _analyze_filtered_commit(self, filtered_commit_data: Dict, sha: str) -> Optional[Dict]:
        """Analyze a commit with filtered files, adding metadata about filtering."""
        try:
            # Choose analysis method based on configuration
            if self.analysis_method == "hours":
                analysis = await self._safe_analyze_commit(
                    lambda: self.commit_analyzer.analyze_commit_traditional_only(filtered_commit_data),
                    filtered_commit_data,
                    sha,
                    "hours",
                )
            elif self.analysis_method == "impact":
                analysis = await self._safe_analyze_commit(
                    lambda: self.commit_analyzer.analyze_commit_impact(filtered_commit_data),
                    filtered_commit_data,
                    sha,
                    "impact",
                )
            else:  # both - run separate API calls for better accuracy
                # Run both analyses concurrently with error handling
                hours_task = self._safe_analyze_commit(
                    lambda: self.commit_analyzer.analyze_commit_traditional_only(filtered_commit_data),
                    filtered_commit_data,
                    sha,
                    "hours",
                )
                impact_task = self._safe_analyze_commit(
                    lambda: self.commit_analyzer.analyze_commit_impact(filtered_commit_data),
                    filtered_commit_data,
                    sha,
                    "impact",
                )

                hours_analysis, impact_analysis = await asyncio.gather(hours_task, impact_task, return_exceptions=True)

                # Handle potential exceptions
                if isinstance(hours_analysis, Exception):
                    print(f"    ❌ Hours analysis failed for filtered {sha[:8]}: {hours_analysis}")
                    hours_analysis = None
                if isinstance(impact_analysis, Exception):
                    print(f"    ❌ Impact analysis failed for filtered {sha[:8]}: {impact_analysis}")
                    impact_analysis = None

                # Merge the results from separate API calls
                if hours_analysis and not hours_analysis.get("error"):
                    analysis = {**hours_analysis}  # Start with hours analysis
                    if impact_analysis and not impact_analysis.get("error"):
                        # Add impact data
                        for key, value in impact_analysis.items():
                            if key.startswith("impact_") or key in ["impact_score", "impact_classification"]:
                                analysis[key] = value
                    print(
                        f"    ✅ {sha[:8]}: {analysis.get('estimated_hours', 0)}h, {analysis.get('impact_score', 0)} pts (filtered)"
                    )
                else:
                    # Both failed, use fallback
                    analysis = self._create_fallback_analysis(filtered_commit_data)
                    print(f"    🔄 {sha[:8]}: Used fallback analysis (filtered commit API errors)")

            if analysis and not analysis.get("error"):
                # Add filtering metadata
                analysis["filtering_applied"] = True
                analysis["files_excluded"] = filtered_commit_data.get("files_excluded", [])
                analysis["files_analyzed"] = filtered_commit_data.get("files_changed", [])
                analysis["original_files_count"] = len(filtered_commit_data.get("files_excluded", [])) + len(
                    filtered_commit_data.get("files_changed", [])
                )

                # Add note to seniority rationale about filtering
                if "seniority_rationale" in analysis:
                    excluded_count = len(filtered_commit_data.get("files_excluded", []))
                    analysis["seniority_rationale"] += f" (Note: {excluded_count} large files excluded from analysis)"

                return analysis

        except Exception as e:
            print(f"    ❌ Error analyzing filtered commit {sha[:8]}: {e}")
            return self._create_fallback_analysis(filtered_commit_data)

        return None

    def _create_fallback_analysis(self, commit_data: Dict) -> Dict:
        """Create a fallback analysis when AI analysis fails."""
        # Simple heuristic-based estimation
        additions = commit_data.get("additions", 0)
        deletions = commit_data.get("deletions", 0)
        files_changed = len(commit_data.get("files_changed", []))
        total_changes = additions + deletions

        # Heuristic estimation based on code changes
        if total_changes == 0:
            estimated_hours = 0.1
            complexity = 1
            impact_score = 1.0
        elif total_changes < 10:
            estimated_hours = 0.5
            complexity = 2
            impact_score = 2.5
        elif total_changes < 50:
            estimated_hours = 1.5
            complexity = 4
            impact_score = 5.0
        elif total_changes < 200:
            estimated_hours = 4.0
            complexity = 6
            impact_score = 8.5
        else:
            estimated_hours = 8.0 + (total_changes / 100)  # Scale with size
            complexity = min(9, 6 + (files_changed // 5))
            impact_score = min(15.0, 8.5 + (total_changes / 200))

        # Cap maximum estimates
        estimated_hours = min(estimated_hours, 16.0)

        return {
            "estimated_hours": round(estimated_hours, 1),
            "complexity_score": complexity,
            "risk_level": "medium" if total_changes > 100 else "low",
            "seniority_score": 5,  # Neutral score
            "seniority_rationale": f"Fallback estimation based on {total_changes} line changes across {files_changed} files",
            "key_changes": [f"Modified {files_changed} files with {additions}+ / {deletions}- lines"],
            "impact_score": round(impact_score, 1),
            "impact_business_value": min(5, max(1, total_changes // 50)),
            "impact_technical_complexity": min(5, max(1, files_changed)),
            "impact_code_quality_points": 0,
            "impact_risk_penalty": 0,
            "impact_classification": "maintenance" if deletions > additions else "feature",
            "analyzed_at": datetime.now().isoformat(),
            "model_used": "heuristic_fallback",
            "fallback_reason": "API analysis failed or context too large",
        }

    def _make_github_request(
        self, url: str, accept_header: str = "application/vnd.github.v3+json", max_retries: int = 3
    ) -> requests.Response:
        """Make a GitHub API request with proper headers, rate limit handling, and retry logic."""
        headers = {"Accept": accept_header}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        for attempt in range(max_retries + 1):
            try:
                response = requests.get(url, headers=headers, timeout=30)

                # Update rate limit info
                if "X-RateLimit-Remaining" in response.headers:
                    self.rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
                    self.rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", 0))

                # Handle rate limiting
                if response.status_code == 403 and self.rate_limit_remaining == 0:
                    reset_time = datetime.fromtimestamp(self.rate_limit_reset)
                    wait_time = (reset_time - datetime.now()).total_seconds() + 60
                    print(f"⏰ Rate limit exceeded. Waiting {wait_time:.0f} seconds until {reset_time}...")
                    time.sleep(wait_time)
                    return self._make_github_request(url, accept_header, max_retries)

                return response

            except (SSLError, ConnectionError, Timeout) as e:
                if attempt < max_retries:
                    wait_time = (2**attempt) + 1  # Exponential backoff: 2, 3, 5 seconds
                    print(f"🔄 Network error (attempt {attempt + 1}/{max_retries + 1}): {type(e).__name__}")
                    print(f"   Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ Network error after {max_retries + 1} attempts: {e}")
                    raise
            except RequestException as e:
                print(f"❌ Request error: {e}")
                raise

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

            branches.extend([branch["name"] for branch in page_branches])
            page += 1

        return branches
    
    def get_all_commits_fast(self, repository: str, since: datetime, until: datetime) -> List[dict]:
        """Get all commits from all branches in one go using the commits API."""
        owner, repo = repository.split("/")
        all_commits = []
        page = 1
        
        # Format dates for GitHub API
        since_str = since.isoformat() + "Z"
        until_str = until.isoformat() + "Z"
        
        print("⚡ Using fast commit fetching (all branches at once)...")
        
        while True:
            # This endpoint returns commits from ALL branches
            url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            url += f"?since={since_str}&until={until_str}&per_page=100&page={page}"
            
            response = self._make_github_request(url)
            
            if response.status_code != 200:
                if page == 1:
                    print(f"⚠️  Failed to fetch commits: {response.status_code}")
                break
            
            page_commits = response.json()
            if not page_commits:
                break
            
            all_commits.extend(page_commits)
            print(f"  📦 Fetched page {page}: {len(page_commits)} commits (total: {len(all_commits)})")
            page += 1
            
        return all_commits

    def get_commits_for_branch(self, repository: str, branch: str, since: datetime, until: datetime) -> List[dict]:
        """Get all commits for a specific branch within the date range."""
        owner, repo = repository.split("/")
        commits = []
        page = 1

        # Format dates for GitHub API
        since_str = since.isoformat() + "Z"
        until_str = until.isoformat() + "Z"

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
                    role=UserRole.EMPLOYEE,
                    is_active=True,
                    metadata={"source": "historical_commit_seeder", "created_from": "github_commits"},
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

    async def analyze_commits_for_day(
        self, repository: str, author_email: str, date: datetime, commits: List[dict]
    ) -> Dict:
        """Analyze all commits for a specific author on a specific day."""
        if self.enable_daily_analysis:
            return await self.analyze_daily_batch(repository, author_email, date, commits)
        else:
            if self.use_openai_batch:
                return await self.analyze_individual_commits_batch(repository, author_email, date, commits)
            return await self.analyze_individual_commits(repository, author_email, date, commits)

    async def analyze_individual_commits(
        self, repository: str, author_email: str, date: datetime, commits: List[dict]
    ) -> Dict:
        """Analyze commits individually using parallel processing."""
        github_username = None
        author_name = None

        print(
            f"\n📅 Analyzing {len(commits)} commits for {author_email} on {date.strftime('%Y-%m-%d')} (parallel processing)"
        )

        # Extract metadata from first commit
        if commits:
            first_commit = commits[0]
            details = self.get_commit_details(repository, first_commit["sha"])
            if details and details.get("author"):
                github_username = details["author"].get("login")
            author_name = first_commit["commit"]["author"]["name"]

        # Check for existing commits if enabled - this is the key deduplication logic
        commit_hashes = [commit["sha"] for commit in commits]
        existing_commits_data = {}
        existing_hashes = set()

        if self.check_existing:
            print(f"  🔍 Checking for existing analyzed commits...")
            # Query database to find which commits already exist
            existing_hashes = set(await self.commit_repo.get_existing_commit_hashes(commit_hashes))

            if existing_hashes:
                print(f"  📦 Found {len(existing_hashes)} existing commits, fetching their analysis data...")
                # Retrieve full analysis data for existing commits
                existing_commits_data = await self.commit_repo.get_commits_with_analysis(list(existing_hashes))
                self.stats["existing_commits"] += len(existing_hashes)
                self.stats["reused_analyses"] += len(existing_commits_data)
                print(f"  ♻️  Reusing {len(existing_commits_data)} existing analyses")

        # Separate commits into those that need analysis and those that don't
        # This is where we decide whether to reuse existing analysis or perform fresh analysis
        commits_to_analyze = []
        analyses = []

        for commit in commits:
            sha = commit["sha"]
            if sha in existing_commits_data:
                # Reuse existing analysis - no API call needed!
                existing_analysis = self._convert_commit_to_analysis(existing_commits_data[sha])
                analyses.append(existing_analysis)
            else:
                # New commit - will need fresh analysis
                commits_to_analyze.append(commit)
                self.stats["new_commits"] += 1

        # Process only new commits in parallel
        if commits_to_analyze:
            print(
                f"  🚀 Processing {len(commits_to_analyze)} new commits with max {self.max_concurrent} concurrent API calls..."
            )

            # Create tasks for parallel processing
            tasks = []
            for commit in commits_to_analyze:
                task = self.analyze_single_commit(commit, repository)
                tasks.append(task)

            # Execute all analyses in parallel with progress tracking
            completed = 0

            # Process in chunks to show progress
            chunk_size = self.max_concurrent * 2  # Process in larger chunks for efficiency
            for i in range(0, len(tasks), chunk_size):
                chunk_tasks = tasks[i : i + chunk_size]
                chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)

                for result in chunk_results:
                    completed += 1
                    if isinstance(result, Exception):
                        print(f"    ❌ Analysis failed: {result}")
                        self.stats["failed_analyses"] += 1
                    elif result:
                        analyses.append(result)
                        self.stats["fresh_analyses"] += 1

                    # Show progress every 10 commits
                    if completed % 10 == 0 or completed == len(commits_to_analyze):
                        print(f"    📊 Progress: {completed}/{len(commits_to_analyze)} new commits processed")

        # Calculate totals
        total_hours = sum(float(a.get("estimated_hours", 0)) for a in analyses)
        total_complexity = sum(float(a.get("complexity_score", 0)) for a in analyses)
        total_impact_score = sum(float(a.get("impact_score", 0)) for a in analyses)

        # Calculate averages
        avg_complexity = total_complexity / len(analyses) if analyses else 0
        avg_impact = total_impact_score / len(analyses) if analyses else 0  # NEW: Average impact

        return {
            "date": date.strftime("%Y-%m-%d"),
            "author_email": author_email,
            "github_username": github_username,
            "author_name": author_name,
            "total_commits": len(commits),
            "analyzed_commits": len(analyses),
            "existing_commits_reused": len(existing_hashes),
            "new_commits_analyzed": len(commits_to_analyze),
            "total_hours": round(total_hours, 1),
            "average_complexity": round(avg_complexity, 1),
            "total_impact_score": round(total_impact_score, 1),  # NEW: Total impact
            "average_impact": round(avg_impact, 1),  # NEW: Average impact
            "analyses": analyses,
            "commit_details": [
                {
                    "sha": commit["sha"],
                    "short_sha": commit["sha"][:8],
                    "message": commit["commit"]["message"],
                    "timestamp": commit["commit"]["author"]["date"],
                    "url": f"https://github.com/{repository}/commit/{commit['sha']}",
                    "author": {
                        "name": commit["commit"]["author"]["name"],
                        "email": commit["commit"]["author"]["email"],
                    },
                }
                for commit in commits
            ],
        }

    async def analyze_daily_batch(
        self, repository: str, author_email: str, date: datetime, commits: List[dict]
    ) -> Dict:
        """Analyze commits using daily batch analysis instead of individual analysis."""
        print(f"\n📅 Daily batch analysis for {author_email} on {date.strftime('%Y-%m-%d')}")

        # Prepare context for daily analysis
        commit_summaries = []
        github_username = None
        author_name = None

        for commit in commits:
            sha = commit["sha"]

            # Get commit details and diff
            details = self.get_commit_details(repository, sha)
            if not details:
                continue

            diff = self.get_commit_diff(repository, sha)
            if not diff:
                continue

            # Extract GitHub username from author data
            if not github_username and details.get("author"):
                github_username = details["author"].get("login")

            # Keep author name for user creation
            if not author_name:
                author_name = commit["commit"]["author"]["name"]

            # Extract file information
            files_changed = []
            additions = 0
            deletions = 0

            for file in details.get("files", []):
                files_changed.append(file.get("filename"))
                additions += file.get("additions", 0)
                deletions += file.get("deletions", 0)

            commit_summaries.append(
                {
                    "hash": sha[:8],
                    "message": commit["commit"]["message"],
                    "timestamp": commit["commit"]["author"]["date"],
                    "repository": repository,
                    "files_changed": files_changed,
                    "additions": additions,
                    "deletions": deletions,
                }
            )

        # Prepare context for AI daily analysis
        context = {
            "analysis_date": date.strftime("%Y-%m-%d"),
            "user_name": author_name or author_email,
            "commits": commit_summaries,
            "total_commits": len(commits),
            "repositories": [repository],
            "total_lines_changed": sum(c.get("additions", 0) + c.get("deletions", 0) for c in commit_summaries),
        }

        # Use AI integration for daily analysis
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from app.integrations.ai_integration_v2 import AIIntegrationV2

            ai_integration = AIIntegrationV2()
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
                "recommendations": [],
            }

        return {
            "date": date.strftime("%Y-%m-%d"),
            "author_email": author_email,
            "github_username": github_username,
            "author_name": author_name,
            "total_commits": len(commits),
            "analyzed_commits": len(commits),
            "total_hours": round(daily_result.get("total_estimated_hours", 0), 1),
            "average_complexity": round(daily_result.get("average_complexity_score", 0), 1),
            "total_impact_score": 0,  # Daily analysis doesn't provide impact scores yet
            "average_impact": 0,
            "analyses": [],  # No individual analyses in daily mode
            "daily_analysis": daily_result,
            "commit_summaries": commit_summaries,  # Include commit summaries for storage
            "commit_details": [
                {
                    "sha": commit["sha"],
                    "short_sha": commit["sha"][:8],
                    "message": commit["commit"]["message"],
                    "timestamp": commit["commit"]["author"]["date"],
                    "url": f"https://github.com/{repository}/commit/{commit['sha']}",
                    "author": {
                        "name": commit["commit"]["author"]["name"],
                        "email": commit["commit"]["author"]["email"],
                    },
                    "files_changed": commit_summaries[i].get("files_changed", []) if i < len(commit_summaries) else [],
                    "additions": commit_summaries[i].get("additions", 0) if i < len(commit_summaries) else 0,
                    "deletions": commit_summaries[i].get("deletions", 0) if i < len(commit_summaries) else 0,
                }
                for i, commit in enumerate(commits)
            ],
        }

    async def seed_repository(
        self,
        repository: str,
        days: int = 30,
        branches: Optional[List[str]] = None,
        dry_run: bool = False,
        single_branch: bool = False,
    ) -> Dict:
        """Seed historical data for a repository."""
        # Calculate date range
        until = datetime.now(timezone.utc)
        since = until - timedelta(days=days)

        print(f"\n🚀 Seeding historical data for {repository}")
        print(f"📅 Date range: {since.strftime('%Y-%m-%d')} to {until.strftime('%Y-%m-%d')}")

        # Reset statistics
        self.stats["total_commits"] = 0

        # Get commits - use fast method for all branches when possible
        if branches:
            # Specific branches requested - use old method
            branches_to_analyze = branches
            all_commits = []
            seen_shas = set()
            
            for branch in branches_to_analyze:
                print(f"\n🔍 Fetching commits from branch: {branch}")
                commits = self.get_commits_for_branch(repository, branch, since, until)
                
                # Deduplicate commits
                for commit in commits:
                    sha = commit["sha"]
                    if sha not in seen_shas:
                        seen_shas.add(sha)
                        all_commits.append(commit)
                
                print(f"  📊 Found {len(commits)} commits ({len(all_commits)} unique total)")
        elif single_branch:
            # Just use the default branch
            print(f"\n🔍 Fetching commits from main branch only...")
            all_commits = self.get_commits_for_branch(repository, "main", since, until)
            if not all_commits:  # Fallback to master if main doesn't exist
                print("  ⚠️  'main' branch not found, trying 'master'...")
                all_commits = self.get_commits_for_branch(repository, "master", since, until)
        else:
            # Fast method - get all commits from all branches at once
            all_commits = self.get_all_commits_fast(repository, since, until)

        # Update total commits statistic
        self.stats["total_commits"] = len(all_commits)

        # Group commits by author and date
        commits_by_author_date = defaultdict(lambda: defaultdict(list))

        for commit in all_commits:
            author_email = commit["commit"]["author"]["email"]
            commit_date = datetime.fromisoformat(commit["commit"]["author"]["date"].replace("Z", "+00:00"))
            date_key = commit_date.date()

            commits_by_author_date[author_email][date_key].append(commit)

        print(f"\n📊 Found {len(commits_by_author_date)} unique authors")
        print(f"📊 Total unique commits: {len(all_commits)}")

        # Analyze commits grouped by author and date
        results = {
            "repository": repository,
            "date_range": {"since": since.isoformat(), "until": until.isoformat()},
            "summary": {
                "total_commits": len(all_commits),
                "unique_authors": len(commits_by_author_date),
                "total_hours": 0.0,
                "total_impact_score": 0.0,  # NEW: Track total impact score
                "daily_summaries": [],
                "analysis_statistics": {},  # Will be populated at the end
            },
        }

        # Process each author's commits by date
        for author_email, dates in commits_by_author_date.items():
            print(f"\n👤 Processing commits for {author_email}")

            for date, commits in sorted(dates.items()):
                day_datetime = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)
                day_analysis = await self.analyze_commits_for_day(repository, author_email, day_datetime, commits)

                results["summary"]["daily_summaries"].append(day_analysis)
                results["summary"]["total_hours"] += day_analysis["total_hours"]
                results["summary"]["total_impact_score"] += day_analysis.get(
                    "total_impact_score", 0
                )  # NEW: Add impact score

                # Store in database if not dry run
                if not dry_run and day_analysis["analyzed_commits"] > 0:
                    await self.store_daily_analysis(repository, day_analysis)

        # Sort daily summaries by date
        results["summary"]["daily_summaries"].sort(key=lambda x: x["date"])
        results["summary"]["total_hours"] = round(results["summary"]["total_hours"], 1)
        results["summary"]["total_impact_score"] = round(
            results["summary"]["total_impact_score"], 1
        )  # NEW: Round impact score

        # Add analysis statistics
        results["summary"]["analysis_statistics"] = {
            "total_commits_processed": self.stats["total_commits"],
            "existing_commits_found": self.stats["existing_commits"],
            "new_commits_found": self.stats["new_commits"],
            "analyses_reused": self.stats["reused_analyses"],
            "fresh_analyses_performed": self.stats["fresh_analyses"],
            "failed_analyses": self.stats["failed_analyses"],
            "check_existing_enabled": self.check_existing,
        }

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
            analysis_date = datetime.strptime(day_analysis["date"], "%Y-%m-%d").date()

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
                parsed_timestamp = (
                    datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if timestamp_str
                    else datetime.now(timezone.utc)
                )
            except:
                parsed_timestamp = datetime.now(timezone.utc)

            work_item_dict = {
                "item_type": "commit",
                "source": "github",
                "source_id": commit_summary.get("hash", ""),
                "title": commit_summary.get("message", "")[:255],  # Truncate if too long
                "description": commit_summary.get("message", ""),
                "url": f"https://github.com/{repository}/commit/{commit_summary.get('hash', '')}",
                "created_at": parsed_timestamp,
                "completed_at": parsed_timestamp,
                "loc_added": commit_summary.get("additions", 0),
                "loc_removed": commit_summary.get("deletions", 0),
                "files_changed": len(commit_summary.get("files_changed", [])),
                "estimated_hours": 0.0,  # Individual hours not available in daily batch
                "item_metadata": {
                    "repository": repository,
                    "files_changed": commit_summary.get("files_changed", []),
                    "analysis_method": "daily_batch",
                },
            }
            work_items.append(work_item_dict)

            # Accumulate totals
            total_loc_added += commit_summary.get("additions", 0)
            total_loc_removed += commit_summary.get("deletions", 0)
            total_files_changed += len(commit_summary.get("files_changed", []))

        # Store the daily analysis with work items included
        daily_analysis_dict = {
            "user_id": str(user.id),
            "analysis_date": analysis_date,
            "total_work_items": len(work_items),
            "total_commits": len(work_items),
            "total_tickets": 0,
            "total_prs": 0,
            "total_loc_added": total_loc_added,
            "total_loc_removed": total_loc_removed,
            "total_files_changed": total_files_changed,
            "total_estimated_hours": day_analysis.get("total_hours", 0.0),
            "daily_summary": daily_result.get("work_summary", ""),
            "key_achievements": daily_result.get("key_achievements", []),
            "technical_highlights": daily_result.get("technical_highlights", []),
            "data_sources": ["github"],
            "processing_status": "completed",
            "work_items": work_items,  # Include work items in creation
        }

        stored_daily_analysis = await self.daily_work_repo.create(daily_analysis_dict)

        print(f"  💾 Stored daily batch analysis for {author_email} on {day_analysis['date']}")
        print(
            f"    📊 {len(work_items)} work items, {total_loc_added}+ / {total_loc_removed}- lines, {day_analysis.get('total_hours', 0)}h estimated"
        )

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
                "scoring_methods": analysis.get("scoring_methods", ["hours_estimation", "impact_points"]),
            }

            # Parse commit timestamp
            commit_timestamp = datetime.now(timezone.utc)
            if analysis.get("timestamp"):
                try:
                    commit_timestamp = datetime.fromisoformat(analysis["timestamp"].replace("Z", "+00:00"))
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
                updated_at=datetime.now(timezone.utc),
            )

            await commit_repo.save_commit(commit_data)

        print(
            f"  💾 Stored {len(day_analysis['analyses'])} individual commit analyses for {author_email} on {day_analysis['date']}"
        )


async def main():
    """Main entry point for the historical seeding script."""
    parser = argparse.ArgumentParser(description="Seed historical commit data from GitHub repositories")
    parser.add_argument(
        "--repo", type=str, default="GolfDaddy-game/unity-game", help="Repository to analyze (format: owner/repo)"
    )
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back (default: 30)")
    parser.add_argument("--branches", type=str, nargs="+", help="Specific branches to analyze (default: all branches)")
    parser.add_argument(
        "--single-branch", action="store_true", help="Only analyze the main branch (faster for testing)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Run analysis without storing results in database")
    parser.add_argument("--model", type=str, help="OpenAI model to use for analysis (e.g., gpt-4o-mini, o1-mini)")
    parser.add_argument("--output", type=str, help="Output file for results (JSON format)")
    parser.add_argument(
        "--analysis-mode",
        type=str,
        choices=["individual", "daily"],
        default="individual",
        help="Analysis granularity: individual (per commit) or daily (batch per day)",
    )
    parser.add_argument(
        "--scoring-method",
        type=str,
        choices=["hours", "impact", "both"],
        default="both",
        help="Scoring method: hours (time estimation), impact (business value), or both",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum concurrent API calls (default: 5, increase for faster processing)",
    )
    parser.add_argument(
        "--use-openai-batch",
        action="store_true",
        help="Use OpenAI Batch API for cheaper asynchronous backfill",
    )
    parser.add_argument(
        "--check-existing",
        action="store_true",
        default=True,
        help="Check for existing commits and reuse their analysis (default: True)",
    )
    parser.add_argument(
        "--no-check-existing",
        dest="check_existing",
        action="store_false",
        help="Skip checking for existing commits and re-analyze everything",
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
    seeder = HistoricalCommitSeeder(
        github_token=github_token,
        model=args.model,
        analysis_method=args.scoring_method,
        max_concurrent=args.max_concurrent,
        check_existing=args.check_existing,
        use_openai_batch=args.use_openai_batch,
    )

    # Set analysis granularity and scoring method
    if args.analysis_mode == "daily":
        seeder.set_daily_analysis_mode(True)
        print(f"🔬 Using daily batch analysis mode")
    else:  # individual
        seeder.set_daily_analysis_mode(False)
        print(f"🔬 Using individual commit analysis mode")

    # Display scoring method and concurrency
    if args.scoring_method == "hours":
        print(f"⏱️  Scoring: Hours estimation only")
    elif args.scoring_method == "impact":
        print(f"📊 Scoring: Impact points only")
    else:  # both
        print(f"🔄 Scoring: Both hours estimation and impact points (separate API calls)")

    if args.analysis_mode == "individual":
        print(f"🚀 Parallel processing: {args.max_concurrent} concurrent API calls")
        if args.use_openai_batch:
            print("💸 OpenAI Batch mode enabled: requests will be queued asynchronously for reduced cost")

    try:
        # Run the seeding process
        results = await seeder.seed_repository(
            repository=args.repo,
            days=args.days,
            branches=args.branches,
            dry_run=args.dry_run,
            single_branch=args.single_branch,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("📊 SEEDING COMPLETE")
        print("=" * 60)
        print(f"Repository: {results['repository']}")
        print(f"Date Range: {args.days} days")
        print(f"Total Commits Analyzed: {results['summary']['total_commits']}")
        print(f"Unique Authors: {results['summary']['unique_authors']}")
        print(f"Total Estimated Hours: {results['summary']['total_hours']}")
        print(f"Total Impact Score: {results['summary']['total_impact_score']}")  # NEW: Show impact score

        # Print analysis statistics if checking existing was enabled
        if args.check_existing and "analysis_statistics" in results["summary"]:
            stats = results["summary"]["analysis_statistics"]
            print("\n📈 Analysis Statistics:")
            print(f"  Existing commits reused: {stats['analyses_reused']}")
            print(f"  New analyses performed: {stats['fresh_analyses_performed']}")
            print(f"  Failed analyses: {stats['failed_analyses']}")

            if stats["analyses_reused"] > 0:
                reuse_percentage = (
                    stats["analyses_reused"] / (stats["analyses_reused"] + stats["fresh_analyses_performed"])
                ) * 100
                print(f"  Reuse rate: {reuse_percentage:.1f}%")

        # Print top contributors by both methods
        author_hours = defaultdict(float)
        author_impact = defaultdict(float)  # NEW: Track impact scores
        for day_summary in results["summary"]["daily_summaries"]:
            author_hours[day_summary["author_email"]] += day_summary["total_hours"]
            author_impact[day_summary["author_email"]] += day_summary.get(
                "total_impact_score", 0
            )  # NEW: Add impact score

        print("\n🏆 Top Contributors by Estimated Hours:")
        for author, hours in sorted(author_hours.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {author}: {hours:.1f} hours")

        print("\n🏆 Top Contributors by Impact Score:")  # NEW: Impact score ranking
        for author, impact in sorted(author_impact.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {author}: {impact:.1f} points")

        # Save results to file if requested
        if args.output:
            # Generate dynamic filename if args.output is "auto"
            if args.output == "auto":
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                repo_name = args.repo.replace("/", "_").replace("-", "_")
                branch_suffix = ""
                if args.branches:
                    branch_name = args.branches[0].replace("/", "_").replace("-", "_")
                    branch_suffix = f"_{branch_name}"
                elif args.single_branch:
                    branch_suffix = "_main"
                else:
                    branch_suffix = "_all_branches"

                filename = f"github_analysis_{repo_name}{branch_suffix}_{args.days}days_{timestamp}.json"
            else:
                filename = args.output

            # Add metadata for import
            results["analysis_metadata"] = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "model_used": args.model or "gpt-4o-mini",
                "analysis_version": "2.0",
                "script_version": "1.0",
                "github_seeding_tool": "historical_commit_seeder",
                "export_format_version": "1.0",
                "dry_run": args.dry_run,
                "filename": filename,
                "command_args": {
                    "repository": args.repo,
                    "days": args.days,
                    "branches": args.branches,
                    "single_branch": args.single_branch,
                },
            }

            with open(filename, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Results saved to {filename}")
            print(f"📊 Export contains {len(results['summary']['daily_summaries'])} daily summaries ready for import")

    except KeyboardInterrupt:
        print("\n⚠️  Seeding interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
