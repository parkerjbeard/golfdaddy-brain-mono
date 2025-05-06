from supabase import create_client, Client
from app.config.settings import settings
import os
from typing import Generator

# Initialize Supabase client
supabase_url: str = str(settings.SUPABASE_URL) # Ensure URL is string
supabase_key: str = settings.SUPABASE_SERVICE_ROLE_KEY

# Check if settings were loaded correctly
if not supabase_url or not supabase_key:
    raise ValueError("Supabase URL and Service Role Key must be set in environment variables.")

# Create the Supabase client instance using the Service Role Key for backend operations
supabase: Client = create_client(supabase_url, supabase_key)

# Optional: Initialize a client with the Anon Key if needed for specific scenarios
# supabase_anon_key: str | None = settings.SUPABASE_ANON_KEY
# supabase_anon: Client | None = None
# if supabase_anon_key:
#     supabase_anon = create_client(supabase_url, supabase_anon_key)

def get_supabase_client() -> Client:
    """Dependency function to get the Supabase client."""
    return supabase

def get_db() -> Generator[Client, None, None]:
    """
    Dependency function to get database client for FastAPI dependency injection.
    This is a wrapper around get_supabase_client that handles the client as a generator.
    
    Yields:
        Client: The Supabase client instance for database operations.
    """
    client = get_supabase_client()
    try:
        yield client
    finally:
        # No need to close the connection with Supabase
        pass