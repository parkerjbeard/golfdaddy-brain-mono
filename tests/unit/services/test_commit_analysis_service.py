# tests/unit/services/test_commit_analysis_service.py

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
import uuid
from pydantic import HttpUrl
from supabase import Client

# Models and Schemas (adjust imports based on your actual project structure)
from app.models.commit import Commit
from app.models.user import User
from app.schemas.github_event import CommitPayload

# Service being tested
from app.services.commit_analysis_service import CommitAnalysisService

# Dependencies to be mocked
from app.repositories.commit_repository import CommitRepository
from app.repositories.user_repository import UserRepository
from app.integrations.ai_integration import AIIntegration

# --- Fixtures ---

@pytest.fixture
def mock_supabase() -> MagicMock:
    """Provides a MagicMock for the Supabase client."""
    mock = MagicMock(spec=Client)
    # Add any necessary method mocks for the Supabase client
    return mock

@pytest.fixture
def mock_user_repo(mocker) -> MagicMock:
    """Provides a MagicMock for the UserRepository."""
    mock = mocker.MagicMock(spec=UserRepository)
    mock.get_user_by_email = mocker.MagicMock()
    # Add mock for get_user_by_github_username if implemented
    # mock.get_user_by_github_username = mocker.MagicMock()
    return mock

@pytest.fixture
def mock_commit_repo(mocker) -> MagicMock:
    """Provides a MagicMock for the CommitRepository."""
    mock = mocker.MagicMock(spec=CommitRepository)
    mock.get_commit_by_hash = mocker.MagicMock()
    mock.create_commit = mocker.MagicMock()
    mock.update_commit_analysis = mocker.MagicMock()
    return mock

@pytest.fixture
def mock_ai_integration(mocker) -> AsyncMock:
    """Provides an AsyncMock for the AiIntegration."""
    # Since the actual call is commented out and returns a placeholder dict,
    # we don't need to mock a specific method for now.
    # If you implement the real call, mock that specific async method.
    # Example: mock.analyze_commit_diff = mocker.AsyncMock()
    return mocker.AsyncMock(spec=AIIntegration)

@pytest.fixture
def commit_analysis_service(
    mock_supabase,
    mock_commit_repo,
    mock_user_repo,
    mock_ai_integration
) -> CommitAnalysisService:
    """Instantiates the service with mocked dependencies."""
    # Patch the __init__ method of the service or pass mocks directly
    with patch("app.services.commit_analysis_service.CommitRepository", return_value=mock_commit_repo), \
         patch("app.services.commit_analysis_service.UserRepository", return_value=mock_user_repo), \
         patch("app.services.commit_analysis_service.AIIntegration", return_value=mock_ai_integration):
        service = CommitAnalysisService(supabase=mock_supabase)
        # Re-assign mocks directly to be sure if __init__ patching doesn't work as expected
        service.supabase = mock_supabase
        service.commit_repository = mock_commit_repo
        service.user_repository = mock_user_repo
        service.ai_integration = mock_ai_integration
        return service

@pytest.fixture
def test_user() -> User:
    """Fixture for a sample User object."""
    user = User(
        id=uuid.uuid4(),
        email="test.author@example.com",
        slack_id="U123",
        # add other necessary fields
    )
    return user

@pytest.fixture
def test_commit_payload() -> CommitPayload:
    """Fixture for a sample CommitPayload input."""
    return CommitPayload(
        commit_hash="a1b2c3d4e5f6",
        commit_message="feat: Implement amazing feature",
        commit_url=HttpUrl("https://github.com/user/repo/commit/a1b2c3d4e5f6"),
        commit_timestamp=datetime.now(timezone.utc),
        author_github_username="testauthor",
        author_email="test.author@example.com",
        repository_name="repo",
        repository_url=HttpUrl("https://github.com/user/repo"),
        branch="main",
        diff_url=HttpUrl("https://github.com/user/repo/commit/a1b2c3d4e5f6.diff"),
    )

