import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime

from app.services.raci_service import RaciService
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.core.exceptions import ResourceNotFoundError, DatabaseError

# --- Fixtures ---

@pytest.fixture
def mock_task_repo():
    return AsyncMock()

@pytest.fixture
def mock_user_repo():
    return AsyncMock()

@pytest.fixture
def mock_notification_service():
    return AsyncMock()

@pytest.fixture
def raci_service(mock_task_repo, mock_user_repo, mock_notification_service):
    with patch('app.services.raci_service.TaskRepository', return_value=mock_task_repo), \
         patch('app.services.raci_service.UserRepository', return_value=mock_user_repo), \
         patch('app.services.raci_service.NotificationService', return_value=mock_notification_service):
        service = RaciService()
        # Explicitly set mock instances if __init__ doesn't pick them up due to patching context
        service.task_repo = mock_task_repo
        service.user_repo = mock_user_repo
        service.notification_service = mock_notification_service
        return service

@pytest.fixture
def sample_user_data():
    def _get_user(id_val=None, name="Test User"):
        return User(id=id_val or uuid4(), name=name, email=f"{name.lower().replace(' ', '.')}@example.com")
    return _get_user

@pytest.fixture
def sample_task_data():
    now = datetime.utcnow()
    return {
        "id": uuid4(),
        "title": "Test Task Title",
        "description": "Test Task Description",
        "status": TaskStatus.ASSIGNED,
        "created_at": now,
        "updated_at": now,
    }

# --- Tests for register_raci_assignments ---

@pytest.mark.asyncio
async def test_register_raci_assignments_success(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    sample_user_data,
    sample_task_data
):
    creator = sample_user_data(name="Creator")
    assignee = sample_user_data(name="Assignee")
    responsible = sample_user_data(name="Responsible")
    accountable = sample_user_data(name="Accountable")
    consulted1 = sample_user_data(name="Consulted1")
    informed1 = sample_user_data(name="Informed1")

    mock_user_repo.get_user_by_id.side_effect = lambda id_val: {
        creator.id: creator,
        assignee.id: assignee,
        responsible.id: responsible,
        accountable.id: accountable,
        consulted1.id: consulted1,
        informed1.id: informed1,
    }.get(id_val)

    created_task_model = Task(
        **sample_task_data,
        title="New Task",
        description="A great new task",
        assignee_id=assignee.id,
        responsible_id=responsible.id,
        accountable_id=accountable.id,
        consulted_ids=[consulted1.id],
        informed_ids=[informed1.id],
        creator_id=creator.id,
        priority="High"
    )
    mock_task_repo.create_task.return_value = created_task_model

    task_details = {
        "title": "New Task",
        "description": "A great new task",
        "assignee_id": assignee.id,
        "creator_id": creator.id,
        "responsible_id": responsible.id,
        "accountable_id": accountable.id,
        "consulted_ids": [consulted1.id],
        "informed_ids": [informed1.id],
        "due_date": None,
        "task_type": "Feature",
        "metadata": {"key": "value"},
        "priority": "High"
    }

    created_task, warnings = await raci_service.register_raci_assignments(**task_details)

    assert created_task is not None
    assert created_task.title == task_details["title"]
    assert created_task.assignee_id == assignee.id
    assert created_task.responsible_id == responsible.id
    assert created_task.accountable_id == accountable.id
    assert created_task.consulted_ids == [consulted1.id]
    assert created_task.informed_ids == [informed1.id]
    assert created_task.creator_id == creator.id
    assert created_task.priority == "High"
    assert len(warnings) == 0
    
    mock_task_repo.create_task.assert_called_once()
    call_args = mock_task_repo.create_task.call_args[0][0] # Get the Task object passed to create_task
    assert call_args.title == task_details["title"]
    assert call_args.assignee_id == assignee.id
    assert call_args.responsible_id == responsible.id # Was explicitly provided
    assert call_args.accountable_id == accountable.id # Was explicitly provided
    assert call_args.status == TaskStatus.ASSIGNED


