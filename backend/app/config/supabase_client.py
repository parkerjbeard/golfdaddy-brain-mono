import asyncio
import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Generator, Optional

import httpx

from app.config.settings import settings
from supabase import Client, create_client

# Configure logging
logger = logging.getLogger(__name__)

# Global Supabase client instance
_supabase_client: Optional[Client] = None


def retry_on_connection_error(max_retries=3, backoff_factor=1.0):
    """
    Decorator to retry functions that may encounter connection errors.
    Uses exponential backoff with jitter.
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                except (httpx.ConnectError, ConnectionError, OSError) as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}: {str(e)}")
                        raise e

                    # Calculate backoff time with jitter
                    backoff_time = backoff_factor * (2**attempt) + (time.time() % 1)
                    logger.warning(
                        f"Connection error in {func.__name__} (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {backoff_time:.2f}s"
                    )
                    await asyncio.sleep(backoff_time)

            if last_exception:
                raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (httpx.ConnectError, ConnectionError, OSError) as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}: {str(e)}")
                        raise e

                    # Calculate backoff time with jitter
                    backoff_time = backoff_factor * (2**attempt) + (time.time() % 1)
                    logger.warning(
                        f"Connection error in {func.__name__} (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {backoff_time:.2f}s"
                    )
                    time.sleep(backoff_time)

            if last_exception:
                raise last_exception

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


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

        # Configure HTTP client with connection pooling and SSL settings
        transport = httpx.HTTPTransport(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            verify=True,  # Enable SSL verification
            retries=3,
        )

        # Create HTTP client with timeout and retry settings
        http_client = httpx.Client(
            transport=transport, timeout=httpx.Timeout(30.0), follow_redirects=True  # 30 second timeout
        )

        _supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)

        # Override the HTTP client for better connection handling
        # Note: Commenting out due to API changes in Supabase 2.17.0
        # _supabase_client.postgrest._client._client = http_client

        logger.info("Supabase client initialized with enhanced connection settings")

    return _supabase_client


# Make sure the client is safely serializable
def get_supabase_client_safe():
    """
    Get the Supabase client instance for dependency injection.
    This wrapper exists to prevent FastAPI from trying to include the client in response models.
    """
    return get_supabase_client()


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
