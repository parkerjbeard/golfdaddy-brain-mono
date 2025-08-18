#!/usr/bin/env python3
"""
Create daily reports for GitHub users so their data appears in dashboard.
"""

import asyncio
import sys
import os
from datetime import datetime, date, timezone
from decimal import Decimal

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from app.config.settings import settings


async def create_daily_reports():
    """Create daily reports for GitHub users based on their commits."""
    
    # Initialize Supabase client
    supabase = create_client(
        str(settings.SUPABASE_URL),
        settings.SUPABASE_SERVICE_KEY
    )
    
    print("📊 Creating daily reports for GitHub users...")
    
    # Get GitHub users
    github_users = [
        '4c956632-a050-4df2-b29f-89aace00bf08',  # William Queen (badjano)
        'e4f766dc-e803-49fd-98ac-de8ed09968be',  # Breno V
        '1ee5b358-613d-4067-89b3-397bfe6028a5',  # Ryan C
    ]
    
    # Get commits grouped by user and date
    commits_response = supabase.table('commits').select('*').in_('author_id', github_users).execute()
    commits = commits_response.data
    
    print(f"Found {len(commits)} commits for GitHub users")
    
    # Group commits by user and date
    from collections import defaultdict
    commits_by_user_date = defaultdict(lambda: defaultdict(list))
    
    for commit in commits:
        if commit['commit_timestamp'] and commit['author_id']:
            # Parse timestamp
            timestamp = datetime.fromisoformat(commit['commit_timestamp'].replace('Z', '+00:00'))
            commit_date = timestamp.date()
            commits_by_user_date[commit['author_id']][commit_date].append(commit)
    
    # Get user info
    users_response = supabase.table('users').select('*').in_('id', github_users).execute()
    users = {u['id']: u for u in users_response.data}
    
    print("\n📝 Creating daily reports...")
    
    for user_id, dates in commits_by_user_date.items():
        user = users.get(user_id)
        if not user:
            continue
            
        user_name = user.get('name', 'Unknown')
        
        for report_date, day_commits in dates.items():
            # Calculate totals for the day
            total_hours = sum(float(c.get('ai_estimated_hours', 0)) for c in day_commits)
            
            if total_hours == 0:
                continue
                
            # Create daily report
            report_data = {
                'user_id': user_id,
                'report_date': report_date.isoformat(),
                'summary': f"Automated report from {len(day_commits)} GitHub commits",
                'achievements': [f"Completed {len(day_commits)} commits"],
                'blockers': [],
                'next_day_plan': ["Continue development"],
                'hours_worked': float(total_hours),
                'mood_rating': 4,  # Default neutral mood
                'productivity_rating': 4,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'is_submitted': True,
                'submitted_at': datetime.now(timezone.utc).isoformat(),
                'metadata': {
                    'source': 'github_import',
                    'commit_count': len(day_commits),
                    'auto_generated': True
                }
            }
            
            try:
                # Check if report already exists
                existing = supabase.table('daily_reports').select('id').eq('user_id', user_id).eq('report_date', report_date.isoformat()).execute()
                
                if existing.data:
                    print(f"  ⚠️  Report already exists for {user_name} on {report_date}")
                else:
                    response = supabase.table('daily_reports').insert(report_data).execute()
                    if response.data:
                        print(f"  ✅ Created report for {user_name} on {report_date}: {total_hours:.1f} hours")
                    
            except Exception as e:
                print(f"  ❌ Error creating report for {user_name} on {report_date}: {e}")
    
    print("\n📈 Verifying reports...")
    
    # Check what reports exist
    for user_id in github_users:
        user = users.get(user_id)
        if user:
            reports = supabase.table('daily_reports').select('report_date').eq('user_id', user_id).execute()
            if reports.data:
                print(f"  {user['name']}: {len(reports.data)} reports created")
            else:
                print(f"  {user['name']}: No reports found")
    
    print("\n✨ Done! Refresh the dashboard to see the data for GitHub users.")


async def main():
    await create_daily_reports()


if __name__ == "__main__":
    asyncio.run(main())