@pytest.mark.asyncio
async def test_register_raci_assignments_default_responsible_accountable(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    sample_user_data,
    sample_task_data
):
    creator = sample_user_data(name="Creator")
    assignee = sample_user_data(name="Assignee")

    mock_user_repo.get_user_by_id.side_effect = lambda id_val: {
        creator.id: creator,
        assignee.id: assignee,
    }.get(id_val)

    created_task_model = Task(
        **sample_task_data,
        title="Defaulted Task",
        description="Task with defaults",
        assignee_id=assignee.id,
        responsible_id=assignee.id, # Defaulted
        accountable_id=assignee.id, # Defaulted
        creator_id=creator.id
    )
    mock_task_repo.create_task.return_value = created_task_model
    
    task_details = {
        "title": "Defaulted Task",
        "description": "Task with defaults",
        "assignee_id": assignee.id,
        "creator_id": creator.id,
        # Responsible and Accountable not provided
    }

    created_task, warnings = await raci_service.register_raci_assignments(**task_details)

    assert created_task is not None
    assert created_task.responsible_id == assignee.id
    assert created_task.accountable_id == assignee.id
    assert len(warnings) == 2 # One for responsible, one for accountable
    assert f"Responsible ID not provided, defaulted to assignee ID: {assignee.id}" in warnings
    assert f"Accountable ID not provided, defaulted to assignee ID: {assignee.id}. Review required." in warnings
    
    mock_task_repo.create_task.assert_called_once()
    call_args = mock_task_repo.create_task.call_args[0][0]
    assert call_args.responsible_id == assignee.id
    assert call_args.accountable_id == assignee.id

@pytest.mark.asyncio
async def test_register_raci_assignments_creator_not_found(raci_service: RaciService, mock_user_repo: AsyncMock):
    assignee_id = uuid4()
    mock_user_repo.get_user_by_id.return_value = None # Creator not found

    with pytest.raises(ResourceNotFoundError, match="Creator User"):
        await raci_service.register_raci_assignments(
            title="Test", description="Test desc", assignee_id=assignee_id, creator_id=uuid4()
        )

@pytest.mark.asyncio
async def test_register_raci_assignments_assignee_not_found(raci_service: RaciService, mock_user_repo: AsyncMock, sample_user_data):
    creator = sample_user_data()
    mock_user_repo.get_user_by_id.side_effect = lambda id_val: creator if id_val == creator.id else None

    with pytest.raises(ResourceNotFoundError, match="Assignee User"):
        await raci_service.register_raci_assignments(
            title="Test", description="Test desc", assignee_id=uuid4(), creator_id=creator.id
        )
        
@pytest.mark.asyncio
async def test_register_raci_assignments_responsible_not_found(raci_service: RaciService, mock_user_repo: AsyncMock, sample_user_data):
    creator = sample_user_data(name="Creator")
    assignee = sample_user_data(name="Assignee")
    
    # Creator and Assignee exist, Responsible does not
    mock_user_repo.get_user_by_id.side_effect = lambda id_val: {
        creator.id: creator,
        assignee.id: assignee,
    }.get(id_val, None)

    with pytest.raises(ResourceNotFoundError, match="Responsible User"):
        await raci_service.register_raci_assignments(
            title="Test", 
            description="Test desc", 
            assignee_id=assignee.id, 
            creator_id=creator.id,
            responsible_id=uuid4() # Non-existent responsible
        )

