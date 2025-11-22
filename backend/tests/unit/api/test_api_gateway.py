import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.api_key_auth import ApiKeyMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_metrics import RequestMetricsMiddleware
from app.core.error_handlers import add_exception_handlers


@pytest.fixture
def test_app():
    """Create a test FastAPI app."""
    app = FastAPI()

    # Add exception handlers to properly handle custom exceptions
    add_exception_handlers(app)

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

        assert response.status_code == 401  # AuthenticationError returns 401

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

        # We'll capture the middleware instance when it's created
        captured_middleware = []

        original_init = RequestMetricsMiddleware.__init__

        def capture_init(self, app):
            original_init(self, app)
            captured_middleware.append(self)

        with patch.object(RequestMetricsMiddleware, "__init__", capture_init):
            # Add the middleware to the app and create client while patch is active
            app.add_middleware(RequestMetricsMiddleware)
            client = TestClient(app)
            # Make a request within patch so instantiation is captured
            with patch("time.time", side_effect=[100, 100.5, 100.5, 100.5, 100.5, 100.5]):
                response = client.get("/test")

        # Check the response
        assert response.status_code == 200

        # Get metrics from the captured middleware instance
        assert len(captured_middleware) > 0
        metrics_middleware = captured_middleware[0]
        metrics = metrics_middleware.get_metrics()

        # Check metrics
        assert metrics["request_count"] >= 1
        assert "GET:/test" in metrics["requests_by_path"]
        assert 200 in metrics["status_codes"]

        # Request timing header should be present
        assert "X-Process-Time" in response.headers
