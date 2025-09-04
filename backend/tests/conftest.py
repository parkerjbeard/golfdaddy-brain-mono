"""
Shared fixtures for all tests in the project.

This file contains pytest fixtures that are accessible to all tests.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
# Removed SQLAlchemy-based test DB fixtures after consolidating to Supabase

from app.config.settings import settings
from app.config.supabase_client import get_supabase_client
from app.main import app

# Add the project root to the path so that we can import from the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


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
            "SUPABASE_URL must be set to a valid Supabase URL. " "Check your environment variables or .env file."
        )

    if not settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_SERVICE_KEY == "your-service-role-key-here":
        raise ValueError(
            "SUPABASE_SERVICE_KEY must be set to a valid service role key. "
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
        id="00000000-0000-0000-0000-000000000000", email="test@example.com", app_metadata={"role": "user"}
    )

    mock_auth.sign_in_with_password.return_value = mock_auth_response
    mock_auth.get_user.return_value = mock_auth_response
    mock_auth.refresh_session.return_value = mock_auth_response

    mock_client.auth = mock_auth

    # Create patch for the get_supabase_client function
    with patch("app.config.supabase_client.get_supabase_client", return_value=mock_client):
        # Also patch any direct imports of the function
        with patch("app.repositories.user_repository.get_supabase_client_safe", return_value=mock_client):
            with patch("app.repositories.task_repository.get_supabase_client", return_value=mock_client):
                yield mock_client


@pytest.fixture(scope="function")
def client(mock_supabase_client):
    """Create a FastAPI TestClient with mocked Supabase dependency."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def event_loop():
    """Provide a session-scoped event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ========== Doc Agent Specific Fixtures ==========


@pytest.fixture
def sample_diff():
    """Sample git diff for testing."""
    return """diff --git a/src/api.py b/src/api.py
index abc1234..def5678 100644
--- a/src/api.py
+++ b/src/api.py
@@ -10,6 +10,18 @@ def authenticate(token: str) -> bool:
     return token.startswith("valid_")
 
 
+def get_user_profile(user_id: str) -> dict:
+    \"\"\"
+    Get user profile by ID.
+    
+    Args:
+        user_id: The user's unique identifier
+        
+    Returns:
+        User profile dictionary
+    \"\"\"
+    return {"id": user_id, "name": "Test User"}
+
+
 def main():
     pass"""


@pytest.fixture
def sample_doc_patch():
    """Sample documentation patch for testing."""
    return """--- a/docs/api.md
+++ b/docs/api.md
@@ -5,3 +5,15 @@
 ### authenticate(token: str) -> bool
 Authenticates a user with the provided token.
+
+### get_user_profile(user_id: str) -> dict
+Retrieves user profile information.
+
+**Parameters:**
+- `user_id` (str): The user's unique identifier
+
+**Returns:**
+- dict: User profile containing id and name
+
+**Example:**
+```python
+profile = get_user_profile("user123")
+```"""


# Slack-related fixtures removed; Slack tests are no longer in scope.


@pytest.fixture
def sample_github_webhook():
    """Sample GitHub webhook payload."""
    return {
        "ref": "refs/heads/main",
        "after": "def1234567890",
        "repository": {
            "name": "test-repo",
            "full_name": "test-owner/test-repo",
            "clone_url": "https://github.com/test-owner/test-repo.git",
        },
        "commits": [
            {
                "id": "def1234567890",
                "message": "Add user profile endpoint",
                "author": {
                    "name": "Test User",
                    "email": "test@example.com",
                },
                "modified": ["src/api.py"],
            }
        ],
    }


## DocApproval fixture removed with documentation agent cleanup


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test documentation patch"

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    return mock_client


@pytest.fixture
def mock_github_client():
    """Mock GitHub client for testing."""
    mock_client = MagicMock()
    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_repo.create_pull = MagicMock(return_value=MagicMock(html_url="https://github.com/test/pr/123"))

    mock_client.get_repo = MagicMock(return_value=mock_repo)

    return mock_client


# Slack service mock removed.


# ========== Test Markers ==========


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "github: mark test as requiring GitHub API")
    config.addinivalue_line("markers", "openai: mark test as requiring OpenAI API")
    # doc_agent marker removed
