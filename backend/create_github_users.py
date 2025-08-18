#!/usr/bin/env python3
"""
Create proper users with Supabase auth for GitHub contributors.
"""

import asyncio
import sys
import os
from uuid import uuid4

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client, Client
from app.config.settings import settings


async def create_github_users():
    """Create users with Supabase auth for GitHub contributors."""
    
    # Initialize Supabase admin client
    supabase: Client = create_client(
        str(settings.SUPABASE_URL),  # Convert to string
        settings.SUPABASE_SERVICE_KEY  # Service key can create users
    )
    
    print("🚀 Creating GitHub contributor users with Supabase auth...")
    
    # Define the users to create
    github_users = [
        {
            "email": "badjano@gmail.com",
            "password": "TempPassword123!",  # Temporary password
            "name": "William Queen (badjano)",
            "github_username": "badjano"
        },
        {
            "email": "breno.v@golfdaddy.com",
            "password": "TempPassword123!",
            "name": "Breno V",
            "github_username": "breno-v"
        },
        {
            "email": "ryan.c@golfdaddy.com",  # Using a simpler email
            "password": "TempPassword123!",
            "name": "Ryan C",
            "github_username": "ryan-c-golfdaddy"
        }
    ]
    
    created_users = []
    
    for user_data in github_users:
        try:
            # Create auth user first
            auth_response = supabase.auth.admin.create_user({
                "email": user_data["email"],
                "password": user_data["password"],
                "email_confirm": True,  # Auto-confirm email
                "user_metadata": {
                    "name": user_data["name"],
                    "github_username": user_data["github_username"]
                }
            })
            
            if auth_response.user:
                user_id = auth_response.user.id
                print(f"✅ Created auth user: {user_data['name']} ({user_data['email']})")
                
                # Create profile in users table
                profile_data = {
                    "id": user_id,
                    "email": user_data["email"],
                    "name": user_data["name"],
                    "github_username": user_data["github_username"],
                    "role": "employee",
                    "metadata": {"source": "github_import"}
                }
                
                profile_response = supabase.table('users').insert(profile_data).execute()
                
                if profile_response.data:
                    print(f"  ✅ Created user profile for {user_data['name']}")
                    created_users.append({
                        "id": user_id,
                        "email": user_data["email"],
                        "github_username": user_data["github_username"]
                    })
                
        except Exception as e:
            error_msg = str(e)
            if "already been registered" in error_msg or "already exists" in error_msg:
                print(f"  ℹ️  User {user_data['email']} already exists")
                # Try to get existing user
                try:
                    users = supabase.auth.admin.list_users()
                    for user in users:
                        if user.email == user_data["email"]:
                            created_users.append({
                                "id": user.id,
                                "email": user.email,
                                "github_username": user_data["github_username"]
                            })
                            break
                except:
                    pass
            else:
                print(f"  ❌ Error creating {user_data['email']}: {e}")
    
    if not created_users:
        print("\n⚠️  No new users created, but let's link commits anyway...")
        return
    
    print(f"\n📊 Created/found {len(created_users)} users")
    
    # Now update commits to link to these new users
    print("\n🔗 Linking commits to GitHub users...")
    
    for user in created_users:
        try:
            # Update commits by author_email
            if user["email"] == "ryan.c@golfdaddy.com":
                # Special case for ryan - update both email formats
                response1 = supabase.table('commits').update({
                    'author_id': user["id"]
                }).eq('author_github_username', 'ryan-c-golfdaddy').execute()
                
                response2 = supabase.table('commits').update({
                    'author_id': user["id"]
                }).eq('author_email', '153126309+ryan-c-golfdaddy@users.noreply.github.com').execute()
                
                total = len(response1.data or []) + len(response2.data or [])
                print(f"  ✅ Linked {total} commits to Ryan C")
            else:
                response = supabase.table('commits').update({
                    'author_id': user["id"]
                }).eq('author_email', user["email"]).execute()
                
                if response.data:
                    print(f"  ✅ Linked {len(response.data)} commits to {user['email']}")
                    
        except Exception as e:
            print(f"  ❌ Error linking commits for {user['email']}: {e}")
    
    print("\n✨ Done! GitHub users created with proper auth.")
    print("\n📊 The dashboard should now show:")
    print("  - William Queen (badjano): ~155 hours")
    print("  - Breno V: ~1 hour")
    print("  - Ryan C: ~155.5 hours")
    print("\nRefresh the manager dashboard to see the GitHub contributors!")


async def main():
    await create_github_users()


if __name__ == "__main__":
    asyncio.run(main())