#!/usr/bin/env python3
"""Simple script to create demo user via API"""

import requests
import json

def create_demo_user():
    """Create demo user via API"""
    
    # First, try to register the user
    print("Creating demo user...")
    
    register_url = "http://localhost:8000/api/v1/auth/register"
    login_url = "http://localhost:8000/api/v1/auth/login"
    
    user_data = {
        "email": "testadmin1@example.com",
        "password": "password123",
        "name": "Demo Admin"
    }
    
    # Try to register
    print(f"Attempting to register user: {user_data['email']}")
    try:
        response = requests.post(register_url, json=user_data)
        
        if response.status_code == 200:
            print("✅ User registered successfully!")
        elif response.status_code == 400 and "already registered" in response.text:
            print("ℹ️  User already exists")
        else:
            print(f"Registration response: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Registration error: {e}")
    
    # Now try to login to verify
    print(f"\nTesting login for: {user_data['email']}")
    try:
        login_data = {
            "email": user_data["email"],
            "password": user_data["password"]
        }
        response = requests.post(login_url, json=login_data)
        
        if response.status_code == 200:
            print("✅ Login successful! User is ready for demo")
            data = response.json()
            if "access_token" in data:
                print("✅ Got access token")
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Login error: {e}")
    
    print("\n" + "="*50)
    print("Demo User Credentials:")
    print(f"Email: {user_data['email']}")
    print(f"Password: {user_data['password']}")
    print("="*50)

if __name__ == "__main__":
    create_demo_user()