@pytest.fixture
def sample_commit_data(test_commit_payload, test_user) -> dict:
    """Data dict used for creating/updating Commit models"""
    return {
        "id": uuid.uuid4(),
        "commit_hash": test_commit_payload.commit_hash,
        "commit_message": test_commit_payload.commit_message,
        "commit_url": str(test_commit_payload.commit_url),
        "commit_timestamp": test_commit_payload.commit_timestamp,
        "author_id": test_user.id,
        "author_github_username": test_commit_payload.author_github_username,
        "author_email": test_commit_payload.author_email,
        "repository_name": test_commit_payload.repository_name,
        "repository_url": str(test_commit_payload.repository_url),
        "branch": test_commit_payload.branch,
        "diff_url": str(test_commit_payload.diff_url),
        "ai_points": None, # Start with no analysis
        "ai_estimated_hours": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

# --- Test Cases ---

@pytest.mark.asyncio
async def test_process_commit_new_commit_success(
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    mock_ai_integration: AsyncMock, # Keep for consistency, though not directly used now
    test_commit_payload: CommitPayload,
    test_user: User,
    sample_commit_data: dict,
):
    """
    Tests the happy path for processing a new commit successfully,
    including user lookup, creation, AI analysis (mocked), and update.
    """
    # --- Arrange ---
    # 1. Commit doesn't exist
    mock_commit_repo.get_commit_by_hash.return_value = None
    # 2. User exists
    mock_user_repo.get_user_by_email.return_value = test_user
    # 3. Commit creation succeeds
    created_commit_mock = Commit(**sample_commit_data) # Create mock obj with initial data
    mock_commit_repo.create_commit.return_value = created_commit_mock
    # 4. AI analysis result (placeholder, adjust if AiIntegration changes)
    mock_analysis_result = {"points": 5, "estimated_hours": 0.5}
    # No specific AI method mock needed yet due to placeholder logic

    # 5. Commit update succeeds
    updated_commit_mock = Commit(**sample_commit_data) # Make a copy
    updated_commit_mock.ai_points = mock_analysis_result["points"]
    updated_commit_mock.ai_estimated_hours = mock_analysis_result["estimated_hours"]
    mock_commit_repo.update_commit_analysis.return_value = updated_commit_mock

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    # Check interactions
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    mock_user_repo.get_user_by_email.assert_called_once_with(test_commit_payload.author_email)
    mock_commit_repo.create_commit.assert_called_once()
    # Verify the data passed to create_commit includes the user_id
    create_args, _ = mock_commit_repo.create_commit.call_args
    assert create_args[0]['author_id'] == test_user.id
    assert create_args[0]['commit_hash'] == test_commit_payload.commit_hash

    # Placeholder AI interaction check (none for now)

    mock_commit_repo.update_commit_analysis.assert_called_once_with(
        commit_hash=test_commit_payload.commit_hash,
        ai_points=mock_analysis_result["points"],
        ai_estimated_hours=mock_analysis_result["estimated_hours"],
    )

    # Check result
    assert result is not None
    assert result.commit_hash == test_commit_payload.commit_hash
    assert result.ai_points == mock_analysis_result["points"]
    assert result.ai_estimated_hours == mock_analysis_result["estimated_hours"]
    assert result.author_id == test_user.id

@pytest.mark.asyncio
# Add patch for the internal method
@patch.object(CommitAnalysisService, '_get_ai_analysis', new_callable=AsyncMock)
async def test_process_commit_existing_needs_analysis(
    mock_get_ai_analysis: AsyncMock, # Add the mock object from the patch
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    test_commit_payload: CommitPayload,
    test_user: User,
    sample_commit_data: dict,
):
    """
    Tests processing a commit that exists but hasn't been analyzed yet.
    """
     # --- Arrange ---
    # 1. Commit exists but lacks AI analysis
    existing_commit_mock = Commit(**sample_commit_data)
    existing_commit_mock.ai_points = None
    existing_commit_mock.ai_estimated_hours = None
    mock_commit_repo.get_commit_by_hash.return_value = existing_commit_mock
    # 2. User exists (still need to look up for context, though not used for creation)
    mock_user_repo.get_user_by_email.return_value = test_user
    # 3. Configure the patched _get_ai_analysis method
    mock_analysis_result = {"points": 7, "estimated_hours": 1.0}
    mock_get_ai_analysis.return_value = mock_analysis_result # Make the patched method return the expected result
    # 4. Commit update succeeds (using the result from the patched method)
    updated_commit_mock = Commit(**sample_commit_data) # Use existing data
    updated_commit_mock.id = existing_commit_mock.id # Ensure ID matches
    updated_commit_mock.ai_points = mock_analysis_result["points"]
    updated_commit_mock.ai_estimated_hours = mock_analysis_result["estimated_hours"]
    mock_commit_repo.update_commit_analysis.return_value = updated_commit_mock

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    mock_user_repo.get_user_by_email.assert_called_once_with(test_commit_payload.author_email)
    mock_commit_repo.create_commit.assert_not_called() # Should not create again

    # Verify _get_ai_analysis was called
    mock_get_ai_analysis.assert_called_once()

    # This assertion should now pass
    mock_commit_repo.update_commit_analysis.assert_called_once_with(
        commit_hash=test_commit_payload.commit_hash,
        ai_points=mock_analysis_result["points"],
        ai_estimated_hours=mock_analysis_result["estimated_hours"],
    )
    assert result is not None
    assert result.id == existing_commit_mock.id
    assert result.ai_points == mock_analysis_result["points"]

@pytest.mark.asyncio
async def test_process_commit_already_processed(
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    test_commit_payload: CommitPayload,
    sample_commit_data: dict,
):
    """
    Tests that if a commit exists and has analysis, it's skipped.
    """
    # --- Arrange ---
    # 1. Commit exists AND has AI points
    existing_commit_mock = Commit(**sample_commit_data)
    existing_commit_mock.ai_points = 10 # Already analyzed
    existing_commit_mock.ai_estimated_hours = 2.0
    mock_commit_repo.get_commit_by_hash.return_value = existing_commit_mock

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    # Should return early, no other calls
    mock_user_repo.get_user_by_email.assert_not_called()
    mock_commit_repo.create_commit.assert_not_called()
    mock_commit_repo.update_commit_analysis.assert_not_called()

    assert result is existing_commit_mock # Should return the existing object

@pytest.mark.asyncio
async def test_process_commit_user_not_found(
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    test_commit_payload: CommitPayload,
    sample_commit_data: dict,
):
    """
    Tests processing when the user cannot be mapped.
    """
    # --- Arrange ---
    mock_commit_repo.get_commit_by_hash.return_value = None
    mock_user_repo.get_user_by_email.return_value = None # User not found
    # Commit creation succeeds
    created_commit_mock = Commit(**sample_commit_data)
    created_commit_mock.author_id = None # Expect author_id to be None
    mock_commit_repo.create_commit.return_value = created_commit_mock
    # AI analysis result
    mock_analysis_result = {"points": 3, "estimated_hours": 0.2}
    # Commit update succeeds
    updated_commit_mock = Commit(**sample_commit_data)
    updated_commit_mock.author_id = None
    updated_commit_mock.ai_points = mock_analysis_result["points"]
    updated_commit_mock.ai_estimated_hours = mock_analysis_result["estimated_hours"]
    mock_commit_repo.update_commit_analysis.return_value = updated_commit_mock

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    mock_user_repo.get_user_by_email.assert_called_once_with(test_commit_payload.author_email)
    mock_commit_repo.create_commit.assert_called_once()
    # Verify author_id is None in the created data
    create_args, _ = mock_commit_repo.create_commit.call_args
    assert create_args[0]['author_id'] is None
    mock_commit_repo.update_commit_analysis.assert_called_once()
    assert result is not None
    assert result.author_id is None # Verify final result has no author_id
    assert result.ai_points == mock_analysis_result["points"]

@pytest.mark.asyncio
async def test_process_commit_create_fails(
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    test_commit_payload: CommitPayload,
    test_user: User,
):
    """Tests processing when commit creation fails in the repository."""
    # --- Arrange ---
    mock_commit_repo.get_commit_by_hash.return_value = None
    mock_user_repo.get_user_by_email.return_value = test_user
    mock_commit_repo.create_commit.return_value = None # Simulate DB error

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    mock_user_repo.get_user_by_email.assert_called_once_with(test_commit_payload.author_email)
    mock_commit_repo.create_commit.assert_called_once()
    mock_commit_repo.update_commit_analysis.assert_not_called() # Should not proceed
    assert result is None

@pytest.mark.asyncio
async def test_process_commit_update_fails(
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    test_commit_payload: CommitPayload,
    test_user: User,
    sample_commit_data: dict,
):
    """Tests processing when updating analysis fails."""
    # --- Arrange ---
    mock_commit_repo.get_commit_by_hash.return_value = None
    mock_user_repo.get_user_by_email.return_value = test_user
    created_commit_mock = Commit(**sample_commit_data)
    mock_commit_repo.create_commit.return_value = created_commit_mock
    mock_analysis_result = {"points": 5, "estimated_hours": 0.5}
    mock_commit_repo.update_commit_analysis.return_value = None # Simulate update failure

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.create_commit.assert_called_once()
    mock_commit_repo.update_commit_analysis.assert_called_once()
    # Should still return the commit object created, just without updated analysis
    assert result is created_commit_mock
    assert result.ai_points is None # Should not have been updated

# Add more tests for AI error scenarios if the placeholder logic is replaced
# e.g., test_process_commit_ai_raises_exception
# e.g., test_process_commit_ai_returns_invalid_data 