import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.api_key_auth import ApiKeyMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_metrics import RequestMetricsMiddleware


@pytest.fixture
def test_app():
    """Create a test FastAPI app."""
    app = FastAPI()

    @app.get("/test")
    def test_endpoint():
        return {"status": "ok"}

    @app.get("/excluded")
    def excluded_endpoint():
        return {"status": "excluded"}

    return app


@pytest.fixture
def api_keys():
    """Sample API keys for testing."""
    return {
        "valid-key": {"owner": "test-user", "role": "user"},
        "admin-key": {"owner": "admin-user", "role": "admin", "rate_limit": 100},
    }


class TestApiKeyMiddleware:
    def test_valid_api_key(self, test_app, api_keys):
        """Test request with valid API key."""
        app = test_app
        app.add_middleware(ApiKeyMiddleware, api_keys=api_keys, api_key_header="X-API-Key")

        client = TestClient(app)
        response = client.get("/test", headers={"X-API-Key": "valid-key"})

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_invalid_api_key(self, test_app, api_keys):
        """Test request with invalid API key."""
        app = test_app
        app.add_middleware(ApiKeyMiddleware, api_keys=api_keys, api_key_header="X-API-Key")

        client = TestClient(app)
        response = client.get("/test", headers={"X-API-Key": "invalid-key"})

        assert response.status_code == 403

    def test_missing_api_key(self, test_app, api_keys):
        """Test request with no API key."""
        app = test_app
        app.add_middleware(ApiKeyMiddleware, api_keys=api_keys, api_key_header="X-API-Key")

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 401

    def test_excluded_path(self, test_app, api_keys):
        """Test request to excluded path."""
        app = test_app
        app.add_middleware(ApiKeyMiddleware, api_keys=api_keys, api_key_header="X-API-Key", exclude_paths=["/excluded"])

        client = TestClient(app)
        response = client.get("/excluded")

        assert response.status_code == 200
        assert response.json() == {"status": "excluded"}


class TestRateLimiter:
    def test_rate_limiting(self, test_app):
        """Test rate limiting."""
        app = test_app
        app.add_middleware(RateLimiterMiddleware, rate_limit_per_minute=2)  # Set a low limit for testing

        client = TestClient(app)

        # First request should succeed
        response1 = client.get("/test")
        assert response1.status_code == 200

        # Second request should succeed
        response2 = client.get("/test")
        assert response2.status_code == 200

        # Third request should be rate limited
        response3 = client.get("/test")
        assert response3.status_code == 429

        # Check headers
        assert "X-RateLimit-Limit" in response1.headers
        assert "X-RateLimit-Remaining" in response1.headers
        assert int(response1.headers["X-RateLimit-Remaining"]) == 1
        assert int(response2.headers["X-RateLimit-Remaining"]) == 0

    def test_custom_rate_limit(self, test_app):
        """Test custom rate limit for specific API key."""
        app = test_app
        app.add_middleware(
            RateLimiterMiddleware,
            rate_limit_per_minute=1,  # Default limit
            api_keys={"custom-key": 3},  # Custom limit for this key
        )

        client = TestClient(app)

        # First request with custom key
        response1 = client.get("/test", headers={"X-API-Key": "custom-key"})
        assert response1.status_code == 200

        # Second request with custom key
        response2 = client.get("/test", headers={"X-API-Key": "custom-key"})
        assert response2.status_code == 200

        # Third request with custom key
        response3 = client.get("/test", headers={"X-API-Key": "custom-key"})
        assert response3.status_code == 200

        # Fourth request with custom key should be rate limited
        response4 = client.get("/test", headers={"X-API-Key": "custom-key"})
        assert response4.status_code == 429

        # Check rate limit in headers
        assert response1.headers["X-RateLimit-Limit"] == "3"

    def test_excluded_path_rate_limit(self, test_app):
        """Test excluded path is not rate limited."""
        app = test_app
        app.add_middleware(RateLimiterMiddleware, rate_limit_per_minute=1, exclude_paths=["/excluded"])  # Low limit

        client = TestClient(app)

        # First request to normal endpoint
        response1 = client.get("/test")
        assert response1.status_code == 200

        # Second request to normal endpoint should be rate limited
        response2 = client.get("/test")
        assert response2.status_code == 429

        # Request to excluded path should not be rate limited
        response3 = client.get("/excluded")
        assert response3.status_code == 200


class TestRequestMetrics:
    def test_metrics_collection(self, test_app):
        """Test metrics collection."""
        app = test_app
        metrics_middleware = RequestMetricsMiddleware(None)

        # Mock the middleware dispatch method to avoid adding it to the app
        original_dispatch = metrics_middleware.dispatch

        async def mock_dispatch(request, call_next):
            # Call the original but with a mocked response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}

            with patch("time.time", side_effect=[100, 100.5]):  # Mock 0.5s duration
                return await original_dispatch(request, lambda: mock_response)

        metrics_middleware.dispatch = mock_dispatch
        app.add_middleware(RequestMetricsMiddleware)

        client = TestClient(app)
        response = client.get("/test")

        # Get metrics
        metrics = metrics_middleware.get_metrics()

        # Check metrics
        assert metrics["request_count"] >= 1
        assert "GET:/test" in metrics["requests_by_path"]
        assert 200 in metrics["status_codes"]

        # Request timing header should be present
        assert "X-Process-Time" in response.headers
