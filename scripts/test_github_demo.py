#!/usr/bin/env python3
"""Test GitHub analysis with last commit"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from backend/.env
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)

# Configuration
API_BASE_URL = os.getenv("VITE_API_URL", "http://localhost:8000")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN not found in backend/.env")
    sys.exit(1)

print("Testing GitHub Analysis Demo")
print("=" * 50)

# Step 1: Authenticate with GitHub
print("\nStep 1: Checking GitHub authentication...")
headers = {"Authorization": f"token {GITHUB_TOKEN}"}
response = requests.get("https://api.github.com/user", headers=headers)

if response.status_code == 200:
    user_data = response.json()
    username = user_data.get('login')
    print(f"✓ Authenticated as: {username}")
    
    # Handle case where username from API differs from repo owner
    # Check if the token works with the actual repo
    actual_username = "parkerjbeard"  # from git remote URL
else:
    print(f"✗ GitHub authentication failed: {response.status_code}")
    sys.exit(1)

# Step 2: Get repository info
print("\nStep 2: Checking repository...")
repo_name = "golfdaddy-brain-mono"
response = requests.get(f"https://api.github.com/repos/{actual_username}/{repo_name}", headers=headers)

if response.status_code == 200:
    repo_data = response.json()
    print(f"✓ Found repository: {repo_data['full_name']}")
else:
    print(f"✗ Repository not found: {username}/{repo_name}")
    print(f"Status code: {response.status_code}")
    sys.exit(1)

# Step 3: Get last commit
print("\nStep 3: Fetching last commit...")
response = requests.get(
    f"https://api.github.com/repos/{actual_username}/{repo_name}/commits",
    headers=headers,
    params={"per_page": 1}
)

if response.status_code == 200:
    commits = response.json()
    if commits:
        last_commit = commits[0]
        commit_sha = last_commit['sha']
        commit_message = last_commit['commit']['message']
        author = last_commit['commit']['author']['name']
        date = last_commit['commit']['author']['date']
        
        print(f"✓ Found last commit:")
        print(f"  SHA: {commit_sha[:7]}")
        print(f"  Message: {commit_message.split('\\n')[0][:60]}...")
        print(f"  Author: {author}")
        print(f"  Date: {date}")
    else:
        print("✗ No commits found")
        sys.exit(1)
else:
    print(f"✗ Failed to fetch commits: {response.status_code}")
    sys.exit(1)

# Step 4: Send commit for analysis
print("\nStep 4: Sending commit for AI analysis...")

webhook_payload = {
    "repository": {
        "name": repo_name,
        "full_name": f"{actual_username}/{repo_name}",
        "owner": {
            "login": actual_username
        }
    },
    "commits": [{
        "id": commit_sha,
        "message": commit_message,
        "author": {
            "name": author,
            "email": "demo@example.com"
        },
        "timestamp": date,
        "url": f"https://github.com/{actual_username}/{repo_name}/commit/{commit_sha}"
    }]
}

# Send to webhook endpoint
webhook_url = f"{API_BASE_URL}/api/v1/webhooks/github"
headers = {
    "Content-Type": "application/json",
    "X-GitHub-Event": "push"
}

response = requests.post(
    webhook_url,
    json=webhook_payload,
    headers=headers
)

if response.status_code == 200:
    print("✓ Commit analysis triggered successfully")
    print(f"Response: {response.json()}")
else:
    print(f"✗ Failed to trigger analysis: {response.status_code}")
    print(f"Response: {response.text}")

print("\n" + "=" * 50)
print("Demo complete!")
print(f"\nView results at: http://localhost:8080/daily-reports")