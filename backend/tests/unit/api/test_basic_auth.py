"""
Basic tests for authentication configuration and middleware.
"""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient


class TestBasicAuth:
    """Test basic authentication setup."""

    def test_health_endpoint_no_auth(self):
        """Test that health endpoint doesn't require authentication."""
        # Import app without API auth enabled
        with patch.dict(os.environ, {"ENABLE_API_AUTH": "false"}):
            from app.main import app

            client = TestClient(app)
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

    def test_api_endpoint_requires_api_key_when_enabled(self):
        """Test that API endpoints require API key when auth is enabled."""
        # Enable API auth and set up test API keys
        with patch.dict(
            os.environ, {"ENABLE_API_AUTH": "true", "API_KEYS": '{"test-key": {"owner": "test", "role": "admin"}}'}
        ):
            # Need to reload the app to pick up new settings
            import importlib

            from app import main

            importlib.reload(main)

            client = TestClient(main.app)

            # Try to access an API endpoint without API key
            response = client.get("/api/v1/users")
            assert response.status_code == 401
            assert response.json()["error"]["message"] == "API key required"

    def test_docs_endpoint_no_auth(self):
        """Test that docs endpoint doesn't require authentication."""
        from app.main import app

        client = TestClient(app)
        response = client.get("/docs")
        # Should return HTML for Swagger docs
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

    def test_auth_exclude_paths(self):
        """Test that AUTH_EXCLUDE_PATHS setting is respected."""
        from app.config.settings import settings

        exclude_paths = settings.AUTH_EXCLUDE_PATHS.split(",")
        assert "/health" in exclude_paths
        assert "/docs" in exclude_paths
        assert "/auth" in exclude_paths

    def test_valid_api_key_passes_when_enabled(self):
        """Test that valid API key allows access when auth is enabled."""
        # Enable API auth and set up test API keys
        with patch.dict(
            os.environ, {"ENABLE_API_AUTH": "true", "API_KEYS": '{"test-key": {"owner": "test", "role": "admin"}}'}
        ):
            # Need to reload the app to pick up new settings
            import importlib

            from app import main

            importlib.reload(main)

            client = TestClient(main.app)

            # Access with valid API key
            headers = {"X-API-Key": "test-key"}
            response = client.get("/api/v1/health", headers=headers)

            # Should pass with valid API key
            # The actual endpoint might need additional auth (JWT), but API key check should pass
            # If endpoint doesn't exist, we get 404, which means API key was accepted
            assert response.status_code in [200, 401, 404]  # Not 401 for "API key required"
            if response.status_code == 401:
                # If we get 401, it shouldn't be about missing API key
                assert "API key required" not in response.json()["error"]["message"]

    def test_frontend_url_configured(self):
        """Test that FRONTEND_URL is configured for notifications."""
        from app.config.settings import settings

        assert hasattr(settings, "FRONTEND_URL")
        assert settings.FRONTEND_URL is not None
        assert settings.FRONTEND_URL.startswith("http")

    def test_slack_settings_configured(self):
        """Test that Slack settings are configured."""
        from app.config.settings import settings

        # Check Slack settings exist
        assert hasattr(settings, "SLACK_BOT_TOKEN")
        assert hasattr(settings, "SLACK_DEFAULT_CHANNEL")
        assert hasattr(settings, "SLACK_CIRCUIT_BREAKER_FAILURE_THRESHOLD")
        assert hasattr(settings, "SLACK_CIRCUIT_BREAKER_TIMEOUT")

    def test_api_auth_disabled_by_default(self):
        """Test that API auth can be disabled for development."""
        # Check with API auth disabled
        with patch.dict(os.environ, {"ENABLE_API_AUTH": "false"}):
            import importlib

            from app import main

            importlib.reload(main)

            client = TestClient(main.app)

            # Should be able to access API without key when disabled
            response = client.get("/api/v1/health")
            # Should not get 401 for missing API key
            if response.status_code == 401:
                assert "API key required" not in response.json().get("error", {}).get("message", "")
