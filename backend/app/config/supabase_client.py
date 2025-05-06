from supabase import create_client, Client
from contextlib import contextmanager
from typing import Optional, Generator
import logging

from app.config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Global Supabase client instance
_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """
    Get the Supabase client instance.
    Creates a new client if one doesn't exist.
    
    Returns:
        Client: The Supabase client instance.
    """
    global _supabase_client
    
    if _supabase_client is None:
        if not settings.supabase_url or not settings.supabase_service_key:
            raise ValueError("Supabase URL and service role key must be set")
        
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )
        logger.info("Supabase client initialized")
    
    return _supabase_client

@contextmanager
def get_supabase() -> Generator[Client, None, None]:
    """
    Context manager for getting a Supabase client.
    
    Yields:
        Client: The Supabase client instance.
    """
    client = get_supabase_client()
    try:
        yield client
    except Exception as e:
        logger.error(f"Error using Supabase client: {e}")
        raise 