from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config.supabase_client import get_supabase_client  # Dependency to override
from app.main import app  # Assuming your FastAPI app instance is here
from app.models.user import User, UserRole  # For constructing mock user objects


# Mock Supabase session and user objects
class MockSupabaseSession:
    def __init__(self, access_token, refresh_token=None, expires_in=3600, user=None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.user = user


class MockSupabaseUser:
    def __init__(self, id, email, app_metadata=None, user_metadata=None):
        self.id = id
        self.email = email
        self.app_metadata = app_metadata if app_metadata else {}
        self.user_metadata = user_metadata if user_metadata else {}


@pytest.fixture
def mock_supabase_client():
    mock_client = MagicMock()
    # Mock auth methods
    mock_client.auth.sign_in_with_password = MagicMock()
    mock_client.auth.refresh_session = MagicMock()
    mock_client.auth.get_user = MagicMock()
    mock_client.auth.sign_out = MagicMock()
    # Mock UserRepository methods if used by dependencies
    # This might be needed for the get_current_user dependency
    with patch("app.repositories.user_repository.UserRepository") as MockUserRepository:
        mock_user_repo_instance = MockUserRepository.return_value
        mock_user_repo_instance.get_user_by_id = MagicMock()
        mock_user_repo_instance.create_user = MagicMock()
        yield mock_client


@pytest.fixture
def client(mock_supabase_client):
    # Override the dependency with the mock
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client

    with TestClient(app) as c:
        yield c

    # Clean up dependency overrides
    app.dependency_overrides = {}


# --- Test Cases Will Go Here ---


def test_ping_auth_endpoints_placeholder(client):
    # A simple placeholder to ensure the setup is working
    # Replace with actual tests
    response_login = client.post("/auth/login", json={"email": "test@example.com", "password": "password"})
    # Depending on mock setup, this might be 401 or 500 if not fully mocked yet
    # For now, just check it doesn't crash
    assert response_login.status_code != 404
