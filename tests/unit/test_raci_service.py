import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.database import Base
from app.models.user import User, UserRole
from app.models.task import Task, TaskStatus
from app.repositories.user_repository import UserRepository
from app.repositories.task_repository import TaskRepository
from app.services.raci_service import RaciService

# Create in-memory SQLite database for testing
@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def users(db_session):
    # Create test users
    user_repo = UserRepository(db_session)
    
    dev_user = user_repo.create_user(
        slack_id="U1",
        name="Developer",
        role=UserRole.DEVELOPER,
        team="Engineering"
    )
    
    manager_user = user_repo.create_user(
        slack_id="U2",
        name="Manager",
        role=UserRole.MANAGER,
        team="Engineering"
    )
    
    other_dev = user_repo.create_user(
        slack_id="U3",
        name="Other Dev",
        role=UserRole.DEVELOPER,
        team="Engineering"
    )
    
    return {
        "developer": dev_user,
        "manager": manager_user,
        "other_dev": other_dev
    }

def test_assign_raci_all_roles_specified(db_session, users):
    # Arrange
    raci_service = RaciService(db_session)
    
    # Act
    task, warnings = raci_service.assign_raci(
        description="Test task",
        assignee_id=users["developer"].id,
        responsible_id=users["developer"].id,
        accountable_id=users["manager"].id,
        consulted_ids=[users["other_dev"].id],
        informed_ids=[users["other_dev"].id]
    )
    
    # Assert
    assert task is not None
    assert task.description == "Test task"
    assert task.assignee_id == users["developer"].id
    assert task.responsible_id == users["developer"].id
    assert task.accountable_id == users["manager"].id
    assert users["other_dev"].id in task.consulted_ids
    assert users["other_dev"].id in task.informed_ids
    assert len(warnings) == 0

def test_assign_raci_default_responsible(db_session, users):
    # Arrange
    raci_service = RaciService(db_session)
    
    # Act - No responsible specified, should default to assignee
    task, warnings = raci_service.assign_raci(
        description="Test task",
        assignee_id=users["developer"].id,
        accountable_id=users["manager"].id
    )
    
    # Assert
    assert task is not None
    assert task.responsible_id == users["developer"].id  # Defaulted to assignee
    assert "Responsible role defaulted to assignee" in warnings

def test_assign_raci_default_accountable(db_session, users):
    # Arrange
    raci_service = RaciService(db_session)
    
    # Act - No accountable specified, should find a manager
    task, warnings = raci_service.assign_raci(
        description="Test task",
        assignee_id=users["developer"].id
    )
    
    # Assert
    assert task is not None
    assert task.accountable_id == users["manager"].id  # Found the team manager
    assert any("Accountable role defaulted to team manager" in w for w in warnings)

def test_raci_validation(db_session, users):
    # Arrange
    raci_service = RaciService(db_session)
    task_repo = TaskRepository(db_session)
    
    # Create a valid task
    task = task_repo.create_task(
        description="Test task",
        assignee_id=users["developer"].id,
        responsible_id=users["developer"].id,
        accountable_id=users["manager"].id
    )
    
    # Act
    is_valid, errors = raci_service.raci_validation(task.id)
    
    # Assert
    assert is_valid is True
    assert len(errors) == 0

def test_escalate_blocked_task(db_session, users):
    # Arrange
    raci_service = RaciService(db_session)
    task_repo = TaskRepository(db_session)
    
    # Create a task
    task = task_repo.create_task(
        description="Test task",
        assignee_id=users["developer"].id,
        responsible_id=users["developer"].id,
        accountable_id=users["manager"].id
    )
    
    # Act
    success, message = raci_service.escalate_blocked_task(
        task_id=task.id,
        blocking_reason="Waiting for API access"
    )
    
    # Assert
    assert success is True
    assert "escalated to" in message
    
    # Verify task status is updated
    updated_task = task_repo.get_task_by_id(task.id)
    assert updated_task.status == TaskStatus.BLOCKED