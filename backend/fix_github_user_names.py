#!/usr/bin/env python3
"""
Fix GitHub user names so they appear properly in dashboard.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from app.config.settings import settings


async def fix_github_user_names():
    """Update GitHub user names in the database."""
    
    # Initialize Supabase client
    supabase = create_client(
        str(settings.SUPABASE_URL),
        settings.SUPABASE_SERVICE_KEY
    )
    
    print("🔧 Fixing GitHub user names...")
    
    # Update the users with proper names
    user_updates = [
        {
            'id': '4c956632-a050-4df2-b29f-89aace00bf08',
            'email': 'badjano@gmail.com',
            'name': 'William Queen (badjano)',
            'github_username': 'badjano'
        },
        {
            'id': 'e4f766dc-e803-49fd-98ac-de8ed09968be',
            'email': 'breno.v@golfdaddy.com',
            'name': 'Breno V',
            'github_username': 'breno-v'
        },
        {
            'id': '1ee5b358-613d-4067-89b3-397bfe6028a5',
            'email': 'ryan.c@golfdaddy.com',
            'name': 'Ryan C (GolfDaddy)',
            'github_username': 'ryan-c-golfdaddy'
        }
    ]
    
    for user in user_updates:
        try:
            response = supabase.table('users').update({
                'name': user['name'],
                'github_username': user['github_username']
            }).eq('id', user['id']).execute()
            
            if response.data:
                print(f"✅ Updated {user['name']} ({user['email']})")
            else:
                print(f"⚠️  No update for {user['email']}")
                
        except Exception as e:
            print(f"❌ Error updating {user['email']}: {e}")
    
    print("\n📊 Verifying user data...")
    
    # Get all users to verify
    users_response = supabase.table('users').select('id, name, email').execute()
    
    print("\nAll users in system:")
    for user in users_response.data:
        name = user.get('name', 'NO NAME')
        email = user.get('email', 'NO EMAIL')
        print(f"  - {name} ({email})")
    
    # Check commit distribution
    print("\n📈 Checking commit distribution...")
    
    commits_response = supabase.table('commits').select('author_id, ai_estimated_hours').execute()
    
    from collections import defaultdict
    hours_by_user = defaultdict(float)
    count_by_user = defaultdict(int)
    
    for c in commits_response.data:
        if c['author_id'] and c['ai_estimated_hours']:
            hours_by_user[c['author_id']] += float(c['ai_estimated_hours'])
            count_by_user[c['author_id']] += 1
    
    # Create user ID to name mapping
    user_map = {u['id']: u['name'] for u in users_response.data}
    
    print("\nHours by user:")
    total_hours = 0
    for user_id, hours in sorted(hours_by_user.items(), key=lambda x: x[1], reverse=True):
        name = user_map.get(user_id, 'Unknown')
        count = count_by_user[user_id]
        total_hours += hours
        print(f"  - {name}: {count} commits, {hours:.1f} hours")
    
    print(f"\nTotal: {total_hours:.1f} hours across all users")
    
    print("\n✨ Done! The dashboard should now show:")
    print("  - William Queen (badjano): ~155 hours")
    print("  - Ryan C (GolfDaddy): ~155.5 hours")
    print("  - Test Manager One: ~300.5 hours")
    print("  - Parker Beard: ~6.8 hours")
    print("  - Breno V: ~1 hour")
    print("\nRefresh the dashboard to see the GitHub contributors with proper names!")


async def main():
    await fix_github_user_names()


if __name__ == "__main__":
    asyncio.run(main())