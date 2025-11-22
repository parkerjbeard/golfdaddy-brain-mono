import sys
import os
from pathlib import Path
from urllib.parse import urlparse

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.config.settings import settings
    db_url = settings.DATABASE_URL
except Exception as e:
    print(f"Error loading settings: {e}")
    sys.exit(1)

if not db_url:
    print("DATABASE_URL is not set or empty.")
    sys.exit(1)

try:
    # Handle asyncpg format if present for parsing
    clean_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(clean_url)
    
    print(f"--- Database Connection Diagnosis ---")
    print(f"Scheme: {parsed.scheme}")
    print(f"Hostname: {parsed.hostname}")
    print(f"Port: {parsed.port}")
    print(f"Username: {parsed.username}")
    print(f"Database: {parsed.path.lstrip('/')}")
    
    if parsed.password:
        print(f"Password: {'*' * len(parsed.password)} (Present)")
    else:
        print(f"Password: (Missing)")

    print("\n--- Analysis ---")
    
    if parsed.port == 6543:
        print("⚠️  Using Port 6543 (Connection Pooler).")
        print("   For migrations, it is often safer to use the Direct Connection (Port 5432).")
        if parsed.username and "." not in parsed.username:
            print("❌ Error: When using port 6543, the username usually needs to be in the format 'user.project_ref'.")
            print(f"   Current username '{parsed.username}' lacks a project reference.")
    
    elif parsed.port == 5432:
        print("✅ Using Port 5432 (Direct Connection).")
        if parsed.username and "." in parsed.username:
             print("ℹ️  Username looks like a pooler username (contains dot). For direct connections, it is usually just 'postgres'.")
    
    print("\n--- Action ---")
    print("Please verify your DATABASE_URL in backend/.env matches your Supabase 'Direct Connection' string.")
    
except Exception as e:
    print(f"Error parsing URL: {e}")
