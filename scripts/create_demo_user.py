#!/usr/bin/env python3
"""Create demo user for GolfDaddy Brain demo"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
import requests

# Load environment variables from backend/.env
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)
else:
    print("Error: backend/.env not found")
    sys.exit(1)

# Get Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def create_demo_user():
    """Create a demo user if it doesn't exist"""
    email = "testadmin1@example.com"
    password = "password123"
    
    print(f"Creating demo user: {email}")
    
    try:
        # Try to create user via Supabase Admin API
        response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "name": "Demo Admin"
            }
        })
        
        if response:
            print(f"✅ User created successfully: {email}")
            print(f"   User ID: {response.user.id}")
            
            # Now create the user profile in public.users table
            try:
                profile_data = {
                    "id": response.user.id,
                    "email": email,
                    "name": "Demo Admin",
                    "role": "admin",
                    "created_at": response.user.created_at
                }
                
                result = supabase.table("users").insert(profile_data).execute()
                print("✅ User profile created in public.users table")
            except Exception as e:
                print(f"⚠️  Profile might already exist: {e}")
        else:
            print("❌ Failed to create user")
            
    except Exception as e:
        if "already been registered" in str(e):
            print(f"⚠️  User already exists: {email}")
            print("   You can use this account for the demo")
        else:
            print(f"❌ Error creating user: {e}")
            
            # Try alternate approach - using the API
            print("\nTrying alternate approach via API...")
            try:
                api_url = "http://localhost:8000/api/v1/auth/register"
                data = {
                    "email": email,
                    "password": password,
                    "name": "Demo Admin"
                }
                response = requests.post(api_url, json=data)
                
                if response.status_code == 200:
                    print("✅ User registered via API")
                else:
                    print(f"❌ API registration failed: {response.status_code}")
                    print(f"   Response: {response.text}")
            except Exception as api_error:
                print(f"❌ API error: {api_error}")

if __name__ == "__main__":
    print("GolfDaddy Brain Demo User Setup")
    print("=" * 40)
    create_demo_user()
    print("\nDemo user credentials:")
    print("  Email: testadmin1@example.com")
    print("  Password: password123")
    print("\nYou can now run the demo script!")