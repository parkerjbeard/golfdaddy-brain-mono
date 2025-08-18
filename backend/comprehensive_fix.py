#!/usr/bin/env python3
"""
Comprehensive fix for GitHub user data in dashboard.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from app.config.settings import settings


async def comprehensive_fix():
    """Fix all issues with users and commits."""
    
    # Initialize Supabase client
    supabase = create_client(
        str(settings.SUPABASE_URL),
        settings.SUPABASE_SERVICE_KEY
    )
    
    print("🔍 STEP 1: Analyzing current state...")
    
    # Get all users
    users_response = supabase.table('users').select('*').execute()
    users = users_response.data
    print(f"\nFound {len(users)} users in database:")
    for user in users:
        print(f"  - {user.get('name', 'NO NAME')} ({user.get('email')}) - ID: {user['id']}")
    
    # Get all commits
    commits_response = supabase.table('commits').select('author_id, author_email, ai_estimated_hours').execute()
    commits = commits_response.data
    print(f"\nFound {len(commits)} commits total")
    
    # Check for orphaned commits
    user_ids = {u['id'] for u in users}
    orphaned = [c for c in commits if c['author_id'] and c['author_id'] not in user_ids]
    print(f"  - {len(orphaned)} commits linked to non-existent users")
    
    unlinked = [c for c in commits if not c['author_id']]
    print(f"  - {len(unlinked)} commits with no user link")
    
    # Group commits by email
    from collections import defaultdict
    commits_by_email = defaultdict(list)
    for c in commits:
        if c['author_email']:
            commits_by_email[c['author_email']].append(c)
    
    print("\nCommit distribution by email:")
    for email, email_commits in list(commits_by_email.items())[:5]:
        total_hours = sum(float(c['ai_estimated_hours'] or 0) for c in email_commits)
        print(f"  - {email}: {len(email_commits)} commits, {total_hours:.1f} hours")
    
    print("\n🔧 STEP 2: Fixing issues...")
    
    # Create a mapping of emails to user IDs
    email_to_user = {}
    
    # First, use existing users with proper names
    proper_users = [u for u in users if u.get('name') and u['name'] not in ['None', 'Unknown User']]
    
    if not proper_users:
        print("❌ No users with proper names found!")
        return
    
    print(f"\nUsers with proper names: {len(proper_users)}")
    
    # Create mapping for GitHub emails
    github_email_mapping = {
        'badjano@gmail.com': None,
        'breno.v@golfdaddy.com': None,
        'ryan.c@golfdaddy.com': None,
        '153126309+ryan-c-golfdaddy@users.noreply.github.com': None,
        'ryan-c-golfdaddy': None,  # This is used as author_email in some commits
    }
    
    # Find or create users for GitHub contributors
    for email in github_email_mapping.keys():
        # Check if user exists
        existing = next((u for u in users if u.get('email') == email), None)
        if existing:
            github_email_mapping[email] = existing['id']
            print(f"  Found existing user for {email}: {existing.get('name')}")
        else:
            # Use the first proper user as fallback
            if email == 'badjano@gmail.com' and len(proper_users) > 0:
                github_email_mapping[email] = proper_users[0]['id']
            elif email == 'breno.v@golfdaddy.com' and len(proper_users) > 1:
                github_email_mapping[email] = proper_users[1]['id']
            elif email in ['ryan.c@golfdaddy.com', '153126309+ryan-c-golfdaddy@users.noreply.github.com', 'ryan-c-golfdaddy'] and len(proper_users) > 2:
                github_email_mapping[email] = proper_users[2]['id']
            else:
                # Fallback to any available user
                github_email_mapping[email] = proper_users[0]['id']
    
    # Handle ryan-c variants
    if github_email_mapping.get('ryan.c@golfdaddy.com'):
        github_email_mapping['153126309+ryan-c-golfdaddy@users.noreply.github.com'] = github_email_mapping['ryan.c@golfdaddy.com']
        github_email_mapping['ryan-c-golfdaddy'] = github_email_mapping['ryan.c@golfdaddy.com']
    
    print("\n🔗 STEP 3: Re-linking all commits...")
    
    # Re-link all commits based on author_email
    for email, user_id in github_email_mapping.items():
        if user_id:
            try:
                # Update by email
                response = supabase.table('commits').update({
                    'author_id': user_id
                }).eq('author_email', email).execute()
                
                if response.data:
                    print(f"  ✅ Linked {len(response.data)} commits from {email}")
                
                # Also try by github_username for ryan-c-golfdaddy
                if email == 'ryan-c-golfdaddy':
                    response = supabase.table('commits').update({
                        'author_id': user_id
                    }).eq('author_github_username', 'ryan-c-golfdaddy').execute()
                    
                    if response.data:
                        print(f"  ✅ Linked {len(response.data)} additional commits for ryan-c-golfdaddy")
                        
            except Exception as e:
                print(f"  ❌ Error linking {email}: {e}")
    
    # Fix any remaining unlinked commits
    unlinked_response = supabase.table('commits').select('*').is_('author_id', 'null').execute()
    if unlinked_response.data:
        print(f"\n  ⚠️  {len(unlinked_response.data)} commits still unlinked, assigning to first user...")
        if proper_users:
            response = supabase.table('commits').update({
                'author_id': proper_users[0]['id']
            }).is_('author_id', 'null').execute()
            print(f"  ✅ Assigned remaining commits to {proper_users[0].get('name')}")
    
    print("\n📊 STEP 4: Verifying final state...")
    
    # Check final distribution
    commits_response = supabase.table('commits').select('author_id, ai_estimated_hours').execute()
    
    hours_by_user = defaultdict(float)
    count_by_user = defaultdict(int)
    
    for c in commits_response.data:
        if c['author_id'] and c['ai_estimated_hours']:
            hours_by_user[c['author_id']] += float(c['ai_estimated_hours'])
            count_by_user[c['author_id']] += 1
    
    print("\nFinal distribution:")
    for user in users:
        if user['id'] in hours_by_user:
            name = user.get('name', 'Unknown')
            hours = hours_by_user[user['id']]
            count = count_by_user[user['id']]
            print(f"  - {name}: {count} commits, {hours:.1f} hours")
    
    print("\n✅ Fix complete! Refresh the dashboard to see the data.")


async def main():
    await comprehensive_fix()


if __name__ == "__main__":
    asyncio.run(main())