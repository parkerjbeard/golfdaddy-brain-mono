#!/usr/bin/env python3
"""
Link imported commits to existing test users in the system.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set required environment variables
from dotenv import load_dotenv
load_dotenv()

from app.config.supabase_client import get_supabase_client_safe


async def link_commits_to_test_users():
    """Link commits to existing test users."""
    
    supabase = get_supabase_client_safe()
    
    print("🔍 Finding existing users...")
    
    # Get all existing users
    response = supabase.table('users').select('id, email, name').execute()
    
    if not response.data:
        print("❌ No users found in the system")
        return
    
    existing_users = response.data
    print(f"Found {len(existing_users)} existing users:")
    for user in existing_users:
        print(f"  - {user['name']} ({user['email']}): {user['id']}")
    
    # Use the first available user for all commits (temporary solution)
    if existing_users:
        selected_user = existing_users[0]
        print(f"\n🔗 Linking all unlinked commits to: {selected_user['name']} ({selected_user['email']})")
        
        # Update all commits that don't have an author_id
        try:
            response = supabase.table('commits').update({
                'author_id': selected_user['id']
            }).is_('author_id', 'null').execute()
            
            if response.data:
                print(f"✅ Successfully linked {len(response.data)} commits to {selected_user['name']}")
            else:
                print("⚠️  No unlinked commits found or update failed")
                
        except Exception as e:
            print(f"❌ Error linking commits: {e}")
    
    # Now let's also distribute commits among users if there are multiple
    if len(existing_users) > 1:
        print("\n📊 Distributing commits among users for better visualization...")
        
        # Get author emails from commits
        response = supabase.table('commits').select('author_email').execute()
        unique_authors = list(set([c['author_email'] for c in response.data if c['author_email']]))
        
        print(f"Found {len(unique_authors)} unique commit authors:")
        for author in unique_authors[:5]:  # Show first 5
            print(f"  - {author}")
        
        # Map each unique author email to a different test user
        author_to_user_map = {}
        for i, author_email in enumerate(unique_authors):
            user_index = i % len(existing_users)
            author_to_user_map[author_email] = existing_users[user_index]
            print(f"  Mapping {author_email} → {existing_users[user_index]['name']}")
        
        # Update commits based on mapping
        for author_email, user in author_to_user_map.items():
            try:
                response = supabase.table('commits').update({
                    'author_id': user['id']
                }).eq('author_email', author_email).execute()
                
                if response.data:
                    print(f"  ✅ Linked {len(response.data)} commits from {author_email} to {user['name']}")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    print("\n✨ Done! Refresh the manager dashboard to see the imported data.")
    print("   The commits are now associated with existing users in your system.")


async def main():
    """Main entry point."""
    await link_commits_to_test_users()


if __name__ == "__main__":
    asyncio.run(main())