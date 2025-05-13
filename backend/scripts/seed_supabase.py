# backend/scripts/seed_supabase.py

import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from uuid import uuid4, UUID
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

import sys
# Correctly construct the path and append it
# This allows the script to find the 'app' module
backend_app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(backend_app_path)

from app.models.user import User, UserRole
from app.models.task import Task, TaskStatus
# from app.models.commit import Commit # Not seeding commits in this version

from app.repositories.user_repository import UserRepository
from app.repositories.task_repository import TaskRepository

# --- Configuration ---
# Load .env from the backend directory (one level up from scripts directory)
dotenv_path = os.path.join(backend_app_path, '.env')
loaded = load_dotenv(dotenv_path=dotenv_path)
print(f"Dotenv loaded from {dotenv_path}: {loaded}") # DEBUG: Check if .env was loaded

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# DEBUG: Print the values read from environment
print(f"DEBUG: Read SUPABASE_URL: {SUPABASE_URL}")
print(f"DEBUG: Read SUPABASE_SERVICE_KEY: {SUPABASE_SERVICE_KEY}")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in your .env file.")
    print(f"Attempted to load .env from: {dotenv_path}")
    exit(1)

# Initialize Supabase client with the service role key for admin operations
try:
    supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
except Exception as e:
    print(f"Error initializing Supabase client: {e}")
    exit(1)

user_repo = UserRepository(client=supabase_admin)
task_repo = TaskRepository(client=supabase_admin)

# --- Test Data Definitions ---
test_users_data = [
    {
        "email": "testuser1@example.com", "password": "password123",
        "profile": {"name": "Test User One", "slack_id": "U0000USER1", "role": UserRole.DEVELOPER, "team": "Alpha"}
    },
    {
        "email": "testmanager1@example.com", "password": "password123",
        "profile": {"name": "Test Manager One", "slack_id": "U000MANAGER1", "role": UserRole.MANAGER, "team": "Core"}
    },
    {
        "email": "testadmin1@example.com", "password": "password123",
        "profile": {"name": "Test Admin One", "slack_id": "U000ADMIN1", "role": UserRole.ADMIN, "team": "Platform"}
    }
]

