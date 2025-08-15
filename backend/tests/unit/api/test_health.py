from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.health import HealthChecker, health_checker, router


@pytest.fixture
def client():
    """Test client for health endpoints."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.data = [{"id": "test-user-1"}]
    mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_response
    return mock_client


class TestHealthChecker:
    """Test HealthChecker class functionality."""

    @pytest.mark.asyncio
    async def test_check_database_success(self, mock_supabase):
        """Test successful database health check."""
        checker = HealthChecker()
        result = await checker.check_database(mock_supabase)

        assert result["status"] == "healthy"
        assert "response_time_ms" in result
        assert result["details"] == "Database connection successful"

    @pytest.mark.asyncio
    async def test_check_database_failure(self):
        """Test database health check failure."""
        checker = HealthChecker()
        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception(
            "Connection failed"
        )

        result = await checker.check_database(mock_supabase)

        assert result["status"] == "unhealthy"
        assert "response_time_ms" in result
        assert "Connection failed" in result["details"]

    @pytest.mark.asyncio
    async def test_check_github_api_success(self):
        """Test successful GitHub API health check."""
        checker = HealthChecker()

        with patch("app.api.health.settings") as mock_settings, patch("app.api.health.Github") as mock_github_class:

            mock_settings.GITHUB_TOKEN = "test-token"

            # Mock GitHub client and rate limit
            mock_github = Mock()
            mock_rate_limit = Mock()
            mock_rate_limit.core.remaining = 4500
            mock_rate_limit.core.limit = 5000
            mock_rate_limit.core.reset.isoformat.return_value = "2023-01-01T12:00:00"
            mock_github.get_rate_limit.return_value = mock_rate_limit
            mock_github_class.return_value = mock_github

            result = await checker.check_github_api()

            assert result["status"] == "healthy"
            assert "response_time_ms" in result
            assert result["details"]["rate_limit_remaining"] == 4500
            assert result["details"]["rate_limit_total"] == 5000

    @pytest.mark.asyncio
    async def test_check_github_api_no_token(self):
        """Test GitHub API health check with no token."""
        checker = HealthChecker()

        with patch("app.api.health.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = None

            result = await checker.check_github_api()

            assert result["status"] == "disabled"
            assert result["details"] == "GitHub token not configured"

    @pytest.mark.asyncio
    async def test_check_github_api_degraded(self):
        """Test GitHub API health check with low rate limit."""
        checker = HealthChecker()

        with patch("app.api.health.settings") as mock_settings, patch("app.api.health.Github") as mock_github_class:

            mock_settings.GITHUB_TOKEN = "test-token"

            # Mock low rate limit
            mock_github = Mock()
            mock_rate_limit = Mock()
            mock_rate_limit.core.remaining = 50  # Less than 100
            mock_rate_limit.core.limit = 5000
            mock_rate_limit.core.reset.isoformat.return_value = "2023-01-01T12:00:00"
            mock_github.get_rate_limit.return_value = mock_rate_limit
            mock_github_class.return_value = mock_github

            result = await checker.check_github_api()

            assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_check_openai_api_success(self):
        """Test successful OpenAI API health check."""
        checker = HealthChecker()

        with patch("app.api.health.settings") as mock_settings, patch("app.api.health.OpenAI") as mock_openai_class:

            mock_settings.OPENAI_API_KEY = "test-key"

            # Mock OpenAI client and models
            mock_openai = Mock()
            mock_models = Mock()
            mock_models.data = [{"id": "gpt-4"}, {"id": "gpt-3.5-turbo"}]
            mock_openai.models.list.return_value = mock_models
            mock_openai_class.return_value = mock_openai

            result = await checker.check_openai_api()

            assert result["status"] == "healthy"
            assert "response_time_ms" in result
            assert result["details"]["available_models"] == 2

    @pytest.mark.asyncio
    async def test_check_openai_api_no_key(self):
        """Test OpenAI API health check with no API key."""
        checker = HealthChecker()

        with patch("app.api.health.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None

            result = await checker.check_openai_api()

            assert result["status"] == "disabled"
            assert result["details"] == "OpenAI API key not configured"

    def test_check_circuit_breakers_healthy(self):
        """Test circuit breaker health check when all are healthy."""
        checker = HealthChecker()

        with patch("app.api.health.circuit_manager") as mock_manager:
            mock_manager.get_status.return_value = {
                "github_api": {"state": "closed", "failure_count": 0},
                "openai_api": {"state": "closed", "failure_count": 0},
            }

            result = checker.check_circuit_breakers()

            assert result["status"] == "healthy"
            assert "All circuit breakers operational" in result["details"]

    def test_check_circuit_breakers_degraded(self):
        """Test circuit breaker health check with half-open breakers."""
        checker = HealthChecker()

        with patch("app.api.health.circuit_manager") as mock_manager:
            mock_manager.get_status.return_value = {
                "github_api": {"state": "half_open", "failure_count": 2},
                "openai_api": {"state": "closed", "failure_count": 0},
            }

            result = checker.check_circuit_breakers()

            assert result["status"] == "degraded"
            assert "github_api" in result["details"]

    def test_check_circuit_breakers_unhealthy(self):
        """Test circuit breaker health check with open breakers."""
        checker = HealthChecker()

        with patch("app.api.health.circuit_manager") as mock_manager:
            mock_manager.get_status.return_value = {
                "github_api": {"state": "open", "failure_count": 5},
                "openai_api": {"state": "closed", "failure_count": 0},
            }

            result = checker.check_circuit_breakers()

            assert result["status"] == "unhealthy"
            assert "github_api" in result["details"]

    def test_check_rate_limiters_healthy(self):
        """Test rate limiter health check when all are healthy."""
        checker = HealthChecker()

        with patch("app.api.health.rate_limiter_manager") as mock_manager:
            mock_manager.get_status.return_value = {
                "github_api": {"available_tokens": 800, "capacity": 1000},
                "openai_api": {"available_tokens": 500, "capacity": 600},
            }

            result = checker.check_rate_limiters()

            assert result["status"] == "healthy"
            assert "All rate limiters operational" in result["details"]

    def test_check_rate_limiters_degraded(self):
        """Test rate limiter health check with high utilization."""
        checker = HealthChecker()

        with patch("app.api.health.rate_limiter_manager") as mock_manager:
            mock_manager.get_status.return_value = {
                "github_api": {"available_tokens": 100, "capacity": 1000},  # 90% utilization
                "openai_api": {"available_tokens": 500, "capacity": 600},
            }

            result = checker.check_rate_limiters()

            assert result["status"] == "degraded"
            assert "github_api" in result["details"]

    def test_check_documentation_config_healthy(self):
        """Test documentation configuration check when fully configured."""
        checker = HealthChecker()

        with patch("app.api.health.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.GITHUB_TOKEN = "test-token"
            mock_settings.DOCUMENTATION_OPENAI_MODEL = "gpt-4"
            mock_settings.DOC_AGENT_OPENAI_MODEL = "gpt-4"
            mock_settings.DOCS_REPOSITORY = "owner/docs"
            mock_settings.ENABLE_DOCS_UPDATES = True

            result = checker.check_documentation_config()

            assert result["status"] == "healthy"
            assert "fully configured" in result["details"]

    def test_check_documentation_config_degraded(self):
        """Test documentation configuration check with missing optional config."""
        checker = HealthChecker()

        with patch("app.api.health.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.GITHUB_TOKEN = "test-token"
            mock_settings.DOCUMENTATION_OPENAI_MODEL = "gpt-4"
            mock_settings.DOC_AGENT_OPENAI_MODEL = "gpt-4"
            # Missing optional configs
            mock_settings.DOCS_REPOSITORY = None
            mock_settings.ENABLE_DOCS_UPDATES = None

            result = checker.check_documentation_config()

            assert result["status"] == "degraded"

    def test_check_documentation_config_unhealthy(self):
        """Test documentation configuration check with missing required config."""
        checker = HealthChecker()

        with patch("app.api.health.settings") as mock_settings:
            # Missing required configs
            mock_settings.OPENAI_API_KEY = None
            mock_settings.GITHUB_TOKEN = None
            mock_settings.DOCUMENTATION_OPENAI_MODEL = None
            mock_settings.DOC_AGENT_OPENAI_MODEL = None
            mock_settings.DOCS_REPOSITORY = None
            mock_settings.ENABLE_DOCS_UPDATES = None

            result = checker.check_documentation_config()

            assert result["status"] == "unhealthy"


class TestHealthEndpoints:
    """Test health API endpoints."""

    def test_basic_health(self, client):
        """Test basic health check endpoint."""
        response = client.get("/health/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "golfdaddy-brain"

    def test_detailed_health_disabled(self, client):
        """Test detailed health check when disabled."""
        with patch.object(health_checker, "detailed_checks", False):
            response = client.get("/health/detailed")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "disabled" in data["message"]

    def test_detailed_health_success(self, client, mock_supabase):
        """Test detailed health check with all services healthy."""
        with (
            patch("app.api.health.get_supabase_client", return_value=mock_supabase),
            patch.object(health_checker, "check_database", new_callable=AsyncMock) as mock_db,
            patch.object(health_checker, "check_github_api", new_callable=AsyncMock) as mock_github,
            patch.object(health_checker, "check_openai_api", new_callable=AsyncMock) as mock_openai,
            patch.object(health_checker, "check_circuit_breakers") as mock_cb,
            patch.object(health_checker, "check_rate_limiters") as mock_rl,
            patch.object(health_checker, "check_documentation_config") as mock_config,
        ):

            # Mock all checks as healthy
            mock_db.return_value = {"status": "healthy"}
            mock_github.return_value = {"status": "healthy"}
            mock_openai.return_value = {"status": "healthy"}
            mock_cb.return_value = {"status": "healthy"}
            mock_rl.return_value = {"status": "healthy"}
            mock_config.return_value = {"status": "healthy"}

            response = client.get("/health/detailed")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "checks" in data
            assert len(data["checks"]) == 6

    def test_detailed_health_degraded(self, client, mock_supabase):
        """Test detailed health check with degraded services."""
        with (
            patch("app.api.health.get_supabase_client", return_value=mock_supabase),
            patch.object(health_checker, "check_database", new_callable=AsyncMock) as mock_db,
            patch.object(health_checker, "check_github_api", new_callable=AsyncMock) as mock_github,
            patch.object(health_checker, "check_openai_api", new_callable=AsyncMock) as mock_openai,
            patch.object(health_checker, "check_circuit_breakers") as mock_cb,
            patch.object(health_checker, "check_rate_limiters") as mock_rl,
            patch.object(health_checker, "check_documentation_config") as mock_config,
        ):

            # Mock some checks as degraded
            mock_db.return_value = {"status": "healthy"}
            mock_github.return_value = {"status": "degraded"}  # Degraded
            mock_openai.return_value = {"status": "healthy"}
            mock_cb.return_value = {"status": "healthy"}
            mock_rl.return_value = {"status": "healthy"}
            mock_config.return_value = {"status": "healthy"}

            response = client.get("/health/detailed")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"  # Overall status should be degraded

    def test_documentation_health(self, client):
        """Test documentation-specific health check."""
        with (
            patch.object(health_checker, "check_github_api", new_callable=AsyncMock) as mock_github,
            patch.object(health_checker, "check_openai_api", new_callable=AsyncMock) as mock_openai,
            patch.object(health_checker, "check_circuit_breakers") as mock_cb,
            patch.object(health_checker, "check_rate_limiters") as mock_rl,
            patch.object(health_checker, "check_documentation_config") as mock_config,
        ):

            # Mock all checks as healthy
            mock_github.return_value = {"status": "healthy"}
            mock_openai.return_value = {"status": "healthy"}
            mock_cb.return_value = {"status": "healthy"}
            mock_rl.return_value = {"status": "healthy"}
            mock_config.return_value = {"status": "healthy"}

            response = client.get("/health/docs")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "documentation_automation"
            assert "checks" in data

    def test_metrics_endpoint(self, client):
        """Test performance metrics endpoint."""
        with (
            patch("app.api.health.circuit_manager") as mock_circuit_manager,
            patch("app.api.health.rate_limiter_manager") as mock_rl_manager,
        ):

            mock_circuit_manager.get_status.return_value = {
                "github_api": {"state": "closed"},
                "openai_api": {"state": "open"},
            }

            mock_rl_manager.get_status.return_value = {
                "github_api": {"available_tokens": 800, "capacity": 1000},
                "openai_api": {"available_tokens": 300, "capacity": 500},
            }

            response = client.get("/health/metrics")

            assert response.status_code == 200
            data = response.json()
            assert "circuit_breakers" in data
            assert "rate_limiters" in data
            assert data["circuit_breakers"]["total"] == 2
            assert data["circuit_breakers"]["open"] == 1

    def test_reset_circuit_breaker_success(self, client):
        """Test successful circuit breaker reset."""
        with patch("app.api.health.circuit_manager") as mock_manager:
            mock_manager.reset_breaker.return_value = True

            response = client.post("/health/circuit-breakers/github_api/reset")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "github_api" in data["message"]

    def test_reset_circuit_breaker_not_found(self, client):
        """Test circuit breaker reset for non-existent breaker."""
        with patch("app.api.health.circuit_manager") as mock_manager:
            mock_manager.reset_breaker.return_value = False

            response = client.post("/health/circuit-breakers/nonexistent/reset")

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]
