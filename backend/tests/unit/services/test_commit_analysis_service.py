# tests/unit/services/test_commit_analysis_service.py

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pydantic import HttpUrl

from app.integrations.commit_analysis import CommitAnalyzer

# Models and Schemas (adjust imports based on your actual project structure)
from app.models.commit import Commit
from app.models.user import User

# Dependencies to be mocked
from app.repositories.commit_repository import CommitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.github_event import CommitPayload

# Service being tested
from app.services.commit_analysis_service import CommitAnalysisService
from supabase import Client

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
    # Async methods must be AsyncMock for awaited calls
    mock.get_user_by_email = mocker.AsyncMock()
    # Provide common async methods used by service
    if not hasattr(mock, "get_user_by_github_username"):
        mock.get_user_by_github_username = mocker.AsyncMock()
    if not hasattr(mock, "update_user"):
        mock.update_user = mocker.AsyncMock()
    if not hasattr(mock, "create_user"):
        mock.create_user = mocker.AsyncMock()
    # Add mock for get_user_by_github_username if implemented
    # mock.get_user_by_github_username = mocker.MagicMock()
    return mock


@pytest.fixture
def mock_commit_repo(mocker) -> MagicMock:
    """Provides a MagicMock for the CommitRepository."""
    mock = mocker.MagicMock(spec=CommitRepository)
    # Async methods must be AsyncMock for awaited calls
    mock.get_commit_by_hash = mocker.AsyncMock()
    mock.save_commit = mocker.AsyncMock()
    if not hasattr(mock, "update_commit_analysis"):
        mock.update_commit_analysis = mocker.AsyncMock()
    return mock


@pytest.fixture
def mock_commit_analyzer(mocker) -> MagicMock:
    """Provides a MagicMock for the CommitAnalyzer (async methods)."""
    mock = mocker.MagicMock(spec=CommitAnalyzer)
    mock.analyze_commit_diff = mocker.AsyncMock()
    # CommitAnalyzer currently doesn't expose analyze_commit_code_quality, but keep for forward compatibility
    if hasattr(mock, "analyze_commit_code_quality"):
        mock.analyze_commit_code_quality = mocker.AsyncMock(
            return_value={"placeholder_quality_score": 0.0, "issues": []}
        )
    return mock


@pytest.fixture
def commit_analysis_service(
    mock_supabase, mock_commit_repo, mock_user_repo, mock_commit_analyzer
) -> CommitAnalysisService:
    """Instantiates the service with mocked dependencies."""
    # Patch the __init__ method of the service or pass mocks directly
    with (
        patch("app.services.commit_analysis_service.CommitRepository", return_value=mock_commit_repo),
        patch("app.services.commit_analysis_service.UserRepository", return_value=mock_user_repo),
        patch("app.services.commit_analysis_service.CommitAnalyzer", return_value=mock_commit_analyzer),
    ):
        service = CommitAnalysisService(supabase=mock_supabase)
        # Re-assign mocks directly to be sure if __init__ patching doesn't work as expected
        service.supabase = mock_supabase
        service.commit_repository = mock_commit_repo
        service.user_repository = mock_user_repo
        service.commit_analyzer = mock_commit_analyzer
        service.ai_integration = mock_commit_analyzer  # backward compatibility alias
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
    mock_commit_analyzer: MagicMock,
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
    # Prefer email path; no user by GitHub username
    mock_user_repo.get_user_by_github_username.return_value = None
    # 2. User exists
    mock_user_repo.get_user_by_email.return_value = test_user
    # If service tries to update missing github_username, return the same user
    mock_user_repo.update_user.return_value = test_user
    # 3. AI analysis result (mocked for ai_integration call inside analyze_commit)
    mock_analysis_result = {"complexity_score": 5, "estimated_hours": 0.5, "seniority_score": 3}
    mock_commit_analyzer.analyze_commit_diff.return_value = mock_analysis_result
    # Ensure optional code quality path returns a dict
    if hasattr(mock_commit_analyzer, "analyze_commit_code_quality"):
        mock_commit_analyzer.analyze_commit_code_quality.return_value = {
            "placeholder_quality_score": 0.0,
            "issues": [],
        }

    # 4. Commit save (which includes analysis data) succeeds
    # Construct what the fully analyzed Commit object would look like to be returned by save_commit
    # This is what analyze_commit would build and pass to save_commit, and what save_commit returns.
    saved_commit_obj = Commit(
        commit_hash=test_commit_payload.commit_hash,
        author_id=test_user.id,
        ai_estimated_hours=mock_analysis_result["estimated_hours"],
        seniority_score=mock_analysis_result["seniority_score"],
        commit_timestamp=test_commit_payload.commit_timestamp,
    )
    mock_commit_repo.save_commit.return_value = saved_commit_obj

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    mock_user_repo.get_user_by_email.assert_called_once_with(test_commit_payload.author_email)
    mock_commit_analyzer.analyze_commit_diff.assert_called_once()
    mock_commit_repo.save_commit.assert_called_once()

    # Assert the structure of the object passed to save_commit
    saved_arg = mock_commit_repo.save_commit.call_args[0][0]
    assert isinstance(saved_arg, Commit)
    assert saved_arg.commit_hash == test_commit_payload.commit_hash
    assert saved_arg.author_id == test_user.id
    assert saved_arg.ai_estimated_hours == mock_analysis_result["estimated_hours"]
    assert saved_arg.seniority_score == mock_analysis_result["seniority_score"]

    assert result is saved_commit_obj