@pytest.mark.asyncio
async def test_register_raci_assignments_consulted_informed_not_found(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    sample_user_data,
    sample_task_data
):
    creator = sample_user_data(name="Creator")
    assignee = sample_user_data(name="Assignee")
    valid_consulted = sample_user_data(name="ValidConsulted")
    non_existent_consulted_id = uuid4()
    non_existent_informed_id = uuid4()

    mock_user_repo.get_user_by_id.side_effect = lambda id_val: {
        creator.id: creator,
        assignee.id: assignee,
        valid_consulted.id: valid_consulted,
        # non_existent IDs will return None
    }.get(id_val)

    created_task_model = Task(
        **sample_task_data,
        title="Consulted/Informed Test",
        assignee_id=assignee.id,
        responsible_id=assignee.id, 
        accountable_id=assignee.id, 
        creator_id=creator.id,
        consulted_ids=[valid_consulted.id], # Only valid one should remain
        informed_ids=[] # Non-existent one should be omitted
    )
    mock_task_repo.create_task.return_value = created_task_model

    task_details = {
        "title": "Consulted/Informed Test",
        "description": "Testing missing C/I users",
        "assignee_id": assignee.id,
        "creator_id": creator.id,
        "consulted_ids": [valid_consulted.id, non_existent_consulted_id],
        "informed_ids": [non_existent_informed_id],
    }

    created_task, warnings = await raci_service.register_raci_assignments(**task_details)

    assert created_task is not None
    assert created_task.consulted_ids == [valid_consulted.id]
    assert created_task.informed_ids == []
    assert len(warnings) == 4 # 2 for default R/A, 1 for missing consulted, 1 for missing informed
    assert f"Consulted user ID {non_existent_consulted_id} not found and will be omitted." in warnings
    assert f"Informed user ID {non_existent_informed_id} not found and will be omitted." in warnings

@pytest.mark.asyncio
async def test_register_raci_assignments_db_error_on_create(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    sample_user_data
):
    creator = sample_user_data(name="Creator")
    assignee = sample_user_data(name="Assignee")

    mock_user_repo.get_user_by_id.side_effect = lambda id_val: {
        creator.id: creator,
        assignee.id: assignee,
    }.get(id_val)
    
    mock_task_repo.create_task.return_value = None # Simulate DB error

    task_details = {
        "title": "DB Error Task",
        "description": "This will fail on save",
        "assignee_id": assignee.id,
        "creator_id": creator.id,
    }
    with pytest.raises(DatabaseError, match="Failed to save the task to the database"):
        await raci_service.register_raci_assignments(**task_details)

# --- Tests for raci_validation ---

@pytest.mark.asyncio
async def test_raci_validation_valid_task(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    sample_user_data,
    sample_task_data
):
    task_id = uuid4()
    creator = sample_user_data(name="Creator")
    assignee = sample_user_data(name="Assignee")
    responsible = sample_user_data(name="Responsible")
    accountable = sample_user_data(name="Accountable")
    consulted = sample_user_data(name="Consulted")
    informed = sample_user_data(name="Informed")

    valid_task = Task(
        **sample_task_data,
        id=task_id,
        title="Valid RACI Task",
        assignee_id=assignee.id,
        responsible_id=responsible.id,
        accountable_id=accountable.id,
        consulted_ids=[consulted.id],
        informed_ids=[informed.id],
        creator_id=creator.id
    )
    mock_task_repo.get_task_by_id.return_value = valid_task
    
    # All users exist
    mock_user_repo.get_user_by_id.side_effect = lambda user_id_val: next(
        (u for u in [creator, assignee, responsible, accountable, consulted, informed] if u.id == user_id_val), None
    )

    is_valid, errors = await raci_service.raci_validation(task_id)
    assert is_valid is True
    assert len(errors) == 0

@pytest.mark.asyncio
async def test_raci_validation_task_not_found(raci_service: RaciService, mock_task_repo: AsyncMock):
    task_id = uuid4()
    mock_task_repo.get_task_by_id.return_value = None

    is_valid, errors = await raci_service.raci_validation(task_id)
    assert is_valid is False
    assert "Task not found" in errors

