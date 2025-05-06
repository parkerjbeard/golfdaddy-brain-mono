import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import jwt
import time
from datetime import datetime, timedelta, timezone

from app.main import app
from app.auth.slack_auth import SlackAuthManager, SlackUserInfo

@pytest.fixture
def test_client():
    """Create a test client."""
    return TestClient(app)

@pytest.fixture
def mock_slack_response():
    """Mock Slack API response."""
    return {
        "ok": True,
        "access_token": "xoxp-test-token",
        "authed_user": {
            "id": "U12345",
            "access_token": "xoxp-user-token"
        },
        "team": {
            "id": "T12345",
            "name": "Test Team"
        }
    }

@pytest.fixture
def mock_user_info():
    """Mock user info from Slack."""
    return {
        "ok": True,
        "user": {
            "id": "U12345",
            "name": "Test User",
            "email": "test@example.com",
            "is_admin": False
        },
        "team": {
            "id": "T12345",
            "name": "Test Team"
        }
    }

class TestSlackAuth:
    
    def test_create_token(self):
        """Test creating JWT token."""
        auth_manager = SlackAuthManager()
        
        # Create a test user
        user_info = SlackUserInfo(
            user_id="U12345",
            email="test@example.com",
            name="Test User",
            team_id="T12345",
            is_admin=False
        )
        
        # Create token
        token = auth_manager.create_token(user_info)
        
        # Verify token
        payload = jwt.decode(
            token, 
            auth_manager.jwt_secret, 
            algorithms=[auth_manager.jwt_algorithm]
        )
        
        # Check payload
        assert payload["sub"] == "U12345"
        assert payload["email"] == "test@example.com"
        assert payload["name"] == "Test User"
        assert payload["team_id"] == "T12345"
        assert payload["is_admin"] is False
        
    def test_verify_token(self):
        """Test verifying a JWT token."""
        auth_manager = SlackAuthManager()
        
        # Create a test payload
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "U12345",
            "email": "test@example.com",
            "name": "Test User",
            "team_id": "T12345",
            "is_admin": False,
            "iat": now.timestamp(),
            "exp": (now + timedelta(hours=1)).timestamp()
        }
        
        # Create token
        token = jwt.encode(
            payload, 
            auth_manager.jwt_secret, 
            algorithm=auth_manager.jwt_algorithm
        )
        
        # Verify token
        decoded = auth_manager.verify_token(token)
        
        # Check payload
        assert decoded["sub"] == "U12345"
        assert decoded["email"] == "test@example.com"
    
    def test_expired_token(self):
        """Test expired token handling."""
        from fastapi import HTTPException
        
        auth_manager = SlackAuthManager()
        
        # Create a test payload with expired token
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "U12345",
            "email": "test@example.com",
            "name": "Test User",
            "team_id": "T12345",
            "is_admin": False,
            "iat": (now - timedelta(hours=2)).timestamp(),
            "exp": (now - timedelta(hours=1)).timestamp()
        }
        
        # Create token
        token = jwt.encode(
            payload, 
            auth_manager.jwt_secret, 
            algorithm=auth_manager.jwt_algorithm
        )
        
        # Verify token should fail
        with pytest.raises(HTTPException) as excinfo:
            auth_manager.verify_token(token)
            
        assert excinfo.value.status_code == 401
        assert "expired" in excinfo.value.detail.lower()

    @patch('requests.post')
    def test_exchange_code_for_token(self, mock_post):
        """Test exchanging code for token."""
        # Mock the requests post response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxp-test-token",
            "authed_user": {
                "id": "U12345",
                "access_token": "xoxp-user-token"
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        auth_manager = SlackAuthManager()
        
        # Call the method
        import asyncio
        response = asyncio.run(auth_manager.exchange_code_for_token("test-code"))
        
        # Check response
        assert response["ok"] is True
        assert response["access_token"] == "xoxp-test-token"
        
        # Verify the call to Slack API
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        assert "test-code" in call_args["data"].values()
    
    @patch('requests.get')
    def test_get_user_info(self, mock_get):
        """Test getting user info from Slack."""
        # Mock the requests get response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "user": {
                "id": "U12345",
                "name": "Test User",
                "email": "test@example.com",
                "is_admin": False
            },
            "team": {
                "id": "T12345",
                "name": "Test Team"
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        auth_manager = SlackAuthManager()
        
        # Call the method
        import asyncio
        user_info = asyncio.run(auth_manager.get_user_info("test-token"))
        
        # Check user info
        assert user_info.user_id == "U12345"
        assert user_info.email == "test@example.com"
        assert user_info.name == "Test User"
        assert user_info.team_id == "T12345"
        assert user_info.is_admin is False
        
        # Verify the call to Slack API
        mock_get.assert_called_once()
        headers = mock_get.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-token"
        
    def test_get_authorization_url(self):
        """Test generating the Slack authorization URL."""
        auth_manager = SlackAuthManager()
        
        # Generate URL with custom state
        url = auth_manager.get_authorization_url("test-state")
        
        # Check URL
        assert "https://slack.com/oauth/v2/authorize" in url
        assert auth_manager.client_id in url
        assert "identity.basic" in url
        assert "identity.email" in url
        assert auth_manager.redirect_uri in url
        assert "test-state" in url 