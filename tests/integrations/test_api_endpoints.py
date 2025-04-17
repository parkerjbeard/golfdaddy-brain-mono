import pytest
from fastapi.testclient import TestClient
import json
from uuid import UUID
from unittest.mock import MagicMock

from app.main import app
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.models.task import Task, TaskStatus

@pytest.fixture
def client(mock_supabase_client):
    # The client fixture is already defined in conftest.py using mock_supabase_client
    return TestClient(app)

@pytest.fixture
def setup_mock_data(mock_supabase_client):
    """Set up mock data in the Supabase client for testing."""
    
    # Create test users
    dev_user = User(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        email="dev@example.com",
        slack_id="U123",
        name="Test Developer",
        role=UserRole.DEVELOPER,
        team="Engineering"
    )
    
    manager_user = User(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        email="manager@example.com",
        slack_id="U456",
        name="Test Manager",
        role=UserRole.MANAGER,
        team="Engineering"
    )
    
    # Mock the user repository responses
    mock_supabase_client.table().select().execute.return_value = MagicMock(
        data=[dev_user.model_dump(), manager_user.model_dump()],
        error=None
    )
    
    # Mock single user lookup
    mock_supabase_client.table().select().eq().maybe_single().execute.side_effect = lambda: MagicMock(
        data=dev_user.model_dump(),
        error=None
    )
    
    # Mock task creation
    task_data = Task(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        description="Test Task",
        status=TaskStatus.ASSIGNED,
        assignee_id=dev_user.id,
        responsible_id=dev_user.id,
        accountable_id=manager_user.id
    )
    
    mock_supabase_client.table().insert().execute.return_value = MagicMock(
        data=[task_data.model_dump()],
        error=None
    )
    
    # Mock task retrieval
    mock_supabase_client.table().select().eq().single().execute.return_value = MagicMock(
        data=task_data.model_dump(),
        error=None
    )
    
    # Mock task update
    updated_task = task_data.model_copy()
    updated_task.description = "Updated task description"
    updated_task.status = TaskStatus.IN_PROGRESS
    
    mock_supabase_client.table().update().eq().execute.return_value = MagicMock(
        data=[updated_task.model_dump()],
        error=None
    )
    
    # Mock task deletion
    mock_supabase_client.table().delete().eq().execute.return_value = MagicMock(
        data=[],
        error=None
    )
    
    return {
        "developer": dev_user,
        "manager": manager_user,
        "task": task_data
    }

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_create_task_endpoint(client, setup_mock_data, mock_supabase_client):
    # Arrange
    test_users = setup_mock_data
    task_data = {
        "description": "Integration test task",
        "assignee_id": str(test_users["developer"].id),
        "responsible_id": str(test_users["developer"].id),
        "accountable_id": str(test_users["manager"].id),
        "due_date": "2023-12-31T23:59:59Z"
    }
    
    # Act
    response = client.post("/tasks", json=task_data)
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Integration test task"
    
    # Verify Supabase was called with the correct data
    mock_supabase_client.table.assert_called_with("tasks")
    mock_supabase_client.table().insert.assert_called_once()

def test_list_tasks_endpoint(client, setup_mock_data, mock_supabase_client):
    # Set up the mock to return a list of tasks
    mock_supabase_client.table().select().execute.return_value = MagicMock(
        data=[setup_mock_data["task"].model_dump()],
        error=None
    )
    
    # Act
    response = client.get("/tasks")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert len(data["tasks"]) >= 1
    
    # Verify Supabase was called correctly
    mock_supabase_client.table.assert_called_with("tasks")
    mock_supabase_client.table().select.assert_called_once()

def test_get_task_endpoint(client, setup_mock_data, mock_supabase_client):
    # Use the mock task from setup
    task_id = str(setup_mock_data["task"].id)
    
    # Act
    response = client.get(f"/tasks/{task_id}")
    
    # Assert
    assert response.status_code == 200
    
    # Verify Supabase was called correctly
    mock_supabase_client.table.assert_called_with("tasks")
    # The next line depends on how your code calls the Supabase client
    # Adjust according to your implementation
    mock_supabase_client.table().select().eq().single().execute.assert_called_once()

def test_update_task_endpoint(client, setup_mock_data, mock_supabase_client):
    # Use the mock task from setup
    task_id = str(setup_mock_data["task"].id)
    
    # Act - Update the task
    update_data = {
        "description": "Updated task description",
        "status": "in_progress"
    }
    response = client.put(f"/tasks/{task_id}", json=update_data)
    
    # Assert
    assert response.status_code == 200
    
    # Verify Supabase was called correctly
    mock_supabase_client.table.assert_called_with("tasks")
    mock_supabase_client.table().update.assert_called_once()
    mock_supabase_client.table().update().eq.assert_called_once_with("id", task_id)

def test_delete_task_endpoint(client, setup_mock_data, mock_supabase_client):
    # Use the mock task from setup
    task_id = str(setup_mock_data["task"].id)
    
    # For the second get after deletion, return None to simulate not found
    mock_supabase_client.table().select().eq().single().execute.side_effect = [
        MagicMock(data=setup_mock_data["task"].model_dump(), error=None),  # First call returns the task
        MagicMock(data=None, error={"code": "PGRST116", "message": "Not found"}, status_code=406)  # Second call returns not found
    ]
    
    # Act - Delete the task
    response = client.delete(f"/tasks/{task_id}")
    
    # Assert
    assert response.status_code == 200
    
    # Verify Supabase was called correctly
    mock_supabase_client.table.assert_called_with("tasks")
    mock_supabase_client.table().delete.assert_called_once()
    mock_supabase_client.table().delete().eq.assert_called_once_with("id", task_id)