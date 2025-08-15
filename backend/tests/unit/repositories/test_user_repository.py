import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository


@pytest.fixture
def mock_supabase_client():
    """Fixture to provide a mocked Supabase client."""
    mock_client = MagicMock()
    # Mock the chain of calls like client.table(...).select(...).eq(...).execute()
    # Or client.table(...).insert(...).execute()
    # Specific mock configurations will be needed for each test or a more generic one here.
    # For example:
    # mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None, error=None)
    # mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=None, error=None)
    return mock_client


def test_create_user(mock_supabase_client):
    # Arrange
    repo = UserRepository(client=mock_supabase_client)

    user_data_to_create = User(
        id=uuid4(), slack_id="U123456", name="Test User", role=UserRole.DEVELOPER, team="Engineering"
    )

    # Configure mock response for insert
    # Example: Successful creation
    mock_response_data = user_data_to_create.model_dump()
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[mock_response_data], error=None
    )

    # Act
    created_user = repo.create_user(user_data_to_create)

    # Assert
    assert created_user is not None
    assert created_user.id == user_data_to_create.id
    assert created_user.slack_id == "U123456"
    mock_supabase_client.table.assert_called_once_with("users")
    mock_supabase_client.table.return_value.insert.assert_called_once_with(
        user_data_to_create.model_dump(exclude_unset=True)
    )
    mock_supabase_client.table.return_value.insert.return_value.execute.assert_called_once()


def test_get_user_by_id(mock_supabase_client):
    # Arrange
    repo = UserRepository(client=mock_supabase_client)
    test_user_id = uuid4()
    mock_user_data = {"id": str(test_user_id), "slack_id": "S123", "name": "Found User", "role": "Developer"}

    # Configure mock response for successful fetch
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=mock_user_data, error=None, status_code=200
    )

    # Act
    found_user = repo.get_user_by_id(test_user_id)

    # Assert
    assert found_user is not None
    assert found_user.id == test_user_id
    mock_supabase_client.table.assert_called_with("users")
    mock_supabase_client.table.return_value.select.assert_called_with("*")
    mock_supabase_client.table.return_value.select.return_value.eq.assert_called_with("id", str(test_user_id))
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.assert_called_once()
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.assert_called_once()

    # Test case for user not found
    mock_supabase_client.reset_mock()
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None, error=None, status_code=406
    )
    not_found_user = repo.get_user_by_id(uuid4())
    assert not_found_user is None


def test_get_user_by_slack_id(mock_supabase_client):
    # Arrange
    repo = UserRepository(client=mock_supabase_client)
    test_slack_id = "U123ABC"
    mock_user_data = {"id": str(uuid4()), "slack_id": test_slack_id, "name": "Slack User", "role": "Manager"}

    # Configure mock response for successful fetch
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=mock_user_data, error=None, status_code=200
    )

    # Act
    found_user = repo.get_user_by_slack_id(test_slack_id)

    # Assert
    assert found_user is not None
    assert found_user.slack_id == test_slack_id
    mock_supabase_client.table.assert_called_with("users")
    mock_supabase_client.table.return_value.select.assert_called_with("*")
    mock_supabase_client.table.return_value.select.return_value.eq.assert_called_with("slack_id", test_slack_id)
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.assert_called_once()
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.assert_called_once()

    # Test case for user not found
    mock_supabase_client.reset_mock()
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None, error=None, status_code=406
    )
    not_found_user = repo.get_user_by_slack_id("nonexistent_slack_id")
    assert not_found_user is None


def test_list_users_by_role(mock_supabase_client):
    # Arrange
    repo = UserRepository(client=mock_supabase_client)
    dev_role = UserRole.DEVELOPER
    mock_dev_users_data = [
        {"id": str(uuid4()), "name": "Dev 1", "role": dev_role.value, "slack_id": "D1"},
        {"id": str(uuid4()), "name": "Dev 2", "role": dev_role.value, "slack_id": "D2"},
    ]

    # Configure mock response for successful fetch
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=mock_dev_users_data, error=None
    )

    # Act
    developers = repo.list_users_by_role(dev_role)

    # Assert
    assert len(developers) == 2
    assert all(user.role == dev_role for user in developers)

    # Test case for no users found for a role
    mock_supabase_client.reset_mock()
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[], error=None
    )
    admins = repo.list_users_by_role(UserRole.ADMIN)
    assert len(admins) == 0


