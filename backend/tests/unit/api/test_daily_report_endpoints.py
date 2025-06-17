import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status, FastAPI
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timezone

from app.main import app # Main FastAPI application
from app.services.daily_report_service import DailyReportService
from app.models.daily_report import DailyReport, DailyReportCreate, AiAnalysis
from app.models.user import User # For mocking current_user

# from httpx import ASGITransport # No longer needed for TestClient
from fastapi.testclient import TestClient # Import TestClient

# Import the actual dependency functions
from app.api.daily_report_endpoints import get_daily_report_service, get_current_active_user

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

BASE_URL = "/reports/daily" # As defined in daily_report_endpoints.py router prefix

@pytest.fixture
def mock_daily_report_service():
    return AsyncMock(spec=DailyReportService)

@pytest.fixture
def current_test_user():
    return User(id=uuid4(), email="testuser@example.com", name="Test User Endpoint")

# Apply dependency overrides for the test session
@pytest.fixture(autouse=True)
def override_dependencies(mock_daily_report_service: AsyncMock, current_test_user: User):
    # app.dependency_overrides[DailyReportService] = lambda: mock_daily_report_service # This might be too broad or not what endpoints use directly
    # Prefer overriding the specific functions used in Depends()
    app.dependency_overrides[get_daily_report_service] = lambda: mock_daily_report_service
    app.dependency_overrides[get_current_active_user] = lambda: current_test_user
    yield
    app.dependency_overrides = {} # Clear overrides after tests