@pytest.mark.asyncio
# @patch.object(CommitAnalysisService, '_get_ai_analysis', new_callable=AsyncMock) # Removed patch
async def test_process_commit_existing_needs_analysis(
    # mock_get_ai_analysis: AsyncMock, # Removed mock parameter
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    mock_commit_analyzer: MagicMock,
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
    existing_commit_mock.ai_estimated_hours = None
    existing_commit_mock.seniority_score = None
    existing_commit_mock.author_id = test_user.id  # Ensure existing commit has author_id for re-analysis context
    mock_commit_repo.get_commit_by_hash.return_value = existing_commit_mock
    # 2. User exists (still need to look up for context, though not used for creation)
    mock_user_repo.get_user_by_github_username.return_value = None
    mock_user_repo.get_user_by_email.return_value = test_user
    mock_user_repo.update_user.return_value = test_user
    # 3. Configure the AIIntegration mock directly on the service instance
    mock_analysis_result = {"complexity_score": 7, "estimated_hours": 1.0, "seniority_score": 6}
    mock_commit_analyzer.analyze_commit_diff.return_value = mock_analysis_result
    if hasattr(mock_commit_analyzer, "analyze_commit_code_quality"):
        mock_commit_analyzer.analyze_commit_code_quality.return_value = {
            "placeholder_quality_score": 0.0,
            "issues": [],
        }
    # 4. Commit save (which includes analysis data) succeeds
    re_analyzed_commit_obj = Commit(
        commit_hash=existing_commit_mock.commit_hash,
        author_id=existing_commit_mock.author_id,
        ai_estimated_hours=mock_analysis_result["estimated_hours"],
        seniority_score=mock_analysis_result["seniority_score"],
        commit_timestamp=existing_commit_mock.commit_timestamp,  # or test_commit_payload.commit_timestamp
    )
    mock_commit_repo.save_commit.return_value = re_analyzed_commit_obj

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    # mock_user_repo.get_user_by_email.assert_called_once_with(test_commit_payload.author_email) # Not called in re-analysis if author_id is known
    mock_commit_analyzer.analyze_commit_diff.assert_called_once()
    mock_commit_repo.save_commit.assert_called_once()

    saved_arg = mock_commit_repo.save_commit.call_args[0][0]
    assert saved_arg.ai_estimated_hours == mock_analysis_result["estimated_hours"]
    assert saved_arg.seniority_score == mock_analysis_result["seniority_score"]

    assert result is re_analyzed_commit_obj
    assert result.ai_estimated_hours == 1.0


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
    existing_commit_mock.ai_estimated_hours = 2.0  # Has been analyzed
    mock_commit_repo.get_commit_by_hash.return_value = existing_commit_mock

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    # Should return early, no other calls
    mock_user_repo.get_user_by_email.assert_not_called()
    mock_commit_repo.save_commit.assert_not_called()

    assert result is existing_commit_mock  # Should return the existing object
    assert result.ai_estimated_hours == 2.0
    # seniority_score should remain whatever the existing object has


@pytest.mark.asyncio
async def test_process_commit_user_not_found(
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    mock_commit_analyzer: MagicMock,
    test_commit_payload: CommitPayload,
    sample_commit_data: dict,
):
    """
    Tests processing when the user cannot be mapped.
    """
    # --- Arrange ---
    mock_commit_repo.get_commit_by_hash.return_value = None
    mock_user_repo.get_user_by_github_username.return_value = None
    mock_user_repo.get_user_by_email.return_value = None  # User not found
    mock_user_repo.update_user.return_value = None

    # AI analysis result
    mock_analysis_result = {"complexity_score": 3, "estimated_hours": 0.2, "seniority_score": 2}
    mock_commit_analyzer.analyze_commit_diff.return_value = mock_analysis_result

    # Commit save succeeds, but with author_id = None
    saved_commit_obj = Commit(
        commit_hash=test_commit_payload.commit_hash,
        author_id=None,  # Important: author_id should be None
        ai_estimated_hours=mock_analysis_result["estimated_hours"],
        seniority_score=mock_analysis_result["seniority_score"],
        commit_timestamp=test_commit_payload.commit_timestamp,
    )
    mock_commit_repo.save_commit.return_value = saved_commit_obj

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    mock_user_repo.get_user_by_email.assert_called_once_with(test_commit_payload.author_email)
    mock_commit_analyzer.analyze_commit_diff.assert_called_once()
    mock_commit_repo.save_commit.assert_called_once()

    saved_arg = mock_commit_repo.save_commit.call_args[0][0]
    assert saved_arg.author_id is None

    assert result is saved_commit_obj
    assert result.author_id is None


@pytest.mark.asyncio
async def test_process_commit_create_fails(
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    mock_commit_analyzer: MagicMock,
    test_commit_payload: CommitPayload,
    test_user: User,
):
    """Tests processing when commit creation fails in the repository."""
    # --- Arrange ---
    mock_commit_repo.get_commit_by_hash.return_value = None
    mock_user_repo.get_user_by_github_username.return_value = None
    mock_user_repo.get_user_by_email.return_value = test_user
    mock_user_repo.update_user.return_value = test_user

    # AI analysis (still happens before save attempt)
    mock_analysis_result = {"complexity_score": 5, "estimated_hours": 0.5, "seniority_score": 4}
    mock_commit_analyzer.analyze_commit_diff.return_value = mock_analysis_result

    mock_commit_repo.save_commit.return_value = None  # Simulate DB error during save

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.get_commit_by_hash.assert_called_once_with(test_commit_payload.commit_hash)
    mock_user_repo.get_user_by_email.assert_called_once_with(test_commit_payload.author_email)
    mock_commit_analyzer.analyze_commit_diff.assert_called_once()
    mock_commit_repo.save_commit.assert_called_once()  # save_commit was called
    assert result is None


@pytest.mark.asyncio
async def test_process_commit_update_fails(
    commit_analysis_service: CommitAnalysisService,
    mock_commit_repo: MagicMock,
    mock_user_repo: MagicMock,
    mock_commit_analyzer: MagicMock,
    test_commit_payload: CommitPayload,
    test_user: User,
    sample_commit_data: dict,
):
    """Tests processing when updating analysis fails."""
    # --- Arrange ---
    mock_commit_repo.get_commit_by_hash.return_value = None
    mock_user_repo.get_user_by_github_username.return_value = None
    mock_user_repo.get_user_by_email.return_value = test_user
    mock_user_repo.update_user.return_value = test_user

    # AI analysis happens
    mock_analysis_result = {"complexity_score": 5, "estimated_hours": 0.5, "seniority_score": 4}
    mock_commit_analyzer.analyze_commit_diff.return_value = mock_analysis_result

    mock_commit_repo.save_commit.return_value = None  # Simulate save failure

    # --- Act ---
    result = await commit_analysis_service.process_commit(test_commit_payload)

    # --- Assert ---
    mock_commit_repo.save_commit.assert_called_once()
    assert result is None

    # In current implementation, there is no separate create/update path asserted here.


# Add more tests for AI error scenarios if the placeholder logic is replaced
# e.g., test_process_commit_ai_raises_exception
# e.g., test_process_commit_ai_returns_invalid_data
