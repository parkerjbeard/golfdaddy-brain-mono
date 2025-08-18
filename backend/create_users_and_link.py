#!/usr/bin/env python3
"""
Create user records for GitHub contributors and link existing commits to them.
"""

import asyncio
import sys
import os
from uuid import uuid4
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set required environment variables
from dotenv import load_dotenv
load_dotenv()

from app.config.supabase_client import get_supabase_client_safe


async def create_users_and_link_commits():
    """Create users and update commits to link to them."""
    
    supabase = get_supabase_client_safe()
    
    # Define the users we need to create
    users_to_create = [
        {
            "email": "badjano@gmail.com",
            "github_username": "badjano",
            "name": "William Queen"  # From the JSON data
        },
        {
            "email": "breno.v@golfdaddy.com", 
            "github_username": "breno-v",
            "name": "Breno V"
        },
        {
            "email": "153126309+ryan-c-golfdaddy@users.noreply.github.com",
            "github_username": "ryan-c-golfdaddy",
            "name": "Ryan C"
        }
    ]
    
    created_users = {}
    
    print("📝 Creating user records...")
    
    for user_data in users_to_create:
        # First check if user already exists
        try:
            # Check by email
            response = supabase.table('users').select('*').eq('email', user_data['email']).execute()
            if response.data and len(response.data) > 0:
                print(f"  ♻️  User {user_data['email']} already exists")
                created_users[user_data['email']] = response.data[0]['id']
                continue
                
            # Check by github username
            response = supabase.table('users').select('*').eq('github_username', user_data['github_username']).execute()
            if response.data and len(response.data) > 0:
                print(f"  ♻️  User {user_data['github_username']} already exists")
                created_users[user_data['email']] = response.data[0]['id']
                continue
                
        except Exception as e:
            print(f"  ⚠️  Error checking existing user: {e}")
        
        # Create new user
        user_id = str(uuid4())
        new_user = {
            'id': user_id,
            'email': user_data['email'],
            'name': user_data['name'],
            'github_username': user_data['github_username'],
            'role': 'employee',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'metadata': {'source': 'github_import', 'created_for_commits': True}
        }
        
        try:
            response = supabase.table('users').insert(new_user).execute()
            if response.data:
                print(f"  ✅ Created user: {user_data['name']} ({user_data['email']})")
                created_users[user_data['email']] = user_id
            else:
                print(f"  ❌ Failed to create user: {user_data['email']}")
        except Exception as e:
            print(f"  ❌ Error creating user {user_data['email']}: {e}")
    
    # Also handle the ryan-c-golfdaddy case (without email domain)
    # This appears to be the same person but with different email formats in commits
    if "153126309+ryan-c-golfdaddy@users.noreply.github.com" in created_users:
        created_users["ryan-c-golfdaddy"] = created_users["153126309+ryan-c-golfdaddy@users.noreply.github.com"]
    
    print(f"\n📊 Created/found {len(created_users)} users")
    
    # Now update commits to link to these users
    print("\n🔗 Linking commits to users...")
    
    for email, user_id in created_users.items():
        try:
            # Update by author_email
            response = supabase.table('commits').update({
                'author_id': user_id
            }).eq('author_email', email).is_('author_id', 'null').execute()
            
            if response.data:
                print(f"  ✅ Linked {len(response.data)} commits for {email}")
            
            # Also update by github_username for the ryan-c-golfdaddy case
            if email == "153126309+ryan-c-golfdaddy@users.noreply.github.com":
                response = supabase.table('commits').update({
                    'author_id': user_id
                }).eq('author_github_username', 'ryan-c-golfdaddy').is_('author_id', 'null').execute()
                
                if response.data:
                    print(f"  ✅ Linked {len(response.data)} additional commits for ryan-c-golfdaddy")
                    
        except Exception as e:
            print(f"  ❌ Error linking commits for {email}: {e}")
    
    print("\n✨ Done! Users created and commits linked.")
    print("\n📊 The dashboard should now show:")
    print("  - William Queen (badjano): ~156 hours")
    print("  - Breno V: ~1 hour") 
    print("  - Ryan C: ~155.5 hours")
    print("\nRefresh the manager dashboard to see the updated data!")


async def main():
    """Main entry point."""
    await create_users_and_link_commits()


if __name__ == "__main__":
    asyncio.run(main())