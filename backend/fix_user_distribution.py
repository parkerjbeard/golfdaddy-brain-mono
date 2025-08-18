#!/usr/bin/env python3
"""
Fix user names and redistribute commits properly.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.config.supabase_client import get_supabase_client_safe


async def fix_user_distribution():
    """Fix user names and redistribute commits."""
    
    supabase = get_supabase_client_safe()
    
    print("🔧 Fixing user names and commit distribution...")
    
    # First, update users with NULL names
    users_to_update = [
        ('0afa3249-0ef5-4d81-aa8d-06c1b4e2e901', 'Test Developer One'),  # test@example.com
        ('731b98a1-5f02-4f11-832a-429e0c0d02a6', 'Test Manager Two'),     # manager@example.com  
        ('46f1e0b5-05ea-44b0-88b8-68ea1a67b3b9', 'Test Admin Two'),      # admin@example.com
    ]
    
    for user_id, new_name in users_to_update:
        try:
            response = supabase.table('users').update({
                'name': new_name
            }).eq('id', user_id).execute()
            if response.data:
                print(f"✅ Updated user {user_id} name to: {new_name}")
        except Exception as e:
            print(f"❌ Error updating user {user_id}: {e}")
    
    print("\n📊 Redistributing commits for better visualization...")
    
    # Now redistribute commits from the GitHub authors
    # Map GitHub authors to specific test users
    author_mappings = [
        # badjano@gmail.com commits (40 commits, 155 hours) -> Test Manager One
        ('badjano@gmail.com', 'ea913bc5-8744-4032-ad90-7404ba8c5bae', 'Test Manager One'),
        
        # ryan-c-golfdaddy commits (11 commits, 103.5 hours) -> Test Admin One
        ('ryan-c-golfdaddy', '2c270f4d-c844-4e30-8b1c-ef60469c5efa', 'Test Admin One'),
        
        # 153126309+ryan... commits (3 commits, 52 hours) -> Test Developer One
        ('153126309+ryan-c-golfdaddy@users.noreply.github.com', '0afa3249-0ef5-4d81-aa8d-06c1b4e2e901', 'Test Developer One'),
        
        # breno.v commits (2 commits, 1 hour) -> Test User One (already correct)
        ('breno.v@golfdaddy.com', 'e3f27dfb-6f99-49d8-94cb-6a935ac057b8', 'Test User One'),
    ]
    
    for author_email, new_user_id, user_name in author_mappings:
        try:
            response = supabase.table('commits').update({
                'author_id': new_user_id
            }).eq('author_email', author_email).execute()
            
            if response.data:
                print(f"✅ Moved {len(response.data)} commits from {author_email} to {user_name}")
        except Exception as e:
            print(f"❌ Error moving commits for {author_email}: {e}")
    
    # Also reassign any remaining test@example.com commits
    try:
        response = supabase.table('commits').update({
            'author_id': '731b98a1-5f02-4f11-832a-429e0c0d02a6'  # Test Manager Two
        }).eq('author_email', 'test@example.com').execute()
        if response.data:
            print(f"✅ Moved {len(response.data)} test commits to Test Manager Two")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n📈 Final distribution should be:")
    print("  - Test Manager One: ~155 hours (badjano's work)")
    print("  - Test Admin One: ~103.5 hours (ryan-c's work)")  
    print("  - Test Developer One: ~52 hours (ryan's GitHub work)")
    print("  - Test User One: ~1 hour (breno's work)")
    print("\n✨ Done! Refresh the dashboard to see the properly distributed data.")


async def main():
    await fix_user_distribution()


if __name__ == "__main__":
    asyncio.run(main())