async def seed_users():
    print("\\n--- Seeding Users (using admin.create_user with email_confirm: False) ---")
    created_user_objects = []

    for user_def in test_users_data:
        email = user_def["email"]
        password = user_def["password"]
        profile_data = user_def["profile"] # We'll use this for the public.users update later
        
        print(f"Processing user: {email}...")
        
        auth_user_id = None
        # Check if user already exists in public.users table by email first
        existing_public_user = await user_repo.get_user_by_email(email)
        if existing_public_user:
            auth_user_id = existing_public_user.id
            print(f"  User {email} already has a public profile with ID: {auth_user_id}. Will update profile.")
        else:
            print(f"  User {email} not found in public profiles. Attempting to create auth user via admin API (email_confirm: False)...")
            try:
                user_attributes = {
                    "email": email,
                    "password": password,
                    "email_confirm": False, # Changed to False to minimize email service interaction
                    "user_metadata": { # Keep minimal or empty if trigger doesn't rely on it heavily
                        # 'initial_name': profile_data.get("name") 
                    }
                }
                # The admin.create_user should return the newly created user object
                created_auth_user_response = await asyncio.to_thread(
                    supabase_admin.auth.admin.create_user,
                    user_attributes
                )
                
                # Check the response structure for the actual user object or error
                # Based on supabase-py source, response from create_user is a UserResponse object
                # which should contain the user if successful.
                if created_auth_user_response and hasattr(created_auth_user_response, 'id') and created_auth_user_response.id:
                    auth_user_id = created_auth_user_response.id
                    print(f"  Auth user created via admin API for {email} with ID: {auth_user_id}. Trigger should create public profile.")
                    await asyncio.sleep(1) # Give a moment for the trigger
                else:
                    # This path might be taken if create_user returns something unexpected on failure
                    # without raising an exception that the `except` block below catches.
                    print(f"  admin.create_user for {email} did not return a user object with an ID. Response: {created_auth_user_response}")
                    # Try to fetch by email in case it was created but response was odd
                    check_again = await user_repo.get_user_by_email(email)
                    if check_again:
                        auth_user_id = check_again.id
                        print(f"  Found public profile for {email} after create_user attempt with ID: {auth_user_id}")
                    else:
                        print(f"  Skipping {email} as auth user creation via admin API seems to have failed and not found by email.")
                        continue

            except Exception as e:
                # More specific error checking for user already existing
                if (hasattr(e, 'status') and e.status == 400 and hasattr(e, 'message') and "User already exists" in e.message) or \
                   (hasattr(e, 'message') and ("User already registered" in str(e.message) or "already exists" in str(e.message).lower())): # Broader check
                    print(f"  Auth user {email} already exists in auth.users (admin.create_user error: {e}). Attempting to fetch public profile.")
                    refetched_public_user = await user_repo.get_user_by_email(email)
                    if refetched_public_user:
                        auth_user_id = refetched_public_user.id
                        print(f"  Found existing public profile for {email} with ID: {auth_user_id} after admin create attempt.")
                    else:
                        print(f"  Auth user {email} exists, but NO public profile found. Manual check needed or trigger issue.")
                        continue 
                else:
                    print(f"  Exception during admin.create_user for {email}: {type(e).__name__} - {e}")
                    # Log more details of the exception if possible
                    if hasattr(e, 'message'): print(f"    Error message: {e.message}")
                    if hasattr(e, 'status'): print(f"    Error status: {e.status}")
                    if hasattr(e, 'code'): print(f"    Error code: {e.code}")
                    continue 

        if not auth_user_id:
            print(f"  Failed to obtain or create auth_user_id for {email}. Skipping profile actions.")
            continue

        # Update/Create public.users profile
        profile_update_data = {
            "name": profile_data.get("name"),
            "slack_id": profile_data.get("slack_id"),
            "role": profile_data.get("role", UserRole.USER),
            "team": profile_data.get("team"),
            "avatar_url": profile_data.get("avatar_url"),
            "email": email
        }
        profile_update_data_cleaned = {k: v for k, v in profile_update_data.items() if v is not None}
        
        public_user_to_process = await user_repo.get_user_by_id(auth_user_id)
        
        if public_user_to_process:
            print(f"  Updating existing public profile for user ID {auth_user_id}.")
            updated_user = await user_repo.update_user(auth_user_id, profile_update_data_cleaned)
            if updated_user:
                 created_user_objects.append(updated_user)
                 print(f"  Successfully updated public profile for {updated_user.email}.")
            else:
                 print(f"  Profile update for ID {auth_user_id} returned None. Fetching user to confirm state.")
                 refetched_user = await user_repo.get_user_by_id(auth_user_id)
                 if refetched_user:
                    created_user_objects.append(refetched_user)
                    print(f"  User {refetched_user.email} confirmed to exist after update attempt.")
                 else:
                    print(f"  Failed to update and then fetch public profile for ID {auth_user_id}.")
        else:
            print(f"  Public profile for {auth_user_id} not found by ID after auth user creation. Creating new public profile.")
            user_model_data = User(id=UUID(str(auth_user_id)), **profile_update_data_cleaned)
            created_public_user = await user_repo.create_user(user_model_data)
            if created_public_user:
                created_user_objects.append(created_public_user)
                print(f"  Successfully created public profile for {created_public_user.email}.")
            else:
                print(f"  Failed to create public profile for user ID {auth_user_id}.")

    return created_user_objects


