import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4, UUID

from app.models.user import User, UserRole
from app.models.task import Task, TaskStatus
from app.services.raci_service import RaciService

@pytest.fixture
def mock_user_repo():
    mock = MagicMock()
    mock.get_user_by_id = MagicMock()
    return mock

@pytest.fixture
def mock_task_repo():
    mock = MagicMock()
    mock.get_task_by_id = MagicMock()
    mock.create_task = MagicMock()
    mock.update_task_status = MagicMock()
    return mock

@pytest.fixture
def raci_service(mock_user_repo, mock_task_repo):
    with patch('app.services.raci_service.UserRepository', return_value=mock_user_repo), \
         patch('app.services.raci_service.TaskRepository', return_value=mock_task_repo):
        service = RaciService()
        return service

@pytest.fixture
def users() -> dict:
    dev_id = uuid4()
    manager_id = uuid4()
    other_dev_id = uuid4()
    return {
        "developer": User(id=dev_id, email="dev@example.com", role=UserRole.DEVELOPER, team="Engineering"),
        "manager": User(id=manager_id, email="manager@example.com", role=UserRole.MANAGER, team="Engineering"),
        "other_dev": User(id=other_dev_id, email="other@example.com", role=UserRole.DEVELOPER, team="Engineering")
    }

def test_assign_raci_all_roles_specified(raci_service: RaciService, users: dict):
    task_id = uuid4()
    assignee = users["developer"]
    responsible = users["developer"]
    accountable = users["manager"]
    consulted = [users["other_dev"]]
    informed = [users["other_dev"]]

    test_task = Task(
        id=task_id,
        description="Test task",
        assignee_id=assignee.id,
        responsible_id=responsible.id,
        accountable_id=accountable.id,
        consulted_ids=[u.id for u in consulted],
        informed_ids=[u.id for u in informed],
        status=TaskStatus.ASSIGNED
    )

    is_valid = raci_service.assign_raci(test_task)

    assert is_valid is True

def test_assign_raci_default_responsible(raci_service: RaciService, users: dict):
    """Test that responsible role defaults to assignee if not provided.
       NOTE: Current RaciService.assign_raci does not create tasks or assign defaults.
       This test is a placeholder and needs rewriting if that functionality is (re-)added.
    """
    pass

def test_assign_raci_default_accountable(raci_service: RaciService, users: dict):
    """Test that accountable role defaults to team manager if not provided.
       NOTE: Current RaciService.assign_raci does not create tasks or assign defaults.
       This test is a placeholder and needs rewriting if that functionality is (re-)added.
    """
    pass

def test_raci_validation(raci_service: RaciService, users: dict, mock_task_repo: MagicMock, mock_user_repo: MagicMock):
    task_id = uuid4()
    dev_user = users["developer"]
    manager_user = users["manager"]
    
    mock_task = Task(
        id=task_id, 
        description="Valid Task", 
        responsible_id=dev_user.id, 
        accountable_id=manager_user.id,
        consulted_ids=[dev_user.id],
        informed_ids=[manager_user.id],
        status=TaskStatus.ASSIGNED
    )
    mock_task_repo.get_task_by_id.return_value = mock_task
    mock_user_repo.get_user_by_id.return_value = dev_user

    is_valid, errors = raci_service.raci_validation(task_id)

    assert is_valid is True
    assert len(errors) == 0
    mock_task_repo.get_task_by_id.assert_called_once_with(task_id)

def test_escalate_blocked_task(raci_service: RaciService, users: dict, mock_task_repo: MagicMock, mock_user_repo: MagicMock):
    task_id = uuid4()
    accountable_user = users["manager"]
    
    mock_task_blocked = Task(
        id=task_id, 
        description="Blocked Task", 
        status=TaskStatus.BLOCKED,
        accountable_id=accountable_user.id
    )
    mock_task_repo.get_task_by_id.return_value = mock_task_blocked
    mock_user_repo.get_user_by_id.return_value = accountable_user

    raci_service.escalate_blocked_task(task_id)

    mock_task_repo.get_task_by_id.assert_called_once_with(task_id)
    mock_user_repo.get_user_by_id.assert_called_once_with(accountable_user.id)