def test_update_user(mock_supabase_client):
    # Arrange
    repo = UserRepository(client=mock_supabase_client)
    user_id_to_update = uuid4()
    original_user_data = {
        "id": str(user_id_to_update),
        "name": "Old Name",
        "role": UserRole.DEVELOPER.value,
        "slack_id": "UOld",
    }
    update_payload = {"name": "Updated Name", "role": UserRole.MANAGER.value}

    # Data returned by Supabase after a successful update
    updated_user_response_data = {**original_user_data, **update_payload}

    # Configure mock response for successful update
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[updated_user_response_data], error=None
    )

    # Act
    updated_user = repo.update_user(user_id_to_update, update_payload.copy())

    # Assert
    assert updated_user is not None
    assert updated_user.id == user_id_to_update
    assert updated_user.role == UserRole.MANAGER
    mock_supabase_client.table.assert_called_with("users")
    expected_payload_for_supabase = {"name": "Updated Name", "role": UserRole.MANAGER.value}
    mock_supabase_client.table.return_value.update.assert_called_with(expected_payload_for_supabase)
    mock_supabase_client.table.return_value.update.return_value.eq.assert_called_with("id", str(user_id_to_update))
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.assert_called_once()

    # Test case for user not found or update failed
    mock_supabase_client.reset_mock()
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=None, error=None
    )
    failed_update_user = repo.update_user(uuid4(), {"name": "Irrelevant"})
    assert failed_update_user is None


def test_update_personal_mastery(mock_supabase_client):
    # Arrange
    repo = UserRepository(client=mock_supabase_client)
    user_id_to_update = uuid4()
    original_user_data = {  # This would typically be what's "in the DB" before update
        "id": str(user_id_to_update),
        "name": "Test User",
        "role": UserRole.MANAGER.value,
        "slack_id": "UMastery",
        "personal_mastery": None,  # Starts as None
    }
    mastery_payload = {"tasks": [{"id": "task1", "title": "Improve Code Reviews", "status": "in_progress"}]}
    update_data_for_repo = {"personal_mastery": mastery_payload}

    # Data returned by Supabase after a successful update
    # Supabase returns the full updated record
    # For Json fields, the DB would return a string or a dict that Pydantic can parse.
    # If the DB returns a dict for a JSONB column, Pydantic's Json type might handle it.
    # However, the error indicates it expects a string for Json type when parsing.
    # Let's ensure the mock provides what the model expects or what the repo handles.
    # The User model has `personal_mastery: Optional[Json[Dict[str, Any]]]`.
    # When User(**response.data[0]) is called, if response.data[0]['personal_mastery'] is a dict,
    # Pydantic's Json type expects a string that is valid JSON.

    # If Supabase returns a dict directly for a jsonb field, and Pydantic Json type has issues,
    # one might need to adjust the model or the repo. But for testing, we mock the repo's output.
    # The error log says: "JSON input should be string, bytes or bytearray"
    # So, the User model instantiation is expecting a string here.

    updated_user_response_dict = {**original_user_data}
    # If the repository layer or Supabase client library would normally give us a string for a JSON field
    # from the DB, then our mock should too.
    # If it gives a dict, and the Pydantic model expects a string, that's a mismatch.
    # Given the error, User model expects a string that can be parsed into JSON.
    updated_user_response_dict["personal_mastery"] = json.dumps(mastery_payload)

    # Configure mock response for successful update
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[updated_user_response_dict], error=None  # Supabase update returns a list
    )

    # Act
    updated_user = repo.update_user(user_id_to_update, update_data_for_repo.copy())  # update_user is generic

    # Assert
    assert updated_user is not None
    assert updated_user.id == user_id_to_update
    assert updated_user.personal_mastery == mastery_payload

    mock_supabase_client.table.assert_called_with("users")
    # The actual update_payload sent to Supabase should be what we passed
    mock_supabase_client.table.return_value.update.assert_called_with(update_data_for_repo)
    mock_supabase_client.table.return_value.update.return_value.eq.assert_called_with("id", str(user_id_to_update))
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.assert_called_once()

    # Test case for update failed (e.g., returns no data)
    mock_supabase_client.reset_mock()  # Reset call counts
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=None, error=None
    )
    failed_update_user = repo.update_user(user_id_to_update, {"personal_mastery": {"new_field": "new_value"}})
    assert failed_update_user is None