async def seed_tasks(users: List[User]):
    print("\\n--- Seeding Tasks ---")
    if not users:
        print("  No users provided to seed tasks. Skipping.")
        return []

    created_tasks_objects = []
    
    dev_user = next((u for u in users if u.role == UserRole.DEVELOPER), users[0] if users else None)
    manager_user = next((u for u in users if u.role == UserRole.MANAGER), users[-1] if users else None)

    if not dev_user or not manager_user:
        print("  Could not find suitable developer/manager users for task assignment. Skipping task seeding.")
        return []

    sample_tasks_data = [
        {
            "title": "Implement Feature Alpha Login", "description": "Detailed description for feature Alpha login flow.",
            "assignee_id": dev_user.id, "responsible_id": dev_user.id, "accountable_id": manager_user.id,
            "creator_id": manager_user.id, "status": TaskStatus.ASSIGNED, "priority": "HIGH",
            "due_date": datetime.now(timezone.utc) + timedelta(days=7)
        },
        {
            "title": "Fix Bug #1024 - User Profile Crash", "description": "Investigate and fix critical bug causing profile page to crash.",
            "assignee_id": dev_user.id, "responsible_id": dev_user.id, "accountable_id": manager_user.id,
            "creator_id": manager_user.id, "status": TaskStatus.IN_PROGRESS, "priority": "CRITICAL",
            "tags": ["bugfix", "critical", "profile"], "estimated_hours": Decimal("8.5")
        },
        {
            "title": "Write API Documentation for /tasks", "description": "User and developer documentation for all /tasks API endpoints.",
            "assignee_id": dev_user.id, "responsible_id": dev_user.id, "accountable_id": manager_user.id,
            "creator_id": manager_user.id, "status": TaskStatus.BLOCKED, "priority": "MEDIUM",
            "blocked": True, "blocked_reason": "Waiting for final API spec from Project Lead.",
            "consulted_ids": [manager_user.id] 
        }
    ]

    for task_data_dict in sample_tasks_data:
        # Ensure all UUIDs are actual UUID objects from Pydantic model fields
        task_data_dict["assignee_id"] = UUID(str(task_data_dict["assignee_id"]))
        task_data_dict["responsible_id"] = UUID(str(task_data_dict["responsible_id"]))
        task_data_dict["accountable_id"] = UUID(str(task_data_dict["accountable_id"]))
        task_data_dict["creator_id"] = UUID(str(task_data_dict["creator_id"]))
        if "consulted_ids" in task_data_dict and task_data_dict["consulted_ids"]:
            task_data_dict["consulted_ids"] = [UUID(str(uid)) for uid in task_data_dict["consulted_ids"]]

        # Create Task Pydantic model instance
        task_to_create = Task(**task_data_dict)
        
        print(f"  Creating task: {task_to_create.title}...")
        created_task_db = await task_repo.create_task(task_to_create)
        if created_task_db:
            print(f"    Successfully created task '{created_task_db.title}' (ID: {created_task_db.id})")
            created_tasks_objects.append(created_task_db)
        else:
            print(f"    Failed to create task: {task_to_create.title}")
            
    return created_tasks_objects

async def get_user_jwt(email, password):
    print(f"\\n--- Attempting to sign in user {email} to get JWT ---")
    try:
        response = await asyncio.to_thread(
            supabase_admin.auth.sign_in_with_password,
            {"email": email, "password": password}
        )
        if response.session and response.session.access_token:
            print(f"  Successfully signed in {email}.")
            print(f"  Access Token (JWT) for {email}: Bearer {response.session.access_token}") 
            return response.session.access_token
        elif response.error:
            print(f"  Error signing in {email}: {response.error}")
        else:
            # Handle cases where response itself might not conform to expected structure
            print(f"  Unknown error or unexpected response structure during sign in for {email}. Response: {vars(response) if response else 'None'}")
    except Exception as e:
        print(f"  Exception during sign in for {email}: {e}")
    return None

async def main():
    print("Starting Supabase data seeding script...")

    seeded_users = await seed_users()
    if not seeded_users:
        print("User seeding did not result in any usable user objects. Aborting further seeding.")
        return

    print("\\nSuccessfully processed users (created/updated public profiles):")
    for user_obj in seeded_users:
        role_display = user_obj.role 
        if hasattr(user_obj.role, 'value'): 
            role_display = user_obj.role.value
        if role_display is None:
            role_display = 'N/A'
        print(f"  - ID: {user_obj.id}, Email: {user_obj.email}, Name: {user_obj.name}, Role: {role_display}")

    seeded_tasks = await seed_tasks(seeded_users)
    if seeded_tasks:
        print("\\nSuccessfully seeded tasks:")
        for task_obj in seeded_tasks:
            status_display = task_obj.status
            if hasattr(task_obj.status, 'value'):
                status_display = task_obj.status.value
            if status_display is None:
                status_display = 'N/A'

            print(f"  - ID: {task_obj.id}, Title: {task_obj.title}, Status: {status_display}, Assignee: {task_obj.assignee_id}")
    
    if seeded_users:
        user_to_login_def = test_users_data[0] 
        print(f"\\nAttempting to get JWT for primary test user: {user_to_login_def['email']}")
        await get_user_jwt(user_to_login_def["email"], user_to_login_def["password"])

    print("\\nData seeding script finished.")
    print("You can now use the printed JWT (if successful) to test authenticated API endpoints.")
    print("Make sure your FastAPI server is running.")

if __name__ == "__main__":
    asyncio.run(main()) 