import pytest
from fastapi.testclient import TestClient
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

# Create in-memory SQLite database for testing
@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Override the dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Create a session for test setup
    db = TestingSessionLocal()
    
    yield db  # Provide the session for test setup
    
    # Cleanup
    db.close()
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def test_users(test_db):
    # Create test users
    user_repo = UserRepository(test_db)
    
    dev_user = user_repo.create_user(
        slack_id="U123",
        name="Test Developer",
        role=UserRole.DEVELOPER,
        team="Engineering"
    )
    
    manager_user = user_repo.create_user(
        slack_id="U456",
        name="Test Manager",
        role=UserRole.MANAGER,
        team="Engineering"
    )
    
    test_db.commit()
    
    return {
        "developer": dev_user,
        "manager": manager_user
    }

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_create_task_endpoint(client, test_users):
    # Arrange
    task_data = {
        "description": "Integration test task",
        "assignee_id": test_users["developer"].id,
        "responsible_id": test_users["developer"].id,
        "accountable_id": test_users["manager"].id,
        "due_date": "2023-12-31T23:59:59Z"
    }
    
    # Act
    response = client.post("/tasks", json=task_data)
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Integration test task"
    assert data["assignee_id"] == test_users["developer"].id
    assert data["responsible_id"] == test_users["developer"].id
    assert data["accountable_id"] == test_users["manager"].id
    assert data["status"] == "assigned"

def test_list_tasks_endpoint(client, test_users):
    # Arrange - Create a task first
    task_data = {
        "description": "Task for listing",
        "assignee_id": test_users["developer"].id
    }
    client.post("/tasks", json=task_data)
    
    # Act
    response = client.get("/tasks")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert len(data["tasks"]) >= 1
    assert data["total"] >= 1

def test_get_task_endpoint(client, test_users):
    # Arrange - Create a task first
    task_data = {
        "description": "Task for retrieval",
        "assignee_id": test_users["developer"].id
    }
    create_response = client.post("/tasks", json=task_data)
    task_id = create_response.json()["id"]
    
    # Act
    response = client.get(f"/tasks/{task_id}")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["description"] == "Task for retrieval"

def test_update_task_endpoint(client, test_users):
    # Arrange - Create a task first
    task_data = {
        "description": "Task for update",
        "assignee_id": test_users["developer"].id
    }
    create_response = client.post("/tasks", json=task_data)
    task_id = create_response.json()["id"]
    
    # Act - Update the task
    update_data = {
        "description": "Updated task description",
        "status": "in_progress"
    }
    response = client.put(f"/tasks/{task_id}", json=update_data)
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["description"] == "Updated task description"
    assert data["status"] == "in_progress"

def test_delete_task_endpoint(client, test_users):
    # Arrange - Create a task first
    task_data = {
        "description": "Task for deletion",
        "assignee_id": test_users["developer"].id
    }
    create_response = client.post("/tasks", json=task_data)
    task_id = create_response.json()["id"]
    
    # Act - Delete the task
    response = client.delete(f"/tasks/{task_id}")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Task deleted successfully"
    
    # Verify it's gone
    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 404