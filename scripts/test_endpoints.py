#!/usr/bin/env python3
"""Test available endpoints"""

import requests

base_url = "http://localhost:8000"

endpoints = [
    "/health",
    "/api/v1/webhooks/github",
    "/dev/test-webhook",
    "/api/webhooks/github",
    "/webhooks/github",
]

print("Testing endpoints...")
print("=" * 50)

for endpoint in endpoints:
    url = f"{base_url}{endpoint}"
    try:
        # Try GET first
        response = requests.get(url, timeout=2)
        print(f"GET  {endpoint}: {response.status_code}")
        
        # Try POST
        response = requests.post(url, json={"test": "data"}, timeout=2)
        print(f"POST {endpoint}: {response.status_code}")
    except Exception as e:
        print(f"ERR  {endpoint}: {str(e)[:50]}")