@pytest.mark.asyncio
async def test_raci_validation_missing_responsible(raci_service: RaciService, mock_task_repo: AsyncMock, mock_user_repo: AsyncMock, sample_user_data, sample_task_data):
    task_id = uuid4()
    creator = sample_user_data()
    assignee = sample_user_data()
    accountable = sample_user_data()

    task_missing_r = Task(
        **sample_task_data,
        id=task_id, 
        assignee_id=assignee.id, 
        responsible_id=None, # Missing
        accountable_id=accountable.id,
        creator_id=creator.id
    )
    mock_task_repo.get_task_by_id.return_value = task_missing_r
    mock_user_repo.get_user_by_id.side_effect = lambda user_id_val: next(
        (u for u in [creator, assignee, accountable] if u.id == user_id_val), None
    )

    is_valid, errors = await raci_service.raci_validation(task_id)
    assert is_valid is False
    assert "Missing Responsible role" in errors

@pytest.mark.asyncio
async def test_raci_validation_user_not_found_in_roles(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    sample_user_data,
    sample_task_data
):
    task_id = uuid4()
    creator = sample_user_data(name="Creator")
    assignee = sample_user_data(name="Assignee")
    responsible_id_non_existent = uuid4()

    task_with_invalid_user = Task(
        **sample_task_data,
        id=task_id, 
        assignee_id=assignee.id, 
        responsible_id=responsible_id_non_existent, 
        accountable_id=assignee.id,
        creator_id=creator.id
    )
    mock_task_repo.get_task_by_id.return_value = task_with_invalid_user
    
    # Only creator and assignee exist
    mock_user_repo.get_user_by_id.side_effect = lambda user_id_val: {
        creator.id: creator,
        assignee.id: assignee,
    }.get(user_id_val, None)

    is_valid, errors = await raci_service.raci_validation(task_id)
    assert is_valid is False
    assert f"User with ID {responsible_id_non_existent} in RACI/task roles not found" in errors

# --- Tests for escalate_blocked_task ---

@pytest.mark.asyncio
async def test_escalate_blocked_task_success_to_accountable(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    mock_notification_service: AsyncMock,
    sample_user_data,
    sample_task_data
):
    task_id = uuid4()
    accountable_user = sample_user_data(name="Accountable")
    blocked_task = Task(
        **sample_task_data,
        id=task_id,
        title="Blocked Task 1",
        status=TaskStatus.BLOCKED,
        accountable_id=accountable_user.id,
        assignee_id=uuid4(), # Needs some assignee
        creator_id=uuid4() # Needs some creator
    )
    mock_task_repo.get_task_by_id.return_value = blocked_task
    mock_user_repo.get_user_by_id.side_effect = lambda id_val: accountable_user if id_val == accountable_user.id else sample_user_data() # Return dummy for others

    await raci_service.escalate_blocked_task(task_id)

    mock_notification_service.blocked_task_alert.assert_called_once_with(
        task_id=task_id,
        reason=f"Task {task_id} ({blocked_task.title[:30]}...) is BLOCKED. Escalating to Accountable User."
    )
    mock_notification_service.notify_task_escalation_fallback.assert_not_called()

@pytest.mark.asyncio
async def test_escalate_blocked_task_fallback_to_creator_no_accountable_id(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    mock_notification_service: AsyncMock,
    sample_user_data,
    sample_task_data
):
    task_id = uuid4()
    creator_user = sample_user_data(name="Creator")
    blocked_task = Task(
        **sample_task_data,
        id=task_id,
        title="Blocked Task No Accountable",
        status=TaskStatus.BLOCKED,
        accountable_id=None, # No accountable ID
        assignee_id=uuid4(),
        creator_id=creator_user.id
    )
    mock_task_repo.get_task_by_id.return_value = blocked_task
    mock_user_repo.get_user_by_id.side_effect = lambda id_val: creator_user if id_val == creator_user.id else sample_user_data()

    await raci_service.escalate_blocked_task(task_id)

    mock_notification_service.blocked_task_alert.assert_not_called()
    mock_notification_service.notify_task_escalation_fallback.assert_called_once()
    call_args = mock_notification_service.notify_task_escalation_fallback.call_args[0]
    assert call_args[0] == blocked_task # task object
    assert call_args[1] == creator_user # escalated_to_user
    assert "Accountable user (ID: Not Set) was not found or not assigned" in call_args[2] # reason_summary

