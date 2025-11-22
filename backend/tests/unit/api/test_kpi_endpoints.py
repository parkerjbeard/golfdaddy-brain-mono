from unittest.mock import MagicMock

import pytest

from app.api.v1.endpoints.kpi import get_kpi_service
from app.auth.dependencies import get_current_user
from app.main import app
from app.models.user import User, UserRole
from app.services.kpi_service import KpiService

# Mock data
EMPLOYEE_USER = User(id="11111111-1111-1111-1111-111111111111", email="emp@test.com", role=UserRole.EMPLOYEE)
MANAGER_USER = User(id="22222222-2222-2222-2222-222222222222", email="mgr@test.com", role=UserRole.MANAGER)
ADMIN_USER = User(id="33333333-3333-3333-3333-333333333333", email="adm@test.com", role=UserRole.ADMIN)


@pytest.fixture
def mock_kpi_service():
    service = MagicMock(spec=KpiService)
    service.get_bulk_widget_summaries.return_value = []
    service.get_user_performance_summary.return_value = {}
    service.get_user_performance_summary_range.return_value = {}
    return service


def test_get_summaries_requires_auth(client):
    """Test that endpoint requires authentication."""
    response = client.get(
        "/api/v1/kpi/performance/widget-summaries?startDate=2025-01-01&endDate=2025-01-07",
        headers={"X-API-Key": "test-api-key"},
    )
    # Should be 401 because no Bearer token provided and get_current_user checks it
    # (Note: API Key middleware passes, but get_current_user requires Bearer)
    assert response.status_code in [401, 422]


def test_get_summaries_forbidden_for_employee(client, mock_kpi_service):
    """Test that employees cannot access manager endpoints."""
    app.dependency_overrides[get_kpi_service] = lambda: mock_kpi_service
    app.dependency_overrides[get_current_user] = lambda: EMPLOYEE_USER

    response = client.get(
        "/api/v1/kpi/performance/widget-summaries?startDate=2025-01-01&endDate=2025-01-07",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 403
    assert "Manager or admin privileges required" in response.text

    app.dependency_overrides = {}


def test_get_summaries_allowed_for_manager(client, mock_kpi_service):
    """Test that managers can access."""
    app.dependency_overrides[get_kpi_service] = lambda: mock_kpi_service
    app.dependency_overrides[get_current_user] = lambda: MANAGER_USER

    response = client.get(
        "/api/v1/kpi/performance/widget-summaries?startDate=2025-01-01&endDate=2025-01-07",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    app.dependency_overrides = {}


def test_get_summaries_allowed_for_admin(client, mock_kpi_service):
    """Test that admins can access."""
    app.dependency_overrides[get_kpi_service] = lambda: mock_kpi_service
    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    response = client.get(
        "/api/v1/kpi/performance/widget-summaries?startDate=2025-01-01&endDate=2025-01-07",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    app.dependency_overrides = {}
