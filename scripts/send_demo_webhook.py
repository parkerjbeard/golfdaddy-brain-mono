#!/usr/bin/env python3
"""Send demo webhook to development endpoint"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv
import json

# Load environment variables from backend/.env
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)

API_BASE_URL = os.getenv("VITE_API_URL", "http://localhost:8000")

print("Sending Demo Webhook")
print("=" * 50)

# Create a simplified webhook payload matching PushEvent schema
webhook_payload = {
    "ref": "refs/heads/main",
    "before": "0000000000000000000000000000000000000000",
    "after": "9a408d4fbfba8b72e8cb5f67c6f123456789abcd",
    "repository": {
        "id": 123456789,
        "name": "golfdaddy-brain-mono",
        "full_name": "parkerjbeard/golfdaddy-brain-mono",
        "url": "https://github.com/parkerjbeard/golfdaddy-brain-mono",
        "html_url": "https://github.com/parkerjbeard/golfdaddy-brain-mono"
    },
    "pusher": {
        "login": "parkerjbeard",
        "name": "Parker Beard",
        "email": "demo@example.com"
    },
    "commits": [{
        "id": "9a408d4fbfba8b72e8cb5f67c6f123456789abcd",
        "distinct": True,
        "message": "Add official apology from Claude for the git history chaos",
        "timestamp": "2025-06-17T17:34:29Z",
        "url": "https://github.com/parkerjbeard/golfdaddy-brain-mono/commit/9a408d4",
        "author": {
            "name": "Parker Beard",
            "email": "demo@example.com",
            "username": "parkerjbeard"
        },
        "committer": {
            "name": "Parker Beard",
            "email": "demo@example.com",
            "username": "parkerjbeard"
        },
        "added": [],
        "removed": [],
        "modified": ["README.md"]
    }],
    "head_commit": {
        "id": "9a408d4fbfba8b72e8cb5f67c6f123456789abcd",
        "distinct": True,
        "message": "Add official apology from Claude for the git history chaos",
        "timestamp": "2025-06-17T17:34:29Z",
        "url": "https://github.com/parkerjbeard/golfdaddy-brain-mono/commit/9a408d4",
        "author": {
            "name": "Parker Beard",
            "email": "demo@example.com",
            "username": "parkerjbeard"
        },
        "committer": {
            "name": "Parker Beard",
            "email": "demo@example.com",
            "username": "parkerjbeard"
        },
        "added": [],
        "removed": [],
        "modified": ["README.md"]
    }
}

# Try development endpoint first
dev_url = f"{API_BASE_URL}/dev/test-webhook"
print(f"\nTrying development endpoint: {dev_url}")

response = requests.post(
    dev_url,
    json=webhook_payload,
    headers={"Content-Type": "application/json"}
)

if response.status_code == 200:
    print("✓ Webhook sent successfully to dev endpoint")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
else:
    print(f"✗ Dev endpoint failed: {response.status_code}")
    print(f"Response: {response.text}")
    
    # Try the regular endpoint without signature
    print("\nTrying regular endpoint without signature...")
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
    
    if response.status_code in [200, 202]:
        print("✓ Webhook sent successfully")
        print(f"Response: {response.json()}")
    else:
        print(f"✗ Failed: {response.status_code}")
        print(f"Response: {response.text}")

print("\n" + "=" * 50)
print("Check http://localhost:8080/daily-reports for results")