@pytest.mark.asyncio
async def test_escalate_blocked_task_fallback_to_creator_accountable_not_found(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    mock_notification_service: AsyncMock,
    sample_user_data,
    sample_task_data
):
    task_id = uuid4()
    non_existent_accountable_id = uuid4()
    creator_user = sample_user_data(name="Creator")
    blocked_task = Task(
        **sample_task_data,
        id=task_id,
        title="Blocked Task Accountable Missing",
        status=TaskStatus.BLOCKED,
        accountable_id=non_existent_accountable_id, 
        assignee_id=uuid4(),
        creator_id=creator_user.id
    )
    mock_task_repo.get_task_by_id.return_value = blocked_task
    # Accountable not found, Creator found
    mock_user_repo.get_user_by_id.side_effect = lambda id_val: creator_user if id_val == creator_user.id else None

    await raci_service.escalate_blocked_task(task_id)

    mock_notification_service.blocked_task_alert.assert_not_called()
    mock_notification_service.notify_task_escalation_fallback.assert_called_once()
    call_args = mock_notification_service.notify_task_escalation_fallback.call_args[0]
    assert call_args[0] == blocked_task
    assert call_args[1] == creator_user
    assert f"Accountable user (ID: {non_existent_accountable_id}) was not found or not assigned" in call_args[2]

@pytest.mark.asyncio
async def test_escalate_blocked_task_task_not_found(
    raci_service: RaciService, mock_task_repo: AsyncMock, mock_notification_service: AsyncMock
):
    task_id = uuid4()
    mock_task_repo.get_task_by_id.return_value = None
    await raci_service.escalate_blocked_task(task_id)
    mock_notification_service.blocked_task_alert.assert_not_called()
    mock_notification_service.notify_task_escalation_fallback.assert_not_called()

@pytest.mark.asyncio
async def test_escalate_blocked_task_task_not_blocked(
    raci_service: RaciService, mock_task_repo: AsyncMock, mock_notification_service: AsyncMock, sample_task_data
):
    task_id = uuid4()
    task_not_blocked = Task(**sample_task_data, id=task_id, status=TaskStatus.ASSIGNED)
    mock_task_repo.get_task_by_id.return_value = task_not_blocked
    await raci_service.escalate_blocked_task(task_id)
    mock_notification_service.blocked_task_alert.assert_not_called()
    mock_notification_service.notify_task_escalation_fallback.assert_not_called()

@pytest.mark.asyncio
async def test_escalate_blocked_task_no_creator_for_fallback(
    raci_service: RaciService, 
    mock_task_repo: AsyncMock, 
    mock_user_repo: AsyncMock, 
    mock_notification_service: AsyncMock,
    sample_task_data
):
    task_id = uuid4()
    blocked_task_no_creator = Task(
        **sample_task_data,
        id=task_id,
        title="Blocked Task No Creator",
        status=TaskStatus.BLOCKED,
        accountable_id=None,
        assignee_id=uuid4(),
        creator_id=None # No creator ID for fallback
    )
    mock_task_repo.get_task_by_id.return_value = blocked_task_no_creator
    mock_user_repo.get_user_by_id.return_value = None # All users not found for this test simplicity

    await raci_service.escalate_blocked_task(task_id)
    mock_notification_service.blocked_task_alert.assert_not_called()
    mock_notification_service.notify_task_escalation_fallback.assert_not_called()
    # Logger should indicate this scenario, but no notification sent if creator_id itself is None