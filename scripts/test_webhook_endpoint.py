#!/usr/bin/env python3
"""
Test webhook endpoint availability
"""

import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)

# Test webhook status endpoint first
status_url = "http://localhost:8000/api/v1/webhooks/github/status"
print(f"Testing webhook status endpoint: {status_url}")

try:
    response = requests.get(status_url)
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {response.json()}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Test webhook endpoint with minimal payload
print("\n" + "="*50)
print("Testing webhook endpoint with minimal payload...")

webhook_url = "http://localhost:8000/api/v1/webhooks/github"
test_payload = {"test": "minimal"}
headers = {
    "X-GitHub-Event": "ping",
    "Content-Type": "application/json"
}

try:
    response = requests.post(webhook_url, json=test_payload, headers=headers)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")