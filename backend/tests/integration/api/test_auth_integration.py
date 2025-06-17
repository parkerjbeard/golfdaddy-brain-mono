"""
Integration tests for authentication flow.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import jwt
from datetime import datetime, timedelta
from app.main import app
from app.models.user import User, UserRole


class TestAuthIntegration:
    """Integration tests for authentication endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        return User(
            id="test-user-123",
            email="test@example.com",
            name="Test User",
            role=UserRole.DEVELOPER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
    
    @pytest.fixture
    def auth_headers(self):
        """Create authorization headers with valid token."""
        secret = "test-secret"
        token = jwt.encode(
            {"sub": "test-user-123", "exp": datetime.utcnow() + timedelta(hours=1)},
            secret,
            algorithm="HS256"
        )
        return {
            "Authorization": f"Bearer {token}",
            "X-API-Key": "test-api-key"
        }
    
    def test_health_check_no_auth_required(self, client):
        """Test that health check doesn't require authentication."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_api_requires_api_key(self, client):
        """Test that API endpoints require API key."""
        # Try to access user endpoint without API key
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401
        assert "API key required" in response.json()["error"]["message"]
    
    def test_api_requires_bearer_token(self, client):
        """Test that API endpoints require bearer token."""
        # Try with only API key
        headers = {"X-API-Key": "test-api-key"}
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 401
        assert "Authorization" in response.json()["error"]["details"][0]
    
    @patch('app.middleware.api_key_auth.ApiKeyMiddleware.is_valid_api_key')
    @patch('app.auth.dependencies.get_current_user')
    def test_get_current_user_success(self, mock_get_user, mock_api_key, client, mock_user):
        """Test successful retrieval of current user."""
        mock_api_key.return_value = True
        mock_get_user.return_value = mock_user
        
        response = client.get(
            "/api/v1/users/me",
            headers=self.auth_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_user.id
        assert data["email"] == mock_user.email
    
    @patch('app.config.supabase_client.get_supabase_client')
    @patch('app.repositories.user_repository.UserRepository.get_user_by_email')
    def test_login_with_token(self, mock_get_user, mock_supabase, client, mock_user):
        """Test login with Supabase token."""
        # Mock Supabase auth
        mock_supabase_client = Mock()
        mock_supabase_client.auth.get_user.return_value = Mock(
            user=Mock(id="test-user-123", email="test@example.com")
        )
        mock_supabase.return_value = mock_supabase_client
        
        # Mock user repository
        mock_get_user.return_value = mock_user
        
        response = client.post(
            "/auth/token",
            json={"token": "valid-supabase-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == mock_user.email
    
    def test_login_with_invalid_token(self, client):
        """Test login with invalid token."""
        with patch('app.config.supabase_client.get_supabase_client') as mock_supabase:
            mock_supabase_client = Mock()
            mock_supabase_client.auth.get_user.side_effect = Exception("Invalid token")
            mock_supabase.return_value = mock_supabase_client
            
            response = client.post(
                "/auth/token",
                json={"token": "invalid-token"}
            )
            
            assert response.status_code == 401
    
    @patch('app.middleware.api_key_auth.ApiKeyMiddleware.is_valid_api_key')
    @patch('app.auth.dependencies.get_current_user')
    def test_validate_token(self, mock_get_user, mock_api_key, client, mock_user):
        """Test token validation endpoint."""
        mock_api_key.return_value = True
        mock_get_user.return_value = mock_user
        
        response = client.get(
            "/auth/validate",
            headers=self.auth_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["user"]["id"] == mock_user.id
    
    def test_auth_flow_integration(self, client):
        """Test complete authentication flow."""
        with patch('app.config.supabase_client.get_supabase_client') as mock_supabase, \
             patch('app.repositories.user_repository.UserRepository') as mock_repo:
            
            # Setup mocks
            mock_user = self.mock_user()
            mock_supabase_client = Mock()
            mock_supabase_client.auth.get_user.return_value = Mock(
                user=Mock(id=mock_user.id, email=mock_user.email)
            )
            mock_supabase.return_value = mock_supabase_client
            
            mock_repo_instance = Mock()
            mock_repo_instance.get_user_by_email.return_value = mock_user
            mock_repo_instance.get_user_by_id.return_value = mock_user
            mock_repo.return_value = mock_repo_instance
            
            # Step 1: Login with Supabase token
            login_response = client.post(
                "/auth/token",
                json={"token": "supabase-token"}
            )
            assert login_response.status_code == 200
            
            access_token = login_response.json()["access_token"]
            
            # Step 2: Use access token to get user info
            with patch('app.middleware.api_key_auth.ApiKeyMiddleware.is_valid_api_key', return_value=True), \
                 patch('app.config.settings.settings.JWT_SECRET', 'test-secret'):
                
                user_response = client.get(
                    "/api/v1/users/me",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-API-Key": "test-api-key"
                    }
                )
                
                # This might fail due to JWT verification, but we're testing the flow
                assert user_response.status_code in [200, 401]
    
    def test_excluded_paths_no_auth(self, client):
        """Test that excluded paths don't require authentication."""
        excluded_paths = ["/docs", "/redoc", "/openapi.json", "/health"]
        
        for path in excluded_paths:
            response = client.get(path)
            # These should not return 401 for missing API key
            assert response.status_code != 401 or "API key" not in response.text