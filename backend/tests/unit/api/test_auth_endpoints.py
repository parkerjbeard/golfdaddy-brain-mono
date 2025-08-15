"""
Unit tests for authentication endpoints.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.api.auth_endpoints import router
from app.models.user import User, UserRole


class TestAuthEndpoints:
    """Test suite for authentication endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user for testing."""
        return User(
            id="test-user-123",
            email="test@example.com",
            name="Test User",
            role=UserRole.DEVELOPER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
        )

    @pytest.fixture
    def mock_supabase(self):
        """Create a mock Supabase client."""
        mock = Mock()
        mock.auth.get_user.return_value = Mock(user=Mock(id="test-user-123", email="test@example.com"))
        return mock

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, mock_user):
        """Test successful retrieval of current user."""
        # Mock the get_current_user dependency
        with patch("app.api.auth_endpoints.get_current_user", return_value=mock_user):
            # Import the function after patching
            from app.api.auth_endpoints import get_current_user_info

            result = await get_current_user_info(mock_user)

            assert result.id == mock_user.id
            assert result.email == mock_user.email
            assert result.role == mock_user.role

    @pytest.mark.asyncio
    async def test_get_current_user_not_authenticated(self):
        """Test get current user when not authenticated."""
        with patch("app.api.auth_endpoints.get_current_user", side_effect=HTTPException(status_code=401)):
            from app.api.auth_endpoints import get_current_user_info

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_info(None)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_token_success(self, mock_supabase, mock_user):
        """Test successful login with Supabase token."""
        token = "valid-supabase-token"

        with (
            patch("app.api.auth_endpoints.get_supabase_client", return_value=mock_supabase),
            patch("app.api.auth_endpoints.UserRepository") as mock_repo,
        ):

            # Mock repository to return user
            mock_repo_instance = Mock()
            mock_repo_instance.get_user_by_email.return_value = mock_user
            mock_repo.return_value = mock_repo_instance

            from app.api.auth_endpoints import login_with_token

            result = await login_with_token(token=token)

            assert result["access_token"] is not None
            assert result["token_type"] == "bearer"
            assert "user" in result
            assert result["user"]["email"] == mock_user.email

    @pytest.mark.asyncio
    async def test_login_with_token_invalid(self, mock_supabase):
        """Test login with invalid token."""
        mock_supabase.auth.get_user.side_effect = Exception("Invalid token")

        with patch("app.api.auth_endpoints.get_supabase_client", return_value=mock_supabase):
            from app.api.auth_endpoints import login_with_token

            with pytest.raises(HTTPException) as exc_info:
                await login_with_token(token="invalid-token")

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, mock_user):
        """Test successful token refresh."""
        # Create a valid JWT token
        secret = "test-secret"
        old_token = jwt.encode(
            {"sub": mock_user.id, "exp": datetime.utcnow() + timedelta(hours=1)}, secret, algorithm="HS256"
        )

        with (
            patch("app.config.settings.settings.JWT_SECRET", secret),
            patch("app.api.auth_endpoints.UserRepository") as mock_repo,
        ):

            mock_repo_instance = Mock()
            mock_repo_instance.get_user_by_id.return_value = mock_user
            mock_repo.return_value = mock_repo_instance

            from app.api.auth_endpoints import refresh_access_token

            result = await refresh_access_token(refresh_token=old_token)

            assert result["access_token"] is not None
            assert result["token_type"] == "bearer"
            assert result["access_token"] != old_token  # New token should be different

    @pytest.mark.asyncio
    async def test_validate_token_success(self, mock_user):
        """Test successful token validation."""
        secret = "test-secret"
        valid_token = jwt.encode(
            {"sub": mock_user.id, "exp": datetime.utcnow() + timedelta(hours=1)}, secret, algorithm="HS256"
        )

        with (
            patch("app.config.settings.settings.JWT_SECRET", secret),
            patch("app.api.auth_endpoints.get_current_user", return_value=mock_user),
        ):

            from app.api.auth_endpoints import validate_token

            result = await validate_token(current_user=mock_user)

            assert result["valid"] is True
            assert result["user"]["id"] == mock_user.id

    def test_create_access_token(self):
        """Test JWT token creation."""
        from app.api.auth_endpoints import create_access_token

        user_id = "test-user-123"
        with (
            patch("app.config.settings.settings.JWT_SECRET", "test-secret"),
            patch("app.config.settings.settings.JWT_EXPIRY_HOURS", 24),
        ):

            token = create_access_token(user_id)

            # Decode token to verify
            decoded = jwt.decode(token, "test-secret", algorithms=["HS256"])
            assert decoded["sub"] == user_id
            assert "exp" in decoded

    @pytest.mark.asyncio
    async def test_update_current_user_success(self, mock_user):
        """Test successful user profile update."""
        update_data = {"name": "Updated Name"}

        with patch("app.api.auth_endpoints.UserRepository") as mock_repo:
            mock_repo_instance = Mock()
            updated_user = Mock(**{**mock_user.__dict__, "name": "Updated Name"})
            mock_repo_instance.update_user.return_value = updated_user
            mock_repo.return_value = mock_repo_instance

            from app.api.auth_endpoints import update_current_user

            result = await update_current_user(user_update=update_data, current_user=mock_user)

            assert result.name == "Updated Name"
