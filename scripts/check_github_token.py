#!/usr/bin/env python3
"""Check GitHub token permissions"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from backend/.env
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN not found in backend/.env")
    sys.exit(1)

print("Checking GitHub Token")
print("=" * 50)

# Check user
headers = {"Authorization": f"token {GITHUB_TOKEN}"}
response = requests.get("https://api.github.com/user", headers=headers)

if response.status_code == 200:
    user = response.json()
    print(f"✓ Authenticated as: {user.get('login')}")
    print(f"  Name: {user.get('name')}")
    print(f"  Email: {user.get('email')}")
else:
    print(f"✗ Authentication failed: {response.status_code}")
    print(f"Response: {response.text}")
    sys.exit(1)

# Check rate limit to see scopes
response = requests.get("https://api.github.com/rate_limit", headers=headers)
if response.status_code == 200:
    print("\n✓ Token is valid")
    # Check response headers for scopes
    scopes = response.headers.get('X-OAuth-Scopes', 'none')
    print(f"  Scopes: {scopes}")

# List repositories
print("\nChecking repository access...")
response = requests.get("https://api.github.com/user/repos", headers=headers, params={"per_page": 5})
if response.status_code == 200:
    repos = response.json()
    print(f"✓ Can access {len(repos)} repositories")
    for repo in repos[:5]:
        print(f"  - {repo['full_name']}")
else:
    print(f"✗ Cannot list repositories: {response.status_code}")

# Try specific repo
print("\nChecking specific repository...")
for repo_path in ["parkerjbeard/golfdaddy-brain", "parkerjbeard/golfdaddy-brain-mono"]:
    response = requests.get(f"https://api.github.com/repos/{repo_path}", headers=headers)
    if response.status_code == 200:
        print(f"✓ Can access: {repo_path}")
    else:
        print(f"✗ Cannot access: {repo_path} (status: {response.status_code})")