#!/usr/bin/env python3
"""
Demo GitHub Analysis - Fetches real commit and sends to webhook
"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv
import json
from datetime import datetime
import hmac
import hashlib

# Load environment variables from backend/.env
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)

API_BASE_URL = os.getenv("VITE_API_URL", "http://localhost:8000")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN not found in backend/.env")
    sys.exit(1)

print("Demo: GitHub Commit Analysis")
print("=" * 50)

# Step 1: Get latest commit from GitHub
print("\nStep 1: Fetching latest commit from GitHub...")
headers = {"Authorization": f"token {GITHUB_TOKEN}"}
repo_owner = "parkerjbeard"
repo_name = "golfdaddy-brain-mono"

# Get latest commit
response = requests.get(
    f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits",
    headers=headers,
    params={"per_page": 1}
)

if response.status_code != 200:
    print(f"✗ Failed to fetch commits: {response.status_code}")
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

# Step 4: Send to webhook
print("\nStep 4: Sending to webhook endpoint...")
webhook_url = f"{API_BASE_URL}/api/v1/webhooks/github"

# Create webhook signature if secret is available
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
webhook_body = json.dumps(webhook_payload)

# Add GitHub webhook headers
webhook_headers = {
    "X-GitHub-Event": "push",
    "X-GitHub-Delivery": f"demo-{datetime.now().isoformat()}",
    "Content-Type": "application/json"
}

# Add signature if webhook secret is configured
if GITHUB_WEBHOOK_SECRET:
    signature = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode('utf-8'),
        webhook_body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    webhook_headers["X-Hub-Signature-256"] = f"sha256={signature}"
    print(f"✓ Added webhook signature")
else:
    print("⚠️ No webhook secret found, sending without signature")

response = requests.post(
    webhook_url,
    data=webhook_body,  # Use data instead of json to send raw body
    headers=webhook_headers
)

if response.status_code == 200:
    print("✓ Webhook processed successfully!")
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
else:
    print(f"✗ Webhook failed: {response.status_code}")
    print(f"Response: {response.text}")

print("\n" + "=" * 50)
print("View full results at: http://localhost:8080/daily-reports")