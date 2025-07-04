#!/usr/bin/env python3
"""Test imports for demo script"""

import sys
from pathlib import Path

print("Python path:")
for p in sys.path:
    print(f"  {p}")

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
print(f"\nBackend path: {backend_path}")
print(f"Exists: {backend_path.exists()}")

if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))
    print("Added to path")

print("\nTrying imports...")

try:
    from app.config.database import get_db
    print("✓ Successfully imported get_db")
except Exception as e:
    print(f"✗ Failed to import get_db: {e}")

try:
    from app.services.commit_analysis_service import CommitAnalysisService
    print("✓ Successfully imported CommitAnalysisService")
except Exception as e:
    print(f"✗ Failed to import CommitAnalysisService: {e}")

try:
    import asyncio
    print("✓ Successfully imported asyncio")
except Exception as e:
    print(f"✗ Failed to import asyncio: {e}")

print("\nChecking pydantic_settings...")
try:
    import pydantic_settings
    print(f"✓ pydantic_settings version: {pydantic_settings.__version__}")
except Exception as e:
    print(f"✗ Failed to import pydantic_settings: {e}")

print("\nChecking environment...")
import os
print(f"GITHUB_TOKEN: {'✓ Set' if os.getenv('GITHUB_TOKEN') else '✗ Not set'}")
print(f"OPENAI_API_KEY: {'✓ Set' if os.getenv('OPENAI_API_KEY') else '✗ Not set'}")
print(f"SUPABASE_URL: {'✓ Set' if os.getenv('SUPABASE_URL') else '✗ Not set'}")
print(f"SUPABASE_SERVICE_KEY: {'✓ Set' if os.getenv('SUPABASE_SERVICE_KEY') else '✗ Not set'}")