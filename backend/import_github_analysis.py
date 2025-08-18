#!/usr/bin/env python3
"""
Import GitHub analysis JSON data into the database.
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timezone
from decimal import Decimal

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set required environment variables
from dotenv import load_dotenv
load_dotenv()

from app.config.supabase_client import get_supabase_client_safe
from app.repositories.commit_repository import CommitRepository
from app.repositories.user_repository import UserRepository
from app.models.commit import Commit
from app.models.user import User, UserRole


async def import_github_analysis(json_file_path: str):
    """Import GitHub analysis data from JSON file."""
    
    print(f"📂 Loading data from: {json_file_path}")
    
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    # Get repository info
    repository = data.get('repository', 'unknown')
    daily_summaries = data.get('summary', {}).get('daily_summaries', [])
    
    if not daily_summaries:
        print("❌ No daily summaries found in JSON file")
        return
    
    print(f"📊 Found {len(daily_summaries)} daily summaries to import")
    
    # Initialize repositories
    supabase = get_supabase_client_safe()
    commit_repo = CommitRepository(supabase)
    user_repo = UserRepository(supabase)
    
    total_commits = 0
    imported_commits = 0
    skipped_commits = 0
    
    for day_summary in daily_summaries:
        author_email = day_summary.get('author_email')
        github_username = day_summary.get('github_username')
        author_name = day_summary.get('author_name', github_username)
        analyses = day_summary.get('analyses', [])
        
        if not analyses:
            continue
            
        print(f"\n👤 Processing {len(analyses)} commits for {author_email} on {day_summary.get('date')}")
        
        # Get or create user
        user = None
        try:
            user = await user_repo.get_user_by_email(author_email)
        except Exception as e:
            print(f"  ⚠️  Could not fetch user by email: {e}")
        
        if not user and github_username:
            try:
                user = await user_repo.get_user_by_github_username(github_username)
            except Exception as e:
                print(f"  ⚠️  Could not fetch user by github username: {e}")
        
        if not user:
            print(f"  📝 Creating user: {author_name} ({author_email})")
            user_dict = {
                "email": author_email,
                "name": author_name or author_email,
                "github_username": github_username,
                "role": UserRole.EMPLOYEE.value,
                "is_active": True,
                "metadata": {"source": "github_analysis_import"}
            }
            try:
                user = await user_repo.create_user(user_dict)
                print(f"  ✅ Created user successfully")
            except Exception as e:
                print(f"  ⚠️  Could not create user: {e}")
                user = None
        
        # Import each commit analysis
        for analysis in analyses:
            total_commits += 1
            commit_hash = analysis.get('commit_hash')
            
            if not commit_hash:
                print(f"  ⚠️  Skipping analysis without commit hash")
                skipped_commits += 1
                continue
            
            # Check if commit already exists
            existing_hashes = await commit_repo.get_existing_commit_hashes([commit_hash])
            if existing_hashes:
                print(f"  ♻️  Commit {commit_hash[:8]} already exists, skipping")
                skipped_commits += 1
                continue
            
            # Parse timestamp
            timestamp_str = analysis.get('timestamp', '')
            try:
                commit_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except:
                commit_timestamp = datetime.now(timezone.utc)
            
            # Build analysis metadata
            analysis_metadata = {
                'model_used': analysis.get('model_used', 'gpt-4o-mini'),
                'analyzed_at': analysis.get('analyzed_at'),
                'key_changes': analysis.get('key_changes', []),
                'seniority_rationale': analysis.get('seniority_rationale', ''),
                'total_lines': analysis.get('total_lines'),
                'total_files': analysis.get('total_files'),
                'initial_anchor': analysis.get('initial_anchor'),
                'final_anchor': analysis.get('final_anchor'),
                'base_hours': analysis.get('base_hours'),
                'multipliers_applied': analysis.get('multipliers_applied'),
                'impact_score': analysis.get('impact_score'),
                'impact_business_value': analysis.get('impact_business_value'),
                'impact_technical_complexity': analysis.get('impact_technical_complexity'),
                'impact_classification': analysis.get('impact_classification'),
            }
            
            # Create commit record
            commit_data = Commit(
                commit_hash=commit_hash,
                commit_message=analysis.get('message', ''),
                commit_url=analysis.get('commit_url', ''),
                repository_name=repository,
                repository_url=f"https://github.com/{repository}",
                author_email=author_email,
                author_github_username=github_username,
                author_id=user.id if user else None,
                complexity_score=int(float(analysis.get('complexity_score', 0))),
                ai_estimated_hours=Decimal(str(analysis.get('estimated_hours', 0))),
                risk_level=analysis.get('risk_level', 'unknown'),
                seniority_score=int(float(analysis.get('seniority_score', 0))),
                ai_analysis_notes=json.dumps(analysis_metadata),
                lines_added=analysis.get('additions', 0),
                lines_deleted=analysis.get('deletions', 0),
                changed_files=analysis.get('files_changed', []),
                commit_timestamp=commit_timestamp,
            )
            
            try:
                await commit_repo.save_commit(commit_data)
                imported_commits += 1
                print(f"  ✅ Imported {commit_hash[:8]}: {analysis.get('estimated_hours', 0)}h, complexity {analysis.get('complexity_score', 0)}")
            except Exception as e:
                print(f"  ❌ Failed to save {commit_hash[:8]}: {e}")
                skipped_commits += 1
    
    print("\n" + "="*60)
    print("📊 IMPORT COMPLETE")
    print("="*60)
    print(f"Total commits in file: {total_commits}")
    print(f"Successfully imported: {imported_commits}")
    print(f"Skipped (existing/errors): {skipped_commits}")
    
    return imported_commits


async def main():
    """Main entry point."""
    json_file = "/Users/parkerbeard/golfdaddy-brain/backend/github_analysis_GolfDaddy_game_unity_game_all_branches_3days_20250817_211448.json"
    
    if not os.path.exists(json_file):
        print(f"❌ File not found: {json_file}")
        sys.exit(1)
    
    imported = await import_github_analysis(json_file)
    
    if imported > 0:
        print(f"\n✨ Data successfully imported! View it in your manager dashboard:")
        print(f"   http://localhost:8080/manager-dashboard")


if __name__ == "__main__":
    asyncio.run(main())