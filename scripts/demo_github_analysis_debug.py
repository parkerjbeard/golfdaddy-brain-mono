#!/usr/bin/env python3
"""
Demo GitHub Analysis with Debug Logging - Fetches real commit and sends to webhook
"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv
import json
from datetime import datetime
import traceback

# Load environment variables from backend/.env
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
print(f"[DEBUG] Looking for .env at: {backend_env_path}")
if backend_env_path.exists():
    load_dotenv(backend_env_path)
    print(f"[DEBUG] ✓ Loaded .env file")
else:
    print(f"[DEBUG] ✗ No .env file found")

# Get environment variables
API_BASE_URL = os.getenv("VITE_API_URL", "http://localhost:8000")
BACKEND_HOST = os.getenv("BACKEND_HOST", "localhost")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8001")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

print(f"[DEBUG] Environment variables:")
print(f"  VITE_API_URL: {API_BASE_URL}")
print(f"  BACKEND_HOST: {BACKEND_HOST}")
print(f"  BACKEND_PORT: {BACKEND_PORT}")
print(f"  GITHUB_TOKEN: {'✓ Found' if GITHUB_TOKEN else '✗ Not found'}")

if not GITHUB_TOKEN:
    print("\nError: GITHUB_TOKEN not found in backend/.env")
    sys.exit(1)

print("\nDemo: GitHub Commit Analysis (Debug Mode)")
print("=" * 50)

# Check backend connectivity
print("\n[DEBUG] Checking backend connectivity...")

# Try different URL patterns
url_patterns = [
    f"{API_BASE_URL}/health",
    f"{API_BASE_URL}/api/v1/health",
    f"http://{BACKEND_HOST}:{BACKEND_PORT}/health",
    f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/v1/health",
    f"http://localhost:8001/health",
    f"http://localhost:8001/api/v1/health"
]

working_base_url = None
for url in url_patterns:
    try:
        print(f"[DEBUG] Trying: {url}")
        response = requests.get(url, timeout=2)
        print(f"[DEBUG]   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"[DEBUG]   ✓ Success! Response: {response.text}")
            # Extract base URL
            if "/api/v1/health" in url:
                working_base_url = url.replace("/api/v1/health", "")
            elif "/health" in url:
                working_base_url = url.replace("/health", "")
            break
    except requests.exceptions.ConnectionError:
        print(f"[DEBUG]   ✗ Connection refused")
    except requests.exceptions.Timeout:
        print(f"[DEBUG]   ✗ Timeout")
    except Exception as e:
        print(f"[DEBUG]   ✗ Error: {e}")

if not working_base_url:
    print("\n✗ Could not connect to backend at any URL")
    print("Make sure the backend is running: cd backend && uvicorn app.main:app --port 8001")
    sys.exit(1)

print(f"\n[DEBUG] Using base URL: {working_base_url}")

# Check webhook endpoint
print("\n[DEBUG] Checking webhook endpoint...")
webhook_urls = [
    f"{working_base_url}/api/v1/webhooks/github",
    f"{working_base_url}/webhooks/github",
    f"{working_base_url}/api/webhooks/github"
]

for webhook_url in webhook_urls:
    try:
        print(f"[DEBUG] Checking: {webhook_url}")
        # Try OPTIONS request first
        response = requests.options(webhook_url, timeout=2)
        print(f"[DEBUG]   OPTIONS status: {response.status_code}")
        print(f"[DEBUG]   Allowed methods: {response.headers.get('Allow', 'Not specified')}")
    except Exception as e:
        print(f"[DEBUG]   OPTIONS failed: {e}")

# Step 1: Get latest commit from GitHub
print("\n\nStep 1: Fetching latest commit from GitHub...")
headers = {"Authorization": f"token {GITHUB_TOKEN}"}
repo_owner = "parkerjbeard"
repo_name = "golfdaddy-brain-mono"

print(f"[DEBUG] Repository: {repo_owner}/{repo_name}")

# Get latest commit
response = requests.get(
    f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits",
    headers=headers,
    params={"per_page": 1}
)

print(f"[DEBUG] GitHub API status: {response.status_code}")

if response.status_code != 200:
    print(f"✗ Failed to fetch commits: {response.status_code}")
    print(f"[DEBUG] Response: {response.text}")
    sys.exit(1)

commits = response.json()
if not commits:
    print("✗ No commits found")
    sys.exit(1)

latest_commit = commits[0]
commit_sha = latest_commit['sha']
commit_message = latest_commit['commit']['message']
author_name = latest_commit['commit']['author']['name']
author_email = latest_commit['commit']['author']['email']
commit_date = latest_commit['commit']['author']['date']

print(f"✓ Found latest commit:")
print(f"  SHA: {commit_sha[:7]}")
print(f"  Message: {commit_message.split('\\n')[0][:60]}...")
print(f"  Author: {author_name}")
print(f"  Date: {commit_date}")

# Step 2: Get commit details
print("\nStep 2: Fetching commit details...")
response = requests.get(
    f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{commit_sha}",
    headers=headers
)

if response.status_code != 200:
    print(f"✗ Failed to fetch commit details: {response.status_code}")
    sys.exit(1)

commit_details = response.json()
files = commit_details.get('files', [])

print(f"✓ Got commit details:")
print(f"  Files changed: {len(files)}")
print(f"  Additions: {commit_details['stats']['additions']}")
print(f"  Deletions: {commit_details['stats']['deletions']}")

# Step 3: Create webhook payload
print("\nStep 3: Creating webhook payload...")
webhook_payload = {
    "ref": "refs/heads/main",
    "before": commit_details.get('parents', [{}])[0].get('sha', '0' * 40),
    "after": commit_sha,
    "repository": {
        "id": 123456789,
        "name": repo_name,
        "full_name": f"{repo_owner}/{repo_name}",
        "url": f"https://github.com/{repo_owner}/{repo_name}",
        "html_url": f"https://github.com/{repo_owner}/{repo_name}"
    },
    "pusher": {
        "login": repo_owner,
        "name": author_name,
        "email": author_email
    },
    "commits": [{
        "id": commit_sha,
        "distinct": True,
        "message": commit_message,
        "timestamp": commit_date,
        "url": latest_commit['html_url'],
        "author": {
            "name": author_name,
            "email": author_email,
            "username": repo_owner
        },
        "committer": {
            "name": author_name,
            "email": author_email,
            "username": repo_owner
        },
        "added": [f['filename'] for f in files if f['status'] == 'added'],
        "removed": [f['filename'] for f in files if f['status'] == 'removed'],
        "modified": [f['filename'] for f in files if f['status'] == 'modified']
    }],
    "head_commit": {
        "id": commit_sha,
        "distinct": True,
        "message": commit_message,
        "timestamp": commit_date,
        "url": latest_commit['html_url'],
        "author": {
            "name": author_name,
            "email": author_email,
            "username": repo_owner
        },
        "committer": {
            "name": author_name,
            "email": author_email,
            "username": repo_owner
        },
        "added": [f['filename'] for f in files if f['status'] == 'added'],
        "removed": [f['filename'] for f in files if f['status'] == 'removed'],
        "modified": [f['filename'] for f in files if f['status'] == 'modified']
    }
}

print(f"\n[DEBUG] Payload preview:")
print(json.dumps(webhook_payload, indent=2)[:500] + "...")

# Step 4: Send to webhook
print("\nStep 4: Sending to webhook endpoint...")

# Try all possible webhook URLs
webhook_urls = [
    f"{working_base_url}/api/v1/webhooks/github",
    f"{working_base_url}/webhooks/github",
    f"{working_base_url}/api/webhooks/github"
]

success = False
for webhook_url in webhook_urls:
    print(f"\n[DEBUG] Trying webhook URL: {webhook_url}")
    
    # Add GitHub webhook headers
    webhook_headers = {
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": f"demo-{datetime.now().isoformat()}",
        "Content-Type": "application/json"
    }
    
    print(f"[DEBUG] Headers: {json.dumps(webhook_headers, indent=2)}")
    
    try:
        response = requests.post(
            webhook_url,
            json=webhook_payload,
            headers=webhook_headers,
            timeout=10
        )
        
        print(f"[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response headers: {dict(response.headers)}")
        print(f"[DEBUG] Response body: {response.text[:500]}...")
        
        if response.status_code == 200:
            print("\n✓ Webhook processed successfully!")
            result = response.json()
            
            if result.get('processed'):
                print("\n📊 Analysis Results:")
                for commit in result['processed']:
                    print(f"\n  Commit: {commit['commit_hash'][:7]}")
                    print(f"  Effort Score: {commit.get('effort_score', 'N/A')}/10")
                    print(f"  Complexity: {commit.get('complexity', 'N/A')}")
                    print(f"  AI Hours: {commit.get('ai_hours', 'N/A')}")
                    print(f"  Categories: {', '.join(commit.get('categories', []))}")
                    
                    if commit.get('ai_analysis'):
                        print(f"\n  AI Analysis:")
                        print(f"  {commit['ai_analysis'][:200]}...")
            else:
                print("\n⚠️ No commits were processed")
                if result.get('errors'):
                    print("\nErrors:")
                    for error in result['errors']:
                        print(f"  - {error['hash'][:7]}: {error['error']}")
            
            success = True
            break
        elif response.status_code == 404:
            print(f"✗ 404 Not Found - Endpoint doesn't exist at this URL")
            # Try to parse error message
            try:
                error_data = response.json()
                print(f"[DEBUG] Error details: {json.dumps(error_data, indent=2)}")
            except:
                pass
        else:
            print(f"✗ Webhook failed: {response.status_code}")
            print(f"[DEBUG] Full response: {response.text}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Connection error: Could not connect to {webhook_url}")
        print(f"[DEBUG] Error: {e}")
    except requests.exceptions.Timeout:
        print(f"✗ Request timeout")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        print(f"[DEBUG] Stack trace:")
        traceback.print_exc()

if not success:
    print("\n✗ Failed to send webhook to any URL")
    print("\nPossible issues:")
    print("1. Backend is not running on the expected port")
    print("2. The webhook endpoint path has changed")
    print("3. Authentication is required for the webhook endpoint")
    print("4. The backend routes are not properly configured")
    
    print("\n[DEBUG] To check available routes, run:")
    print("  cd backend && python -c \"from app.main import app; print([r.path for r in app.routes])\"")

print("\n" + "=" * 50)