async def test_submit_eod_report_success(
    async_client: AsyncClient, 
    mock_daily_report_service: AsyncMock, 
    current_test_user: User
):
    report_create_data = {"raw_text_input": "Test EOD content"}
    # The user_id in payload is usually ignored or validated against current_user by the service.
    # The endpoint passes current_user.id to the service.
    
    expected_report_id = uuid4()
    mock_created_report = DailyReport(
        id=expected_report_id,
        user_id=current_test_user.id, 
        raw_text_input=report_create_data["raw_text_input"],
        ai_analysis=AiAnalysis(summary="AI Done"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    mock_daily_report_service.submit_daily_report.return_value = mock_created_report

    response = await async_client.post(f"{BASE_URL}/", json=report_create_data)

    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    assert response_data["id"] == str(expected_report_id)
    assert response_data["user_id"] == str(current_test_user.id)
    assert response_data["raw_text_input"] == report_create_data["raw_text_input"]
    mock_daily_report_service.submit_daily_report.assert_called_once()
    # Check that the service was called with report_in and current_user.id
    call_args = mock_daily_report_service.submit_daily_report.call_args[0]
    assert isinstance(call_args[0], DailyReportCreate)
    assert call_args[0].raw_text_input == report_create_data["raw_text_input"]
    assert call_args[1] == current_test_user.id # current_user_id argument

async def test_submit_eod_report_service_exception(
    async_client: AsyncClient, mock_daily_report_service: AsyncMock
):
    report_create_data = {"raw_text_input": "Test EOD content"}
    mock_daily_report_service.submit_daily_report.side_effect = Exception("Service layer error")

    response = await async_client.post(f"{BASE_URL}/", json=report_create_data)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "Service layer error"}

async def test_submit_eod_report_validation_error(async_client: AsyncClient):
    # raw_text_input is required by DailyReportCreate, user_id is also required but endpoint uses current_user
    invalid_payload = {} # Missing raw_text_input
    response = await async_client.post(f"{BASE_URL}/", json=invalid_payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # Pydantic v2 error structure
    assert "detail" in response.json()
    assert any("Input should be a valid string" in err["msg"] and "raw_text_input" in err["loc"] for err in response.json()["detail"])

async def test_get_my_daily_reports_success(
    async_client: AsyncClient, mock_daily_report_service: AsyncMock, current_test_user: User
):
    report_id_1 = uuid4()
    report_id_2 = uuid4()
    mock_reports = [
        DailyReport(id=report_id_1, user_id=current_test_user.id, raw_text_input="Report 1", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)),
        DailyReport(id=report_id_2, user_id=current_test_user.id, raw_text_input="Report 2", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    ]
    mock_daily_report_service.get_reports_for_user.return_value = mock_reports

    response = await async_client.get(f"{BASE_URL}/me")
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["id"] == str(report_id_1)
    assert response_data[1]["id"] == str(report_id_2)
    mock_daily_report_service.get_reports_for_user.assert_called_once_with(current_test_user.id)

async def test_get_my_daily_report_for_date_success(
    async_client: AsyncClient, mock_daily_report_service: AsyncMock, current_test_user: User
):
    report_date_str = "2023-10-26"
    report_date_obj = datetime.strptime(report_date_str, "%Y-%m-%d")
    report_id = uuid4()

    mock_report = DailyReport(
        id=report_id, user_id=current_test_user.id, raw_text_input="Report for date", 
        report_date=report_date_obj, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    mock_daily_report_service.get_user_report_for_date.return_value = mock_report

    response = await async_client.get(f"{BASE_URL}/me/{report_date_str}")
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert response_data["id"] == str(report_id)
    mock_daily_report_service.get_user_report_for_date.assert_called_once_with(current_test_user.id, report_date_obj)

async def test_get_my_daily_report_for_date_not_found(
    async_client: AsyncClient, mock_daily_report_service: AsyncMock, current_test_user: User
):
    report_date_str = "2023-10-27"
    report_date_obj = datetime.strptime(report_date_str, "%Y-%m-%d")
    mock_daily_report_service.get_user_report_for_date.return_value = None

    response = await async_client.get(f"{BASE_URL}/me/{report_date_str}")
    assert response.status_code == status.HTTP_200_OK # Endpoint returns Optional[DailyReport], so 200 with null body is expected
    assert response.json() is None
    mock_daily_report_service.get_user_report_for_date.assert_called_once_with(current_test_user.id, report_date_obj)

async def test_get_my_daily_report_for_date_invalid_format(async_client: AsyncClient):
    response = await async_client.get(f"{BASE_URL}/me/invalid-date")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Invalid date format. Use YYYY-MM-DD."}

async def test_get_daily_report_by_id_success(
    async_client: AsyncClient, mock_daily_report_service: AsyncMock, current_test_user: User
):
    report_id = uuid4()
    mock_report = DailyReport(
        id=report_id, user_id=current_test_user.id, raw_text_input="Specific Report", 
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    mock_daily_report_service.get_report_by_id.return_value = mock_report

    response = await async_client.get(f"{BASE_URL}/{report_id}")
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert response_data["id"] == str(report_id)
    mock_daily_report_service.get_report_by_id.assert_called_once_with(report_id)

async def test_get_daily_report_by_id_not_found(
    async_client: AsyncClient, mock_daily_report_service: AsyncMock
):
    report_id = uuid4()
    mock_daily_report_service.get_report_by_id.return_value = None

    response = await async_client.get(f"{BASE_URL}/{report_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Report not found"}

async def test_get_daily_report_by_id_invalid_uuid(async_client: AsyncClient):
    invalid_uuid = "not-a-uuid"
    response = await async_client.get(f"{BASE_URL}/{invalid_uuid}")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # FastAPI/Pydantic will handle this validation for path parameters
    content = response.json()
    assert "detail" in content
    assert any(err["type"] == "uuid_parsing" and err["loc"] == ["path", "report_id"] for err in content["detail"])

# Fixture to provide a TestClient instance for tests
@pytest.fixture(scope="function")
def async_client() -> TestClient: # Changed to TestClient, synchronous fixture
    # Use the global app instance from app.main
    with TestClient(app) as client:
        yield client

# Ensure all test coroutines are properly marked (they are with pytestmark) 