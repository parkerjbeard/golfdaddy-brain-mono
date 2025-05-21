import pytest
import uuid
import asyncio
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
from app.services.raci_service import RaciService
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.core.exceptions import ResourceNotFoundError, DatabaseError

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

class TestRaciServiceIntegration:
    """
    Integration tests for RaciService.
    
    These tests interact with a real test database to verify:
    - RACI role assignment and validation
    - Task creation with proper relationships
    - Data persistence and retrieval
    """
    
    @pytest.fixture(scope="function")
    async def setup_test_db(self):
        """
        Fixture to prepare the test database environment.
        
        This sets up clean database tables before each test
        and cleans up after the test completes.
        """
        # Generate unique table names for this test run to isolate tests
        test_id = str(uuid.uuid4()).replace("-", "_")
        
        # Define test table names
        users_table = f"users_test_{test_id}"
        tasks_table = f"tasks_test_{test_id}"
        
        # Patch the repository classes to use our test tables
        user_repo_patch = patch('app.repositories.user_repository.UserRepository._table', users_table)
        task_repo_patch = patch('app.repositories.task_repository.TaskRepository._table', tasks_table)
        
        # Mock the notification service to avoid actual notifications during testing
        notification_mock = MagicMock()
        notification_patch = patch('app.services.raci_service.NotificationService', return_value=notification_mock)
        
        # Apply all patches
        user_repo_patch.start()
        task_repo_patch.start()
        notification_patch.start()
        
        # Create and return the service and repositories for testing
        user_repo = UserRepository()
        task_repo = TaskRepository()
        raci_service = RaciService()
        
        # Return test fixtures
        yield {
            "raci_service": raci_service,
            "user_repo": user_repo,
            "task_repo": task_repo,
            "notification_mock": notification_mock,
            "users_table": users_table,
            "tasks_table": tasks_table
        }
        
        # Stop all patches
        user_repo_patch.stop()
        task_repo_patch.stop()
        notification_patch.stop()
    
    @pytest.fixture(scope="function")
    async def setup_test_users(self, setup_test_db):
        """Create test users for RACI role assignment tests."""
        user_repo = setup_test_db["user_repo"]
        
        # Create test users with different roles
        creator_id = uuid.uuid4()
        creator = User(
            id=creator_id,
            name="Test Creator",
            email="creator@example.com",
            role=UserRole.MANAGER,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True
        )
        
        assignee_id = uuid.uuid4()
        assignee = User(
            id=assignee_id,
            name="Test Assignee",
            email="assignee@example.com",
            role=UserRole.DEVELOPER,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True
        )
        
        responsible_id = uuid.uuid4()
        responsible = User(
            id=responsible_id,
            name="Test Responsible",
            email="responsible@example.com",
            role=UserRole.DEVELOPER,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True
        )
        
        accountable_id = uuid.uuid4()
        accountable = User(
            id=accountable_id,
            name="Test Accountable",
            email="accountable@example.com",
            role=UserRole.MANAGER,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True
        )
        
        consulted_id = uuid.uuid4()
        consulted = User(
            id=consulted_id,
            name="Test Consulted",
            email="consulted@example.com",
            role=UserRole.DEVELOPER,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True
        )
        
        informed_id = uuid.uuid4()
        informed = User(
            id=informed_id,
            name="Test Informed",
            email="informed@example.com",
            role=UserRole.USER,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True
        )
        
        # Create users in the database
        await user_repo.create_user(creator)
        await user_repo.create_user(assignee)
        await user_repo.create_user(responsible)
        await user_repo.create_user(accountable)
        await user_repo.create_user(consulted)
        await user_repo.create_user(informed)
        
        # Return the user IDs for test use
        return {
            "creator_id": creator_id,
            "assignee_id": assignee_id,
            "responsible_id": responsible_id,
            "accountable_id": accountable_id,
            "consulted_id": consulted_id,
            "informed_id": informed_id
        }
    
    @pytest.mark.asyncio
    async def test_register_raci_assignments_complete(self, setup_test_db, setup_test_users):
        """Test creating a task with complete RACI role assignments."""
        raci_service = setup_test_db["raci_service"]
        task_repo = setup_test_db["task_repo"]
        
        # Get test user IDs
        user_ids = await setup_test_users
        
        # Task details
        title = "Integration Test Task"
        description = "This is a test task created with complete RACI assignments"
        due_date = datetime.now() + timedelta(days=7)
        
        # Create task with full RACI roles
        task, warnings = await raci_service.register_raci_assignments(
            title=title,
            description=description,
            assignee_id=user_ids["assignee_id"],
            creator_id=user_ids["creator_id"],
            responsible_id=user_ids["responsible_id"],
            accountable_id=user_ids["accountable_id"],
            consulted_ids=[user_ids["consulted_id"]],
            informed_ids=[user_ids["informed_id"]],
            due_date=due_date,
            task_type="integration_test",
            priority="HIGH"
        )
        
        # Verify the task was created successfully
        assert task is not None
        assert task.id is not None
        assert task.title == title
        assert task.description == description
        assert task.assignee_id == user_ids["assignee_id"]
        assert task.creator_id == user_ids["creator_id"]
        assert task.responsible_id == user_ids["responsible_id"]
        assert task.accountable_id == user_ids["accountable_id"]
        assert user_ids["consulted_id"] in task.consulted_ids
        assert user_ids["informed_id"] in task.informed_ids
        assert task.due_date == due_date
        assert task.task_type == "integration_test"
        assert task.priority == "HIGH"
        assert task.status == TaskStatus.ASSIGNED
        assert len(warnings) == 0  # No warnings expected for complete assignments
        
        # Verify the task was persisted by retrieving it from the database
        retrieved_task = await task_repo.get_task_by_id(task.id)
        assert retrieved_task is not None
        assert retrieved_task.id == task.id
        assert retrieved_task.title == title
        assert retrieved_task.responsible_id == user_ids["responsible_id"]
        assert retrieved_task.accountable_id == user_ids["accountable_id"]
    
    @pytest.mark.asyncio
    async def test_register_raci_assignments_defaults(self, setup_test_db, setup_test_users):
        """Test creating a task with minimal RACI role assignments, letting the service set defaults."""
        raci_service = setup_test_db["raci_service"]
        task_repo = setup_test_db["task_repo"]
        
        # Get test user IDs
        user_ids = await setup_test_users
        
        # Task details
        title = "Minimal RACI Test Task"
        description = "This is a test task created with minimal RACI assignments"
        
        # Create task with minimal RACI roles (only required ones)
        task, warnings = await raci_service.register_raci_assignments(
            title=title,
            description=description,
            assignee_id=user_ids["assignee_id"],
            creator_id=user_ids["creator_id"]
        )
        
        # Verify the task was created successfully
        assert task is not None
        assert task.id is not None
        assert task.title == title
        assert task.description == description
        assert task.assignee_id == user_ids["assignee_id"]
        assert task.creator_id == user_ids["creator_id"]
        # Default values - responsible and accountable should default to assignee
        assert task.responsible_id == user_ids["assignee_id"]
        assert task.accountable_id == user_ids["assignee_id"]
        assert task.status == TaskStatus.ASSIGNED
        # Should have warnings about defaulted values
        assert len(warnings) > 0
        assert any("Responsible ID not provided" in warning for warning in warnings)
        assert any("Accountable ID not provided" in warning for warning in warnings)
        
        # Verify the task was persisted with defaults
        retrieved_task = await task_repo.get_task_by_id(task.id)
        assert retrieved_task is not None
        assert retrieved_task.id == task.id
        assert retrieved_task.responsible_id == user_ids["assignee_id"]
        assert retrieved_task.accountable_id == user_ids["assignee_id"]
    
    @pytest.mark.asyncio
    async def test_raci_validation(self, setup_test_db, setup_test_users):
        """Test validating RACI roles for an existing task."""
        raci_service = setup_test_db["raci_service"]
        user_ids = await setup_test_users
        
        # First create a task
        task, _ = await raci_service.register_raci_assignments(
            title="Validation Test Task",
            description="Task for RACI validation testing",
            assignee_id=user_ids["assignee_id"],
            creator_id=user_ids["creator_id"],
            responsible_id=user_ids["responsible_id"],
            accountable_id=user_ids["accountable_id"]
        )
        
        # Validate the RACI roles
        is_valid, errors = await raci_service.raci_validation(task.id)
        
        # Should be valid
        assert is_valid is True
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_raci_validation_nonexistent_task(self, setup_test_db):
        """Test validating RACI roles for a nonexistent task."""
        raci_service = setup_test_db["raci_service"]
        
        # Try to validate a task that doesn't exist
        is_valid, errors = await raci_service.raci_validation(uuid.uuid4())
        
        # Should not be valid
        assert is_valid is False
        assert len(errors) == 1
        assert errors[0] == "Task not found"
    
    @pytest.mark.asyncio
    async def test_escalate_blocked_task(self, setup_test_db, setup_test_users):
        """Test escalation of a blocked task."""
        raci_service = setup_test_db["raci_service"]
        task_repo = setup_test_db["task_repo"]
        notification_mock = setup_test_db["notification_mock"]
        
        # Get test user IDs
        user_ids = await setup_test_users
        
        # Create a task
        task, _ = await raci_service.register_raci_assignments(
            title="Blocked Task",
            description="Task for testing escalation",
            assignee_id=user_ids["assignee_id"],
            creator_id=user_ids["creator_id"],
            responsible_id=user_ids["responsible_id"],
            accountable_id=user_ids["accountable_id"]
        )
        
        # Mark the task as blocked
        await task_repo.update_task(task.id, {
            "status": TaskStatus.BLOCKED,
            "blocked": True,
            "blocked_reason": "Test blocking reason"
        })
        
        # Trigger escalation
        await raci_service.escalate_blocked_task(task.id)
        
        # Verify notification was sent to accountable user
        notification_mock.blocked_task_alert.assert_called_once()
        # Extract the call arguments
        call_args = notification_mock.blocked_task_alert.call_args[1]
        assert call_args["task_id"] == task.id
        assert "BLOCKED" in call_args["reason"]
        assert "Escalating to Accountable User" in call_args["reason"] 