import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from app.main import app # Assuming your FastAPI app instance is here
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.user import User, UserRole
from app.services.raci_service import RaciService
from app.core.exceptions import ResourceNotFoundError, BadRequestError

# --- Fixtures for API tests ---

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_raci_service():
    return AsyncMock(spec=RaciService)

@pytest.fixture
def mock_notification_service_api(): # Renamed to avoid conflict with service test mock
    return AsyncMock()

@pytest.fixture
def mock_current_user_data():
    user_id = uuid4()
    return User(id=user_id, email="testcurrent@example.com", name="Current User", role=UserRole.DEVELOPER)

@pytest.fixture(autouse=True)
def override_dependencies(mock_raci_service, mock_notification_service_api, mock_current_user_data):
    # This fixture will automatically apply to all tests in this file
    
    # Mock get_current_user_profile directly if it's complex or to ensure specific user
    def get_mock_current_user():
        return mock_current_user_data

    # Mock service instantiation within endpoints
    def get_mock_raci_service_instance():
        return mock_raci_service
    
    def get_mock_notification_service_instance():
        return mock_notification_service_api

    # Mock repository instantiation if RaciService was not mocked (not needed if RaciService is mocked)
    # mock_task_repo_dep = AsyncMock()
    # mock_user_repo_dep = AsyncMock()
    # def get_mock_task_repo_instance(): return mock_task_repo_dep
    # def get_mock_user_repo_instance(): return mock_user_repo_dep

    app.dependency_overrides[RaciService] = get_mock_raci_service_instance # If RaciService is directly injected
    # If services are created via functions like get_raci_service():
    from app.api import task_endpoints # Import the module where get_raci_service is defined
    app.dependency_overrides[task_endpoints.get_raci_service] = get_mock_raci_service_instance
    app.dependency_overrides[task_endpoints.get_notification_service] = get_mock_notification_service_instance
    app.dependency_overrides[task_endpoints.get_current_user_profile] = get_mock_current_user
    # app.dependency_overrides[task_endpoints.get_task_repository] = get_mock_task_repo_instance
    # app.dependency_overrides[task_endpoints.get_user_repository] = get_mock_user_repo_instance
    
    yield
    app.dependency_overrides = {} # Clear overrides after tests


# --- Tests for POST /tasks (RACI Task Creation) ---

TASK_API_ENDPOINT = "/tasks"

def test_create_task_success(
    client: TestClient, 
    mock_raci_service: AsyncMock, 
    mock_notification_service_api: AsyncMock,
    mock_current_user_data: User
):
    assignee_id = uuid4()
    task_id = uuid4()
    now = datetime.utcnow()

    request_payload = {
        "title": "API Test Task",
        "description": "Description from API test",
        "assignee_id": str(assignee_id),
        "creator_id": str(mock_current_user_data.id), # Frontend sends this
        "responsible_id": None,
        "accountable_id": None,
        "consulted_ids": [],
        "informed_ids": [],
        "due_date": None,
        "task_type": "API_FEATURE",
        "metadata": {"source": "api_test"},
        "priority": "MEDIUM"
    }

    # Mock RaciService response
    mock_created_task = Task(
        id=task_id, title=request_payload["title"], description=request_payload["description"], 
        status=TaskStatus.ASSIGNED, assignee_id=assignee_id, responsible_id=assignee_id, 
        accountable_id=assignee_id, creator_id=mock_current_user_data.id, 
        created_at=now, updated_at=now, priority=TaskPriority.MEDIUM, task_type="API_FEATURE"
    )
    mock_raci_service.register_raci_assignments.return_value = (mock_created_task, ["Test warning"])

    response = client.post(TASK_API_ENDPOINT, json=request_payload)

    assert response.status_code == 201
    response_json = response.json()
    assert response_json["id"] == str(task_id)
    assert response_json["title"] == request_payload["title"]
    assert response_json["priority"] == "Medium"
    assert "Test warning" in response_json["warnings"]

    mock_raci_service.register_raci_assignments.assert_called_once()
    call_args = mock_raci_service.register_raci_assignments.call_args[1]
    assert call_args["title"] == request_payload["title"]
    assert call_args["assignee_id"] == assignee_id
    assert call_args["creator_id"] == mock_current_user_data.id # Endpoint uses current_user.id
    assert call_args["priority"] == request_payload["priority"]
    
    mock_notification_service_api.task_created_notification.assert_called_once_with(
        mock_created_task, mock_current_user_data.id
    )

def test_create_task_missing_title(client: TestClient):
    assignee_id = uuid4()
    request_payload = {
        # "title": "API Test Task", # Title is missing
        "description": "Description from API test",
        "assignee_id": str(assignee_id),
        "creator_id": str(uuid4()), 
    }
    response = client.post(TASK_API_ENDPOINT, json=request_payload)
    assert response.status_code == 422 # Unprocessable Entity for Pydantic validation error
    assert "title" in response.json()["detail"][0]["loc"]

def test_create_task_raci_service_raises_resource_not_found(
    client: TestClient, mock_raci_service: AsyncMock, mock_current_user_data: User
):
    assignee_id = uuid4()
    request_payload = {
        "title": "Task with bad user",
        "description": "A user ID is bad",
        "assignee_id": str(assignee_id),
        "creator_id": str(mock_current_user_data.id),
    }
    mock_raci_service.register_raci_assignments.side_effect = ResourceNotFoundError(resource_name="User", resource_id=str(assignee_id))

    response = client.post(TASK_API_ENDPOINT, json=request_payload)
    assert response.status_code == 404 # Should be mapped from ResourceNotFoundError
    assert "User not found" in response.json()["detail"]

def test_create_task_raci_service_raises_bad_request(
    client: TestClient, mock_raci_service: AsyncMock, mock_current_user_data: User
):
    assignee_id = uuid4()
    request_payload = {
        "title": "Task with bad data",
        "description": "Some data is bad",
        "assignee_id": str(assignee_id),
        "creator_id": str(mock_current_user_data.id),
    }
    # Simulate a scenario where RaciService returns (None, ["Validation failed"]) which leads to BadRequestError
    mock_raci_service.register_raci_assignments.return_value = (None, ["RACI validation failed: accountable needed"])

    response = client.post(TASK_API_ENDPOINT, json=request_payload)
    # The endpoint raises BadRequestError if created_task is None and warnings exist
    assert response.status_code == 400 
    assert "RACI validation failed: accountable needed" in response.json()["detail"] 