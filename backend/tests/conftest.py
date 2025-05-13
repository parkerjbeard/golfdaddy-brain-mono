"""
Shared fixtures for all tests in the project.

This file contains pytest fixtures that are accessible to all tests.
"""
import pytest
import os
import sys
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.config.settings import settings
from app.main import app
from app.config.supabase_client import get_supabase_client

# Add the project root to the path so that we can import from the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Define shared fixtures here
@pytest.fixture
def app_config():
    """Return a base configuration for tests."""
    return {
        "testing": True,
        "debug": True,
    }

@pytest.fixture(scope="session", autouse=True)
def set_test_mode():
    """Set up test mode with Supabase settings."""
    # Save original settings
    original_mode = settings.TESTING_MODE
    
    # Set test mode
    settings.TESTING_MODE = True
    
    # Make sure Supabase URL and key are properly set for testing
    # Convert HttpUrl to string for the 'in' check
    supabase_url_str = str(settings.SUPABASE_URL) 
    if not supabase_url_str or "your-project-ref" in supabase_url_str:
        raise ValueError(
            "SUPABASE_URL must be set to a valid Supabase URL. "
            "Check your environment variables or .env file."
        )
    
    if not settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_SERVICE_ROLE_KEY == "your-service-role-key-here":
        raise ValueError(
            "SUPABASE_SERVICE_ROLE_KEY must be set to a valid service role key. "
            "Check your environment variables or .env file."
        )
    
    yield
    
    # Restore original settings
    settings.TESTING_MODE = original_mode

@pytest.fixture(scope="function")
def mock_supabase_client():
    """
    Create a mock Supabase client for testing.
    
    This avoids making actual requests to Supabase during tests.
    """
    # Create mock Table and Query objects
    mock_query = MagicMock()
    mock_query.execute.return_value = MagicMock(data=[], error=None)
    
    # Create methods that return the mock query
    mock_select = MagicMock(return_value=mock_query)
    mock_insert = MagicMock(return_value=mock_query)
    mock_update = MagicMock(return_value=mock_query)
    mock_delete = MagicMock(return_value=mock_query)
    mock_eq = MagicMock(return_value=mock_query)
    mock_single = MagicMock(return_value=mock_query)
    mock_maybe_single = MagicMock(return_value=mock_query)
    
    # Chain methods
    mock_query.select = mock_select
    mock_query.insert = mock_insert
    mock_query.update = mock_update
    mock_query.delete = mock_delete
    mock_query.eq = mock_eq
    mock_query.single = mock_single
    mock_query.maybe_single = mock_maybe_single
    
    # Create mock Table that returns the mock query
    mock_table = MagicMock()
    mock_table.select.return_value = mock_query
    mock_table.insert.return_value = mock_query
    mock_table.update.return_value = mock_query
    mock_table.delete.return_value = mock_query
    
    # Create mock client that returns the mock table
    mock_client = MagicMock()
    mock_client.table.return_value = mock_table
    
    # Create mock auth with sign_in and get_user methods
    mock_auth = MagicMock()
    mock_session = MagicMock()
    mock_session.access_token = "mock_access_token"
    mock_session.refresh_token = "mock_refresh_token"
    mock_session.expires_in = 3600
    
    mock_auth_response = MagicMock()
    mock_auth_response.session = mock_session
    mock_auth_response.user = MagicMock(
        id="00000000-0000-0000-0000-000000000000",
        email="test@example.com",
        app_metadata={"role": "user"}
    )
    
    mock_auth.sign_in_with_password.return_value = mock_auth_response
    mock_auth.get_user.return_value = mock_auth_response
    mock_auth.refresh_session.return_value = mock_auth_response
    
    mock_client.auth = mock_auth
    
    # Create patch for the get_supabase_client function
    with patch('app.config.supabase_client.get_supabase_client', return_value=mock_client):
        # Also patch any direct imports of the function
        with patch('app.repositories.user_repository.get_supabase_client', return_value=mock_client):
            with patch('app.repositories.task_repository.get_supabase_client', return_value=mock_client):
                yield mock_client

@pytest.fixture(scope="function")
def client(mock_supabase_client):
    """Create a FastAPI TestClient with mocked Supabase dependency."""
    with TestClient(app) as test_client:
        yield test_client 