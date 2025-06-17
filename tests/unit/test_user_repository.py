import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.database import Base
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

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

def test_create_user(db_session):
    # Arrange
    repo = UserRepository(db_session)
    
    # Act
    user = repo.create_user(
        slack_id="U123456",
        name="Test User",
        role=UserRole.DEVELOPER,
        team="Engineering"
    )
    
    # Assert
    assert user.id is not None
    assert user.slack_id == "U123456"
    assert user.name == "Test User"
    assert user.role == UserRole.DEVELOPER
    assert user.team == "Engineering"
    
    # Verify it's in the database
    db_user = db_session.query(User).filter(User.slack_id == "U123456").first()
    assert db_user is not None
    assert db_user.id == user.id

def test_get_user_by_slack_id(db_session):
    # Arrange
    repo = UserRepository(db_session)
    user = repo.create_user(
        slack_id="U123456",
        name="Test User",
        role=UserRole.DEVELOPER
    )
    
    # Act
    found_user = repo.get_user_by_slack_id("U123456")
    not_found_user = repo.get_user_by_slack_id("nonexistent")
    
    # Assert
    assert found_user is not None
    assert found_user.id == user.id
    assert not_found_user is None

def test_list_users_by_role(db_session):
    # Arrange
    repo = UserRepository(db_session)
    repo.create_user(slack_id="U1", name="Dev 1", role=UserRole.DEVELOPER)
    repo.create_user(slack_id="U2", name="Dev 2", role=UserRole.DEVELOPER)
    repo.create_user(slack_id="U3", name="Manager", role=UserRole.MANAGER)
    
    # Act
    developers = repo.list_users_by_role(UserRole.DEVELOPER)
    managers = repo.list_users_by_role(UserRole.MANAGER)
    admins = repo.list_users_by_role(UserRole.ADMIN)
    
    # Assert
    assert len(developers) == 2
    assert len(managers) == 1
    assert len(admins) == 0

def test_update_user(db_session):
    # Arrange
    repo = UserRepository(db_session)
    user = repo.create_user(
        slack_id="U123456",
        name="Test User",
        role=UserRole.DEVELOPER
    )
    
    # Act
    updated_user = repo.update_user(
        user.id,
        name="Updated Name",
        role=UserRole.MANAGER
    )
    
    # Assert
    assert updated_user is not None
    assert updated_user.name == "Updated Name"
    assert updated_user.role == UserRole.MANAGER
    
    # Verify changes in database
    db_user = db_session.query(User).filter(User.id == user.id).first()
    assert db_user.name == "Updated Name"
    assert db_user.role == UserRole.MANAGER

def test_update_personal_mastery(db_session):
    # Arrange
    repo = UserRepository(db_session)
    user = repo.create_user(
        slack_id="U123456",
        name="Test User",
        role=UserRole.MANAGER
    )
    
    # Act
    mastery_data = {
        "tasks": [
            {"id": "task1", "title": "Improve Code Reviews", "status": "in_progress"}
        ]
    }
    updated_user = repo.update_personal_mastery(user.id, mastery_data)
    
    # Assert
    assert updated_user is not None
    assert updated_user.personal_mastery == mastery_data
    
    # Verify changes in database
    db_user = db_session.query(User).filter(User.id == user.id).first()
    assert db_user.personal_mastery == mastery_data